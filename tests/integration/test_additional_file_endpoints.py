"""Integration contract for Vigenere and Playfair multipart endpoints."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app import config
from app.errors import messages
from app.main import app
from app.services.file_processing import UTF8_BOM

VIGENERE_FILE = "/api/vigenere/file"
PLAYFAIR_FILE = "/api/playfair/file"
FILE_PATHS = (VIGENERE_FILE, PLAYFAIR_FILE)
_UNSET = object()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _post_file(
    client: TestClient,
    path: str,
    *,
    filename: str = "input.txt",
    content: bytes = b"Attack at dawn!",
    key: object = "LEMON",
    action: object = "encrypt",
    response_mode: object = "content",
    include_file: bool = True,
):
    data: dict[str, object] = {}
    if key is not _UNSET:
        data["key"] = key
    if action is not _UNSET:
        data["action"] = action
    if response_mode is not _UNSET:
        data["response_mode"] = response_mode
    files = {"file": (filename, content, "text/plain")} if include_file else None
    return client.post(path, files=files, data=data)


def _assert_content(response, result: str) -> None:
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "content-disposition" not in response.headers
    assert response.json() == {"success": True, "result": result}
    assert set(response.json()) == {"success", "result"}


def _assert_error(response, status: int, message: str) -> None:
    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/json")
    assert "content-disposition" not in response.headers
    assert response.json() == {"success": False, "message": message}
    assert set(response.json()) == {"success", "message"}


def test_vigenere_and_playfair_content_modes_use_their_text_cores(client: TestClient) -> None:
    _assert_content(_post_file(client, VIGENERE_FILE), "Lxfopv ef rnhr!")
    _assert_content(
        _post_file(
            client,
            PLAYFAIR_FILE,
            content=b"HIDE THE GOLD IN THE TREE STUMP",
            key="PLAYFAIR EXAMPLE",
        ),
        "BMODZBXDNABEKUDMUIXMMOUVIF",
    )


@pytest.mark.parametrize(
    ("path", "content", "key", "expected"),
    [
        (VIGENERE_FILE, b"Attack at dawn!", "LEMON", "Lxfopv ef rnhr!"),
        (PLAYFAIR_FILE, b"HIDE THE GOLD", "PLAYFAIR EXAMPLE", "BMODZBXDNAGE"),
    ],
)
def test_omitted_response_mode_defaults_to_content(
    client: TestClient, path: str, content: bytes, key: str, expected: str
) -> None:
    _assert_content(
        _post_file(
            client,
            path,
            content=content,
            key=key,
            response_mode=_UNSET,
        ),
        expected,
    )


@pytest.mark.parametrize(
    ("path", "content", "key", "action", "expected", "filename"),
    [
        (
            VIGENERE_FILE,
            b"Attack at dawn!",
            "LEMON",
            "encrypt",
            b"Lxfopv ef rnhr!",
            "bao.cao.encrypted.txt",
        ),
        (
            PLAYFAIR_FILE,
            b"BMODZBXDNAGE",
            "PLAYFAIR EXAMPLE",
            "decrypt",
            b"HIDETHEGOLD",
            "bao.cao.decrypted.txt",
        ),
    ],
)
def test_file_mode_returns_server_owned_attachment(
    client: TestClient,
    path: str,
    content: bytes,
    key: str,
    action: str,
    expected: bytes,
    filename: str,
) -> None:
    response = _post_file(
        client,
        path,
        filename="bao.cao.TXT",
        content=content,
        key=key,
        action=action,
        response_mode="file",
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert filename in response.headers["content-disposition"]
    assert response.content == expected


@pytest.mark.parametrize("path", FILE_PATHS)
@pytest.mark.parametrize("had_bom", [False, True])
def test_attachment_preserves_bom_state(client: TestClient, path: str, had_bom: bool) -> None:
    key = "LEMON" if path == VIGENERE_FILE else "PLAYFAIR EXAMPLE"
    content = b"AB" if path == VIGENERE_FILE else b"HI"
    response = _post_file(
        client,
        path,
        content=(UTF8_BOM if had_bom else b"") + content,
        key=key,
        response_mode="file",
    )

    assert response.status_code == 200
    assert response.content.startswith(UTF8_BOM) is had_bom


def test_content_mode_strips_bom_from_logical_result(client: TestClient) -> None:
    _assert_content(
        _post_file(client, VIGENERE_FILE, content=UTF8_BOM + b"Attack"),
        "Lxfopv",
    )


def test_vigenere_preserves_crlf_unicode_and_key_position(client: TestClient) -> None:
    _assert_content(
        _post_file(
            client,
            VIGENERE_FILE,
            content="A\r\néA".encode(),
            key="BC",
        ),
        "B\r\néC",
    )


def test_playfair_file_normalizes_format_and_drops_trailing_decrypt_filler(
    client: TestClient,
) -> None:
    encrypted = _post_file(
        client,
        PLAYFAIR_FILE,
        content=b"HIDE\r\nTHE GOLD!",
        key="PLAYFAIR EXAMPLE",
    )
    _assert_content(encrypted, "BMODZBXDNAGE")

    decrypted = _post_file(
        client,
        PLAYFAIR_FILE,
        content=b"GWGW",
        key="PLAYFAIR EXAMPLE",
        action="decrypt",
    )
    _assert_content(decrypted, "XQX")


@pytest.mark.parametrize("path", FILE_PATHS)
def test_exact_five_mib_is_accepted(client: TestClient, path: str) -> None:
    content = b"AB" * (config.MAX_FILE_BYTES // 2)
    key = "A" if path == VIGENERE_FILE else "MONARCHY"

    response = _post_file(client, path, content=content, key=key)

    assert response.status_code == 200
    assert len(response.json()["result"]) == config.MAX_FILE_BYTES


@pytest.mark.parametrize("path", FILE_PATHS)
def test_first_byte_over_five_mib_is_rejected(client: TestClient, path: str) -> None:
    key = "A" if path == VIGENERE_FILE else "MONARCHY"

    response = _post_file(
        client,
        path,
        content=b"A" * (config.MAX_FILE_BYTES + 1),
        key=key,
    )

    _assert_error(response, 413, messages.FILE_TOO_LARGE)


@pytest.mark.parametrize("path", FILE_PATHS)
def test_missing_empty_extension_and_encoding_errors(client: TestClient, path: str) -> None:
    key = "KEY" if path == VIGENERE_FILE else "MONARCHY"

    _assert_error(
        _post_file(client, path, key=key, include_file=False),
        422,
        messages.MISSING_FILE,
    )
    _assert_error(_post_file(client, path, key=key, content=b""), 422, messages.EMPTY_FILE)
    _assert_error(
        _post_file(client, path, key=key, filename="bad.txt.exe"),
        415,
        messages.UNSUPPORTED_FILE_TYPE,
    )
    _assert_error(
        _post_file(client, path, key=key, content=b"\xff\xfe"),
        415,
        messages.UNSUPPORTED_ENCODING,
    )


def test_whitespace_only_differs_by_algorithm(client: TestClient) -> None:
    _assert_content(_post_file(client, VIGENERE_FILE, content=b"   \r\n"), "   \r\n")
    _assert_error(
        _post_file(
            client,
            PLAYFAIR_FILE,
            content=b"   \r\n",
            key="MONARCHY",
        ),
        422,
        messages.PLAYFAIR_TEXT_EMPTY,
    )


@pytest.mark.parametrize(
    ("path", "key", "message"),
    [
        (VIGENERE_FILE, "KEY 1", messages.INVALID_VIGENERE_KEY),
        (PLAYFAIR_FILE, "123 ---", messages.INVALID_PLAYFAIR_KEY),
    ],
)
def test_key_error_precedes_extension_and_size(
    client: TestClient, path: str, key: str, message: str
) -> None:
    response = _post_file(
        client,
        path,
        filename="bad.md",
        content=b"A" * (config.MAX_FILE_BYTES + 1),
        key=key,
    )

    _assert_error(response, 422, message)


@pytest.mark.parametrize(
    ("key", "action", "response_mode", "message"),
    [
        (_UNSET, "encrypt", "content", messages.MISSING_KEY),
        ("KEY", _UNSET, "content", messages.INVALID_ACTION),
        ("KEY", "ENCRYPT", "content", messages.INVALID_ACTION),
        ("KEY", "encrypt", "FILE", messages.INVALID_RESPONSE_MODE),
    ],
)
def test_vigenere_scalar_field_validation(
    client: TestClient,
    key: object,
    action: object,
    response_mode: object,
    message: str,
) -> None:
    _assert_error(
        _post_file(
            client,
            VIGENERE_FILE,
            key=key,
            action=action,
            response_mode=response_mode,
        ),
        422,
        message,
    )


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"123 ", messages.PLAYFAIR_TEXT_EMPTY),
        (b"ABC", messages.PLAYFAIR_CIPHERTEXT_ODD),
        (b"AABC", messages.PLAYFAIR_DUPLICATE_DIGRAPH),
    ],
)
def test_playfair_post_decode_validation(client: TestClient, content: bytes, message: str) -> None:
    _assert_error(
        _post_file(
            client,
            PLAYFAIR_FILE,
            content=content,
            key="MONARCHY",
            action="decrypt" if content != b"123 " else "encrypt",
            response_mode="file",
        ),
        422,
        message,
    )


def test_invalid_utf8_precedes_playfair_content_validation(client: TestClient) -> None:
    _assert_error(
        _post_file(
            client,
            PLAYFAIR_FILE,
            content=b"\xff\xfe",
            key="MONARCHY",
        ),
        415,
        messages.UNSUPPORTED_ENCODING,
    )


@pytest.mark.parametrize("path", FILE_PATHS)
def test_malformed_and_truncated_multipart_are_canonical(client: TestClient, path: str) -> None:
    malformed = client.post(
        path,
        content=b"not multipart",
        headers={"content-type": "multipart/form-data; boundary=broken"},
    )
    truncated = client.post(
        path,
        content=(
            b'--cut\r\nContent-Disposition: form-data; name="file"; filename="input.txt"\r\n\r\nABC'
        ),
        headers={"content-type": "multipart/form-data; boundary=cut"},
    )

    _assert_error(malformed, 422, messages.INVALID_REQUEST_BODY)
    _assert_error(truncated, 422, messages.INVALID_REQUEST_BODY)


def test_openapi_documents_both_file_success_modes(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    for path in FILE_PATHS:
        operation = schema["paths"][path]["post"]
        request_schema = operation["requestBody"]["content"]["multipart/form-data"]["schema"]
        assert set(request_schema["required"]) == {"file", "key", "action"}
        assert request_schema["properties"]["file"] == {
            "type": "string",
            "format": "binary",
            "description": messages.FILE_API_UPLOAD_DESCRIPTION,
        }
        assert request_schema["properties"]["key"]["type"] == "string"
        assert request_schema["properties"]["action"]["enum"] == ["encrypt", "decrypt"]
        assert request_schema["properties"]["response_mode"]["default"] == "content"
        assert set(operation["responses"]["200"]["content"]) == {
            "application/json",
            "text/plain",
        }
        assert set(operation["responses"]["422"]["content"]) == {"application/json"}


def test_unexpected_file_mode_failure_is_sanitized_without_attachment_or_payload_log(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def fail(*args: object) -> str:
        raise RuntimeError("secret-file-content SECRETKEY")

    monkeypatch.setattr("app.api.routes_additional_file.transform_vigenere", fail)
    caplog.set_level("ERROR", logger="app.errors.handlers")

    response = _post_file(
        client,
        VIGENERE_FILE,
        content=b"secret-file-content",
        key="SECRETKEY",
        response_mode="file",
    )

    _assert_error(response, 500, messages.UNEXPECTED_FAILURE)
    assert "RuntimeError" in caplog.text
    assert "secret-file-content" not in caplog.text
    assert "SECRETKEY" not in caplog.text


def test_caesar_file_contract_remains_unchanged(client: TestClient) -> None:
    response = client.post(
        "/api/caesar/file",
        files={"file": ("input.txt", b"Hello World", "text/plain")},
        data={"key": "3", "action": "encrypt", "response_mode": "content"},
    )

    _assert_content(response, "Khoor Zruog")
