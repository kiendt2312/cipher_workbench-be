"""Multipart endpoint for encrypting and decrypting UTF-8 text files."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.history_recorder import note_history
from app.api.request_size_guard import MultipartCompletionGuard
from app.api.schemas import MISSING, FileCipherResponse, validate_file_form_fields
from app.core.caesar import transform_text
from app.errors import messages
from app.errors.exceptions import EmptyFileError, MissingFileError, UnsupportedFileTypeError
from app.services.file_processing import (
    build_attachment_body,
    build_content_disposition,
    build_result_filename,
    decode_file_bytes,
    has_allowed_extension,
    read_limited_bytes,
    result_byte_length,
)

router = APIRouter(prefix="/api/caesar", tags=["file"])

_SUCCESS_CONTENT = FileCipherResponse.model_json_schema()
_ERROR_CONTENT = {
    "type": "object",
    "required": ["success", "message"],
    "properties": {
        "success": {"type": "boolean", "const": False},
        "message": {"type": "string"},
    },
}


@router.post(
    "/file",
    response_class=Response,
    responses={
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
    },
)
async def process_file(
    request: Request,
    # Keep metadata validation before this first read to preserve error precedence.
    file: Annotated[
        UploadFile | None, File(description=messages.FILE_API_UPLOAD_DESCRIPTION)
    ] = None,
    key: Annotated[str | None, Form()] = None,
    action: Annotated[str | None, Form()] = None,
    response_mode: Annotated[str | None, Form()] = "content",
) -> Response:
    if request.scope.get(MultipartCompletionGuard.SCOPE_KEY) is False:
        raise StarletteHTTPException(status_code=400, detail="Malformed multipart body")

    if file is None:
        raise MissingFileError()

    # FastAPI maps an explicit empty form value to this parameter's default.
    # Read the already-cached FormData so omission and an empty value remain distinct.
    form = await request.form()
    raw_response_mode = form.get("response_mode", MISSING)
    parsed_key, parsed_action, parsed_response_mode = validate_file_form_fields(
        key,
        action,
        raw_response_mode,
    )
    note_history(request, operation=parsed_action, response_mode=parsed_response_mode)

    if not has_allowed_extension(file.filename):
        raise UnsupportedFileTypeError()

    raw = await read_limited_bytes(file)
    note_history(request, input_length=len(raw))
    if raw == b"":
        raise EmptyFileError()

    text, had_bom = decode_file_bytes(raw)
    del raw  # Release the upload buffer before transforming or constructing the response.
    result = transform_text(text, parsed_key, parsed_action)
    note_history(request, output_length=result_byte_length(result, had_bom))

    if parsed_response_mode == "content":
        return JSONResponse(
            content=FileCipherResponse(success=True, result=result).model_dump(mode="json")
        )

    result_filename = build_result_filename(file.filename, parsed_action)
    return Response(
        content=build_attachment_body(result, had_bom),
        media_type="text/plain",
        headers={"Content-Disposition": build_content_disposition(result_filename)},
    )
