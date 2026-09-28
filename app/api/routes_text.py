"""JSON endpoints for encrypting and decrypting text."""

from typing import Literal

from fastapi import APIRouter, Request

from app.api.history_recorder import note_history
from app.api.schemas import (
    TextCipherRequest,
    TextCipherResponse,
    decode_text_request,
    validate_text_request,
)
from app.core.caesar import transform_text

router = APIRouter(prefix="/api/caesar", tags=["text"])
_REQUEST_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {"schema": TextCipherRequest.model_json_schema()},
        },
    }
}


async def _process_text(
    request: Request, operation: Literal["encrypt", "decrypt"]
) -> TextCipherResponse:
    payload = decode_text_request(await request.body(), request.headers.get("content-type"))
    text, key = validate_text_request(payload)
    note_history(request, input_length=len(text))
    result = transform_text(text, key, operation)
    note_history(request, output_length=len(result))
    return TextCipherResponse(success=True, result=result)


@router.post("/encrypt", response_model=TextCipherResponse, openapi_extra=_REQUEST_BODY)
async def encrypt_text(request: Request) -> TextCipherResponse:
    return await _process_text(request, "encrypt")


@router.post("/decrypt", response_model=TextCipherResponse, openapi_extra=_REQUEST_BODY)
async def decrypt_text(request: Request) -> TextCipherResponse:
    return await _process_text(request, "decrypt")
