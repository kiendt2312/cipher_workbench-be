"""Strict JSON endpoints for Affine text transformations."""

from typing import Literal

from fastapi import APIRouter, Request

from app.api.history_recorder import note_history
from app.api.schemas import (
    AffineTextCipherRequest,
    TextCipherResponse,
    decode_affine_text_request,
    validate_affine_text_request,
)
from app.core.affine import transform_text
from app.errors import messages

router = APIRouter(prefix="/api/affine", tags=["Affine"])

_REQUEST_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {"schema": AffineTextCipherRequest.model_json_schema()},
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
    payload = decode_affine_text_request(
        await request.body(),
        request.headers.get("content-type"),
    )
    text, multiplier, shift = validate_affine_text_request(payload)
    note_history(request, input_length=len(text))
    result = transform_text(text, multiplier, shift, operation)
    note_history(request, output_length=len(result))
    return TextCipherResponse(success=True, result=result)


@router.post(
    "/encrypt",
    response_model=TextCipherResponse,
    responses=_ERROR_RESPONSES,
    openapi_extra=_REQUEST_BODY,
)
async def encrypt_affine_text(request: Request) -> TextCipherResponse:
    return await _process_text(request, "encrypt")


@router.post(
    "/decrypt",
    response_model=TextCipherResponse,
    responses=_ERROR_RESPONSES,
    openapi_extra=_REQUEST_BODY,
)
async def decrypt_affine_text(request: Request) -> TextCipherResponse:
    return await _process_text(request, "decrypt")
