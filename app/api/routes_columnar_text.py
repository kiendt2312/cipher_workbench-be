"""Strict JSON endpoints for Columnar Transposition text transforms."""

from typing import Literal

from fastapi import APIRouter, Request

from app.api.history_recorder import note_history
from app.api.schemas import (
    TextCipherResponse,
    decode_columnar_text_request,
    validate_columnar_text_request,
)
from app.core.columnar import transform_text
from app.errors import messages

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
_REQUEST_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["text", "key"],
                    "properties": {
                        "text": {"type": "string"},
                        "key": _KEY_SCHEMA,
                    },
                    "additionalProperties": False,
                }
            },
        },
    }
}
_ERROR_CONTENT = {
    "type": "object",
    "required": ["success", "message"],
    "properties": {
        "success": {"type": "boolean", "const": False},
        "message": {"type": "string"},
    },
    "additionalProperties": False,
}
_ERROR_RESPONSES = {
    413: {
        "description": messages.REQUEST_TOO_LARGE,
        "content": {"application/json": {"schema": _ERROR_CONTENT}},
    },
    422: {
        "description": messages.INVALID_REQUEST_BODY,
        "content": {"application/json": {"schema": _ERROR_CONTENT}},
    },
    500: {
        "description": messages.UNEXPECTED_FAILURE,
        "content": {"application/json": {"schema": _ERROR_CONTENT}},
    },
}


async def _process_text(
    request: Request,
    operation: Literal["encrypt", "decrypt"],
) -> TextCipherResponse:
    payload = decode_columnar_text_request(
        await request.body(),
        request.headers.get("content-type"),
    )
    text, ranks = validate_columnar_text_request(payload)
    note_history(request, input_length=len(text))
    result = transform_text(text, ranks, operation)
    note_history(request, output_length=len(result))
    return TextCipherResponse(success=True, result=result)


@router.post(
    "/encrypt",
    response_model=TextCipherResponse,
    responses=_ERROR_RESPONSES,
    openapi_extra=_REQUEST_BODY,
)
async def encrypt_columnar_text(request: Request) -> TextCipherResponse:
    return await _process_text(request, "encrypt")


@router.post(
    "/decrypt",
    response_model=TextCipherResponse,
    responses=_ERROR_RESPONSES,
    openapi_extra=_REQUEST_BODY,
)
async def decrypt_columnar_text(request: Request) -> TextCipherResponse:
    return await _process_text(request, "decrypt")
