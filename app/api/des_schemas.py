"""Strict decoding and ordered validation for the DES JSON and multipart APIs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Final, Literal

from starlette.datastructures import FormData, UploadFile

from app import config
from app.api.schemas import JsonIntegerToken
from app.core import des
from app.errors import messages
from app.errors.exceptions import (
    DesError,
    InvalidActionError,
    InvalidRequestBodyError,
    InvalidResponseModeError,
    MissingFileError,
)

MISSING: Final = object()
MAX_TEXT_BYTES = config.MAX_FILE_BYTES

ENCRYPT_FIELDS = frozenset({"text", "key", "inputFormat", "mode", "iv"})
DECRYPT_FIELDS = frozenset({"text", "key", "outputFormat", "mode", "iv"})
TRACE_FIELDS = frozenset({"block", "key", "operation"})
FILE_FIELDS = frozenset({"file", "key", "action", "mode", "iv", "response_mode"})

_STRING_FIELDS = frozenset({"text", "key", "block", "iv"})
_FORMATS = ("text", "hex")
_MODES = ("ECB", "CBC")
_OPERATIONS = ("encrypt", "decrypt")


@dataclass(frozen=True)
class DesEncryptRequest:
    text: str
    data: bytes
    pad: bool
    key: int
    mode: des.Mode
    iv: int | None


@dataclass(frozen=True)
class DesDecryptRequest:
    text: str
    data: bytes
    output_format: Literal["text", "hex"]
    key: int
    mode: des.Mode
    iv: int | None


@dataclass(frozen=True)
class DesTraceRequest:
    block: int
    key: int
    operation: des.Operation


@dataclass(frozen=True)
class DesFileForm:
    file: UploadFile
    key: int
    action: Literal["encrypt", "decrypt"]
    response_mode: Literal["content", "file"]
    mode: des.Mode
    iv: int | None


def map_core_error(exc: des.DesError) -> DesError:
    """Translate a core error code into the public status and Vietnamese message."""

    templates = {
        "E01": messages.DES_TEXT_EMPTY,
        "E02": messages.DES_MISSING_KEY,
        "E03": messages.DES_KEY_NOT_HEX,
        "E04": messages.DES_KEY_LENGTH,
        "E05": messages.DES_DATA_NOT_HEX,
        "E06": messages.DES_DATA_LENGTH,
        "E07": messages.DES_INVALID_PADDING,
        "E08": messages.DES_INVALID_UTF8,
        "E09": messages.DES_INVALID_IV,
        "E13": messages.DES_TRACE_BLOCK,
    }
    return DesError(422, templates[exc.code].format(n=exc.count))


def _parameter_error(name: str) -> DesError:
    return DesError(422, messages.DES_INVALID_PARAMETER.format(name=name))


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for key, value in pairs:
        if key in decoded:
            raise InvalidRequestBodyError()
        decoded[key] = value
    return decoded


def _reject_constant(value: str) -> None:
    raise json.JSONDecodeError("Non-standard JSON constant", value, 0)


def _has_surrogate(value: str) -> bool:
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def decode(raw: bytes, content_type: str | None, allowed: frozenset[str]) -> dict[str, Any]:
    """Decode one exact JSON object; any shape or string-field type problem is a body error."""

    media_type = content_type.partition(";")[0].strip().lower() if content_type else ""
    if media_type != "application/json" and not (
        media_type.startswith("application/") and media_type.endswith("+json")
    ):
        raise InvalidRequestBodyError()
    try:
        value = json.loads(
            raw,
            parse_int=JsonIntegerToken,
            parse_constant=_reject_constant,
            object_pairs_hook=_strict_object,
        )
    except InvalidRequestBodyError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
        raise InvalidRequestBodyError() from exc
    if type(value) is not dict or any(key not in allowed for key in value):
        raise InvalidRequestBodyError()
    for name in _STRING_FIELDS & value.keys():
        field = value[name]
        if field is not None and (type(field) is not str or _has_surrogate(field)):
            raise InvalidRequestBodyError()
    return value


def _check_size(value: Any) -> None:
    if type(value) is str and len(value.encode("utf-8")) > MAX_TEXT_BYTES:
        raise DesError(413, messages.DES_TOO_LARGE)


def _choice(payload: dict[str, Any], name: str, allowed: tuple[str, ...]) -> Any:
    value = payload.get(name, MISSING)
    if value is MISSING:
        return allowed[0]
    if type(value) is not str or value not in allowed:
        raise _parameter_error(name)
    return value


def _string(value: Any) -> str:
    return value if type(value) is str else ""


def _key(value: Any) -> int:
    try:
        return des.parse_key(_string(value))
    except des.DesError as exc:
        raise map_core_error(exc) from None


def _iv(mode: str, value: Any) -> int | None:
    """Parse the IV only for CBC; ECB ignores whatever was sent."""

    if mode != "CBC":
        return None
    try:
        return des.parse_iv(_string(value))
    except des.DesError as exc:
        raise map_core_error(exc) from None


def _hex_data(text: str) -> bytes:
    try:
        return des.parse_hex(text)
    except des.DesError as exc:
        raise map_core_error(exc) from None


def validate_encrypt(payload: dict[str, Any]) -> DesEncryptRequest:
    """Size, parameters, key, IV, then data, as ordered in `des-error-handling`."""

    _check_size(payload.get("text"))
    input_format = _choice(payload, "inputFormat", _FORMATS)
    mode = _choice(payload, "mode", _MODES)
    key = _key(payload.get("key"))
    iv = _iv(mode, payload.get("iv"))
    text = _string(payload.get("text"))
    if input_format == "hex":
        return DesEncryptRequest(text, _hex_data(text), False, key, mode, iv)
    if text == "":
        raise DesError(422, messages.DES_TEXT_EMPTY)
    return DesEncryptRequest(text, text.encode("utf-8"), True, key, mode, iv)


def validate_decrypt(payload: dict[str, Any]) -> DesDecryptRequest:
    """Size, parameters, key, IV, then ciphertext hex."""

    _check_size(payload.get("text"))
    output_format = _choice(payload, "outputFormat", _FORMATS)
    mode = _choice(payload, "mode", _MODES)
    key = _key(payload.get("key"))
    iv = _iv(mode, payload.get("iv"))
    text = _string(payload.get("text"))
    return DesDecryptRequest(text, _hex_data(text), output_format, key, mode, iv)


def validate_trace(payload: dict[str, Any]) -> DesTraceRequest:
    """Size, operation, key, then exactly one block (E13)."""

    _check_size(payload.get("block"))
    operation = _choice(payload, "operation", _OPERATIONS)
    key = _key(payload.get("key"))
    try:
        block = des.parse_block(_string(payload.get("block")))
    except des.DesError as exc:
        raise map_core_error(exc) from None
    return DesTraceRequest(block, key, operation)


def validate_file_form(form: FormData) -> DesFileForm:
    """Validate the exact DES multipart form in the inherited file-route order."""

    names = [name for name, _ in form.multi_items()]
    if any(name not in FILE_FIELDS for name in names) or len(names) != len(set(names)):
        raise InvalidRequestBodyError()

    file = form.get("file", MISSING)
    if file is MISSING or file is None:
        raise MissingFileError()
    if not isinstance(file, UploadFile):
        raise InvalidRequestBodyError()

    key = form.get("key")
    if isinstance(key, UploadFile):
        raise InvalidRequestBodyError()

    action = form.get("action", MISSING)
    response_mode = form.get("response_mode", MISSING)
    mode = form.get("mode", MISSING)
    iv = form.get("iv")

    parsed_key = _key(key)
    if action not in _OPERATIONS:
        raise InvalidActionError()
    if response_mode is MISSING:
        response_mode = "content"
    elif response_mode not in ("content", "file"):
        raise InvalidResponseModeError()
    if mode is MISSING:
        mode = "ECB"
    elif mode not in _MODES:
        raise _parameter_error("mode")
    return DesFileForm(file, parsed_key, action, response_mode, mode, _iv(mode, iv))
