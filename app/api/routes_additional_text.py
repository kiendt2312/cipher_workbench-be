"""JSON endpoints for Vigenere and Playfair text transformations."""

from typing import Literal

from fastapi import APIRouter, Request

from app.api.history_recorder import note_history
from app.api.schemas import (
    PaddingInfo,
    PlayfairDecryptResponse,
    StringKeyCipherRequest,
    TextCipherResponse,
    decode_string_key_request,
    validate_additional_text_request,
)
from app.core.playfair import decrypt_with_padding as decrypt_playfair_with_padding
from app.core.playfair import transform_text as transform_playfair
from app.core.vigenere import transform_text as transform_vigenere
from app.errors import messages

vigenere_router = APIRouter(prefix="/api/vigenere", tags=["Vigenère"])
playfair_router = APIRouter(prefix="/api/playfair", tags=["Playfair"])

_REQUEST_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {"schema": StringKeyCipherRequest.model_json_schema()},
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


async def _request_fields(
    request: Request,
    cipher: Literal["vigenere", "playfair"],
    operation: Literal["encrypt", "decrypt"],
) -> tuple[str, str]:
    payload = decode_string_key_request(await request.body(), request.headers.get("content-type"))
    return validate_additional_text_request(payload, cipher, operation)


async def _process_vigenere(
    request: Request, operation: Literal["encrypt", "decrypt"]
) -> TextCipherResponse:
    text, key = await _request_fields(request, "vigenere", operation)
    note_history(request, input_length=len(text))
    result = transform_vigenere(text, key, operation)
    note_history(request, output_length=len(result))
    return TextCipherResponse(success=True, result=result)


async def _encrypt_playfair(request: Request) -> TextCipherResponse:
    text, key = await _request_fields(request, "playfair", "encrypt")
    note_history(request, input_length=len(text))
    result = transform_playfair(text, key, "encrypt")
    note_history(request, output_length=len(result))
    return TextCipherResponse(success=True, result=result)


async def _decrypt_playfair(request: Request) -> PlayfairDecryptResponse:
    text, key = await _request_fields(request, "playfair", "decrypt")
    note_history(request, input_length=len(text))
    result, positions, filtered = decrypt_playfair_with_padding(text, key)
    note_history(request, output_length=len(result))
    return PlayfairDecryptResponse(
        success=True,
        result=result,
        padding=PaddingInfo(count=len(positions), positions=positions, filtered=filtered),
    )


@vigenere_router.post(
    "/encrypt",
    response_model=TextCipherResponse,
    responses=_ERROR_RESPONSES,
    openapi_extra=_REQUEST_BODY,
)
async def encrypt_vigenere_text(request: Request) -> TextCipherResponse:
    return await _process_vigenere(request, "encrypt")


@vigenere_router.post(
    "/decrypt",
    response_model=TextCipherResponse,
    responses=_ERROR_RESPONSES,
    openapi_extra=_REQUEST_BODY,
)
async def decrypt_vigenere_text(request: Request) -> TextCipherResponse:
    return await _process_vigenere(request, "decrypt")


@playfair_router.post(
    "/encrypt",
    response_model=TextCipherResponse,
    responses=_ERROR_RESPONSES,
    openapi_extra=_REQUEST_BODY,
)
async def encrypt_playfair_text(request: Request) -> TextCipherResponse:
    return await _encrypt_playfair(request)


@playfair_router.post(
    "/decrypt",
    response_model=PlayfairDecryptResponse,
    responses=_ERROR_RESPONSES,
    openapi_extra=_REQUEST_BODY,
)
async def decrypt_playfair_text(request: Request) -> PlayfairDecryptResponse:
    return await _decrypt_playfair(request)
