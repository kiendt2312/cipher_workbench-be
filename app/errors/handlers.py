"""HTTP adapters for application and framework exceptions."""

import logging
import traceback
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import messages
from .exceptions import AppError, HillError, RsaError

logger = logging.getLogger(__name__)

RSA_PATHS = frozenset(
    {
        "/api/rsa/keys",
        "/api/rsa/keys/random",
        "/api/rsa/encrypt",
        "/api/rsa/decrypt",
    }
)


def _error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "message": message},
    )


def _rsa_error_response(
    status_code: int, code: str, message: str, field: str | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "code": code, "message": message, "field": field},
    )


def _log_server_error(request: Request, exc: Exception) -> None:
    timestamp = datetime.now(UTC).isoformat()
    frames = traceback.extract_tb(exc.__traceback__)
    safe_traceback = "\n".join(
        f'  File "{frame.filename}", line {frame.lineno}, in {frame.name}' for frame in frames
    )
    logger.error(
        "Server exception type=%s method=%s path=%s time=%s\n"
        "Traceback (most recent call last):\n%s",
        type(exc).__name__,
        request.method,
        request.url.path,
        timestamp,
        safe_traceback or "  <unavailable>",
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    if exc.status_code >= 500:
        _log_server_error(request, exc)
    if isinstance(exc, RsaError):
        return _rsa_error_response(exc.status_code, exc.code, exc.message, exc.field)
    if isinstance(exc, HillError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": exc.message,
                "code": exc.code,
                "details": exc.details,
            },
        )
    return _error_response(exc.status_code, exc.message)


async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    del exc
    if request.url.path in RSA_PATHS:
        return _rsa_error_response(422, "INVALID_REQUEST", messages.RSA_INVALID_REQUEST)
    return _error_response(422, messages.INVALID_REQUEST_BODY)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if request.url.path in RSA_PATHS:
        if exc.status_code == 415:
            return _rsa_error_response(
                415, "UNSUPPORTED_MEDIA_TYPE", messages.RSA_UNSUPPORTED_MEDIA_TYPE
            )
        if exc.status_code >= 500:
            _log_server_error(request, exc)
            return _rsa_error_response(500, "INTERNAL_ERROR", messages.RSA_INTERNAL_ERROR)
        return _rsa_error_response(422, "INVALID_REQUEST", messages.RSA_INVALID_REQUEST)
    if exc.status_code == 400:
        # Starlette reports malformed multipart bodies as HTTP 400.  At the
        # public boundary this is the same unreadable-body prerequisite as a
        # malformed JSON document, whose approved contract is canonical 422.
        return _error_response(422, messages.INVALID_REQUEST_BODY)
    if exc.status_code >= 500:
        _log_server_error(request, exc)

    if isinstance(exc.detail, str) and exc.detail in messages.CANONICAL_MESSAGES:
        message = exc.detail
    elif exc.status_code >= 500:
        message = messages.UNEXPECTED_FAILURE
    else:
        message = messages.INVALID_REQUEST_BODY
    return _error_response(exc.status_code, message)


async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    _log_server_error(request, exc)
    if request.url.path in RSA_PATHS:
        return _rsa_error_response(500, "INTERNAL_ERROR", messages.RSA_INTERNAL_ERROR)
    return _error_response(500, messages.UNEXPECTED_FAILURE)


def register_exception_handlers(app: FastAPI) -> None:
    """Register the complete application error contract on a FastAPI app."""

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unexpected_exception_handler)
