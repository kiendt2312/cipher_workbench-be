"""Strict decoding and deterministic validation for the Hill JSON API."""

from __future__ import annotations

import json
import re
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Final

from app.api.schemas import JsonIntegerToken
from app.errors.exceptions import HillError

MISSING: Final = object()
MAX_TEXT_BYTES = 1024 * 1024
_ASCII_KEYWORD = re.compile(r"^[A-Za-z]+$")

MESSAGES = {
    "E01": "Nhập văn bản hoặc tải file .txt để bắt đầu.",
    "E02": "Văn bản không có chữ cái nào để mã hóa. Hill chỉ xử lý A\u2013Z.",
    "E06": "Văn bản vượt quá giới hạn 1 MiB.",
    "E08": "Cấp ma trận khóa phải từ 2 đến 4.",
    "E10": "Tùy chọn Hill không hợp lệ.",
    "E11": "Dữ liệu gửi lên không hợp lệ.",
}


@dataclass(frozen=True)
class HillRequest:
    text: str | None
    matrix: list[list[int]]
    options: dict[str, object]


def error(
    code: str,
    *,
    details: dict[str, object] | None = None,
    message: str | None = None,
) -> HillError:
    return HillError(413 if code == "E06" else 422, code, message or MESSAGES[code], details)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise error("E11")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise json.JSONDecodeError("non-standard JSON constant", value, 0)


def _has_surrogate(value: Any) -> bool:
    if isinstance(value, str):
        return any(0xD800 <= ord(character) <= 0xDFFF for character in value)
    if isinstance(value, list):
        return any(_has_surrogate(item) for item in value)
    if isinstance(value, dict):
        return any(_has_surrogate(key) or _has_surrogate(item) for key, item in value.items())
    return False


def decode(raw: bytes, content_type: str | None, allowed: set[str]) -> dict[str, Any]:
    media_type = content_type.partition(";")[0].strip().lower() if content_type else ""
    if media_type != "application/json" and not (
        media_type.startswith("application/") and media_type.endswith("+json")
    ):
        raise error("E11")
    try:
        value = json.loads(
            raw,
            parse_int=JsonIntegerToken,
            parse_constant=_reject_constant,
            object_pairs_hook=_pairs,
        )
    except HillError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
        raise error("E11") from exc
    if type(value) is not dict or _has_surrogate(value) or any(key not in allowed for key in value):
        raise error("E11")
    return value


def _integer(value: Any) -> int | None:
    if type(value) is int:
        return value % 26
    if type(value) is JsonIntegerToken:
        negative = value.startswith("-")
        residue = 0
        for digit in value.removeprefix("-"):
            residue = (residue * 10 + ord(digit) - ord("0")) % 26
        return (-residue if negative else residue) % 26
    return None


def _m(value: Any) -> int:
    if type(value) is JsonIntegerToken and len(value) == 1 and value in {"2", "3", "4"}:
        return int(value)
    if type(value) is int and value in {2, 3, 4}:
        return value
    details: dict[str, object] = {"min": 2, "max": 4}
    if type(value) is JsonIntegerToken:
        with suppress(ValueError):
            details["m"] = int(value)
    elif type(value) is int:
        details["m"] = value
    raise error("E08", details=details)


def _matrix(value: Any) -> list[list[int]]:
    if type(value) is not list:
        raise error(
            "E03", details={"reason": "invalid_shape"}, message="Khóa ma trận không hợp lệ."
        )
    if len(value) not in {2, 3, 4}:
        raise error("E08", details={"min": 2, "max": 4, "m": len(value)})
    size = len(value)
    matrix: list[list[int]] = []
    for row_index, row in enumerate(value, 1):
        if type(row) is not list or len(row) != size:
            raise error(
                "E03",
                details={"reason": "invalid_shape"},
                message="Khóa ma trận không hợp lệ.",
            )
        parsed_row: list[int] = []
        for column_index, cell in enumerate(row, 1):
            parsed = _integer(cell)
            if parsed is None:
                raise error(
                    "E03",
                    details={"reason": "invalid_cell", "row": row_index, "column": column_index},
                    message=f"Ô hàng {row_index} cột {column_index} phải là số nguyên.",
                )
            parsed_row.append(parsed)
        matrix.append(parsed_row)
    return matrix


def _keyword(value: Any, size: int) -> list[list[int]]:
    valid_count = (
        sum(character.isascii() and character.isalpha() for character in value)
        if type(value) is str
        else None
    )
    if (
        type(value) is not str
        or _ASCII_KEYWORD.fullmatch(value) is None
        or len(value) != size * size
    ):
        actual = valid_count if valid_count is not None else 0
        raise error(
            "E09",
            details={"m": size, "expected": size * size, "actual": valid_count},
            message=f"Từ khóa cần đúng {size * size} chữ cái, hiện có {actual}.",
        )
    values = [ord(character.upper()) - ord("A") for character in value]
    return [values[index : index + size] for index in range(0, len(values), size)]


def validate_key(payload: dict[str, Any]) -> list[list[int]]:
    has_key = "key" in payload
    has_keyword = "keyword" in payload
    if has_key == has_keyword:
        raise error("E03", details={"reason": "key_variant"}, message="Khóa Hill không hợp lệ.")
    if has_key:
        if "m" in payload:
            raise error("E11")
        return _matrix(payload["key"])
    return _keyword(payload["keyword"], _m(payload.get("m", MISSING)))


def _options(value: Any) -> dict[str, object]:
    if value is MISSING:
        return {"stripDiacritics": False, "padChar": "X"}
    if type(value) is not dict or any(key not in {"stripDiacritics", "padChar"} for key in value):
        raise error("E10", details={"field": "options"})
    strip = value.get("stripDiacritics", False)
    pad = value.get("padChar", "X")
    if type(strip) is not bool:
        raise error("E10", details={"field": "stripDiacritics"})
    if type(pad) is not str or len(pad) != 1 or not ("A" <= pad <= "Z"):
        raise error("E10", details={"field": "padChar"})
    return {"stripDiacritics": strip, "padChar": pad}


def validate_transform(payload: dict[str, Any]) -> HillRequest:
    text = payload.get("text", MISSING)
    if type(text) is str and len(text.encode("utf-8")) > MAX_TEXT_BYTES:
        raise error(
            "E06",
            details={"actualBytes": len(text.encode("utf-8")), "maxBytes": MAX_TEXT_BYTES},
        )
    if text is MISSING or text is None or (type(text) is str and text.strip() == ""):
        raise error("E01")
    if type(text) is not str:
        raise error("E11")
    matrix = validate_key(payload)
    options = _options(payload.get("options", MISSING))
    return HillRequest(text=text, matrix=matrix, options=options)
