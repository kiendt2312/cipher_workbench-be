"""Integration contract for the strict Affine multipart endpoint."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app import config
from app.errors import messages
from app.errors.exceptions import FileReadError
from app.main import app
from app.services.file_processing import UTF8_BOM

FILE_PATH = "/api/affine/file"
_UNSET = object()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _post_file(
    client: TestClient,
    *,
    filename: str = "input.txt",
    content: bytes = b"HELLO",
    a: object = "5",
    b: object = "8",
    action: object = "encrypt",
    response_mode: object = "content",
    include_file: bool = True,
):
    data: dict[str, object] = {}
    if a is not _UNSET:
        data["a"] = a
    if b is not _UNSET:
        data["b"] = b
    if action is not _UNSET:
        data["action"] = action
    if response_mode is not _UNSET:
        data["response_mode"] = response_mode
    files = {"file": (filename, content, "text/plain")} if include_file else None
    return client.post(FILE_PATH, data=data, files=files)


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


@pytest.mark.parametrize(
    ("content", "action", "expected"),
    [(b"HELLO", "encrypt", "RCLLA"), (b"RCLLA", "decrypt", "HELLO")],
)
def test_affine_file_content_uses_the_same_core(
    client: TestClient,
    content: bytes,
    action: str,
    expected: str,
) -> None:
    _assert_content(_post_file(client, content=content, action=action), expected)


def test_affine_file_omitted_response_mode_defaults_to_content(client: TestClient) -> None:
    _assert_content(_post_file(client, response_mode=_UNSET), "RCLLA")


def test_affine_file_accepts_negative_large_and_trimmed_keys(client: TestClient) -> None:
    _assert_content(_post_file(client, a=" -21 ", b=" -18 "), "RCLLA")
    _assert_content(_post_file(client, a="57", b="60"), "RCLLA")


def test_affine_file_accepts_32_character_signed_decimal_keys(client: TestClient) -> None:
    _assert_content(
        _post_file(
            client,
            a="+0000000000000000000000000000005",
            b="+0000000000000000000000000000008",
        ),
        "RCLLA",
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("a", _UNSET, messages.MISSING_AFFINE_MULTIPLIER),
        ("a", "", messages.MISSING_AFFINE_MULTIPLIER),
        ("a", "5.0", messages.INVALID_AFFINE_MULTIPLIER),
        ("a", "9" * 33, messages.INVALID_AFFINE_MULTIPLIER),
        ("b", _UNSET, messages.MISSING_AFFINE_SHIFT),
        ("b", "", messages.MISSING_AFFINE_SHIFT),
        ("b", "8.0", messages.INVALID_AFFINE_SHIFT),
        ("b", "9" * 33, messages.INVALID_AFFINE_SHIFT),
    ],
)
def test_affine_file_key_validation_contract(
    client: TestClient,
    field: str,
    value: object,
    message: str,
) -> None:
    kwargs = {field: value}
    _assert_error(_post_file(client, **kwargs), 422, message)


def test_affine_file_validation_precedence_is_deterministic(client: TestClient) -> None:
    missing_file = client.post(
        FILE_PATH,
        files=[
            ("action", (None, "bad")),
            ("response_mode", (None, "content")),
        ],
    )
    _assert_error(
        missing_file,
        422,
        messages.MISSING_FILE,
    )
    _assert_error(
        _post_file(client, filename="bad.md", a="2", b=_UNSET, action="bad"),
        422,
        messages.NON_INVERTIBLE_AFFINE_MULTIPLIER,
    )
    _assert_error(
        _post_file(client, filename="bad.md", b="bad", action="bad"),
        422,
        messages.INVALID_AFFINE_SHIFT,
    )
    _assert_error(
        _post_file(client, content=b"", action="ENCRYPT", response_mode="FILE"),
        422,
        messages.INVALID_ACTION,
    )
    _assert_error(
        _post_file(client, content=b"", response_mode="FILE"),
        422,
        messages.INVALID_RESPONSE_MODE,
    )
    _assert_error(
        _post_file(client, action=_UNSET),
        422,
        messages.INVALID_ACTION,
    )


def test_affine_file_mode_error_is_json_without_attachment(client: TestClient) -> None:
    _assert_error(
        _post_file(client, a="2", response_mode="file"),
        422,
        messages.NON_INVERTIBLE_AFFINE_MULTIPLIER,
    )


def test_affine_file_rejects_unknown_and_duplicate_fields(client: TestClient) -> None:
    unknown = client.post(
        FILE_PATH,
        files={"file": ("input.txt", b"HELLO", "text/plain")},
        data={"a": "5", "b": "8", "action": "encrypt", "key": "5"},
    )
    duplicate = client.post(
        FILE_PATH,
        files=[
            ("file", ("input.txt", b"HELLO", "text/plain")),
            ("a", (None, "5")),
            ("a", (None, "7")),
            ("b", (None, "8")),
            ("action", (None, "encrypt")),
        ],
    )

    _assert_error(unknown, 422, messages.INVALID_REQUEST_BODY)
    _assert_error(duplicate, 422, messages.INVALID_REQUEST_BODY)


def test_affine_file_part_without_filename_is_body_framing_error(client: TestClient) -> None:
    response = client.post(
        FILE_PATH,
        data={"file": "HELLO", "a": "5", "b": "8", "action": "encrypt"},
    )

    _assert_error(response, 422, messages.INVALID_REQUEST_BODY)


def test_affine_file_empty_filename_uses_extension_error(client: TestClient) -> None:
    body = (
        b"--empty-name\r\n"
        b'Content-Disposition: form-data; name="file"; filename=""\r\n'
        b"Content-Type: text/plain\r\n\r\nHELLO\r\n"
        b'--empty-name\r\nContent-Disposition: form-data; name="a"\r\n\r\n5\r\n'
        b'--empty-name\r\nContent-Disposition: form-data; name="b"\r\n\r\n8\r\n'
        b"--empty-name\r\n"
        b'Content-Disposition: form-data; name="action"\r\n\r\nencrypt\r\n'
        b"--empty-name--\r\n"
    )
    response = client.post(
        FILE_PATH,
        content=body,
        headers={"content-type": "multipart/form-data; boundary=empty-name"},
    )

    _assert_error(response, 415, messages.UNSUPPORTED_FILE_TYPE)


@pytest.mark.parametrize("filename", ["bad.md", "data.txt.exe", "readme"])
def test_affine_file_requires_a_final_txt_extension(
    client: TestClient,
    filename: str,
) -> None:
    _assert_error(_post_file(client, filename=filename), 415, messages.UNSUPPORTED_FILE_TYPE)


def test_affine_file_zero_size_and_invalid_utf8_errors(client: TestClient) -> None:
    _assert_error(_post_file(client, content=b""), 422, messages.EMPTY_FILE)
    _assert_error(_post_file(client, content=b"\xff\xfe"), 415, messages.UNSUPPORTED_ENCODING)


def test_affine_file_exact_five_mib_including_bom_is_accepted(client: TestClient) -> None:
    content = UTF8_BOM + b"A" * (config.MAX_FILE_BYTES - len(UTF8_BOM))
    response = _post_file(client, content=content, response_mode="file")

    assert response.status_code == 200
    assert len(response.content) == config.MAX_FILE_BYTES
    assert response.content.startswith(UTF8_BOM)


def test_affine_file_first_byte_over_five_mib_is_rejected(client: TestClient) -> None:
    response = _post_file(client, content=b"A" * (config.MAX_FILE_BYTES + 1))

    _assert_error(response, 413, messages.FILE_TOO_LARGE)


def test_affine_file_preserves_crlf_whitespace_unicode_and_emoji(client: TestClient) -> None:
    _assert_content(_post_file(client, content="Hé🙂z!\r\n".encode()), "Ré🙂d!\r\n")
    _assert_content(_post_file(client, content=b" \t\r\n"), " \t\r\n")


@pytest.mark.parametrize("had_bom", [False, True])
def test_affine_attachment_preserves_exact_bom_state(
    client: TestClient,
    had_bom: bool,
) -> None:
    response = _post_file(
        client,
        content=(UTF8_BOM if had_bom else b"") + b"HELLO",
        response_mode="file",
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.content == (UTF8_BOM if had_bom else b"") + b"RCLLA"


@pytest.mark.parametrize(
    ("filename", "action", "content", "expected_fragment"),
    [
        ("note.txt", "encrypt", b"HELLO", "note.encrypted.txt"),
        ("secret.txt", "decrypt", b"RCLLA", "secret.decrypted.txt"),
        ("bao.cao.TXT", "encrypt", b"HELLO", "bao.cao.encrypted.txt"),
        ("../nested/input.txt", "encrypt", b"HELLO", "input.encrypted.txt"),
        (
            "dữ liệu.txt",
            "encrypt",
            b"HELLO",
            "filename*=UTF-8''d%E1%BB%AF%20li%E1%BB%87u.encrypted.txt",
        ),
    ],
)
def test_affine_attachment_filename_is_server_owned_and_safe(
    client: TestClient,
    filename: str,
    action: str,
    content: bytes,
    expected_fragment: str,
) -> None:
    response = _post_file(
        client,
        filename=filename,
        content=content,
        action=action,
        response_mode="file",
    )

    assert response.status_code == 200
    assert expected_fragment in response.headers["content-disposition"]
    assert "affine" not in response.headers["content-disposition"].lower()


def test_affine_content_mode_strips_bom_without_metadata(client: TestClient) -> None:
    _assert_content(_post_file(client, content=UTF8_BOM + b"HELLO"), "RCLLA")


def test_affine_truncated_multipart_is_rejected_before_field_validation(
    client: TestClient,
) -> None:
    response = client.post(
        FILE_PATH,
        content=(
            b'--cut\r\nContent-Disposition: form-data; name="file"; filename="input.txt"\r\n'
            b"Content-Type: text/plain\r\n\r\nHELLO"
        ),
        headers={"content-type": "multipart/form-data; boundary=cut"},
    )

    _assert_error(response, 422, messages.INVALID_REQUEST_BODY)


def test_affine_file_openapi_is_exact(client: TestClient) -> None:
    operation = client.get("/openapi.json").json()["paths"][FILE_PATH]["post"]
    schema = operation["requestBody"]["content"]["multipart/form-data"]["schema"]

    assert set(schema["required"]) == {"file", "a", "b", "action"}
    assert schema["additionalProperties"] is False
    assert schema["properties"]["file"]["format"] == "binary"
    for name in ("a", "b"):
        assert schema["properties"][name] == {
            "type": "string",
            "pattern": r"^[+-]?[0-9]+$",
            "maxLength": 32,
        }
    assert schema["properties"]["action"]["enum"] == ["encrypt", "decrypt"]
    assert schema["properties"]["response_mode"] == {
        "type": "string",
        "enum": ["content", "file"],
        "default": "content",
    }
    assert set(operation["responses"]) == {"200", "413", "415", "422", "500"}
    assert set(operation["responses"]["200"]["content"]) == {
        "application/json",
        "text/plain",
    }
    for status in ("413", "415", "422", "500"):
        error_schema = operation["responses"][status]["content"]["application/json"]["schema"]
        assert set(error_schema["required"]) == {"success", "message"}
        assert set(error_schema["properties"]) == {"success", "message"}


def test_cipher_post_route_inventory_is_exactly_twenty_six(client: TestClient) -> None:
    paths = {
        path
        for path, operations in client.get("/openapi.json").json()["paths"].items()
        if path.startswith("/api/") and "post" in operations
    }

    expected = {
        f"/api/{cipher}/{operation}"
        for cipher in ("caesar", "vigenere", "playfair", "affine", "columnar", "des")
        for operation in ("encrypt", "decrypt", "file")
    }
    expected.update({"/api/hill/encrypt", "/api/hill/decrypt", "/api/hill/key/analyze"})
    expected.add("/api/des/trace")
    expected.update(
        {
            "/api/rsa/keys",
            "/api/rsa/keys/random",
            "/api/rsa/encrypt",
            "/api/rsa/decrypt",
        }
    )
    assert paths == expected


def test_affine_file_requests_are_stateless(client: TestClient) -> None:
    first = _post_file(client, content=b"HELLO")
    _post_file(client, content=b"AAAA", a="1", b="1")
    second = _post_file(client, content=b"HELLO")

    assert first.json() == second.json() == {"success": True, "result": "RCLLA"}


def test_affine_unexpected_file_failure_is_sanitized_without_payload_log(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw_a = "+0000000000000000000000000000005"
    raw_b = "+0000000000000000000000000000008"

    def fail_after_transform(*args: object) -> bytes:
        del args
        raise RuntimeError("technical attachment failure")

    monkeypatch.setattr("app.api.routes_affine_file.build_attachment_body", fail_after_transform)
    caplog.set_level("ERROR", logger="app.errors.handlers")
    response = _post_file(
        client,
        content=b"HELLO",
        a=raw_a,
        b=raw_b,
        response_mode="file",
    )

    _assert_error(response, 500, messages.UNEXPECTED_FAILURE)
    assert "RuntimeError" in caplog.text
    assert "HELLO" not in caplog.text
    assert "RCLLA" not in caplog.text
    assert raw_a not in caplog.text
    assert raw_b not in caplog.text


def test_affine_file_read_failure_uses_canonical_safe_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def fail_read(reader: object) -> bytes:
        del reader
        raise FileReadError()

    monkeypatch.setattr("app.api.routes_affine_file.read_limited_bytes", fail_read)
    caplog.set_level("ERROR", logger="app.errors.handlers")
    response = _post_file(client, content=b"private-content", response_mode="file")

    _assert_error(response, 500, messages.FILE_READ_FAILURE)
    assert "FileReadError" in caplog.text
    assert "private-content" not in caplog.text
