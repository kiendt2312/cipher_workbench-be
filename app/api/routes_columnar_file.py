"""Strict multipart endpoint for Columnar Transposition file transforms."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.history_recorder import note_history
from app.api.request_size_guard import MultipartCompletionGuard
from app.api.schemas import FileCipherResponse, validate_columnar_file_form
from app.core.columnar import transform_text
from app.errors import messages
from app.errors.exceptions import EmptyFileError, InvalidRequestBodyError, UnsupportedFileTypeError
from app.services.file_processing import (
    build_attachment_body,
    build_content_disposition,
    build_result_filename,
    decode_file_bytes,
    has_allowed_extension,
    read_limited_bytes,
)

router = APIRouter(prefix="/api/columnar", tags=["Columnar Transposition"])

_KEY_SCHEMA = {
    "type": "string",
    "description": (
        "Khóa được trim chỉ bằng ASCII whitespace và dài tối đa 2.048 ký tự sau trim. "
        "Dùng hoán vị số cho 2 đến 256 cột (token cách nhau bằng dấu phẩy hoặc ASCII "
        "whitespace, có thể có một cặp ngoặc nhọn ngoài cùng) hoặc từ khóa 2 đến 256 "
        "chữ cái A-Z; từ khóa được xếp hạng ổn định, không phân biệt hoa thường."
    ),
    "examples": ["3 1 4 2", "BALLOON"],
}
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
                    "required": ["file", "key", "action"],
                    "additionalProperties": False,
                    "properties": {
                        "file": {
                            "type": "string",
                            "format": "binary",
                            "description": messages.FILE_API_UPLOAD_DESCRIPTION,
                        },
                        "key": _KEY_SCHEMA,
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
async def process_columnar_file(request: Request) -> Response:
    try:
        form = await request.form()
    except ValueError as exc:
        raise InvalidRequestBodyError() from exc
    if request.scope.get(MultipartCompletionGuard.SCOPE_KEY) is not True:
        raise StarletteHTTPException(status_code=400, detail="Malformed multipart body")

    file, ranks, action, response_mode = validate_columnar_file_form(form)
    note_history(request, operation=action, response_mode=response_mode)
    if not has_allowed_extension(file.filename):
        raise UnsupportedFileTypeError()

    raw = await read_limited_bytes(file)
    note_history(request, input_length=len(raw))
    if raw == b"":
        raise EmptyFileError()

    text, had_bom = decode_file_bytes(raw)
    del raw
    result = transform_text(text, ranks, action)
    note_history(request, output_length=len(result.encode("utf-8")))

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
