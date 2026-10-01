"""Integration contract for the strict Columnar JSON endpoints."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.errors import messages
from app.main import app

ENCRYPT_PATH = "/api/columnar/encrypt"
DECRYPT_PATH = "/api/columnar/decrypt"
COLUMNAR_TEXT_PATHS = (ENCRYPT_PATH, DECRYPT_PATH)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _assert_success(response, expected: str) -> None:
    assert response.status_code == 200
    assert response.json() == {"success": True, "result": expected}
    assert set(response.json()) == {"success", "result"}


def _assert_error(response, message: str, status: int = 422) -> None:
    assert response.status_code == status
    assert response.json() == {"success": False, "message": message}
    assert set(response.json()) == {"success", "message"}


def _numeric_key_of_length(length: int) -> str:
    tail = " ".join(str(rank) for rank in range(2, 257))
    return "1" + " " * (length - len(tail) - 1) + tail


@pytest.mark.parametrize(
    ("plaintext", "key", "ciphertext"),
    [
        ("khoacongnghethongtin", "3 6 2 1 5 4", "agnonokntioetchghghn"),
        ("ABCDE", "3 1 4 2", "BDAEC"),
        ("MEET ME AT NOON", "BALLOON", "EAM NETT EO NMO"),
        ("A B\r\nC!", "2 1 3", " \nA\r!BC"),
        ("😀A𝄞é", "2 1 3", "A😀é𝄞"),
        ("XY", "3 1 2 4", "YX"),
    ],
)
def test_columnar_text_canonical_vectors_and_decrypt_back(
    client: TestClient,
    plaintext: str,
    key: str,
    ciphertext: str,
) -> None:
    encrypted = client.post(ENCRYPT_PATH, json={"text": plaintext, "key": key})
    _assert_success(encrypted, ciphertext)
    _assert_success(
        client.post(DECRYPT_PATH, json={"text": ciphertext, "key": key}),
        plaintext,
    )


def test_columnar_text_accepts_vendor_json_without_advertising_it(client: TestClient) -> None:
    response = client.post(
        ENCRYPT_PATH,
        content=b'{"text":"ABCDE","key":"3 1 4 2"}',
        headers={"content-type": "application/vnd.example+json"},
    )
    _assert_success(response, "BDAEC")


@pytest.mark.parametrize(
    "body",
    [
        b"not-json",
        b"[]",
        b"null",
        b'{"text":"","key":123,"extra":true}',
        b'{"text":"ABCDE","text":"FGHIJ","key":"AB"}',
        b'{"text":"ABCDE","key":"AB","key":"BA"}',
    ],
)
@pytest.mark.parametrize("path", COLUMNAR_TEXT_PATHS)
def test_columnar_text_rejects_framing_shape_and_duplicate_errors_first(
    client: TestClient,
    path: str,
    body: bytes,
) -> None:
    response = client.post(path, content=body, headers={"content-type": "application/json"})
    _assert_error(response, messages.INVALID_REQUEST_BODY)


@pytest.mark.parametrize("path", COLUMNAR_TEXT_PATHS)
def test_columnar_text_rejects_non_json_media_before_fields(
    client: TestClient,
    path: str,
) -> None:
    response = client.post(
        path,
        content=b'{"text":"","key":null}',
        headers={"content-type": "text/plain"},
    )
    _assert_error(response, messages.INVALID_REQUEST_BODY)


@pytest.mark.parametrize("path", COLUMNAR_TEXT_PATHS)
@pytest.mark.parametrize("text", [None, "", 123, [], {}])
def test_columnar_text_field_precedes_every_key_error(
    client: TestClient,
    path: str,
    text: object,
) -> None:
    _assert_error(client.post(path, json={"text": text, "key": 123}), messages.TEXT_EMPTY)


def test_columnar_text_keeps_whitespace_exactly(client: TestClient) -> None:
    original = " \t\r\n"
    encrypted = client.post(ENCRYPT_PATH, json={"text": original, "key": "2 1"})
    decrypted = client.post(
        DECRYPT_PATH,
        json={"text": encrypted.json()["result"], "key": "2 1"},
    )
    _assert_success(decrypted, original)


@pytest.mark.parametrize("key", [pytest.param(None, id="null"), "", " \t\r\n\f\v "])
def test_columnar_missing_key_variants_precede_type_and_content(
    client: TestClient,
    key: str | None,
) -> None:
    _assert_error(
        client.post(ENCRYPT_PATH, json={"text": "ABCDE", "key": key}),
        messages.MISSING_KEY,
    )


def test_columnar_absent_key_uses_missing_key_error(client: TestClient) -> None:
    _assert_error(client.post(ENCRYPT_PATH, json={"text": "ABCDE"}), messages.MISSING_KEY)


@pytest.mark.parametrize("key", [123, True, 1.5, [], {}])
def test_columnar_key_requires_json_string_without_coercion(
    client: TestClient,
    key: object,
) -> None:
    _assert_error(
        client.post(ENCRYPT_PATH, json={"text": "ABCDE", "key": key}),
        messages.INVALID_STRING_KEY,
    )


@pytest.mark.parametrize(
    "key",
    ["312", "01 2", "1,,2", "1 1", "A B", "ÉTÉ", "\u00a0AB\u00a0"],
)
def test_columnar_invalid_key_content_uses_one_canonical_error(
    client: TestClient,
    key: str,
) -> None:
    _assert_error(
        client.post(ENCRYPT_PATH, json={"text": "ABCDE", "key": key}),
        messages.INVALID_COLUMNAR_KEY,
    )


def test_columnar_accepts_minimum_and_maximum_column_counts(client: TestClient) -> None:
    _assert_success(client.post(ENCRYPT_PATH, json={"text": "XY", "key": "2 1"}), "YX")
    key_256 = " ".join(str(rank) for rank in range(1, 257))
    _assert_success(client.post(ENCRYPT_PATH, json={"text": "XY", "key": key_256}), "XY")
    _assert_success(client.post(ENCRYPT_PATH, json={"text": "XY", "key": "A" * 256}), "XY")


def test_columnar_text_key_length_boundary_uses_otherwise_valid_numeric_key(
    client: TestClient,
) -> None:
    key_at_limit = _numeric_key_of_length(2048)
    key_over_limit = _numeric_key_of_length(2049)
    _assert_success(client.post(ENCRYPT_PATH, json={"text": "XY", "key": key_at_limit}), "XY")
    _assert_error(
        client.post(ENCRYPT_PATH, json={"text": "XY", "key": key_over_limit}),
        messages.INVALID_COLUMNAR_KEY,
    )


@pytest.mark.parametrize(
    "body",
    [
        b'{"text":"\\ud83d","key":"AB"}',
        b'{"text":"\\ude00","key":"AB"}',
        b'{"text":"\\ude00\\ud83d","key":"AB"}',
        b'{"text":"ABCDE","key":"\\ud83d"}',
        b'{"text":"ABCDE","key":"\\ude00"}',
        b'{"text":"ABCDE","key":"\\ude00\\ud83d"}',
        b'{"\\ud83d":"x","text":"ABCDE","key":"AB"}',
        b'{"\\ude00":"x","text":"ABCDE","key":"AB"}',
        b'{"\\ude00\\ud83d":"x","text":"ABCDE","key":"AB"}',
    ],
)
def test_columnar_lone_surrogate_is_always_invalid_body(
    client: TestClient,
    body: bytes,
) -> None:
    response = client.post(
        ENCRYPT_PATH,
        content=body,
        headers={"content-type": "application/json"},
    )
    _assert_error(response, messages.INVALID_REQUEST_BODY)


def test_columnar_valid_surrogate_pair_matches_literal_non_bmp(client: TestClient) -> None:
    escaped = client.post(
        ENCRYPT_PATH,
        content=b'{"text":"\\ud83d\\ude00A","key":"BA"}',
        headers={"content-type": "application/json"},
    )
    literal = client.post(ENCRYPT_PATH, json={"text": "😀A", "key": "BA"})

    _assert_success(escaped, "A😀")
    assert escaped.json() == literal.json()
    _assert_success(client.post(DECRYPT_PATH, json={"text": "A😀", "key": "BA"}), "😀A")


def test_columnar_text_openapi_is_exact(client: TestClient) -> None:
    openapi = client.get("/openapi.json").json()

    for path in COLUMNAR_TEXT_PATHS:
        operation = openapi["paths"][path]["post"]
        assert operation["tags"] == ["Columnar Transposition"]
        assert set(operation["requestBody"]["content"]) == {"application/json"}
        schema = operation["requestBody"]["content"]["application/json"]["schema"]
        assert schema["required"] == ["text", "key"]
        assert schema["additionalProperties"] is False
        assert schema["properties"]["text"]["type"] == "string"
        key_schema = schema["properties"]["key"]
        assert key_schema["type"] == "string"
        assert key_schema["examples"] == ["3 1 4 2", "BALLOON"]
        assert "ASCII" in key_schema["description"]
        assert "2.048" in key_schema["description"]
        assert not ({"pattern", "oneOf", "maxLength"} & set(key_schema))
        assert set(operation["responses"]) == {"200", "413", "422", "500"}


def test_des_addition_has_twenty_two_cipher_post_routes(client: TestClient) -> None:
    paths = {
        path
        for path, operations in client.get("/openapi.json").json()["paths"].items()
        if path.startswith("/api/") and "post" in operations
    }
    assert len(paths) == 22
    assert {ENCRYPT_PATH, DECRYPT_PATH} <= paths
    assert "/api/columnar/file" in paths


def test_columnar_text_requests_are_stateless(client: TestClient) -> None:
    payload = {"text": "ABCDE", "key": "3 1 4 2"}
    first = client.post(ENCRYPT_PATH, json=payload)
    client.post(ENCRYPT_PATH, json={"text": "secret", "key": "BA"})
    second = client.post(ENCRYPT_PATH, json=payload)
    assert first.json() == second.json() == {"success": True, "result": "BDAEC"}


def test_columnar_text_unexpected_failure_is_sanitized_without_payload_log(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw_text = "PRIVATE-COLUMNAR-TEXT"
    raw_key = "3 1 4 2"

    def fail_transform(*args: object) -> str:
        del args
        raise RuntimeError("technical transform failure")

    monkeypatch.setattr("app.api.routes_columnar_text.transform_text", fail_transform)
    caplog.set_level("ERROR", logger="app.errors.handlers")
    response = client.post(ENCRYPT_PATH, json={"text": raw_text, "key": raw_key})

    _assert_error(response, messages.UNEXPECTED_FAILURE, status=500)
    assert "RuntimeError" in caplog.text
    assert raw_text not in caplog.text
    assert raw_key not in caplog.text
