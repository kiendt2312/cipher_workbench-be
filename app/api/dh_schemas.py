"""Strict transport parsing and response models for educational Diffie-Hellman."""

from __future__ import annotations

import json
import re
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.errors import messages
from app.errors.exceptions import DhError

MISSING: Final = object()
DECIMAL = re.compile(r"0|[1-9][0-9]*", re.ASCII)


class JsonIntegerToken(str):
    """Raw JSON integer token retained for strict control validation."""


class JsonFloatToken(str):
    """Raw JSON float token, never accepted as an integer control."""


class ExactModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ParamsRequest(ExactModel):
    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"examples": [{"q": "23", "alpha": "5"}]}
    )
    q: str
    alpha: str = None  # type: ignore[assignment]


class RandomParamsRequest(ExactModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"bits": 128}]})
    bits: Literal[16, 32, 64, 128]


class KeyPairRequest(ExactModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        json_schema_extra={"examples": [{"q": "353", "alpha": "3", "privateKey": "97"}]},
    )
    q: str
    alpha: str
    private_key: str = Field(default=None, alias="privateKey")  # type: ignore[assignment]


class SharedSecretRequest(ExactModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        json_schema_extra={"examples": [{"q": "353", "privateKey": "97", "otherPublicKey": "248"}]},
    )
    q: str
    private_key: str = Field(alias="privateKey")
    other_public_key: str = Field(alias="otherPublicKey")


class ExchangeRequest(ExactModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        json_schema_extra={
            "examples": [{"q": "353", "alpha": "3", "privateKeyA": "97", "privateKeyB": "233"}]
        },
    )
    q: str
    alpha: str
    private_key_a: str = Field(default=None, alias="privateKeyA")  # type: ignore[assignment]
    private_key_b: str = Field(default=None, alias="privateKeyB")  # type: ignore[assignment]


class DhCaesarJsonRequest(SharedSecretRequest):
    action: Literal["encrypt", "decrypt"]
    data: str


class DhErrorResponse(ExactModel):
    success: Literal[False]
    code: str
    message: str
    field: str | None


class WarningResponse(ExactModel):
    code: str
    message: str


class ModPowStepResponse(ExactModel):
    index: int
    bit: Literal[0, 1]
    exponent_prefix: str = Field(alias="exponentPrefix")
    squared: str
    multiplied: str | None
    result: str


class PrimitiveRootCheckResponse(ExactModel):
    factor: str
    exponent: str
    result: str
    passes: bool


class ParamsResponse(ExactModel):
    success: Literal[True]
    q: str
    alpha: str | None
    factors: list[str]
    primitive_root_checks: list[PrimitiveRootCheckResponse] = Field(alias="primitiveRootChecks")
    suggested_alpha: str | None = Field(alias="suggestedAlpha")


class RandomParamsResponse(ParamsResponse):
    p: str


class KeyPairResponse(ExactModel):
    success: Literal[True]
    private_key: str = Field(alias="privateKey")
    public_key: str = Field(alias="publicKey")
    steps: list[ModPowStepResponse]


class SharedSecretResponse(ExactModel):
    success: Literal[True]
    shared_key: str = Field(alias="sharedKey")
    steps: list[ModPowStepResponse]


class ExchangeStepsResponse(ExactModel):
    public_key_a: list[ModPowStepResponse] = Field(alias="publicKeyA")
    public_key_b: list[ModPowStepResponse] = Field(alias="publicKeyB")
    shared_key_a: list[ModPowStepResponse] = Field(alias="sharedKeyA")
    shared_key_b: list[ModPowStepResponse] = Field(alias="sharedKeyB")


class ExchangeResponse(ExactModel):
    success: Literal[True]
    private_key_a: str = Field(alias="privateKeyA")
    private_key_b: str = Field(alias="privateKeyB")
    public_key_a: str = Field(alias="publicKeyA")
    public_key_b: str = Field(alias="publicKeyB")
    shared_key_a: str = Field(alias="sharedKeyA")
    shared_key_b: str = Field(alias="sharedKeyB")
    match: bool
    steps: ExchangeStepsResponse
    warning: WarningResponse


class DhCaesarResponse(ExactModel):
    success: Literal[True]
    shared_key: str = Field(alias="sharedKey")
    shift: str
    result: str
    warning: WarningResponse | None = None


def error(status: int, code: str, message: str, field: str | None = None) -> DhError:
    return DhError(status, code, message, field)


def _invalid(field: str | None = None) -> DhError:
    return error(422, "INVALID_REQUEST", messages.DH_INVALID_REQUEST, field)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for key, value in pairs:
        if key in decoded:
            raise _invalid(key)
        decoded[key] = value
    return decoded


def _reject_constant(value: str) -> None:
    raise json.JSONDecodeError("Non-standard JSON constant", value, 0)


def decode_json(raw: bytes, content_type: str | None) -> dict[str, Any]:
    media_type = content_type.partition(";")[0].strip().lower() if content_type else ""
    if media_type != "application/json":
        raise error(415, "UNSUPPORTED_MEDIA_TYPE", messages.DH_UNSUPPORTED_MEDIA_TYPE)
    try:
        decoded = json.loads(
            raw.decode("utf-8-sig", errors="strict"),
            parse_int=JsonIntegerToken,
            parse_float=JsonFloatToken,
            parse_constant=_reject_constant,
            object_pairs_hook=_strict_object,
        )
    except DhError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
        raise _invalid() from exc
    if type(decoded) is not dict:
        raise _invalid()
    return decoded


def fields(payload: dict[str, Any], *, allowed: tuple[str, ...], required: tuple[str, ...]) -> None:
    allowed_set = frozenset(allowed)
    for name in payload:
        if name not in allowed_set:
            raise _invalid(name)
    for name in required:
        if name not in payload:
            raise _invalid(name)


def decimal(raw: Any, field: str, *, manual_q: bool = False) -> int:
    if type(raw) is not str or DECIMAL.fullmatch(raw) is None:
        raise error(422, "NOT_INTEGER", messages.DH_NOT_INTEGER, field)
    value = int(raw)
    if field == "q" and value.bit_length() > 128:
        message = messages.DH_Q_OUT_OF_RANGE_MANUAL if manual_q else messages.DH_Q_OUT_OF_RANGE_128
        raise error(422, "Q_OUT_OF_RANGE", message, field)
    return value


def bits(raw: Any) -> int:
    if type(raw) is not JsonIntegerToken:
        raise error(422, "BITS_INVALID", messages.DH_BITS_INVALID, "bits")
    value = int(raw)
    if value not in (16, 32, 64, 128):
        raise error(422, "BITS_INVALID", messages.DH_BITS_INVALID, "bits")
    return value


def action(raw: Any) -> Literal["encrypt", "decrypt"]:
    if raw not in ("encrypt", "decrypt"):
        raise error(422, "INVALID_ACTION", messages.DH_INVALID_ACTION, "action")
    return raw


def serialize_steps(steps: Any) -> list[dict[str, Any]]:
    return [
        {
            "index": step.index,
            "bit": step.bit,
            "exponentPrefix": str(step.exponent_prefix),
            "squared": str(step.squared),
            "multiplied": None if step.multiplied is None else str(step.multiplied),
            "result": str(step.result),
        }
        for step in steps
    ]


def serialize_checks(checks: Any) -> list[dict[str, Any]]:
    return [
        {
            "factor": str(check.factor),
            "exponent": str(check.exponent),
            "result": str(check.result),
            "passes": check.passes,
        }
        for check in checks
    ]


def json_request_schema(model: type[BaseModel]) -> dict[str, Any]:
    return {
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": model.model_json_schema(by_alias=True)}},
        }
    }


def caesar_request_schema() -> dict[str, Any]:
    multipart_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["file", "q", "privateKey", "otherPublicKey", "action"],
        "properties": {
            "file": {"type": "string", "format": "binary"},
            "q": {"type": "string"},
            "privateKey": {"type": "string"},
            "otherPublicKey": {"type": "string"},
            "action": {"type": "string", "enum": ["encrypt", "decrypt"]},
        },
    }
    return {
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": DhCaesarJsonRequest.model_json_schema(by_alias=True)
                },
                "multipart/form-data": {"schema": multipart_schema},
            },
        }
    }
