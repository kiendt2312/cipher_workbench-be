"""Strict multipart endpoint for Affine file transformations."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.history_recorder import note_history
from app.api.request_size_guard import MultipartCompletionGuard
from app.api.schemas import FileCipherResponse, validate_affine_file_form
from app.core.affine import transform_text
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

router = APIRouter(prefix="/api/affine", tags=["Affine"])

_SUCCESS_CONTENT = FileCipherResponse.model_json_schema()
_ERROR_CONTENT = {
    "type": "object",
    "required": ["success", "message"],
    "properties": {
        "success": {"type": "boolean", "const": False},
        "message": {"type": "string"},
    },
    "additionalProperties": False,
}
_RESPONSES = {
    200: {
        "description": messages.FILE_API_SUCCESS_DESCRIPTION,
        "content": {
            "application/json": {"schema": _SUCCESS_CONTENT},
            "text/plain": {"schema": {"type": "string", "format": "binary"}},
        },
    },
    413: {
        "description": messages.FILE_TOO_LARGE,
        "content": {"application/json": {"schema": _ERROR_CONTENT}},
    },
    415: {
        "description": messages.FILE_API_UNSUPPORTED_DESCRIPTION,
        "content": {"application/json": {"schema": _ERROR_CONTENT}},
    },
    422: {
        "description": messages.FILE_API_INVALID_MULTIPART_DESCRIPTION,
        "content": {"application/json": {"schema": _ERROR_CONTENT}},
    },
    500: {
        "description": messages.FILE_READ_FAILURE,
        "content": {"application/json": {"schema": _ERROR_CONTENT}},
    },
}
_FILE_REQUEST_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["file", "a", "b", "action"],
                    "additionalProperties": False,
                    "properties": {
                        "file": {
                            "type": "string",
                            "format": "binary",
                            "description": messages.FILE_API_UPLOAD_DESCRIPTION,
                        },
                        "a": {
                            "type": "string",
                            "pattern": r"^[+-]?[0-9]+$",
                            "maxLength": 32,
                        },
                        "b": {
                            "type": "string",
                            "pattern": r"^[+-]?[0-9]+$",
                            "maxLength": 32,
                        },
                        "action": {
                            "type": "string",
                            "enum": ["encrypt", "decrypt"],
                        },
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


@router.post(
    "/file",
    response_class=Response,
    responses=_RESPONSES,
    openapi_extra=_FILE_REQUEST_BODY,
)
async def process_affine_file(request: Request) -> Response:
    form = await request.form()
    if request.scope.get(MultipartCompletionGuard.SCOPE_KEY) is not True:
        raise StarletteHTTPException(status_code=400, detail="Malformed multipart body")

    file, multiplier, shift, action, response_mode = validate_affine_file_form(form)
    note_history(request, operation=action, response_mode=response_mode)
    if not has_allowed_extension(file.filename):
        raise UnsupportedFileTypeError()

    raw = await read_limited_bytes(file)
    note_history(request, input_length=len(raw))
    if raw == b"":
        raise EmptyFileError()

    text, had_bom = decode_file_bytes(raw)
    del raw
    result = transform_text(text, multiplier, shift, action)
    note_history(request, output_length=result_byte_length(result, had_bom))

    if response_mode == "content":
        return JSONResponse(
            content=FileCipherResponse(success=True, result=result).model_dump(mode="json")
        )

    result_filename = build_result_filename(file.filename, action)
    return Response(
        content=build_attachment_body(result, had_bom),
        media_type="text/plain",
        headers={"Content-Disposition": build_content_disposition(result_filename)},
    )
