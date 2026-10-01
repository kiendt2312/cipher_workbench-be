"""Strict multipart endpoint for DES file transformations."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.des_schemas import DesFileForm, map_core_error, validate_file_form
from app.api.history_recorder import note_history
from app.api.request_size_guard import MultipartCompletionGuard
from app.api.routes_des import DesResponse, decrypt_data, encrypt_data
from app.core import des
from app.errors import messages
from app.errors.exceptions import EmptyFileError, UnsupportedFileTypeError
from app.services.file_processing import (
    build_attachment_body,
    build_content_disposition,
    build_result_filename,
    decode_file_bytes,
    has_allowed_extension,
    read_limited_bytes,
    result_byte_length,
)

router = APIRouter(prefix="/api/des", tags=["DES"])

_ERROR_CONTENT = {
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "required": ["success", "message"],
                "properties": {
                    "success": {"type": "boolean", "const": False},
                    "message": {"type": "string"},
                },
                "additionalProperties": False,
            }
        }
    }
}
_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "description": messages.FILE_API_SUCCESS_DESCRIPTION,
        "content": {
            "application/json": {"schema": DesResponse.model_json_schema()},
            "text/plain": {"schema": {"type": "string", "format": "binary"}},
        },
    },
    413: {"description": messages.FILE_TOO_LARGE, **_ERROR_CONTENT},
    415: {"description": messages.FILE_API_UNSUPPORTED_DESCRIPTION, **_ERROR_CONTENT},
    422: {"description": messages.FILE_API_INVALID_MULTIPART_DESCRIPTION, **_ERROR_CONTENT},
    500: {"description": messages.FILE_READ_FAILURE, **_ERROR_CONTENT},
}
_FILE_REQUEST_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["file", "key", "action"],
                    "additionalProperties": False,
                    "properties": {
                        "file": {
                            "type": "string",
                            "format": "binary",
                            "description": messages.FILE_API_UPLOAD_DESCRIPTION,
                        },
                        "key": {"type": "string", "description": "16 ký tự hex (64 bit)."},
                        "action": {"type": "string", "enum": ["encrypt", "decrypt"]},
                        "mode": {"type": "string", "enum": ["ECB", "CBC"], "default": "ECB"},
                        "iv": {"type": "string", "description": "16 ký tự hex khi mode = CBC."},
                        "response_mode": {
                            "type": "string",
                            "enum": ["content", "file"],
                            "default": "content",
                        },
                    },
                }
            }
        },
    }
}


def _transform(form: DesFileForm, text: str) -> tuple[str, list[dict[str, Any]]]:
    """encrypt: file text → PKCS#7 → hex; decrypt: file hex → UTF-8 text."""

    if form.action == "encrypt":
        return encrypt_data(text.encode("utf-8"), form.key, form.mode, form.iv, pad=True)
    try:
        data = des.parse_hex(text)
    except des.DesError as exc:
        raise map_core_error(exc) from None
    return decrypt_data(data, form.key, form.mode, form.iv, as_text=True)


@router.post(
    "/file",
    response_class=Response,
    responses=_RESPONSES,
    openapi_extra=_FILE_REQUEST_BODY,
)
async def process_des_file(request: Request) -> Response:
    form_data = await request.form()
    if request.scope.get(MultipartCompletionGuard.SCOPE_KEY) is not True:
        raise StarletteHTTPException(status_code=400, detail="Malformed multipart body")

    form = validate_file_form(form_data)
    note_history(request, operation=form.action, response_mode=form.response_mode)
    if not has_allowed_extension(form.file.filename):
        raise UnsupportedFileTypeError()

    raw = await read_limited_bytes(form.file)
    note_history(request, input_length=len(raw))
    if raw == b"":
        raise EmptyFileError()

    text, had_bom = decode_file_bytes(raw)
    del raw
    result, warnings = await run_in_threadpool(_transform, form, text)
    note_history(request, output_length=result_byte_length(result, had_bom))

    if form.response_mode == "content":
        return JSONResponse(
            content=DesResponse(success=True, result=result, warnings=warnings).model_dump(
                mode="json"
            )
        )

    result_filename = build_result_filename(form.file.filename, form.action)
    return Response(
        content=build_attachment_body(result, had_bom),
        media_type="text/plain",
        headers={"Content-Disposition": build_content_disposition(result_filename)},
    )
