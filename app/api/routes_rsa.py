"""Four strict, stateless textbook-RSA educational endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.history_recorder import note_history
from app.api.request_size_guard import MultipartCompletionGuard
from app.api.rsa_schemas import (
    FileEncryptRequest,
    ManualKeyResponse,
    NumberDecryptRequest,
    NumberDecryptResponse,
    NumberEncryptRequest,
    NumberEncryptResponse,
    RandomKeyResponse,
    RsaErrorResponse,
    TextDecryptRequest,
    TextDecryptResponse,
    TextEncryptRequest,
    TextEncryptResponse,
    decode_json,
    error,
    map_core_error,
    parse_form_trace,
    serialize_key,
    serialize_trace,
    validate_decrypt,
    validate_encrypt,
    validate_file_form,
    validate_manual_key,
    validate_random_key,
)
from app.core import rsa
from app.errors import messages

router = APIRouter(prefix="/api/rsa", tags=["RSA (giáo dục)"])
WARNING = (
    "Textbook RSA 16-128 bit chỉ dùng để học thuật toán; không có OAEP, không an toàn "
    "cho dữ liệu thật và không xác thực khóa hay metadata."
)

_DECIMAL = {"type": "string", "pattern": "^[0-9]+$", "maxLength": 128}
_CONTROL = {"type": "integer"}
_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": RsaErrorResponse, "description": description}
    for status, description in (
        (413, messages.RSA_REQUEST_TOO_LARGE),
        (415, messages.RSA_UNSUPPORTED_MEDIA_TYPE),
        (422, "Dữ liệu RSA không hợp lệ."),
        (500, messages.RSA_INTERNAL_ERROR),
    )
}


def _object(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _json_body(schema: dict[str, Any], example: dict[str, Any]) -> dict[str, Any]:
    return {
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": schema, "example": example}},
        }
    }


_MANUAL_BODY = _json_body(
    _object({"p": _DECIMAL, "q": _DECIMAL, "e": _DECIMAL}, ["p", "q", "e"]),
    {"p": "17", "q": "11", "e": "7"},
)
_MANUAL_BODY["requestBody"]["content"]["application/json"]["examples"] = {
    "TC-01": {"value": {"p": "17", "q": "11", "e": "7"}},
    "TC-03": {"value": {"p": "61", "q": "53", "e": "17"}},
}
_MANUAL_BODY["requestBody"]["content"]["application/json"].pop("example")
_RANDOM_BODY = _json_body(
    _object({"bits": {"type": "integer", "enum": [16, 32, 64, 128]}}, ["bits"]),
    {"bits": 128},
)
_ENCRYPT_NUMBER = _object(
    {
        "e": _DECIMAL,
        "n": _DECIMAL,
        "inputType": {"const": "number"},
        "data": _DECIMAL,
        "traceBlockIndex": _CONTROL,
    },
    ["e", "n", "inputType", "data"],
)
_ENCRYPT_TEXT = _object(
    {
        "e": _DECIMAL,
        "n": _DECIMAL,
        "inputType": {"const": "text"},
        "mode": {"type": "string", "enum": ["char", "block"]},
        "data": {"type": "string", "minLength": 1, "maxLength": 10_000},
        "traceBlockIndex": _CONTROL,
    },
    ["e", "n", "inputType", "mode", "data"],
)
_MULTIPART = _object(
    {
        "file": {"type": "string", "format": "binary"},
        "e": _DECIMAL,
        "n": _DECIMAL,
        "mode": {"type": "string", "enum": ["char", "block"]},
        "traceBlockIndex": {"type": "string", "pattern": "^(0|[1-9][0-9]*)$"},
    },
    ["file", "e", "n", "mode"],
)
_ENCRYPT_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {"oneOf": [_ENCRYPT_NUMBER, _ENCRYPT_TEXT]},
                "example": {"e": "17", "n": "3233", "inputType": "number", "data": "65"},
            },
            "multipart/form-data": {"schema": _MULTIPART},
        },
    }
}
_DECRYPT_NUMBER = _object(
    {
        "d": _DECIMAL,
        "n": _DECIMAL,
        "inputType": {"const": "number"},
        "cipher": {"type": "array", "minItems": 1, "maxItems": 1, "items": _DECIMAL},
        "traceBlockIndex": _CONTROL,
    },
    ["d", "n", "inputType", "cipher"],
)
_DECRYPT_CHAR = _object(
    {
        "d": _DECIMAL,
        "n": _DECIMAL,
        "inputType": {"const": "text"},
        "mode": {"const": "char"},
        "cipher": {"type": "array", "minItems": 1, "maxItems": 10_000, "items": _DECIMAL},
        "traceBlockIndex": _CONTROL,
    },
    ["d", "n", "inputType", "mode", "cipher"],
)
_DECRYPT_BLOCK = _object(
    {
        "d": _DECIMAL,
        "n": _DECIMAL,
        "inputType": {"const": "text"},
        "mode": {"const": "block"},
        "cipher": {"type": "array", "minItems": 1, "maxItems": 40_000, "items": _DECIMAL},
        "originalUtf8ByteLength": {"type": "integer", "minimum": 1, "maximum": 40_000},
        "traceBlockIndex": _CONTROL,
    },
    ["d", "n", "inputType", "mode", "cipher", "originalUtf8ByteLength"],
)
_DECRYPT_BODY = _json_body(
    {"oneOf": [_DECRYPT_NUMBER, _DECRYPT_CHAR, _DECRYPT_BLOCK]},
    {"d": "23", "n": "187", "inputType": "number", "cipher": ["11"]},
)


def _core_call(function: Any, *args: Any, default_field: str | None = None, **kwargs: Any) -> Any:
    try:
        return function(*args, **kwargs)
    except rsa.RsaCoreError as exc:
        raise map_core_error(exc, default_field) from None


def _encrypt(validated: NumberEncryptRequest | TextEncryptRequest) -> dict[str, Any]:
    if isinstance(validated, NumberEncryptRequest):
        if validated.trace_index not in (None, 0):
            raise error(
                422, "TRACE_INDEX_OUT_OF_RANGE", messages.RSA_TRACE_INDEX, "traceBlockIndex"
            )
        result = _core_call(
            rsa.transform_number,
            validated.data,
            validated.e,
            validated.n,
            "encrypt",
            trace=validated.trace_index is not None,
            default_field="data",
        )
        return {
            "success": True,
            "inputType": "number",
            "blocks": [str(value) for value in result.blocks],
            "cipher": [str(value) for value in result.values],
            "blockSize": None,
            "trace": serialize_trace(result.trace),
        }
    function = (
        rsa.transform_char_encrypt if validated.mode == "char" else rsa.transform_block_encrypt
    )
    result = _core_call(
        function,
        validated.data,
        validated.e,
        validated.n,
        trace_index=validated.trace_index,
        default_field="data",
    )
    return {
        "success": True,
        "inputType": "text",
        "mode": validated.mode,
        "blocks": [str(value) for value in result.blocks],
        "cipher": [str(value) for value in result.values],
        "blockSize": result.block_size,
        "originalUtf8ByteLength": result.original_utf8_byte_length,
        "trace": serialize_trace(result.trace),
    }


def _decrypt(validated: NumberDecryptRequest | TextDecryptRequest) -> dict[str, Any]:
    if isinstance(validated, NumberDecryptRequest):
        if validated.trace_index not in (None, 0):
            raise error(
                422, "TRACE_INDEX_OUT_OF_RANGE", messages.RSA_TRACE_INDEX, "traceBlockIndex"
            )
        result = _core_call(
            rsa.transform_number,
            validated.cipher[0],
            validated.d,
            validated.n,
            "decrypt",
            trace=validated.trace_index is not None,
            default_field="cipher[0]",
        )
        return {
            "success": True,
            "inputType": "number",
            "blocks": [str(value) for value in result.blocks],
            "plaintext": str(result.blocks[0]),
            "blockSize": None,
            "trace": serialize_trace(result.trace),
        }
    if validated.mode == "char":
        result, plaintext = _core_call(
            rsa.transform_char_decrypt,
            validated.cipher,
            validated.d,
            validated.n,
            trace_index=validated.trace_index,
            default_field="cipher",
        )
    else:
        assert validated.original_utf8_byte_length is not None
        result, plaintext = _core_call(
            rsa.transform_block_decrypt,
            validated.cipher,
            validated.d,
            validated.n,
            validated.original_utf8_byte_length,
            trace_index=validated.trace_index,
            default_field="cipher",
        )
    return {
        "success": True,
        "inputType": "text",
        "mode": validated.mode,
        "blocks": [str(value) for value in result.blocks],
        "plaintext": plaintext,
        "blockSize": result.block_size,
        "originalUtf8ByteLength": result.original_utf8_byte_length,
        "trace": serialize_trace(result.trace),
    }


@router.post(
    "/keys",
    response_model=ManualKeyResponse,
    response_model_by_alias=True,
    responses=_ERROR_RESPONSES,
    description=WARNING,
    openapi_extra=_MANUAL_BODY,
)
async def create_manual_key(request: Request) -> dict[str, Any]:
    payload = decode_json(await request.body(), request.headers.get("content-type"))
    p, q, e = validate_manual_key(payload)
    material = await run_in_threadpool(_core_call, rsa.generate_manual_key, p, q, e)
    return serialize_key(material, include_primes=False)


@router.post(
    "/keys/random",
    response_model=RandomKeyResponse,
    response_model_by_alias=True,
    responses=_ERROR_RESPONSES,
    description=WARNING,
    openapi_extra=_RANDOM_BODY,
)
async def create_random_key(request: Request) -> dict[str, Any]:
    payload = decode_json(await request.body(), request.headers.get("content-type"))
    bits = validate_random_key(payload)
    material = await run_in_threadpool(_core_call, rsa.generate_random_key, bits)
    return serialize_key(material, include_primes=True)


async def _multipart_encrypt(request: Request) -> dict[str, Any]:
    form = await request.form(max_files=10, max_fields=10, max_part_size=1024)
    if request.scope.get(MultipartCompletionGuard.SCOPE_KEY) is not True:
        raise StarletteHTTPException(status_code=400, detail="Malformed multipart body")
    validated: FileEncryptRequest = validate_file_form(form)
    filename = validated.file.filename
    if not filename or not filename.lower().endswith(".txt"):
        raise error(415, "FILE_INVALID", messages.RSA_FILE_EXTENSION, "file")
    try:
        raw = await validated.file.read(1_000_001)
    except Exception as exc:
        raise error(500, "FILE_READ_FAILED", messages.RSA_FILE_READ_FAILED, "file") from exc
    if len(raw) > 1_000_000:
        raise error(413, "FILE_INVALID", messages.RSA_FILE_TOO_LARGE, "file")
    if not raw:
        raise error(422, "EMPTY_INPUT", messages.RSA_EMPTY_INPUT, "file")
    note_history(request, input_length=len(raw))
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise error(415, "FILE_INVALID", messages.RSA_FILE_ENCODING, "file") from exc
    if len(text) > rsa.MAX_TEXT_CODEPOINTS:
        raise error(422, "INPUT_TOO_LARGE", messages.RSA_TEXT_TOO_LARGE, "file")
    try:
        rsa.validate_transform_key(validated.e, validated.n, "encrypt")
        if validated.mode == "char":
            for codepoint in map(ord, text):
                if codepoint >= validated.n:
                    raise rsa.RsaCoreError("P_TOO_LARGE", value=codepoint, n=validated.n)
        else:
            rsa.pack_block_text(text, validated.n)
    except rsa.RsaCoreError as exc:
        raise map_core_error(exc, "file") from None
    trace_index = parse_form_trace(validated.trace_index_raw)
    value = TextEncryptRequest(validated.e, validated.n, validated.mode, text, trace_index)
    return await run_in_threadpool(_encrypt, value)


@router.post(
    "/encrypt",
    response_model=NumberEncryptResponse | TextEncryptResponse,
    response_model_by_alias=True,
    responses=_ERROR_RESPONSES,
    description=WARNING,
    openapi_extra=_ENCRYPT_BODY,
)
async def encrypt(request: Request) -> dict[str, Any]:
    media_type = request.headers.get("content-type", "").partition(";")[0].strip().lower()
    if media_type == "multipart/form-data":
        return await _multipart_encrypt(request)
    if media_type != "application/json":
        raise error(415, "UNSUPPORTED_MEDIA_TYPE", messages.RSA_UNSUPPORTED_MEDIA_TYPE)
    payload = decode_json(await request.body(), request.headers.get("content-type"))
    validated = validate_encrypt(payload)
    if isinstance(validated, TextEncryptRequest):
        note_history(request, input_length=len(validated.data))
    return await run_in_threadpool(_encrypt, validated)


@router.post(
    "/decrypt",
    response_model=NumberDecryptResponse | TextDecryptResponse,
    response_model_by_alias=True,
    responses=_ERROR_RESPONSES,
    description=WARNING,
    openapi_extra=_DECRYPT_BODY,
)
async def decrypt(request: Request) -> dict[str, Any]:
    payload = decode_json(await request.body(), request.headers.get("content-type"))
    validated = validate_decrypt(payload)
    result = await run_in_threadpool(_decrypt, validated)
    if isinstance(validated, TextDecryptRequest):
        note_history(request, output_length=len(result["plaintext"]))
    return result
