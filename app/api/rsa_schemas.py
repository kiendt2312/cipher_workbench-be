"""Strict decoding, ordered validation and exact response models for RSA."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field
from starlette.datastructures import FormData, UploadFile

from app.core import rsa
from app.errors import messages
from app.errors.exceptions import RsaError

MISSING: Final = object()
DECIMAL = re.compile(r"[0-9]+", re.ASCII)
FORM_INTEGER = re.compile(r"0|[1-9][0-9]*", re.ASCII)


class JsonIntegerToken(str):
    """A raw JSON integer lexeme retained until bounded validation."""


class JsonFloatToken(str):
    """A raw JSON float lexeme that must never be accepted as a control integer."""


class ExactModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RsaErrorResponse(ExactModel):
    success: Literal[False]
    code: str
    message: str
    field: str | None


class EuclidStep(ExactModel):
    index: int
    q: str | None
    r: str
    t: str


class PublicKey(ExactModel):
    e: str
    n: str


class PrivateKey(ExactModel):
    d: str
    n: str


class ManualKeyResponse(ExactModel):
    success: Literal[True]
    n: str
    phi: str
    e: str
    d: str
    public_key: PublicKey = Field(alias="publicKey")
    private_key: PrivateKey = Field(alias="privateKey")
    egcd_steps: list[EuclidStep] = Field(alias="egcdSteps")


class RandomKeyResponse(ManualKeyResponse):
    p: str
    q: str


class ModPowStep(ExactModel):
    i: int
    bit: Literal[0, 1]
    base: str
    before: str
    result: str


class TransformTrace(ExactModel):
    operation: Literal["encrypt", "decrypt"]
    block_index: int = Field(alias="blockIndex")
    input: str
    exponent: str
    modulus: str
    result: str
    steps: list[ModPowStep]


class NumberEncryptResponse(ExactModel):
    success: Literal[True]
    input_type: Literal["number"] = Field(alias="inputType")
    blocks: list[str]
    cipher: list[str]
    block_size: None = Field(alias="blockSize")
    trace: TransformTrace | None


class TextEncryptResponse(ExactModel):
    success: Literal[True]
    input_type: Literal["text"] = Field(alias="inputType")
    mode: Literal["char", "block"]
    blocks: list[str]
    cipher: list[str]
    block_size: int = Field(alias="blockSize")
    original_utf8_byte_length: int = Field(alias="originalUtf8ByteLength")
    trace: TransformTrace | None


class NumberDecryptResponse(ExactModel):
    success: Literal[True]
    input_type: Literal["number"] = Field(alias="inputType")
    blocks: list[str]
    plaintext: str
    block_size: None = Field(alias="blockSize")
    trace: TransformTrace | None


class TextDecryptResponse(ExactModel):
    success: Literal[True]
    input_type: Literal["text"] = Field(alias="inputType")
    mode: Literal["char", "block"]
    blocks: list[str]
    plaintext: str
    block_size: int = Field(alias="blockSize")
    original_utf8_byte_length: int = Field(alias="originalUtf8ByteLength")
    trace: TransformTrace | None


@dataclass(frozen=True)
class NumberEncryptRequest:
    e: int
    n: int
    data: int
    trace_index: int | None


@dataclass(frozen=True)
class TextEncryptRequest:
    e: int
    n: int
    mode: Literal["char", "block"]
    data: str
    trace_index: int | None


@dataclass(frozen=True)
class NumberDecryptRequest:
    d: int
    n: int
    cipher: tuple[int, ...]
    trace_index: int | None


@dataclass(frozen=True)
class TextDecryptRequest:
    d: int
    n: int
    mode: Literal["char", "block"]
    cipher: tuple[int, ...]
    original_utf8_byte_length: int | None
    trace_index: int | None


@dataclass(frozen=True)
class FileEncryptRequest:
    file: UploadFile
    e: int
    n: int
    mode: Literal["char", "block"]
    trace_index_raw: str | None


def error(status: int, code: str, message: str, field: str | None = None) -> RsaError:
    return RsaError(status, code, message, field)


def _invalid(field: str | None = None) -> RsaError:
    return error(422, "INVALID_REQUEST", messages.RSA_INVALID_REQUEST, field)


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
        raise error(415, "UNSUPPORTED_MEDIA_TYPE", messages.RSA_UNSUPPORTED_MEDIA_TYPE)
    try:
        text = raw.decode("utf-8-sig", errors="strict")
        decoded = json.loads(
            text,
            parse_int=JsonIntegerToken,
            parse_float=JsonFloatToken,
            parse_constant=_reject_constant,
            object_pairs_hook=_strict_object,
        )
    except RsaError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
        raise _invalid() from exc
    if type(decoded) is not dict:
        raise _invalid()
    return decoded


def _fields(
    payload: dict[str, Any], *, allowed: tuple[str, ...], required: tuple[str, ...]
) -> None:
    allowed_set = frozenset(allowed)
    for name in payload:
        if name not in allowed_set:
            raise _invalid(name)
    for name in required:
        if name not in payload:
            raise _invalid(name)


def parse_decimal(raw: Any, field: str) -> int:
    if type(raw) is not str or DECIMAL.fullmatch(raw) is None:
        raise error(422, "NOT_INTEGER", messages.RSA_NOT_INTEGER, field)
    if len(raw) > 128:
        raise error(422, "NUMBER_TOO_LARGE", messages.RSA_NUMBER_TOO_LARGE, field)
    value = int(raw)
    if value > rsa.MAX_OPERAND:
        raise error(422, "NUMBER_TOO_LARGE", messages.RSA_NUMBER_TOO_LARGE, field)
    return value


def _control(
    raw: Any,
    field: str,
    code: Literal["INVALID_BITS", "INVALID_LENGTH_METADATA", "TRACE_INDEX_OUT_OF_RANGE"],
) -> int:
    message = {
        "INVALID_BITS": messages.RSA_INVALID_BITS,
        "INVALID_LENGTH_METADATA": messages.RSA_INVALID_LENGTH_METADATA,
        "TRACE_INDEX_OUT_OF_RANGE": messages.RSA_TRACE_INDEX,
    }[code]
    if type(raw) is not JsonIntegerToken:
        raise error(422, code, message, field)
    unsigned = raw[1:] if raw.startswith("-") else raw
    if len(unsigned) > 10 or raw.startswith("-"):
        raise error(422, code, message, field)
    return int(raw)


def _trace_index(payload: dict[str, Any]) -> int | None:
    raw = payload.get("traceBlockIndex", MISSING)
    if raw is MISSING:
        return None
    return _control(raw, "traceBlockIndex", "TRACE_INDEX_OUT_OF_RANGE")


def validate_manual_key(payload: dict[str, Any]) -> tuple[int, int, int]:
    _fields(payload, allowed=("p", "q", "e"), required=("p", "q", "e"))
    return (
        parse_decimal(payload["p"], "p"),
        parse_decimal(payload["q"], "q"),
        parse_decimal(payload["e"], "e"),
    )


def validate_random_key(payload: dict[str, Any]) -> int:
    _fields(payload, allowed=("bits",), required=("bits",))
    bits = _control(payload["bits"], "bits", "INVALID_BITS")
    if bits not in rsa.ALLOWED_KEY_BITS:
        raise error(422, "INVALID_BITS", messages.RSA_INVALID_BITS, "bits")
    return bits


def _input_type(payload: dict[str, Any]) -> Literal["number", "text"]:
    value = payload.get("inputType", MISSING)
    if value not in ("number", "text"):
        raise _invalid("inputType")
    return value


def _mode(payload: dict[str, Any]) -> Literal["char", "block"]:
    value = payload.get("mode", MISSING)
    if value not in ("char", "block"):
        raise _invalid("mode")
    return value


def _text_data(payload: dict[str, Any], field: str = "data") -> str:
    value = payload.get(field, MISSING)
    if type(value) is not str:
        raise _invalid(field)
    if value == "":
        raise error(422, "EMPTY_INPUT", messages.RSA_EMPTY_INPUT, field)
    if len(value) > rsa.MAX_TEXT_CODEPOINTS:
        raise error(422, "INPUT_TOO_LARGE", messages.RSA_TEXT_TOO_LARGE, field)
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise error(422, "DECODE_FAILED", messages.RSA_DECODE_FAILED, field) from exc
    return value


def _cipher_values(payload: dict[str, Any], limit: int) -> tuple[int, ...]:
    value = payload.get("cipher", MISSING)
    if type(value) is not list:
        raise _invalid("cipher")
    if not value:
        raise error(422, "EMPTY_INPUT", messages.RSA_EMPTY_INPUT, "cipher")
    if len(value) > limit:
        raise error(422, "INPUT_TOO_LARGE", messages.RSA_COLLECTION_TOO_LARGE, "cipher")
    return tuple(parse_decimal(item, f"cipher[{index}]") for index, item in enumerate(value))


def validate_encrypt(payload: dict[str, Any]) -> NumberEncryptRequest | TextEncryptRequest:
    input_type = _input_type(payload)
    if input_type == "number":
        _fields(
            payload,
            allowed=("e", "n", "inputType", "data", "traceBlockIndex"),
            required=("e", "n", "inputType", "data"),
        )
        e = parse_decimal(payload["e"], "e")
        n = parse_decimal(payload["n"], "n")
        data = parse_decimal(payload["data"], "data")
        try:
            rsa.validate_transform_key(e, n, "encrypt")
            if data >= n:
                raise rsa.RsaCoreError("P_TOO_LARGE", value=data, n=n)
        except rsa.RsaCoreError as exc:
            raise map_core_error(exc, "data") from None
        return NumberEncryptRequest(e, n, data, _trace_index(payload))

    mode = _mode(payload)
    _fields(
        payload,
        allowed=("e", "n", "inputType", "mode", "data", "traceBlockIndex"),
        required=("e", "n", "inputType", "mode", "data"),
    )
    data = _text_data(payload)
    e = parse_decimal(payload["e"], "e")
    n = parse_decimal(payload["n"], "n")
    try:
        rsa.validate_transform_key(e, n, "encrypt")
        if mode == "char":
            for value in map(ord, data):
                if value >= n:
                    raise rsa.RsaCoreError("P_TOO_LARGE", value=value, n=n)
        else:
            rsa.pack_block_text(data, n)
    except rsa.RsaCoreError as exc:
        raise map_core_error(exc, "data") from None
    return TextEncryptRequest(e, n, mode, data, _trace_index(payload))


def validate_decrypt(payload: dict[str, Any]) -> NumberDecryptRequest | TextDecryptRequest:
    input_type = _input_type(payload)
    if input_type == "number":
        _fields(
            payload,
            allowed=("d", "n", "inputType", "cipher", "traceBlockIndex"),
            required=("d", "n", "inputType", "cipher"),
        )
        raw_cipher = payload.get("cipher")
        if type(raw_cipher) is not list or len(raw_cipher) != 1:
            raise _invalid("cipher")
        d = parse_decimal(payload["d"], "d")
        n = parse_decimal(payload["n"], "n")
        cipher = (parse_decimal(raw_cipher[0], "cipher[0]"),)
        try:
            rsa.validate_transform_key(d, n, "decrypt")
            if cipher[0] >= n:
                raise rsa.RsaCoreError("CIPHER_TOO_LARGE", index=0)
        except rsa.RsaCoreError as exc:
            raise map_core_error(exc, "cipher[0]") from None
        return NumberDecryptRequest(d, n, cipher, _trace_index(payload))

    mode = _mode(payload)
    required = ["d", "n", "inputType", "mode", "cipher"]
    allowed = [*required, "traceBlockIndex"]
    if mode == "block":
        allowed.append("originalUtf8ByteLength")
    _fields(payload, allowed=tuple(allowed), required=tuple(required))
    if mode == "block" and "originalUtf8ByteLength" not in payload:
        raise error(
            422,
            "INVALID_LENGTH_METADATA",
            messages.RSA_INVALID_LENGTH_METADATA,
            "originalUtf8ByteLength",
        )
    limit = rsa.MAX_TEXT_CODEPOINTS if mode == "char" else rsa.MAX_BLOCK_CIPHER_ITEMS
    raw_cipher = payload.get("cipher")
    if type(raw_cipher) is not list:
        raise _invalid("cipher")
    if not raw_cipher:
        raise error(422, "EMPTY_INPUT", messages.RSA_EMPTY_INPUT, "cipher")
    if len(raw_cipher) > limit:
        raise error(422, "INPUT_TOO_LARGE", messages.RSA_COLLECTION_TOO_LARGE, "cipher")
    length: int | None = None
    if mode == "block":
        length = _control(
            payload["originalUtf8ByteLength"],
            "originalUtf8ByteLength",
            "INVALID_LENGTH_METADATA",
        )
        if not 1 <= length <= rsa.MAX_BLOCK_CIPHER_ITEMS:
            raise error(
                422,
                "INVALID_LENGTH_METADATA",
                messages.RSA_INVALID_LENGTH_METADATA,
                "originalUtf8ByteLength",
            )
    d = parse_decimal(payload["d"], "d")
    n = parse_decimal(payload["n"], "n")
    cipher = tuple(parse_decimal(item, f"cipher[{index}]") for index, item in enumerate(raw_cipher))
    try:
        rsa.validate_transform_key(d, n, "decrypt")
        for index, value in enumerate(cipher):
            if value >= n:
                raise rsa.RsaCoreError("CIPHER_TOO_LARGE", index=index)
        if mode == "block":
            size = rsa.block_size(n)
            assert length is not None
            if (length + size - 1) // size != len(cipher):
                raise rsa.RsaCoreError("INVALID_LENGTH_METADATA")
    except rsa.RsaCoreError as exc:
        raise map_core_error(exc, "cipher") from None
    return TextDecryptRequest(d, n, mode, cipher, length, _trace_index(payload))


def validate_file_form(form: FormData) -> FileEncryptRequest:
    allowed = frozenset({"file", "e", "n", "mode", "traceBlockIndex"})
    names = [name for name, _ in form.multi_items()]
    for name in names:
        if name not in allowed or names.count(name) > 1:
            raise _invalid(name)
    file = form.get("file", MISSING)
    if file is MISSING:
        raise _invalid("file")
    if not isinstance(file, UploadFile):
        raise _invalid("file")
    for required in ("e", "n", "mode"):
        if required not in names:
            raise _invalid(required)
    raw_e = form.get("e")
    raw_n = form.get("n")
    raw_mode = form.get("mode")
    if isinstance(raw_e, UploadFile) or isinstance(raw_n, UploadFile):
        raise _invalid("e" if isinstance(raw_e, UploadFile) else "n")
    e = parse_decimal(raw_e, "e")
    n = parse_decimal(raw_n, "n")
    if raw_mode not in ("char", "block"):
        raise _invalid("mode")
    raw_trace = form.get("traceBlockIndex", MISSING)
    if raw_trace is not MISSING and type(raw_trace) is not str:
        raise _invalid("traceBlockIndex")
    return FileEncryptRequest(file, e, n, raw_mode, None if raw_trace is MISSING else raw_trace)


def parse_form_trace(raw: str | None) -> int | None:
    if raw is None:
        return None
    if FORM_INTEGER.fullmatch(raw) is None or len(raw) > 10:
        raise error(422, "TRACE_INDEX_OUT_OF_RANGE", messages.RSA_TRACE_INDEX, "traceBlockIndex")
    return int(raw)


def map_core_error(exc: rsa.RsaCoreError, default_field: str | None = None) -> RsaError:
    details = exc.details
    code = exc.code
    field = details.get("field", default_field)
    status = 422
    if code == "NOT_PRIME":
        message = f"{field} = {details['value']} không phải số nguyên tố."
    elif code == "SAME_PRIME":
        message = messages.RSA_SAME_PRIME
    elif code == "E_OUT_OF_RANGE":
        message = (
            f"e phải thỏa 1 < e < phi(n) = {details['phi']}."
            if "phi" in details
            else "e phải thỏa 1 < e < n."
        )
    elif code == "D_OUT_OF_RANGE":
        message = messages.RSA_D_OUT_OF_RANGE
    elif code == "E_NOT_COPRIME":
        message = (
            f"gcd({details['e']}, {details['phi']}) = {details['gcd']}, không tồn tại d. "
            f"Gợi ý e = {details['suggestion']}."
        )
    elif code == "PRIME_TOO_LARGE":
        message = messages.RSA_PRIME_TOO_LARGE
    elif code == "P_TOO_LARGE":
        field = field or "data"
        message = f"P = {details['value']} ≥ n = {details['n']}. Hãy chia khối hoặc dùng n lớn hơn."
    elif code == "N_TOO_SMALL":
        field = "n"
        message = (
            messages.RSA_BLOCK_N_TOO_SMALL if details.get("block") else messages.RSA_N_TOO_SMALL
        )
    elif code == "CIPHER_TOO_LARGE":
        index = details.get("index")
        field = f"cipher[{index}]" if index is not None else field or "cipher"
        message = messages.RSA_CIPHER_TOO_LARGE
    elif code == "DECODE_FAILED":
        index = details.get("index")
        field = f"cipher[{index}]" if index is not None else field or "cipher"
        message = messages.RSA_DECODE_FAILED
    elif code == "EMPTY_INPUT":
        message = messages.RSA_EMPTY_INPUT
    elif code == "INPUT_TOO_LARGE":
        message = (
            messages.RSA_TEXT_TOO_LARGE
            if details.get("kind") == "text"
            else messages.RSA_COLLECTION_TOO_LARGE
        )
    elif code == "INVALID_LENGTH_METADATA":
        field = "originalUtf8ByteLength"
        message = messages.RSA_INVALID_LENGTH_METADATA
    elif code == "TRACE_INDEX_OUT_OF_RANGE":
        field = "traceBlockIndex"
        message = messages.RSA_TRACE_INDEX
    elif code == "NUMBER_TOO_LARGE":
        message = messages.RSA_NUMBER_TOO_LARGE
    elif code == "INVALID_BITS":
        message = messages.RSA_INVALID_BITS
    else:
        return error(500, "INTERNAL_ERROR", messages.RSA_INTERNAL_ERROR)
    return error(status, code, message, field if isinstance(field, str) else default_field)


def serialize_key(material: rsa.KeyMaterial, *, include_primes: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
        "success": True,
        "n": str(material.n),
        "phi": str(material.phi),
        "e": str(material.e),
        "d": str(material.d),
        "publicKey": {"e": str(material.e), "n": str(material.n)},
        "privateKey": {"d": str(material.d), "n": str(material.n)},
        "egcdSteps": [
            {
                "index": row["index"],
                "q": None if row["q"] is None else str(row["q"]),
                "r": str(row["r"]),
                "t": str(row["t"]),
            }
            for row in material.egcd_steps
        ],
    }
    if include_primes:
        result["p"] = str(material.p)
        result["q"] = str(material.q)
    return result


def serialize_trace(trace: dict[str, Any] | None) -> dict[str, Any] | None:
    if trace is None:
        return None
    return {
        "operation": trace["operation"],
        "blockIndex": trace["blockIndex"],
        "input": str(trace["input"]),
        "exponent": str(trace["exponent"]),
        "modulus": str(trace["modulus"]),
        "result": str(trace["result"]),
        "steps": [
            {
                "i": row["i"],
                "bit": row["bit"],
                "base": str(row["base"]),
                "before": str(row["before"]),
                "result": str(row["result"]),
            }
            for row in trace["steps"]
        ],
    }
