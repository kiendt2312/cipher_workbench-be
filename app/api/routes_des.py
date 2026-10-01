"""Strict JSON endpoints for DES encryption, decryption and single-block tracing."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from app.api.des_schemas import (
    DECRYPT_FIELDS,
    ENCRYPT_FIELDS,
    TRACE_FIELDS,
    decode,
    map_core_error,
    validate_decrypt,
    validate_encrypt,
    validate_trace,
)
from app.api.history_recorder import note_history
from app.core import des
from app.errors import messages

router = APIRouter(prefix="/api/des", tags=["DES"])


class DesWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: Literal["W01", "W02", "W03"]
    message: str
    details: dict[str, int]


class DesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    success: Literal[True]
    result: str
    warnings: list[DesWarning]


class DesSubkey(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n: int
    shift: int
    c: str
    d: str
    k: str


class DesSboxLookup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    row: int
    col: int
    value: int


class DesRound(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    n: int
    subkey: int
    expansion: str
    xor_key: str = Field(alias="xorKey")
    sbox: list[DesSboxLookup]
    sbox_output: str = Field(alias="sboxOutput")
    f: str
    l: str  # noqa: E741 - name fixed by the public contract
    r: str


class DesTrace(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    operation: Literal["encrypt", "decrypt"]
    input: str
    key: str
    pc1: str
    subkeys: list[DesSubkey]
    ip: str
    l0: str
    r0: str
    rounds: list[DesRound]
    pre_output: str = Field(alias="preOutput")


class DesTraceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    success: Literal[True]
    result: str
    trace: DesTrace
    warnings: list[DesWarning]


_KEY = {"type": "string", "description": "16 ký tự hex (64 bit), bỏ qua khoảng trắng."}
_MODE = {"type": "string", "enum": ["ECB", "CBC"], "default": "ECB"}
_IV = {
    "type": ["string", "null"],
    "description": "16 ký tự hex, bắt buộc khi mode = CBC, bị bỏ qua khi ECB.",
}
_TEXT = {"type": "string", "description": "Tối đa 5 MiB (5.242.880 byte) khi mã hóa UTF-8."}
_FORMAT = {"type": "string", "enum": ["text", "hex"], "default": "text"}


def _request_body(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    schema = {
        "type": "object",
        "required": required,
        "properties": properties,
        "additionalProperties": False,
    }
    return {"requestBody": {"required": True, "content": {"application/json": {"schema": schema}}}}


_ERROR_SCHEMA = {
    "type": "object",
    "required": ["success", "message"],
    "properties": {
        "success": {"type": "boolean", "const": False},
        "message": {"type": "string"},
    },
    "additionalProperties": False,
}
_ERROR_CONTENT = {"content": {"application/json": {"schema": _ERROR_SCHEMA}}}
_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    413: {"description": messages.DES_TOO_LARGE, **_ERROR_CONTENT},
    422: {"description": "Dữ liệu DES không hợp lệ.", **_ERROR_CONTENT},
    500: {"description": messages.UNEXPECTED_FAILURE, **_ERROR_CONTENT},
}


def key_warnings(key: int) -> list[dict[str, Any]]:
    """W01/W02 for weak and semi-weak keys, compared without parity bits."""

    strength = des.key_strength(key)
    if strength == "weak":
        return [{"code": "W01", "message": messages.DES_WEAK_KEY, "details": {}}]
    if strength == "semi_weak":
        return [{"code": "W02", "message": messages.DES_SEMI_WEAK_KEY, "details": {}}]
    return []


def ecb_warnings(mode: des.Mode, ciphertext: bytes) -> list[dict[str, Any]]:
    """W03 when ECB produced at least two identical ciphertext blocks."""

    repeated = des.repeated_blocks(ciphertext) if mode == "ECB" else 0
    if not repeated:
        return []
    return [
        {
            "code": "W03",
            "message": messages.DES_ECB_REPEATED_BLOCKS,
            "details": {"repeatedBlocks": repeated},
        }
    ]


def encrypt_data(
    data: bytes, key: int, mode: des.Mode, iv: int | None, *, pad: bool
) -> tuple[str, list[dict[str, Any]]]:
    """Encrypt validated data and collect warnings; CPU-bound, run off the event loop."""

    ciphertext = des.encrypt_bytes(des.pkcs7_pad(data) if pad else data, key, mode, iv)
    return ciphertext.hex().upper(), key_warnings(key) + ecb_warnings(mode, ciphertext)


def decrypt_data(
    data: bytes, key: int, mode: des.Mode, iv: int | None, *, as_text: bool
) -> tuple[str, list[dict[str, Any]]]:
    """Decrypt validated ciphertext to text (unpad + UTF-8) or raw hex."""

    plain = des.decrypt_bytes(data, key, mode, iv)
    try:
        result = des.decode_utf8(des.pkcs7_unpad(plain)) if as_text else plain.hex().upper()
    except des.DesError as exc:
        raise map_core_error(exc) from None
    return result, key_warnings(key)


@router.post(
    "/encrypt",
    response_model=DesResponse,
    responses=_ERROR_RESPONSES,
    openapi_extra=_request_body(
        {"text": _TEXT, "key": _KEY, "inputFormat": _FORMAT, "mode": _MODE, "iv": _IV},
        ["text", "key"],
    ),
)
async def encrypt_des(request: Request) -> dict[str, Any]:
    payload = decode(await request.body(), request.headers.get("content-type"), ENCRYPT_FIELDS)
    validated = validate_encrypt(payload)
    note_history(request, input_length=len(validated.text))
    result, warnings = await run_in_threadpool(
        encrypt_data, validated.data, validated.key, validated.mode, validated.iv, pad=validated.pad
    )
    note_history(request, output_length=len(result))
    return {"success": True, "result": result, "warnings": warnings}


@router.post(
    "/decrypt",
    response_model=DesResponse,
    responses=_ERROR_RESPONSES,
    openapi_extra=_request_body(
        {"text": _TEXT, "key": _KEY, "outputFormat": _FORMAT, "mode": _MODE, "iv": _IV},
        ["text", "key"],
    ),
)
async def decrypt_des(request: Request) -> dict[str, Any]:
    payload = decode(await request.body(), request.headers.get("content-type"), DECRYPT_FIELDS)
    validated = validate_decrypt(payload)
    note_history(request, input_length=len(validated.text))
    result, warnings = await run_in_threadpool(
        decrypt_data,
        validated.data,
        validated.key,
        validated.mode,
        validated.iv,
        as_text=validated.output_format == "text",
    )
    note_history(request, output_length=len(result))
    return {"success": True, "result": result, "warnings": warnings}


@router.post(
    "/trace",
    response_model=DesTraceResponse,
    response_model_by_alias=True,
    responses=_ERROR_RESPONSES,
    openapi_extra=_request_body(
        {
            "block": {"type": "string", "description": "Đúng 16 ký tự hex (một khối)."},
            "key": _KEY,
            "operation": {"type": "string", "enum": ["encrypt", "decrypt"], "default": "encrypt"},
        },
        ["block", "key"],
    ),
)
async def trace_des(request: Request) -> dict[str, Any]:
    payload = decode(await request.body(), request.headers.get("content-type"), TRACE_FIELDS)
    validated = validate_trace(payload)
    trace = des.trace_block(validated.key, validated.block, validated.operation)
    result = trace.pop("result")
    return {
        "success": True,
        "result": result,
        "trace": trace,
        "warnings": key_warnings(validated.key),
    }
