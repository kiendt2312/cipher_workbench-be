"""Multipart endpoints for Vigenere and Playfair file transformations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.history_recorder import note_history
from app.api.request_size_guard import MultipartCompletionGuard
from app.api.schemas import (
    MISSING,
    FileCipherResponse,
    validate_additional_file_form_fields,
    validate_playfair_content,
)
from app.core.playfair import transform_text as transform_playfair
from app.core.vigenere import transform_text as transform_vigenere
from app.errors import messages
from app.errors.exceptions import EmptyFileError, MissingFileError, UnsupportedFileTypeError
from app.services.file_processing import (
    build_attachment_body,
    build_content_disposition,
    build_result_filename,
    decode_file_bytes,
    has_allowed_extension,
    read_limited_bytes,
)

CipherName = Literal["vigenere", "playfair"]
Operation = Literal["encrypt", "decrypt"]
Transformer = Callable[[str, str, Operation], str]

vigenere_file_router = APIRouter(prefix="/api/vigenere", tags=["Vigenère"])
playfair_file_router = APIRouter(prefix="/api/playfair", tags=["Playfair"])

_SUCCESS_CONTENT = FileCipherResponse.model_json_schema()
_ERROR_CONTENT = {
    "type": "object",
    "required": ["success", "message"],
    "properties": {
        "success": {"type": "boolean", "const": False},
        "message": {"type": "string"},
    },
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
                    "properties": {
                        "file": {
                            "type": "string",
                            "format": "binary",
                            "description": messages.FILE_API_UPLOAD_DESCRIPTION,
                        },
                        "key": {"type": "string"},
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


async def _process_file(
    request: Request,
    file: UploadFile | None,
    key: str | None,
    action: str | None,
    cipher: CipherName,
    transformer: Transformer,
) -> Response:
    if request.scope.get(MultipartCompletionGuard.SCOPE_KEY) is False:
        raise StarletteHTTPException(status_code=400, detail="Malformed multipart body")
    if file is None:
        raise MissingFileError()

    form = await request.form()
    raw_response_mode = form.get("response_mode", MISSING)
    parsed_key, parsed_action, parsed_response_mode = validate_additional_file_form_fields(
        key,
        action,
        raw_response_mode,
        cipher,
    )
    note_history(request, operation=parsed_action, response_mode=parsed_response_mode)

    if not has_allowed_extension(file.filename):
        raise UnsupportedFileTypeError()

    raw = await read_limited_bytes(file)
    note_history(request, input_length=len(raw))
    if raw == b"":
        raise EmptyFileError()

    text, had_bom = decode_file_bytes(raw)
    del raw
    if cipher == "playfair":
        validate_playfair_content(text, parsed_action)
    result = transformer(text, parsed_key, parsed_action)
    note_history(request, output_length=len(result.encode("utf-8")))

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


@vigenere_file_router.post(
    "/file",
    response_class=Response,
    responses=_RESPONSES,
    openapi_extra=_FILE_REQUEST_BODY,
)
async def process_vigenere_file(
    request: Request,
    file: Annotated[
        UploadFile | None, File(description=messages.FILE_API_UPLOAD_DESCRIPTION)
    ] = None,
    key: Annotated[str | None, Form()] = None,
    action: Annotated[str | None, Form()] = None,
    response_mode: Annotated[str | None, Form()] = "content",
) -> Response:
    del response_mode
    return await _process_file(request, file, key, action, "vigenere", transform_vigenere)


@playfair_file_router.post(
    "/file",
    response_class=Response,
    responses=_RESPONSES,
    openapi_extra=_FILE_REQUEST_BODY,
)
async def process_playfair_file(
    request: Request,
    file: Annotated[
        UploadFile | None, File(description=messages.FILE_API_UPLOAD_DESCRIPTION)
    ] = None,
    key: Annotated[str | None, Form()] = None,
    action: Annotated[str | None, Form()] = None,
    response_mode: Annotated[str | None, Form()] = "content",
) -> Response:
    del response_mode
    return await _process_file(request, file, key, action, "playfair", transform_playfair)
