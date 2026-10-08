"""Recorder, health and history API behaviour with an in-memory store instead of PostgreSQL."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api import history_recorder, routes_rsa, routes_text
from app.errors import messages
from app.history.store import OperationEntry
from app.main import app
from tests.integration.history_cases import cipher_requests

SENSITIVE_URL = "sqlite+aiosqlite:////tmp/missing-history.sqlite3"


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[OperationEntry]]:
    entries: list[OperationEntry] = []

    async def fake_record(database: object, entry: OperationEntry) -> None:
        entries.append(entry)

    monkeypatch.setattr(history_recorder, "record_operation", fake_record)
    yield entries


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[TestClient]:
    database_path = tmp_path / "missing-history.sqlite3"
    database_url = f"sqlite+aiosqlite:////{database_path.as_posix().lstrip('/')}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("HISTORY_API_ENABLED", "true")
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def client_without_db(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("HISTORY_API_ENABLED", "true")
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.mark.parametrize("case", cipher_requests(), ids=lambda case: case.path)
def test_each_cipher_route_records_its_metadata(
    client: TestClient, recorded: list[OperationEntry], case
) -> None:
    response = client.post(case.path, **case.kwargs)

    assert response.status_code == 200
    assert len(recorded) == 1
    entry = recorded[0]
    assert (entry.cipher, entry.source, entry.operation) == (
        case.cipher,
        case.source,
        case.operation,
    )
    assert entry.http_status == 200
    assert entry.succeeded is True
    assert entry.input_length is not None
    assert entry.input_length > 0
    assert entry.output_length is not None
    assert entry.output_length > 0
    assert entry.duration_ms >= 0
    assert entry.response_mode == ("file" if case.source == "file" else None)


def test_text_lengths_count_code_points(client: TestClient, recorded) -> None:
    client.post("/api/vigenere/encrypt", json={"text": "Attack at dawn!", "key": "LEMON"})
    assert (recorded[0].input_length, recorded[0].output_length) == (15, 15)


def test_hill_records_only_transforms_with_code_point_lengths(client: TestClient, recorded) -> None:
    response = client.post("/api/hill/encrypt", json={"text": "Aế", "key": [[3, 3], [2, 5]]})
    client.post("/api/hill/key/analyze", json={"key": [[3, 3], [2, 5]]})
    client.get("/api/hill/key/random?m=2")

    assert response.status_code == 200
    assert len(recorded) == 1
    entry = recorded[0]
    assert (entry.cipher, entry.source, entry.operation) == ("hill", "text", "encrypt")
    assert (entry.input_length, entry.output_length) == (2, 3)
    assert entry.response_mode is None


def test_des_records_transforms_but_not_trace(client: TestClient, recorded) -> None:
    response = client.post(
        "/api/des/encrypt", json={"text": "Hello World", "key": "133457799BBCDFF1"}
    )
    client.post("/api/des/trace", json={"block": "0123456789ABCDEF", "key": "133457799BBCDFF1"})

    assert response.status_code == 200
    assert len(recorded) == 1
    entry = recorded[0]
    assert (entry.cipher, entry.source, entry.operation) == ("des", "text", "encrypt")
    assert (entry.input_length, entry.output_length) == (11, 32)
    assert entry.response_mode is None


@pytest.mark.parametrize(
    ("path", "kwargs"),
    [
        ("/api/rsa/keys", {"json": {"p": "17", "q": "11", "e": "7"}}),
        ("/api/rsa/keys/random", {"json": {"bits": 16}}),
    ],
)
def test_rsa_key_routes_never_record_history(
    client: TestClient, recorded: list[OperationEntry], path: str, kwargs: dict
) -> None:
    client.post(path, **kwargs)
    assert recorded == []


def test_only_dh_caesar_records_private_metadata(
    client: TestClient, recorded: list[OperationEntry]
) -> None:
    client.post("/api/dh/params", json={"q": "23"})
    client.post("/api/dh/keypair", json={"q": "23", "alpha": "5", "privateKey": "6"})
    response = client.post(
        "/api/dh/caesar",
        json={
            "q": "353",
            "privateKey": "97",
            "otherPublicKey": "248",
            "action": "encrypt",
            "data": "Hello World",
        },
    )
    assert response.status_code == 200
    assert len(recorded) == 1
    entry = recorded[0]
    assert (entry.cipher, entry.source, entry.operation) == ("dh", "text", "encrypt")
    assert (entry.input_length, entry.output_length, entry.response_mode) == (11, 11, None)
    assert set(entry.__dict__) == {
        "cipher",
        "source",
        "operation",
        "response_mode",
        "input_length",
        "output_length",
        "http_status",
        "succeeded",
        "duration_ms",
    }


def test_dh_file_bom_history_uses_raw_and_output_bytes(
    client: TestClient, recorded: list[OperationEntry]
) -> None:
    response = client.post(
        "/api/dh/caesar",
        data={
            "q": "353",
            "privateKey": "97",
            "otherPublicKey": "248",
            "action": "encrypt",
        },
        files={"file": ("secret.txt", b"\xef\xbb\xbf\xc3\xa9")},
    )
    assert response.status_code == 200
    entry = recorded[0]
    assert (entry.cipher, entry.source, entry.operation) == ("dh", "file", "encrypt")
    assert (entry.input_length, entry.output_length, entry.response_mode) == (5, 5, None)


def test_dh_caesar_errors_record_status_and_validated_operation(
    client: TestClient, recorded: list[OperationEntry]
) -> None:
    empty = client.post(
        "/api/dh/caesar",
        json={
            "q": "23",
            "privateKey": "6",
            "otherPublicKey": "8",
            "action": "decrypt",
            "data": "",
        },
    )
    unsupported = client.post(
        "/api/dh/caesar", content=b"x", headers={"content-type": "text/plain"}
    )
    assert (empty.status_code, unsupported.status_code) == (422, 415)
    assert len(recorded) == 2
    assert (recorded[0].operation, recorded[0].http_status, recorded[0].succeeded) == (
        "decrypt",
        422,
        False,
    )
    assert (recorded[1].source, recorded[1].operation, recorded[1].http_status) == (
        "text",
        None,
        415,
    )


@pytest.mark.parametrize(
    ("path", "payload", "status", "operation"),
    [
        (
            "/api/rsa/encrypt",
            {"e": "17", "n": "3233", "inputType": "number", "data": "65"},
            200,
            "encrypt",
        ),
        (
            "/api/rsa/decrypt",
            {"d": "23", "n": "187", "inputType": "number", "cipher": ["11"]},
            200,
            "decrypt",
        ),
        (
            "/api/rsa/encrypt",
            {"e": "7", "n": "187", "inputType": "number", "data": "200"},
            422,
            "encrypt",
        ),
    ],
)
def test_rsa_number_success_and_error_record_only_standard_metadata(
    client: TestClient,
    recorded: list[OperationEntry],
    path: str,
    payload: dict,
    status: int,
    operation: str,
) -> None:
    response = client.post(path, json=payload)

    assert response.status_code == status
    assert len(recorded) == 1
    entry = recorded[0]
    assert (entry.cipher, entry.source, entry.operation) == ("rsa", "text", operation)
    assert (entry.http_status, entry.succeeded) == (status, status == 200)
    assert (entry.input_length, entry.output_length, entry.response_mode) == (None, None, None)


def test_rsa_text_lengths_cover_only_plaintext_side(
    client: TestClient, recorded: list[OperationEntry]
) -> None:
    encrypted = client.post(
        "/api/rsa/encrypt",
        json={
            "e": "3",
            "n": "67591",
            "inputType": "text",
            "mode": "block",
            "data": "Hi!",
            "traceBlockIndex": 0,
        },
    )
    decrypted = client.post(
        "/api/rsa/decrypt",
        json={
            "d": "44715",
            "n": "67591",
            "inputType": "text",
            "mode": "block",
            "cipher": ["37222", "6468"],
            "originalUtf8ByteLength": 3,
            "traceBlockIndex": 0,
        },
    )

    assert encrypted.status_code == decrypted.status_code == 200
    assert len(recorded) == 2
    encrypt_entry, decrypt_entry = recorded
    assert (encrypt_entry.input_length, encrypt_entry.output_length) == (3, None)
    assert (decrypt_entry.input_length, decrypt_entry.output_length) == (None, 3)
    assert set(encrypt_entry.__dict__) == {
        "cipher",
        "source",
        "operation",
        "response_mode",
        "input_length",
        "output_length",
        "http_status",
        "succeeded",
        "duration_ms",
    }


def test_rsa_multipart_records_raw_input_bytes_only(
    client: TestClient, recorded: list[OperationEntry]
) -> None:
    raw = b"\xef\xbb\xbfA"
    response = client.post(
        "/api/rsa/encrypt",
        data={"e": "3", "n": "67591", "mode": "block", "traceBlockIndex": "0"},
        files={"file": ("secret-name.txt", raw, "text/plain")},
    )

    assert response.status_code == 200
    assert len(recorded) == 1
    entry = recorded[0]
    assert (entry.cipher, entry.source, entry.operation) == ("rsa", "file", "encrypt")
    assert (entry.input_length, entry.output_length, entry.response_mode) == (4, None, None)
    dumped = repr(entry)
    assert "secret-name" not in dumped
    assert "67591" not in dumped
    assert "traceBlockIndex" not in dumped


@pytest.mark.parametrize(
    ("kwargs", "status"),
    [
        (
            {
                "data": {"e": "3", "n": "67591", "mode": "block"},
                "files": {"file": ("secret.bin", b"secret", "application/octet-stream")},
            },
            415,
        ),
        (
            {
                "content": b"{}",
                "headers": {
                    "content-type": "multipart/form-data; boundary=x",
                    "content-length": str(64 * 1024 * 1024 + 1),
                },
            },
            413,
        ),
    ],
)
def test_rsa_multipart_failures_are_recorded_as_file_source(
    client: TestClient,
    recorded: list[OperationEntry],
    kwargs: dict,
    status: int,
) -> None:
    response = client.post("/api/rsa/encrypt", **kwargs)

    assert response.status_code == status
    assert len(recorded) == 1
    entry = recorded[0]
    assert (entry.cipher, entry.source, entry.operation) == ("rsa", "file", "encrypt")
    assert (entry.http_status, entry.succeeded, entry.output_length) == (status, False, None)


def test_rsa_unexpected_error_is_recorded_without_leaking_payload(
    client: TestClient,
    recorded: list[OperationEntry],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken_encrypt(*args: object) -> dict:
        raise RuntimeError("private marker 2753")

    monkeypatch.setattr(routes_rsa, "_encrypt", broken_encrypt)
    response = client.post(
        "/api/rsa/encrypt",
        json={
            "e": "3",
            "n": "67591",
            "inputType": "text",
            "mode": "block",
            "data": "sensitive plaintext",
        },
    )

    assert response.status_code == 500
    for _ in range(100):
        if recorded:
            break
        time.sleep(0.01)
    assert len(recorded) == 1
    entry = recorded[0]
    assert (entry.http_status, entry.succeeded, entry.input_length) == (500, False, 19)
    assert "sensitive plaintext" not in repr(entry)
    assert "2753" not in repr(entry)


@pytest.mark.parametrize(
    ("path", "kwargs", "status", "operation"),
    [
        (
            "/api/des/encrypt",
            {"json": {"text": "a" * (5 * 1024 * 1024 + 1), "key": "x"}},
            413,
            "encrypt",
        ),
        (
            "/api/des/decrypt",
            {"json": {"text": "85E813540F0AB405", "key": "133457799BBCDFF1"}},
            422,
            "decrypt",
        ),
        (
            "/api/des/file",
            {
                "data": {"key": "133457799BBCDFF1", "action": "encrypt"},
                "files": {"file": ("x.md", b"abc", "text/plain")},
            },
            415,
            "encrypt",
        ),
    ],
)
def test_failed_des_requests_are_recorded(
    client: TestClient, recorded, path: str, kwargs: dict, status: int, operation: str
) -> None:
    response = client.post(path, **kwargs)

    assert response.status_code == status
    assert len(recorded) == 1
    entry = recorded[0]
    assert (entry.cipher, entry.operation, entry.http_status, entry.succeeded) == (
        "des",
        operation,
        status,
        False,
    )
    assert entry.output_length is None


def test_failed_hill_transform_is_recorded_without_sensitive_content(
    client: TestClient, recorded
) -> None:
    response = client.post(
        "/api/hill/encrypt",
        json={"text": "sensitive", "key": [[2, 4], [1, 3]]},
    )

    assert response.status_code == 422
    assert len(recorded) == 1
    entry = recorded[0]
    assert (entry.cipher, entry.operation, entry.http_status, entry.succeeded) == (
        "hill",
        "encrypt",
        422,
        False,
    )
    assert entry.input_length == len("sensitive")
    assert entry.output_length is None
    assert not hasattr(entry, "text")
    assert not hasattr(entry, "key")


def test_hill_text_limit_rejection_is_recorded_as_413(client: TestClient, recorded) -> None:
    response = client.post(
        "/api/hill/encrypt",
        json={"text": "A" * (5 * 1024 * 1024 + 1), "key": [[3, 3], [2, 5]]},
    )

    assert response.status_code == 413
    assert len(recorded) == 1
    entry = recorded[0]
    assert (entry.cipher, entry.source, entry.operation) == ("hill", "text", "encrypt")
    assert (entry.http_status, entry.succeeded, entry.input_length, entry.output_length) == (
        413,
        False,
        None,
        None,
    )


def test_file_lengths_count_utf8_bytes(client: TestClient, recorded) -> None:
    client.post(
        "/api/caesar/file",
        data={"key": "1", "action": "encrypt"},
        files={"file": ("a.txt", "é".encode(), "text/plain")},
    )
    entry = recorded[0]
    assert (entry.input_length, entry.output_length, entry.response_mode) == (2, 2, "content")


@pytest.mark.parametrize("response_mode", ["content", "file"])
def test_file_lengths_count_the_bom_on_both_sides(
    client: TestClient, recorded, response_mode: str
) -> None:
    client.post(
        "/api/caesar/file",
        data={"key": "1", "action": "encrypt", "response_mode": response_mode},
        files={"file": ("a.txt", b"\xef\xbb\xbf" + "é".encode(), "text/plain")},
    )
    entry = recorded[0]
    assert (entry.input_length, entry.output_length) == (5, 5)


def test_playfair_decrypt_records_raw_result_length_for_text_and_content(
    client: TestClient, recorded
) -> None:
    client.post("/api/playfair/decrypt", json={"text": "PDGW", "key": "PLAYFAIR EXAMPLE"})
    client.post(
        "/api/playfair/file",
        data={"key": "PLAYFAIR EXAMPLE", "action": "decrypt", "strip_padding": "true"},
        files={"file": ("a.txt", b"PDGW", "text/plain")},
    )
    assert [entry.output_length for entry in recorded] == [4, 4]


@pytest.mark.parametrize(("strip_padding", "output_length"), [("false", 4), ("true", 3)])
def test_playfair_attachment_records_returned_body_length(
    client: TestClient, recorded, strip_padding: str, output_length: int
) -> None:
    client.post(
        "/api/playfair/file",
        data={
            "key": "PLAYFAIR EXAMPLE",
            "action": "decrypt",
            "response_mode": "file",
            "strip_padding": strip_padding,
        },
        files={"file": ("a.txt", b"PDGW", "text/plain")},
    )
    assert recorded[0].output_length == output_length


def test_unexpected_error_is_recorded_as_500(
    client: TestClient, recorded, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_transform(*args: object) -> str:
        raise RuntimeError("boom")

    monkeypatch.setattr(routes_text, "transform_text", broken_transform)
    response = client.post("/api/caesar/encrypt", json={"text": "Hi", "key": 1})

    assert response.status_code == 500
    for _ in range(100):
        if recorded:
            break
        time.sleep(0.01)
    assert [(entry.http_status, entry.succeeded) for entry in recorded] == [(500, False)]


def test_unexpected_error_response_does_not_wait_for_recording(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def slow_record(database: object, entry: OperationEntry) -> None:
        await asyncio.sleep(1)

    def broken_transform(*args: object) -> str:
        raise RuntimeError("boom")

    monkeypatch.setattr(history_recorder, "RECORD_TIMEOUT_SECONDS", 2)
    monkeypatch.setattr(history_recorder, "record_operation", slow_record)
    monkeypatch.setattr(routes_text, "transform_text", broken_transform)
    started = time.perf_counter()
    response = client.post("/api/caesar/encrypt", json={"text": "Hi", "key": 1})

    assert response.status_code == 500
    assert time.perf_counter() - started < 0.5


def test_note_history_keeps_earlier_values_and_rejects_unknown_fields() -> None:
    request = SimpleNamespace(state=SimpleNamespace(history_notes={}))
    history_recorder.note_history(request, operation="encrypt", response_mode="file")
    history_recorder.note_history(request, input_length=3)

    assert request.state.history_notes == {
        "operation": "encrypt",
        "response_mode": "file",
        "input_length": 3,
    }
    with pytest.raises(TypeError):
        history_recorder.note_history(request, input_lenght=3)


def test_health_503_is_documented_in_vietnamese(client_without_db: TestClient) -> None:
    schema = client_without_db.get("/openapi.json").json()
    response = schema["paths"]["/api/health"]["get"]["responses"]["503"]
    assert response["description"] == messages.DATABASE_UNAVAILABLE


def test_rejected_request_is_recorded_as_failure(client: TestClient, recorded) -> None:
    response = client.post("/api/vigenere/encrypt", json={"text": "hi", "key": "LE MON"})

    assert response.status_code == 422
    entry = recorded[0]
    assert (entry.operation, entry.http_status, entry.succeeded) == ("encrypt", 422, False)
    assert entry.input_length is None
    assert entry.output_length is None


def test_file_rejected_before_action_has_no_operation(client: TestClient, recorded) -> None:
    response = client.post(
        "/api/caesar/file",
        data={"action": "encrypt"},
        files={"file": ("a.txt", b"x", "text/plain")},
    )

    assert response.status_code == 422
    entry = recorded[0]
    assert (entry.source, entry.operation, entry.http_status) == ("file", None, 422)


def test_request_size_guard_rejection_is_recorded(client: TestClient, recorded) -> None:
    response = client.post(
        "/api/caesar/encrypt",
        content=b"{}",
        headers={"content-type": "application/json", "content-length": str(64 * 1024 * 1024 + 1)},
    )

    assert response.status_code == 413
    assert recorded[0].http_status == 413


def test_non_cipher_routes_are_not_recorded(client: TestClient, recorded) -> None:
    client.get("/")
    client.get("/api/health")
    client.get("/api/history")
    assert recorded == []


def test_nothing_is_recorded_without_database(client_without_db: TestClient, recorded) -> None:
    response = client_without_db.post("/api/caesar/encrypt", json={"text": "Hi", "key": 1})
    assert response.json() == {"success": True, "result": "Ij"}
    assert recorded == []


def test_recording_failure_leaves_response_untouched(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def failing_record(database: object, entry: OperationEntry) -> None:
        raise ConnectionError(f"cannot reach {SENSITIVE_URL}")

    monkeypatch.setattr(history_recorder, "record_operation", failing_record)
    with caplog.at_level(logging.WARNING):
        response = client.post("/api/caesar/encrypt", json={"text": "Hi", "key": 1})

    assert response.status_code == 200
    assert response.json() == {"success": True, "result": "Ij"}
    assert "Could not record cipher operation history" in caplog.text
    assert "topsecret" not in caplog.text
    assert "Hi" not in caplog.text


def test_dh_recording_failure_leaves_response_untouched_and_redacted(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    payload = {
        "q": "353",
        "privateKey": "97",
        "otherPublicKey": "248",
        "action": "encrypt",
        "data": "dh-private-marker",
    }
    expected = client.post("/api/dh/caesar", json=payload)

    async def failing_record(database: object, entry: OperationEntry) -> None:
        raise ConnectionError(f"cannot reach {SENSITIVE_URL}")

    monkeypatch.setattr(history_recorder, "record_operation", failing_record)
    with caplog.at_level(logging.WARNING):
        response = client.post("/api/dh/caesar", json=payload)

    assert response.status_code == expected.status_code == 200
    assert response.json() == expected.json()
    assert "Could not record cipher operation history" in caplog.text
    for secret in ("dh-private-marker", "353", "97", "248", "topsecret"):
        assert secret not in caplog.text


def test_simulated_disk_full_is_best_effort_bounded_and_redacted(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def disk_full(database: object, entry: OperationEntry) -> None:
        raise sqlite3.OperationalError(f"database or disk is full: {SENSITIVE_URL}")

    monkeypatch.setattr(history_recorder, "record_operation", disk_full)
    started = time.monotonic()
    with caplog.at_level(logging.WARNING):
        response = client.post("/api/caesar/encrypt", json={"text": "Hi", "key": 1})
    elapsed = time.monotonic() - started

    assert elapsed < 0.5
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"success": True, "result": "Ij"}
    assert "Could not record cipher operation history" in caplog.text
    assert "disk is full" not in caplog.text
    assert "topsecret" not in caplog.text


def test_hill_response_is_unchanged_when_recording_fails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def failing_record(database: object, entry: OperationEntry) -> None:
        raise ConnectionError(f"cannot reach {SENSITIVE_URL}")

    monkeypatch.setattr(history_recorder, "record_operation", failing_record)
    with caplog.at_level(logging.WARNING):
        response = client.post("/api/hill/encrypt", json={"text": "HELP", "key": [[3, 3], [2, 5]]})

    assert response.status_code == 200
    assert response.json()["result"] == "DPLE"
    assert "Could not record cipher operation history" in caplog.text
    assert "HELP" not in caplog.text
    assert "DPLE" not in caplog.text


def test_rsa_response_is_unchanged_when_recording_fails(
    client: TestClient,
    recorded: list[OperationEntry],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def failing_record(database: object, entry: OperationEntry) -> None:
        raise ConnectionError(f"cannot reach {SENSITIVE_URL}")

    payload = {
        "e": "3",
        "n": "67591",
        "inputType": "text",
        "mode": "block",
        "data": "private marker",
    }
    expected = client.post("/api/rsa/encrypt", json=payload)
    assert len(recorded) == 1
    monkeypatch.setattr(history_recorder, "record_operation", failing_record)
    with caplog.at_level(logging.WARNING):
        response = client.post("/api/rsa/encrypt", json=payload)

    assert response.status_code == 200
    assert response.status_code == expected.status_code
    assert response.headers["content-type"] == expected.headers["content-type"]
    assert response.json() == expected.json()
    assert "Could not record cipher operation history" in caplog.text
    assert "private marker" not in caplog.text
    assert "67591" not in caplog.text
    assert "topsecret" not in caplog.text


def test_slow_recording_is_abandoned(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def slow_record(database: object, entry: OperationEntry) -> None:
        await asyncio.sleep(5)

    monkeypatch.setattr(history_recorder, "RECORD_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(history_recorder, "record_operation", slow_record)
    with caplog.at_level(logging.WARNING):
        response = client.post("/api/caesar/encrypt", json={"text": "Hi", "key": 1})

    assert response.json() == {"success": True, "result": "Ij"}
    assert "Could not record cipher operation history" in caplog.text


def test_health_reports_disabled_database(client_without_db: TestClient) -> None:
    response = client_without_db.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "result": {"app": "ok", "database": "disabled", "history": "enabled"},
    }


def test_health_reports_unreachable_database_without_leaking_url(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json() == {
        "success": True,
        "result": {"app": "ok", "database": "unavailable", "history": "enabled"},
    }
    assert "topsecret" not in response.text
    assert "127.0.0.1" not in response.text


def test_history_is_unavailable_without_database(client_without_db: TestClient) -> None:
    response = client_without_db.get("/api/history")
    assert response.status_code == 503
    assert response.json() == {"success": False, "message": messages.HISTORY_UNAVAILABLE}


def test_history_is_unavailable_when_database_is_unreachable(client: TestClient) -> None:
    response = client.get("/api/history")
    assert response.status_code == 503
    assert response.json() == {"success": False, "message": messages.HISTORY_UNAVAILABLE}
    assert "topsecret" not in response.text


@pytest.mark.parametrize(
    ("query", "message"),
    [
        ("limit=0", messages.INVALID_HISTORY_LIMIT),
        ("limit=101", messages.INVALID_HISTORY_LIMIT),
        ("limit=500", messages.INVALID_HISTORY_LIMIT),
        ("limit=abc", messages.INVALID_HISTORY_LIMIT),
        ("limit=-1", messages.INVALID_HISTORY_LIMIT),
        ("limit=%EF%BC%95", messages.INVALID_HISTORY_LIMIT),
        ("cursor=broken", messages.INVALID_HISTORY_CURSOR),
        ("cipher=rot13", messages.INVALID_HISTORY_FILTER),
        ("operation=ENCRYPT", messages.INVALID_HISTORY_FILTER),
    ],
)
def test_history_query_validation(client_without_db: TestClient, query: str, message: str) -> None:
    response = client_without_db.get(f"/api/history?{query}")
    assert response.status_code == 422
    assert response.json() == {"success": False, "message": message}
