"""Request and response schemas for the text and file cipher endpoints."""

from __future__ import annotations

import json
import re
from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.datastructures import FormData, UploadFile

from app.core.affine import normalize_keys as normalize_affine_keys
from app.core.columnar import ASCII_WHITESPACE
from app.core.columnar import parse_key as parse_columnar_key
from app.core.playfair import normalize_keyword as normalize_playfair_keyword
from app.core.playfair import normalize_text as normalize_playfair_text
from app.errors.exceptions import (
    DuplicatePlayfairDigraphError,
    EmptyPlayfairTextError,
    EmptyTextError,
    InvalidActionError,
    InvalidAffineMultiplierError,
    InvalidAffineShiftError,
    InvalidColumnarKeyError,
    InvalidKeyError,
    InvalidPlayfairKeyError,
    InvalidRequestBodyError,
    InvalidResponseModeError,
    InvalidStringKeyError,
    InvalidStripPaddingError,
    InvalidVigenereKeyError,
    MissingAffineMultiplierError,
    MissingAffineShiftError,
    MissingFileError,
    MissingKeyError,
    NonInvertibleAffineMultiplierError,
    OddPlayfairCiphertextError,
)

MISSING: Final = object()
MULTIPART_KEY_MAX_LENGTH = 32
_MULTIPART_KEY_PATTERN = re.compile(r"^[+-]?[0-9]+$")
_CANONICAL_DECIMAL_KEY_PATTERN = r"^(?:0|[1-9][0-9]*)$"
_CANONICAL_DECIMAL_KEY_RE = re.compile(_CANONICAL_DECIMAL_KEY_PATTERN, re.ASCII)
_VIGENERE_KEY_PATTERN = re.compile(r"^[A-Za-z]+$")


class JsonIntegerToken(str):
    """A syntactically valid JSON integer retained without a Python int conversion."""


def _reject_nonstandard_json_constant(value: str) -> None:
    """Reject NaN and infinities, which Python accepts but JSON does not define."""

    raise json.JSONDecodeError("Non-standard JSON constant", value, 0)


class TextCipherRequest(BaseModel):
    """Raw JSON fields retained for deterministic, application-level validation."""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"required": ["text", "key"]},
    )

    text: Any = Field(default_factory=lambda: MISSING, json_schema_extra={"type": "string"})
    key: Any = Field(
        default_factory=lambda: MISSING,
        json_schema_extra={
            "oneOf": [
                {"type": "integer"},
                {"type": "string", "pattern": _CANONICAL_DECIMAL_KEY_PATTERN},
            ]
        },
    )


class StringKeyCipherRequest(BaseModel):
    """Raw JSON fields for ciphers whose key contract is a string."""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"required": ["text", "key"]},
    )

    text: Any = Field(default_factory=lambda: MISSING, json_schema_extra={"type": "string"})
    key: Any = Field(default_factory=lambda: MISSING, json_schema_extra={"type": "string"})


class AffineTextCipherRequest(BaseModel):
    """Strict raw JSON fields for deterministic Affine validation."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "required": ["text", "a", "b"],
            "additionalProperties": False,
        },
    )

    text: Any = Field(default_factory=lambda: MISSING, json_schema_extra={"type": "string"})
    a: Any = Field(default_factory=lambda: MISSING, json_schema_extra={"type": "integer"})
    b: Any = Field(default_factory=lambda: MISSING, json_schema_extra={"type": "integer"})


class ColumnarTextCipherRequest(BaseModel):
    """Strict raw JSON fields for deterministic Columnar validation."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "required": ["text", "key"],
            "additionalProperties": False,
        },
    )

    text: Any = Field(default_factory=lambda: MISSING, json_schema_extra={"type": "string"})
    key: Any = Field(default_factory=lambda: MISSING, json_schema_extra={"type": "string"})


class TextCipherResponse(BaseModel):
    """The exact success envelope returned by both text endpoints."""

    success: Literal[True]
    result: str


class FileCipherResponse(BaseModel):
    """The exact success envelope for the file endpoint's content mode."""

    success: Literal[True]
    result: str


class PaddingInfo(BaseModel):
    """Padding letters detected in a raw decrypt ``result``.

    ``positions`` index the letters taking part in the cipher, not string characters;
    ``filtered`` is ``result`` without the letters at those positions.
    """

    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=0)
    positions: list[Annotated[int, Field(ge=0)]]
    filtered: str


class PlayfairDecryptResponse(BaseModel):
    """Playfair decrypt success envelope: raw ``result`` plus detected fillers."""

    model_config = ConfigDict(extra="forbid")

    success: Literal[True]
    result: str
    padding: PaddingInfo


def _parse_decimal_key(value: str) -> int:
    """Normalize a validated decimal token without converting huge values to Python ints."""

    negative = value.startswith("-")
    digits = value[1:] if value[:1] in "+-" else value
    normalized = 0
    for digit in digits:
        normalized = (normalized * 10 + ord(digit) - ord("0")) % 26
    return -normalized if negative else normalized


def parse_key(value: Any) -> int:
    """Validate a JSON integer or canonical unsigned decimal-string key."""

    if value is MISSING or value is None or (type(value) is str and value == ""):
        raise MissingKeyError()
    if type(value) is JsonIntegerToken:
        return _parse_decimal_key(value)
    if type(value) is str:
        if _CANONICAL_DECIMAL_KEY_RE.fullmatch(value) is None:
            raise InvalidKeyError()
        return _parse_decimal_key(value)
    if type(value) is not int:
        raise InvalidKeyError()
    return value


def decode_text_request(raw: bytes, content_type: str | None) -> TextCipherRequest:
    """Decode a JSON object while retaining unbounded integer tokens safely."""

    media_type = content_type.partition(";")[0].strip().lower() if content_type else ""
    if media_type != "application/json" and not (
        media_type.startswith("application/") and media_type.endswith("+json")
    ):
        raise InvalidRequestBodyError()

    try:
        decoded = json.loads(
            raw,
            parse_int=JsonIntegerToken,
            parse_constant=_reject_nonstandard_json_constant,
        )
        if type(decoded) is not dict:
            raise InvalidRequestBodyError()
        return TextCipherRequest.model_validate(decoded)
    except InvalidRequestBodyError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, RecursionError) as exc:
        raise InvalidRequestBodyError() from exc


def decode_string_key_request(raw: bytes, content_type: str | None) -> StringKeyCipherRequest:
    """Decode a JSON object without coercing either string-key cipher field."""

    media_type = content_type.partition(";")[0].strip().lower() if content_type else ""
    if media_type != "application/json" and not (
        media_type.startswith("application/") and media_type.endswith("+json")
    ):
        raise InvalidRequestBodyError()

    try:
        decoded = json.loads(
            raw,
            parse_int=JsonIntegerToken,
            parse_constant=_reject_nonstandard_json_constant,
        )
        if type(decoded) is not dict:
            raise InvalidRequestBodyError()
        return StringKeyCipherRequest.model_validate(decoded)
    except InvalidRequestBodyError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, RecursionError) as exc:
        raise InvalidRequestBodyError() from exc


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for key, value in pairs:
        if key in decoded:
            raise InvalidRequestBodyError()
        decoded[key] = value
    return decoded


def decode_affine_text_request(raw: bytes, content_type: str | None) -> AffineTextCipherRequest:
    """Decode one exact Affine JSON object while retaining unbounded integer tokens."""

    media_type = content_type.partition(";")[0].strip().lower() if content_type else ""
    if media_type != "application/json" and not (
        media_type.startswith("application/") and media_type.endswith("+json")
    ):
        raise InvalidRequestBodyError()

    try:
        decoded = json.loads(
            raw,
            parse_int=JsonIntegerToken,
            parse_constant=_reject_nonstandard_json_constant,
            object_pairs_hook=_strict_json_object,
        )
        if type(decoded) is not dict:
            raise InvalidRequestBodyError()
        return AffineTextCipherRequest.model_validate(decoded)
    except InvalidRequestBodyError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, RecursionError) as exc:
        raise InvalidRequestBodyError() from exc


def _has_json_surrogate(value: Any) -> bool:
    if isinstance(value, str):
        return any(0xD800 <= ord(character) <= 0xDFFF for character in value)
    if isinstance(value, list):
        return any(_has_json_surrogate(item) for item in value)
    if isinstance(value, dict):
        return any(
            _has_json_surrogate(key) or _has_json_surrogate(item) for key, item in value.items()
        )
    return False


def decode_columnar_text_request(
    raw: bytes,
    content_type: str | None,
) -> ColumnarTextCipherRequest:
    """Decode one exact Columnar JSON object and reject residual surrogates."""

    media_type = content_type.partition(";")[0].strip().lower() if content_type else ""
    if media_type != "application/json" and not (
        media_type.startswith("application/") and media_type.endswith("+json")
    ):
        raise InvalidRequestBodyError()

    try:
        decoded = json.loads(
            raw,
            parse_int=JsonIntegerToken,
            parse_constant=_reject_nonstandard_json_constant,
            object_pairs_hook=_strict_json_object,
        )
        if _has_json_surrogate(decoded) or type(decoded) is not dict:
            raise InvalidRequestBodyError()
        return ColumnarTextCipherRequest.model_validate(decoded)
    except InvalidRequestBodyError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, RecursionError) as exc:
        raise InvalidRequestBodyError() from exc


def _json_integer_residue(
    value: Any,
    missing_error: type[Exception],
    invalid_error: type[Exception],
) -> int:
    if value is MISSING or value is None:
        raise missing_error()
    if type(value) is JsonIntegerToken:
        negative = value.startswith("-")
        digits = value[1:] if negative else value
        residue = 0
        for digit in digits:
            residue = (residue * 10 + ord(digit) - ord("0")) % 26
        return (-residue if negative else residue) % 26
    if type(value) is not int:
        raise invalid_error()
    return value % 26


def _normalize_affine_multiplier(multiplier: int) -> int:
    """Normalize an Affine multiplier and map invertibility to the API error."""

    try:
        normalized_multiplier, _ = normalize_affine_keys(multiplier, 0)
    except ValueError as exc:
        raise NonInvertibleAffineMultiplierError() from exc
    return normalized_multiplier


def validate_affine_text_request(payload: AffineTextCipherRequest) -> tuple[str, int, int]:
    """Apply Affine text validation in the contract-defined text → a → b order."""

    if payload.text is MISSING or type(payload.text) is not str or payload.text == "":
        raise EmptyTextError()

    multiplier = _json_integer_residue(
        payload.a,
        MissingAffineMultiplierError,
        InvalidAffineMultiplierError,
    )
    normalized_multiplier = _normalize_affine_multiplier(multiplier)

    shift = _json_integer_residue(
        payload.b,
        MissingAffineShiftError,
        InvalidAffineShiftError,
    )
    return payload.text, normalized_multiplier, shift


def _parse_affine_form_integer(
    value: Any,
    missing_error: type[Exception],
    invalid_error: type[Exception],
) -> int:
    if value is MISSING or value is None:
        raise missing_error()
    if type(value) is not str:
        raise invalid_error()

    stripped = value.strip()
    if stripped == "":
        raise missing_error()
    if len(stripped) > MULTIPART_KEY_MAX_LENGTH:
        raise invalid_error()
    if _MULTIPART_KEY_PATTERN.fullmatch(stripped) is None:
        raise invalid_error()
    return int(stripped) % 26


def validate_affine_file_form(
    form: FormData,
) -> tuple[
    UploadFile,
    int,
    int,
    Literal["encrypt", "decrypt"],
    Literal["content", "file"],
]:
    """Validate an exact Affine multipart form in deterministic field order."""

    allowed = {"file", "a", "b", "action", "response_mode"}
    items = list(form.multi_items())
    names = [name for name, _ in items]
    if any(name not in allowed for name in names) or len(names) != len(set(names)):
        raise InvalidRequestBodyError()

    file = form.get("file", MISSING)
    if file is MISSING or file is None:
        raise MissingFileError()
    if not isinstance(file, UploadFile):
        raise InvalidRequestBodyError()

    multiplier = _parse_affine_form_integer(
        form.get("a", MISSING),
        MissingAffineMultiplierError,
        InvalidAffineMultiplierError,
    )
    normalized_multiplier = _normalize_affine_multiplier(multiplier)

    shift = _parse_affine_form_integer(
        form.get("b", MISSING),
        MissingAffineShiftError,
        InvalidAffineShiftError,
    )

    action = form.get("action", MISSING)
    if action not in ("encrypt", "decrypt"):
        raise InvalidActionError()

    response_mode = form.get("response_mode", MISSING)
    if response_mode is MISSING or response_mode is None:
        parsed_response_mode = "content"
    elif response_mode not in ("content", "file"):
        raise InvalidResponseModeError()
    else:
        parsed_response_mode = response_mode

    return file, normalized_multiplier, shift, action, parsed_response_mode


def _parse_columnar_key(value: Any) -> tuple[int, ...]:
    if value is MISSING or value is None:
        raise MissingKeyError()
    if type(value) is not str:
        raise InvalidStringKeyError()
    if value.strip(ASCII_WHITESPACE) == "":
        raise MissingKeyError()

    try:
        return parse_columnar_key(value)
    except ValueError:
        raise InvalidColumnarKeyError() from None


def validate_columnar_text_request(
    payload: ColumnarTextCipherRequest,
) -> tuple[str, tuple[int, ...]]:
    """Apply Columnar text validation in text then key precedence."""

    if payload.text is MISSING or type(payload.text) is not str or payload.text == "":
        raise EmptyTextError()
    return payload.text, _parse_columnar_key(payload.key)


def validate_columnar_file_form(
    form: FormData,
) -> tuple[
    UploadFile,
    tuple[int, ...],
    Literal["encrypt", "decrypt"],
    Literal["content", "file"],
]:
    """Validate one exact Columnar multipart form in deterministic order."""

    allowed = {"file", "key", "action", "response_mode"}
    items = list(form.multi_items())
    names = [name for name, _ in items]
    if any(name not in allowed for name in names) or len(names) != len(set(names)):
        raise InvalidRequestBodyError()

    file = form.get("file", MISSING)
    if file is MISSING or file is None:
        raise MissingFileError()
    if not isinstance(file, UploadFile):
        raise InvalidRequestBodyError()

    ranks = _parse_columnar_key(form.get("key", MISSING))

    action = form.get("action", MISSING)
    if action not in ("encrypt", "decrypt"):
        raise InvalidActionError()

    response_mode = form.get("response_mode", MISSING)
    if response_mode is MISSING or response_mode is None:
        parsed_response_mode = "content"
    elif response_mode not in ("content", "file"):
        raise InvalidResponseModeError()
    else:
        parsed_response_mode = response_mode

    return file, ranks, action, parsed_response_mode


def parse_multipart_key(value: Any) -> int:
    """Parse the explicitly supported decimal grammar used by multipart forms."""

    if value is MISSING or value is None:
        raise MissingKeyError()
    if type(value) is not str:
        raise InvalidKeyError()

    stripped = value.strip()
    if stripped == "":
        raise MissingKeyError()
    if len(stripped) > MULTIPART_KEY_MAX_LENGTH:
        raise InvalidKeyError()
    if _MULTIPART_KEY_PATTERN.fullmatch(stripped) is None:
        raise InvalidKeyError()

    try:
        return int(stripped)
    except (OverflowError, ValueError) as exc:
        raise InvalidKeyError() from exc


def validate_file_form_fields(
    key: Any,
    action: Any,
    response_mode: Any,
) -> tuple[int, str, str]:
    """Validate multipart scalar fields in the approved deterministic order."""

    if key is MISSING or key is None or (type(key) is str and key.strip() == ""):
        raise MissingKeyError()
    if action is MISSING or action is None:
        raise InvalidActionError()

    parsed_key = parse_multipart_key(key)
    if action not in ("encrypt", "decrypt"):
        raise InvalidActionError()

    if response_mode is MISSING or response_mode is None:
        parsed_response_mode = "content"
    elif response_mode not in ("content", "file"):
        raise InvalidResponseModeError()
    else:
        parsed_response_mode = response_mode

    return parsed_key, action, parsed_response_mode


def validate_text_request(payload: TextCipherRequest) -> tuple[str, int]:
    """Apply text validation before key presence and key type validation."""

    if payload.text is MISSING or type(payload.text) is not str or payload.text == "":
        raise EmptyTextError()
    return payload.text, parse_key(payload.key)


def _parse_string_key(value: Any) -> str:
    if value is MISSING or value is None or (type(value) is str and value == ""):
        raise MissingKeyError()
    if type(value) is not str:
        raise InvalidStringKeyError()
    return value


def _validate_algorithm_key(key: str, cipher: Literal["vigenere", "playfair"]) -> None:
    if cipher == "vigenere":
        if _VIGENERE_KEY_PATTERN.fullmatch(key) is None:
            raise InvalidVigenereKeyError()
        return

    try:
        normalize_playfair_keyword(key)
    except ValueError as exc:
        raise InvalidPlayfairKeyError() from exc


def validate_playfair_content(text: str, operation: str) -> None:
    """Apply Playfair validation that follows key and transport validation."""

    normalized = normalize_playfair_text(text)
    if not normalized:
        raise EmptyPlayfairTextError()
    if operation == "decrypt":
        if len(normalized) % 2:
            raise OddPlayfairCiphertextError()
        if any(
            normalized[index] == normalized[index + 1] for index in range(0, len(normalized), 2)
        ):
            raise DuplicatePlayfairDigraphError()


def validate_additional_text_request(
    payload: StringKeyCipherRequest,
    cipher: Literal["vigenere", "playfair"],
    operation: Literal["encrypt", "decrypt"],
) -> tuple[str, str]:
    """Validate a string-key text request in the contract-defined order."""

    if payload.text is MISSING or type(payload.text) is not str or payload.text == "":
        raise EmptyTextError()
    key = _parse_string_key(payload.key)
    _validate_algorithm_key(key, cipher)
    if cipher == "playfair":
        validate_playfair_content(payload.text, operation)
    return payload.text, key


def validate_additional_file_form_fields(
    key: Any,
    action: Any,
    response_mode: Any,
    cipher: Literal["vigenere", "playfair"],
) -> tuple[str, Literal["encrypt", "decrypt"], Literal["content", "file"]]:
    """Validate new cipher multipart fields in the accepted precedence order."""

    parsed_key = _parse_string_key(key)
    if action is MISSING or action is None:
        raise InvalidActionError()

    _validate_algorithm_key(parsed_key, cipher)
    if action not in ("encrypt", "decrypt"):
        raise InvalidActionError()

    if response_mode is MISSING or response_mode is None:
        parsed_response_mode = "content"
    elif response_mode not in ("content", "file"):
        raise InvalidResponseModeError()
    else:
        parsed_response_mode = response_mode

    return parsed_key, action, parsed_response_mode


def validate_strip_padding(value: Any) -> bool:
    """Validate the optional Playfair multipart ``strip_padding`` flag."""

    if value is MISSING or value is None:
        return False
    if value not in ("true", "false"):
        raise InvalidStripPaddingError()
    return value == "true"
