"""Strict JSON endpoints for Hill text transforms and key operations."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from app.api.hill_schemas import decode, error, validate_key, validate_transform
from app.api.history_recorder import note_history
from app.api.schemas import PaddingInfo
from app.core import hill
from app.errors.exceptions import HillError as ApiHillError

router = APIRouter(prefix="/api/hill", tags=["Hill"])

Residue = Annotated[int, Field(ge=0, le=25)]
HillVector = Annotated[list[Residue], Field(min_length=2, max_length=4)]
HillMatrix = Annotated[list[HillVector], Field(min_length=2, max_length=4)]


class HillBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: HillVector
    output: HillVector


class HillWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: Literal["W01", "W02", "W03"]
    message: str
    details: dict[str, Any]


class HillKeyAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    matrix: HillMatrix
    m: int
    det: int
    gcd: int
    det_inverse: int = Field(alias="detInverse")
    adjugate: HillMatrix
    inverse: HillMatrix


class HillEncryptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    success: Literal[True]
    result: str
    blocks: list[HillBlock]
    key: HillKeyAnalysis
    warnings: list[HillWarning]


class HillDecryptResponse(HillEncryptResponse):
    padding: PaddingInfo


class HillKeyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    success: Literal[True]
    result: HillKeyAnalysis
    warnings: list[HillWarning]


_MATRIX_KEY = {
    "type": "array",
    "minItems": 2,
    "maxItems": 4,
    "items": {
        "type": "array",
        "minItems": 2,
        "maxItems": 4,
        "items": {"type": "integer"},
    },
}
_OPTIONS = {
    "type": "object",
    "properties": {
        "stripDiacritics": {"type": "boolean", "default": False},
        "padChar": {
            "type": "string",
            "pattern": "^[A-Z]$",
            "default": "X",
            "description": (
                "Mã hóa: chữ đệm cho khối cuối. Giải mã: chữ dùng để nhận diện tối đa "
                "m - 1 ký tự đệm ở cuối trong padding; không đổi result."
            ),
        },
    },
    "additionalProperties": False,
}
_KEY_VARIANTS = [
    {
        "type": "object",
        "required": ["key"],
        "properties": {"key": _MATRIX_KEY},
        "additionalProperties": False,
    },
    {
        "type": "object",
        "required": ["keyword", "m"],
        "properties": {
            "keyword": {"type": "string", "pattern": "^[A-Za-z]+$"},
            "m": {"type": "integer", "minimum": 2, "maximum": 4},
        },
        "additionalProperties": False,
    },
]
_TRANSFORM_SCHEMA = {
    "oneOf": [
        {
            **variant,
            "required": ["text", *variant["required"]],
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Tối đa 5 MiB (5.242.880 byte) khi mã hóa UTF-8.",
                },
                **variant["properties"],
                "options": _OPTIONS,
            },
        }
        for variant in _KEY_VARIANTS
    ],
    "description": "Hill dùng vector hàng y = x·K mod 26.",
}
_ANALYZE_SCHEMA = {"oneOf": _KEY_VARIANTS}
_ERROR_SCHEMA = {
    "type": "object",
    "required": ["success", "message", "code", "details"],
    "properties": {
        "success": {"type": "boolean", "const": False},
        "message": {"type": "string"},
        "code": {"type": "string", "pattern": "^E(?:0[1-6]|0[8-9]|1[01])$"},
        "details": {"type": "object"},
    },
    "additionalProperties": False,
}
_COMMON_ERROR = {"content": {"application/json": {"schema": _ERROR_SCHEMA}}}
_ERROR_RESPONSES = {
    413: {"description": "Text Hill vượt giới hạn 5 MiB.", **_COMMON_ERROR},
    422: {"description": "Dữ liệu Hill không hợp lệ.", **_COMMON_ERROR},
    500: {
        "description": "Lỗi hệ thống; response dùng envelope lỗi chung.",
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["success", "message"],
                    "properties": {
                        "success": {"type": "boolean", "const": False},
                        "message": {"type": "string"},
                    },
                }
            }
        },
    },
}


def _map_core_error(exc: hill.HillError) -> ApiHillError:
    message = str(exc)
    if exc.code == "E02":
        message = "Văn bản không có chữ cái nào để mã hóa. Hill chỉ xử lý A\u2013Z."
    elif exc.code == "E04":
        message = (
            f"Khóa không khả nghịch: det K mod 26 = {exc.details['det']}, "
            f"chia hết cho {exc.details['divisor']}. Hãy đổi khóa."
        )
    return ApiHillError(413 if exc.code == "E06" else 422, exc.code, message, exc.details)


def _analyze(matrix: list[list[int]]) -> dict[str, Any]:
    try:
        return hill.analyze_key(matrix)
    except hill.HillError as exc:
        raise _map_core_error(exc) from exc


async def _transform(request: Request, operation: Literal["encrypt", "decrypt"]) -> dict[str, Any]:
    payload = decode(
        await request.body(),
        request.headers.get("content-type"),
        {"text", "key", "keyword", "m", "options"},
    )
    validated = validate_transform(payload)
    note_history(request, input_length=len(validated.text or ""))
    try:
        transform = hill.encrypt if operation == "encrypt" else hill.decrypt
        result = transform(
            validated.text or "",
            validated.matrix,
            options=validated.options,
        )
    except hill.HillError as exc:
        raise _map_core_error(exc) from exc
    note_history(request, output_length=len(result["result"]))
    return {"success": True, **result}


@router.post(
    "/encrypt",
    response_model=HillEncryptResponse,
    responses=_ERROR_RESPONSES,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": _TRANSFORM_SCHEMA}},
        }
    },
)
async def encrypt_hill(request: Request) -> dict[str, Any]:
    return await _transform(request, "encrypt")


@router.post(
    "/decrypt",
    response_model=HillDecryptResponse,
    responses=_ERROR_RESPONSES,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": _TRANSFORM_SCHEMA}},
        }
    },
)
async def decrypt_hill(request: Request) -> dict[str, Any]:
    return await _transform(request, "decrypt")


@router.post(
    "/key/analyze",
    response_model=HillKeyResponse,
    responses={422: _ERROR_RESPONSES[422], 500: _ERROR_RESPONSES[500]},
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": _ANALYZE_SCHEMA}},
        }
    },
)
async def analyze_hill_key(request: Request) -> dict[str, Any]:
    payload = decode(
        await request.body(), request.headers.get("content-type"), {"key", "keyword", "m"}
    )
    analysis = _analyze(validate_key(payload))
    return {"success": True, "result": analysis, "warnings": hill.warnings_for_key(analysis)}


def _random_m(request: Request) -> int:
    values = request.query_params.getlist("m")
    if len(values) != 1 or values[0] not in {"2", "3", "4"}:
        details: dict[str, object] = {"min": 2, "max": 4}
        if len(values) == 1 and values[0].isascii() and values[0].isdigit():
            details["m"] = int(values[0])
        raise error("E08", details=details)
    return int(values[0])


@router.get(
    "/key/random",
    response_model=HillKeyResponse,
    responses={422: _ERROR_RESPONSES[422], 500: _ERROR_RESPONSES[500]},
    openapi_extra={
        "parameters": [
            {
                "name": "m",
                "in": "query",
                "required": True,
                "description": "Cấp ma trận Hill, xuất hiện đúng một lần.",
                "schema": {"type": "integer", "minimum": 2, "maximum": 4},
            }
        ]
    },
)
async def random_hill_key(request: Request) -> dict[str, Any]:
    result = hill.random_key_result(_random_m(request))
    return {"success": True, **result}
