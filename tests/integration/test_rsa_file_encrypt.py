"""Multipart plaintext-only RSA encrypt contract and deterministic precedence."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _post(client: TestClient, content: bytes, **data: str):
    form = {"e": "3", "n": "67591", "mode": "block", **data}
    return client.post(
        "/api/rsa/encrypt",
        data=form,
        files={"file": ("plain.txt", content, "application/octet-stream")},
    )


def test_file_and_json_block_encrypt_are_identical(client: TestClient) -> None:
    file_response = _post(client, b"Hi!")
    json_response = client.post(
        "/api/rsa/encrypt",
        json={"e": "3", "n": "67591", "inputType": "text", "mode": "block", "data": "Hi!"},
    )
    assert file_response.status_code == 200
    assert file_response.headers["content-type"].startswith("application/json")
    assert "content-disposition" not in file_response.headers
    assert file_response.json() == json_response.json()


def test_file_bom_and_newlines_are_content(client: TestClient) -> None:
    text = "\ufeffA\r\nB\n"
    response = client.post(
        "/api/rsa/encrypt",
        data={"e": "3", "n": "67591", "mode": "char"},
        files={"file": ("plain.TXT", text.encode(), "ignored/type")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["blocks"][0] == "65279"
    assert body["originalUtf8ByteLength"] == len(text.encode())
    assert len(body["blocks"]) == len(text)


def test_file_size_exact_limit_passes_size_then_hits_text_cap(client: TestClient) -> None:
    exact = client.post(
        "/api/rsa/encrypt",
        data={"e": "3", "n": "67591", "mode": "block"},
        files={"file": ("plain.txt", b"A" * 1_000_000, "text/plain")},
    )
    assert exact.status_code == 422
    assert exact.json()["code"] == "INPUT_TOO_LARGE"

    over = client.post(
        "/api/rsa/encrypt",
        data={"e": "3", "n": "67591", "mode": "block"},
        files={"file": ("plain.txt", b"A" * 1_000_001, "text/plain")},
    )
    assert over.status_code == 413
    assert over.json() == {
        "success": False,
        "code": "FILE_INVALID",
        "message": "File vượt quá dung lượng tối đa 1 MB.",
        "field": "file",
    }


@pytest.mark.parametrize(
    ("filename", "content", "status", "code", "message"),
    [
        ("plain.bin", b"abc", 415, "FILE_INVALID", "Chỉ nhận file .txt."),
        ("plain.txt.bin", b"abc", 415, "FILE_INVALID", "Chỉ nhận file .txt."),
        ("plain.txt", b"", 422, "EMPTY_INPUT", "Dữ liệu đầu vào đang rỗng."),
        ("plain.txt", b"\xff", 415, "FILE_INVALID", "File phải sử dụng UTF-8."),
    ],
)
def test_file_validation_errors(
    client: TestClient, filename: str, content: bytes, status: int, code: str, message: str
) -> None:
    response = client.post(
        "/api/rsa/encrypt",
        data={"e": "3", "n": "67591", "mode": "block"},
        files={"file": (filename, content, "text/plain")},
    )
    assert response.status_code == status
    assert response.json() == {"success": False, "code": code, "message": message, "field": "file"}


def test_multipart_exact_fields_duplicate_and_scalar_file(client: TestClient) -> None:
    duplicate = client.post(
        "/api/rsa/encrypt",
        files=[
            ("file", ("plain.txt", b"abc", "text/plain")),
            ("e", (None, "3")),
            ("e", (None, "5")),
            ("n", (None, "67591")),
            ("mode", (None, "block")),
        ],
    )
    assert duplicate.status_code == 422
    assert duplicate.json()["field"] == "e"

    scalar_file = client.post(
        "/api/rsa/encrypt",
        data={"file": "not-an-upload", "e": "3", "n": "67591", "mode": "block"},
        files={"unused": ("x.txt", b"x", "text/plain")},
    )
    assert scalar_file.status_code == 422
    assert scalar_file.json()["code"] == "INVALID_REQUEST"


def test_multipart_precedence_numeric_extension_size_decode_trace(client: TestClient) -> None:
    bad_e = client.post(
        "/api/rsa/encrypt",
        data={"e": "x", "n": "67591", "mode": "block"},
        files={"file": ("plain.bin", b"A" * 1_000_001, "text/plain")},
    )
    assert (bad_e.json()["code"], bad_e.json()["field"]) == ("NOT_INTEGER", "e")

    extension = client.post(
        "/api/rsa/encrypt",
        data={"e": "3", "n": "67591", "mode": "block"},
        files={"file": ("plain.bin", b"A" * 1_000_001, "text/plain")},
    )
    assert extension.json()["message"] == "Chỉ nhận file .txt."

    size = _post(client, b"\xff" + b"A" * 1_000_000)
    assert size.json()["message"] == "File vượt quá dung lượng tối đa 1 MB."

    domain_before_trace = client.post(
        "/api/rsa/encrypt",
        data={"e": "7", "n": "187", "mode": "block", "traceBlockIndex": "bad"},
        files={"file": ("plain.txt", b"A", "text/plain")},
    )
    assert domain_before_trace.json()["code"] == "N_TOO_SMALL"


def test_file_trace_and_codepoint_boundaries(client: TestClient) -> None:
    traced = client.post(
        "/api/rsa/encrypt",
        data={"e": "3", "n": "67591", "mode": "block", "traceBlockIndex": "1"},
        files={"file": ("plain.txt", b"Hi!", "text/plain")},
    )
    assert traced.status_code == 200
    assert traced.json()["trace"]["blockIndex"] == 1

    accepted = client.post(
        "/api/rsa/encrypt",
        data={"e": "3", "n": "67591", "mode": "block"},
        files={"file": ("plain.txt", ("A" * 10_000).encode(), "text/plain")},
    )
    assert accepted.status_code == 200
    rejected = client.post(
        "/api/rsa/encrypt",
        data={"e": "3", "n": "67591", "mode": "block"},
        files={"file": ("plain.txt", ("A" * 10_001).encode(), "text/plain")},
    )
    assert rejected.status_code == 422
    assert (rejected.json()["code"], rejected.json()["field"]) == ("INPUT_TOO_LARGE", "file")


def test_decrypt_multipart_and_malformed_encrypt_are_rejected(client: TestClient) -> None:
    decrypt = client.post(
        "/api/rsa/decrypt",
        files={"file": ("cipher.txt", b"11", "text/plain")},
    )
    assert decrypt.status_code == 415
    assert decrypt.json()["code"] == "UNSUPPORTED_MEDIA_TYPE"

    malformed = client.post(
        "/api/rsa/encrypt",
        content=b"--missing-close\r\n",
        headers={"content-type": "multipart/form-data; boundary=missing-close"},
    )
    assert malformed.status_code == 422
    assert malformed.json()["code"] == "INVALID_REQUEST"


def test_unexpected_file_read_failure_uses_safe_rsa_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken_read(self: UploadFile, size: int = -1) -> bytes:
        del self, size
        raise OSError("private filesystem detail")

    monkeypatch.setattr(UploadFile, "read", broken_read)
    response = _post(client, b"Hi!")
    assert response.status_code == 500
    assert response.json() == {
        "success": False,
        "code": "FILE_READ_FAILED",
        "message": "Không thể đọc file.",
        "field": "file",
    }
    assert "filesystem" not in response.text
