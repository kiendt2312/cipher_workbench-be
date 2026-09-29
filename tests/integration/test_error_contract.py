"""Integration contract tests for the 13 canonical error messages."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.errors import messages
from app.errors.exceptions import (
    AppError,
    DuplicatePlayfairDigraphError,
    EmptyFileError,
    EmptyPlayfairTextError,
    EmptyTextError,
    FileReadError,
    FileTooLargeError,
    InvalidActionError,
    InvalidKeyError,
    InvalidPlayfairKeyError,
    InvalidResponseModeError,
    InvalidStringKeyError,
    InvalidVigenereKeyError,
    MissingFileError,
    MissingKeyError,
    OddPlayfairCiphertextError,
    UnsupportedEncodingError,
    UnsupportedFileTypeError,
)
from app.errors.handlers import register_exception_handlers
from app.main import app as production_app


class ValidationPayload(BaseModel):
    value: int


def _build_error_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/errors/text-empty")
    async def text_empty() -> None:
        raise EmptyTextError()

    @app.get("/errors/missing-key")
    async def missing_key() -> None:
        raise MissingKeyError()

    @app.get("/errors/invalid-key")
    async def invalid_key() -> None:
        raise InvalidKeyError()

    @app.get("/errors/invalid-string-key")
    async def invalid_string_key() -> None:
        raise InvalidStringKeyError()

    @app.get("/errors/invalid-vigenere-key")
    async def invalid_vigenere_key() -> None:
        raise InvalidVigenereKeyError()

    @app.get("/errors/invalid-playfair-key")
    async def invalid_playfair_key() -> None:
        raise InvalidPlayfairKeyError()

    @app.get("/errors/empty-playfair-text")
    async def empty_playfair_text() -> None:
        raise EmptyPlayfairTextError()

    @app.get("/errors/odd-playfair-ciphertext")
    async def odd_playfair_ciphertext() -> None:
        raise OddPlayfairCiphertextError()

    @app.get("/errors/duplicate-playfair-digraph")
    async def duplicate_playfair_digraph() -> None:
        raise DuplicatePlayfairDigraphError()

    @app.get("/errors/missing-file")
    async def missing_file() -> None:
        raise MissingFileError()

    @app.get("/errors/empty-file")
    async def empty_file() -> None:
        raise EmptyFileError()

    @app.get("/errors/unsupported-file-type")
    async def unsupported_file_type() -> None:
        raise UnsupportedFileTypeError()

    @app.get("/errors/file-too-large")
    async def file_too_large() -> None:
        raise FileTooLargeError()

    @app.get("/errors/unsupported-encoding")
    async def unsupported_encoding() -> None:
        raise UnsupportedEncodingError()

    @app.get("/errors/invalid-action")
    async def invalid_action() -> None:
        raise InvalidActionError()

    @app.get("/errors/invalid-response-mode")
    async def invalid_response_mode() -> None:
        raise InvalidResponseModeError()

    @app.get("/errors/file-read")
    async def file_read() -> None:
        raise FileReadError()

    @app.post("/errors/unexpected")
    async def unexpected() -> None:
        raise RuntimeError("request-body-secret file-secret result-secret")

    @app.post("/errors/request-validation")
    async def request_validation(payload: ValidationPayload) -> ValidationPayload:
        return payload

    @app.get("/errors/http-exception")
    async def http_exception() -> None:
        raise StarletteHTTPException(status_code=418, detail="teapot")

    @app.get("/errors/http-bad-request")
    async def http_bad_request() -> None:
        raise StarletteHTTPException(status_code=400, detail="Malformed request body")

    @app.get("/errors/http-canonical")
    async def http_canonical() -> None:
        raise StarletteHTTPException(status_code=422, detail=messages.INVALID_ACTION)

    @app.get("/errors/http-server-exception")
    async def http_server_exception() -> None:
        raise StarletteHTTPException(status_code=503, detail="Service Unavailable")

    return app


@pytest.fixture
def error_client() -> Iterator[TestClient]:
    with TestClient(_build_error_app(), raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def production_client() -> Iterator[TestClient]:
    with TestClient(production_app, raise_server_exceptions=False) as client:
        yield client


def _assert_error(client: TestClient, path: str, status_code: int, message: str) -> None:
    response = client.get(path)

    assert response.status_code == status_code
    assert response.json() == {"success": False, "message": message}
    assert "detail" not in response.json()


# Canonical row 1/13: Thiếu hoặc rỗng text.
def test_canonical_text_empty_error(error_client: TestClient) -> None:
    _assert_error(error_client, "/errors/text-empty", 422, messages.TEXT_EMPTY)


# Canonical row 2/13: Thiếu key.
def test_canonical_missing_key_error(error_client: TestClient) -> None:
    _assert_error(error_client, "/errors/missing-key", 422, messages.MISSING_KEY)


# Canonical row 3/13: Key không phải số nguyên.
def test_canonical_invalid_key_error(error_client: TestClient) -> None:
    _assert_error(error_client, "/errors/invalid-key", 422, messages.INVALID_KEY)


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("/errors/invalid-string-key", messages.INVALID_STRING_KEY),
        ("/errors/invalid-vigenere-key", messages.INVALID_VIGENERE_KEY),
        ("/errors/invalid-playfair-key", messages.INVALID_PLAYFAIR_KEY),
        ("/errors/empty-playfair-text", messages.PLAYFAIR_TEXT_EMPTY),
        ("/errors/odd-playfair-ciphertext", messages.PLAYFAIR_CIPHERTEXT_ODD),
        ("/errors/duplicate-playfair-digraph", messages.PLAYFAIR_DUPLICATE_DIGRAPH),
    ],
)
def test_additional_cipher_errors_use_exact_two_field_envelope(
    error_client: TestClient, path: str, message: str
) -> None:
    _assert_error(error_client, path, 422, message)


# Canonical row 4/13: missing-file mapping.
def test_canonical_missing_file_error(error_client: TestClient) -> None:
    _assert_error(error_client, "/errors/missing-file", 422, messages.MISSING_FILE)


# Canonical row 5/13: File 0 byte.
def test_canonical_empty_file_error(error_client: TestClient) -> None:
    _assert_error(error_client, "/errors/empty-file", 422, messages.EMPTY_FILE)


# Canonical row 6/13: File không có đuôi .txt.
def test_canonical_unsupported_file_type_error(error_client: TestClient) -> None:
    _assert_error(
        error_client, "/errors/unsupported-file-type", 415, messages.UNSUPPORTED_FILE_TYPE
    )


# Canonical row 7/13: File lớn hơn 5 MiB.
def test_canonical_file_too_large_error(error_client: TestClient) -> None:
    _assert_error(error_client, "/errors/file-too-large", 413, messages.FILE_TOO_LARGE)


# Canonical row 8/13: File không phải UTF-8.
def test_canonical_unsupported_encoding_error(error_client: TestClient) -> None:
    _assert_error(error_client, "/errors/unsupported-encoding", 415, messages.UNSUPPORTED_ENCODING)


# Canonical row 9/13: Action không hợp lệ.
def test_canonical_invalid_action_error(error_client: TestClient) -> None:
    _assert_error(error_client, "/errors/invalid-action", 422, messages.INVALID_ACTION)


# Canonical row 10/13: Response mode không hợp lệ.
def test_canonical_invalid_response_mode_error(error_client: TestClient) -> None:
    _assert_error(
        error_client, "/errors/invalid-response-mode", 422, messages.INVALID_RESPONSE_MODE
    )


# Canonical row 11/13: Lỗi đọc file.
def test_canonical_file_read_error(
    error_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("ERROR", logger="app.errors.handlers")
    _assert_error(error_client, "/errors/file-read", 500, messages.FILE_READ_FAILURE)
    assert "FileReadError" in caplog.text
    assert "Traceback (most recent call last)" in caplog.text
    assert "method=GET" in caplog.text
    assert "path=/errors/file-read" in caplog.text
    assert "time=" in caplog.text


# Canonical row 12/13: Lỗi ngoài dự kiến.
def test_canonical_unexpected_error(
    error_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("ERROR", logger="app.errors.handlers")
    response = error_client.post(
        "/errors/unexpected",
        json={
            "text": "request-body-secret",
            "file": "file-secret",
            "result": "result-secret",
        },
    )

    assert response.status_code == 500
    assert response.json() == {"success": False, "message": messages.UNEXPECTED_FAILURE}
    assert "detail" not in response.json()
    assert "RuntimeError" in caplog.text
    assert "Traceback (most recent call last)" in caplog.text
    assert "method=POST" in caplog.text
    assert "path=/errors/unexpected" in caplog.text
    assert "time=" in caplog.text
    assert all(
        secret not in caplog.text
        for secret in ("request-body-secret", "file-secret", "result-secret")
    )


# Canonical row 13/13: Body JSON không hợp lệ.
def test_canonical_invalid_request_body_error(error_client: TestClient) -> None:
    response = error_client.post(
        "/errors/request-validation",
        content=b"not json at all",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {"success": False, "message": messages.INVALID_REQUEST_BODY}
    assert "detail" not in response.json()


def test_starlette_http_exception_sanitizes_noncanonical_detail(error_client: TestClient) -> None:
    response = error_client.get("/errors/http-exception")

    assert response.status_code == 418
    assert response.json() == {"success": False, "message": messages.INVALID_REQUEST_BODY}
    assert "teapot" not in response.text
    assert "detail" not in response.json()


def test_starlette_bad_request_maps_to_canonical_unreadable_body(error_client: TestClient) -> None:
    response = error_client.get("/errors/http-bad-request")

    assert response.status_code == 422
    assert response.json() == {"success": False, "message": messages.INVALID_REQUEST_BODY}
    assert "Malformed request body" not in response.text
    assert "detail" not in response.json()


def test_starlette_http_exception_preserves_canonical_detail(error_client: TestClient) -> None:
    response = error_client.get("/errors/http-canonical")

    assert response.status_code == 422
    assert response.json() == {"success": False, "message": messages.INVALID_ACTION}
    assert "detail" not in response.json()


def test_starlette_http_exception_sanitizes_noncanonical_server_detail(
    error_client: TestClient,
) -> None:
    response = error_client.get("/errors/http-server-exception")

    assert response.status_code == 503
    assert response.json() == {"success": False, "message": messages.UNEXPECTED_FAILURE}
    assert "Service Unavailable" not in response.text
    assert "detail" not in response.json()


def test_docs_endpoint_is_available(production_client: TestClient) -> None:
    response = production_client.get("/docs")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_unknown_api_route_is_vietnamese_canonical_without_detail(
    production_client: TestClient,
) -> None:
    response = production_client.get("/api/caesar/not-found")

    assert response.status_code == 404
    assert response.json() == {"success": False, "message": messages.INVALID_REQUEST_BODY}
    assert response.json()["message"] in messages.CANONICAL_MESSAGES
    assert "Not Found" not in response.text
    assert "detail" not in response.json()


def test_production_app_registers_all_four_handlers() -> None:
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    assert AppError in production_app.exception_handlers
    assert RequestValidationError in production_app.exception_handlers
    assert StarletteHTTPException in production_app.exception_handlers
    assert Exception in production_app.exception_handlers
