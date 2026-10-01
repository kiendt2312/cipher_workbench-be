"""Pure Hill cipher arithmetic and text transformations.

The module deliberately contains no HTTP, schema, or persistence concerns.  It
uses row vectors throughout: a block ``x`` is transformed as ``x @ K`` modulo
26.  The structured ``encrypt`` and ``decrypt`` functions return the data that
the Hill API needs, while ``transform_text`` is a small string-only adapter
matching the other core cipher modules.
"""

from __future__ import annotations

import secrets
import unicodedata
from collections.abc import Mapping, Sequence
from itertools import chain, islice
from math import gcd as _gcd
from typing import Any, Literal

MODULUS = 26
MIN_MATRIX_SIZE = 2
MAX_MATRIX_SIZE = 4
MAX_TEXT_BYTES = 5 * 1024 * 1024

Operation = Literal["encrypt", "decrypt"]
type Matrix = list[list[int]]
type WarningItem = dict[str, Any]


class HillError(ValueError):
    """A framework-independent Hill validation or arithmetic error.

    ``code`` and ``details`` are intentionally kept on the domain exception so
    an HTTP adapter can map errors without coupling this module to FastAPI.
    """

    def __init__(self, code: str, message: str, details: Mapping[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(message)


class TransformResult(dict[str, Any]):
    """Mapping returned by :func:`encrypt` and :func:`decrypt`.

    The properties are conveniences for callers that prefer attribute access;
    the mapping itself has the exact ``result``, ``blocks``, ``key`` and
    ``warnings`` fields used by the Hill response contract, plus ``padding``
    on decrypt.
    """

    @property
    def result(self) -> str:
        return self["result"]

    @property
    def blocks(self) -> list[dict[str, list[int]]]:
        return self["blocks"]

    @property
    def key(self) -> dict[str, Any]:
        return self["key"]

    @property
    def warnings(self) -> list[WarningItem]:
        return self["warnings"]


_VIETNAMESE_ACCENTED = frozenset(
    ""
    "ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬ"
    "àáảãạăằắẳẵặâầấẩẫậ"
    "ÈÉẺẼẸÊỀẾỂỄỆ"
    "èéẻẽẹêềếểễệ"
    "ÌÍỈĨỊ"
    "ìíỉĩị"
    "ÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢ"
    "òóỏõọôồốổỗộơờớởỡợ"
    "ÙÚỦŨỤƯỪỨỬỮỰ"
    "ùúủũụưừứửữự"
    "ỲÝỶỸỴ"
    "ỳýỷỹỵ"
    "Đđ"
)


def mod(value: int, modulus: int = MODULUS) -> int:
    """Return a non-negative remainder."""

    if type(modulus) is not int or modulus <= 0:
        raise ValueError("modulus must be a positive integer")
    return value % modulus


def gcd(left: int, right: int) -> int:
    """Return the non-negative greatest common divisor."""

    return _gcd(left, right)


def modular_inverse(value: int, modulus: int = MODULUS) -> int:
    """Return the positive modular inverse or raise when it does not exist."""

    if type(modulus) is not int or modulus <= 1:
        raise ValueError("modulus must be an integer greater than 1")

    remainder, next_remainder = mod(value, modulus), modulus
    coefficient, next_coefficient = 1, 0
    while next_remainder:
        quotient = remainder // next_remainder
        remainder, next_remainder = (
            next_remainder,
            remainder - quotient * next_remainder,
        )
        coefficient, next_coefficient = (
            next_coefficient,
            coefficient - quotient * next_coefficient,
        )

    if remainder != 1:
        raise HillError(
            "E04",
            f"{value} has no inverse modulo {modulus}",
            {"det": mod(value, modulus), "gcd": remainder},
        )
    return mod(coefficient, modulus)


# The shorter spelling is useful to arithmetic-focused callers and keeps the
# implementation discoverable beside the HTML pseudocode's ``modInverse``.
mod_inverse = modular_inverse


def _invalid_matrix(reason: str, **details: Any) -> HillError:
    return HillError("E03", "Khóa ma trận không hợp lệ.", {"reason": reason, **details})


def _validate_m(m: int) -> int:
    if type(m) is not int or not MIN_MATRIX_SIZE <= m <= MAX_MATRIX_SIZE:
        details: dict[str, Any] = {"min": MIN_MATRIX_SIZE, "max": MAX_MATRIX_SIZE}
        if type(m) is int:
            details["m"] = m
        raise HillError("E08", "Cấp ma trận khóa phải từ 2 đến 4.", details)
    return m


def _square_integer_matrix(matrix: Sequence[Sequence[int]]) -> Matrix:
    """Materialize a non-empty square integer matrix for arithmetic helpers."""

    if isinstance(matrix, (str, bytes, bytearray)) or not isinstance(matrix, Sequence):
        raise ValueError("matrix must be a square integer sequence")

    rows = [list(row) if isinstance(row, Sequence) else [] for row in matrix]
    size = len(rows)
    if size == 0 or any(len(row) != size for row in rows):
        raise ValueError("matrix must be a square integer sequence")
    if any(type(value) is not int for row in rows for value in row):
        raise ValueError("matrix must contain integers")
    return rows


def normalize_matrix(matrix: Sequence[Sequence[int]]) -> Matrix:
    """Validate a 2x2-4x4 matrix and normalize every cell modulo 26."""

    if isinstance(matrix, (str, bytes, bytearray)) or not isinstance(matrix, Sequence):
        raise _invalid_matrix("matrix must be a square sequence")

    rows = list(matrix)
    size = len(rows)
    if not MIN_MATRIX_SIZE <= size <= MAX_MATRIX_SIZE:
        details: dict[str, Any] = {
            "min": MIN_MATRIX_SIZE,
            "max": MAX_MATRIX_SIZE,
            "m": size,
        }
        raise HillError("E08", "Cấp ma trận khóa phải từ 2 đến 4.", details)

    normalized: Matrix = []
    for row_index, row in enumerate(rows, start=1):
        if isinstance(row, (str, bytes, bytearray)) or not isinstance(row, Sequence):
            raise _invalid_matrix("row is not a sequence", row=row_index)
        values = list(row)
        if len(values) != size:
            raise _invalid_matrix("matrix is not square", row=row_index)
        normalized_row: list[int] = []
        for column_index, value in enumerate(values, start=1):
            if type(value) is not int:
                raise _invalid_matrix(
                    "matrix cell is not an integer",
                    row=row_index,
                    column=column_index,
                )
            normalized_row.append(mod(value))
        normalized.append(normalized_row)
    return normalized


def minor(matrix: Sequence[Sequence[int]], row: int, column: int) -> Matrix:
    """Return ``matrix`` with one row and column removed."""

    materialized = _square_integer_matrix(matrix)
    size = len(materialized)
    if not 0 <= row < size or not 0 <= column < size:
        raise IndexError("minor row and column are out of range")
    return [
        [value for column_index, value in enumerate(values) if column_index != column]
        for row_index, values in enumerate(materialized)
        if row_index != row
    ]


def determinant(matrix: Sequence[Sequence[int]]) -> int:
    """Return the integer determinant using Laplace expansion."""

    materialized = _square_integer_matrix(matrix)
    size = len(materialized)
    if size == 1:
        return materialized[0][0]
    if size == 2:
        return materialized[0][0] * materialized[1][1] - materialized[0][1] * materialized[1][0]
    return sum(
        (-1 if column % 2 else 1)
        * materialized[0][column]
        * determinant(minor(materialized, 0, column))
        for column in range(size)
    )


det = determinant


def adjugate(matrix: Sequence[Sequence[int]]) -> Matrix:
    """Return the adjugate, reduced to residues in ``0..25``."""

    materialized = _square_integer_matrix(matrix)
    size = len(materialized)
    if size == 1:
        return [[1]]
    return [
        [
            mod(((-1) if (row + column) % 2 else 1) * determinant(minor(materialized, column, row)))
            for column in range(size)
        ]
        for row in range(size)
    ]


def row_times_matrix(vector: Sequence[int], matrix: Sequence[Sequence[int]]) -> list[int]:
    """Multiply a row vector by a square matrix modulo 26."""

    materialized = _square_integer_matrix(matrix)
    values = list(vector) if isinstance(vector, Sequence) else []
    if len(values) != len(materialized) or any(type(value) is not int for value in values):
        raise ValueError("vector length must match matrix size and contain integers")
    return _row_times_normalized_matrix(values, materialized)


def _row_times_normalized_matrix(vector: Sequence[int], matrix: Matrix) -> list[int]:
    """Multiply already validated values without repeating matrix validation."""

    return [
        mod(sum(vector[row] * matrix[row][column] for row in range(len(vector))))
        for column in range(len(vector))
    ]


def matrix_multiply(left: Sequence[Sequence[int]], right: Sequence[Sequence[int]]) -> Matrix:
    """Multiply two same-sized square matrices modulo 26."""

    left_matrix = _square_integer_matrix(left)
    right_matrix = _square_integer_matrix(right)
    if len(left_matrix) != len(right_matrix):
        raise ValueError("matrix sizes must match")
    size = len(left_matrix)
    return [
        [
            mod(sum(left_matrix[row][inner] * right_matrix[inner][column] for inner in range(size)))
            for column in range(size)
        ]
        for row in range(size)
    ]


def inverse_mod26(matrix: Sequence[Sequence[int]]) -> Matrix:
    """Return the modular inverse of a valid Hill key."""

    normalized = normalize_matrix(matrix)
    det_value = mod(determinant(normalized))
    divisor = gcd(det_value, MODULUS)
    if divisor != 1:
        raise HillError(
            "E04",
            f"Khóa không khả nghịch: det K mod 26 = {det_value}.",
            {"det": det_value, "gcd": divisor, "divisor": 2 if det_value % 2 == 0 else 13},
        )
    determinant_inverse = modular_inverse(det_value)
    return [[mod(determinant_inverse * value) for value in row] for row in adjugate(normalized)]


inverse = inverse_mod26


def normalize_keyword(keyword: str, m: int) -> Matrix:
    """Convert an exact ASCII keyword to a row-major Hill matrix."""

    size = _validate_m(m)
    if type(keyword) is not str:
        actual: int | None = None
    else:
        actual = sum("A" <= char <= "Z" or "a" <= char <= "z" for char in keyword)
    expected = size * size
    if type(keyword) is not str or len(keyword) != expected or actual != expected:
        raise HillError(
            "E09",
            f"Từ khóa cần đúng {expected} chữ cái, hiện có {actual}.",
            {"m": size, "expected": expected, "actual": actual},
        )

    values = [ord(char.upper()) - ord("A") for char in keyword]
    return [values[offset : offset + size] for offset in range(0, expected, size)]


keyword_to_matrix = normalize_keyword


def normalize_key(
    key: Sequence[Sequence[int]] | None = None,
    *,
    keyword: str | None = None,
    m: int | None = None,
) -> Matrix:
    """Normalize either a matrix key or an explicitly sized keyword key."""

    if key is not None and keyword is not None:
        raise _invalid_matrix("key and keyword are mutually exclusive")
    if keyword is not None:
        if m is None:
            raise HillError("E08", "Cấp ma trận khóa phải từ 2 đến 4.", {"min": 2, "max": 4})
        return normalize_keyword(keyword, m)
    if key is None:
        raise _invalid_matrix("missing key")

    normalized = normalize_matrix(key)
    if m is not None:
        _validate_m(m)
        if m != len(normalized):
            raise _invalid_matrix("matrix size does not match m")
    return normalized


def _analysis_for_matrix(matrix: Matrix) -> dict[str, Any]:
    det_value = mod(determinant(matrix))
    divisor = gcd(det_value, MODULUS)
    if divisor != 1:
        raise HillError(
            "E04",
            f"Khóa không khả nghịch: det K mod 26 = {det_value}, chia hết cho "
            f"{2 if det_value % 2 == 0 else 13}.",
            {"det": det_value, "gcd": divisor, "divisor": 2 if det_value % 2 == 0 else 13},
        )
    determinant_inverse = modular_inverse(det_value)
    adjugate_matrix = adjugate(matrix)
    inverse_matrix = [
        [mod(determinant_inverse * value) for value in row] for row in adjugate_matrix
    ]
    return {
        "matrix": [row[:] for row in matrix],
        "m": len(matrix),
        "det": det_value,
        "gcd": divisor,
        "detInverse": determinant_inverse,
        "adjugate": adjugate_matrix,
        "inverse": inverse_matrix,
    }


def analyze_key(
    key: Sequence[Sequence[int]] | None = None,
    *,
    keyword: str | None = None,
    m: int | None = None,
) -> dict[str, Any]:
    """Normalize and analyze a matrix or keyword key."""

    return _analysis_for_matrix(normalize_key(key, keyword=keyword, m=m))


analyze = analyze_key


def _identity(size: int) -> Matrix:
    return [[1 if row == column else 0 for column in range(size)] for row in range(size)]


def warnings_for_key(
    analysis_or_key: Mapping[str, Any] | Sequence[Sequence[int]],
) -> list[WarningItem]:
    """Return W03 when a key is the identity or self-inverse."""

    if isinstance(analysis_or_key, Mapping) and "matrix" in analysis_or_key:
        analysis = dict(analysis_or_key)
    else:
        analysis = analyze_key(analysis_or_key)  # type: ignore[arg-type]

    matrix = analysis["matrix"]
    if matrix == _identity(analysis["m"]):
        reason = "identity"
    elif matrix == analysis["inverse"]:
        reason = "self_inverse"
    else:
        return []
    return [
        {
            "code": "W03",
            "message": "Khóa này là ma trận đơn vị hoặc tự nghịch đảo, không đảm bảo bí mật.",
            "details": {"reason": reason},
        }
    ]


key_warnings = warnings_for_key


def random_key(m: int, rng: Any | None = None) -> Matrix:
    """Generate a non-identity invertible key of order ``m``.

    ``rng`` is injectable for deterministic unit tests and only needs a
    ``randrange(stop)`` method.  Production calls use ``secrets.SystemRandom``.
    """

    size = _validate_m(m)
    source = rng if rng is not None else secrets.SystemRandom()
    identity = _identity(size)
    while True:
        candidate = [[source.randrange(MODULUS) for _ in range(size)] for _ in range(size)]
        if candidate == identity:
            continue
        try:
            _analysis_for_matrix(candidate)
        except HillError as error:
            if error.code == "E04":
                continue
            raise
        return candidate


generate_random_key = random_key
random_matrix = random_key


def random_key_result(m: int, rng: Any | None = None) -> dict[str, Any]:
    """Return the analysis and warnings for one generated key."""

    matrix = random_key(m, rng=rng)
    analysis = analyze_key(matrix)
    return {"result": analysis, "warnings": warnings_for_key(analysis)}


def _is_ascii_letter(char: str) -> bool:
    return "A" <= char <= "Z" or "a" <= char <= "z"


def _is_mark(char: str) -> bool:
    return unicodedata.category(char).startswith("M")


def _is_vietnamese_cluster(cluster: str) -> bool:
    return unicodedata.normalize("NFC", cluster) in _VIETNAMESE_ACCENTED


def _strip_vietnamese_cluster(cluster: str) -> str:
    normalized = unicodedata.normalize("NFD", cluster)
    base = normalized[0]
    if base == "Đ":
        base = "D"
    elif base == "đ":
        base = "d"
    if not _is_ascii_letter(base):
        raise ValueError("invalid Vietnamese cluster")
    return base.upper() if cluster[0].isupper() else base.lower()


class _PreparedText:
    __slots__ = ("accented_count", "parts", "slots", "uppercase", "values")

    def __init__(self) -> None:
        self.parts: list[str] = []
        self.values: list[int] = []
        self.slots: list[int] = []
        self.uppercase: list[bool] = []
        self.accented_count = 0


def _prepare_text(text: str, strip_diacritics: bool) -> _PreparedText:
    prepared = _PreparedText()
    if text.isascii():
        prepared.parts = list(text)
        for part_index, source_char in enumerate(prepared.parts):
            ordinal = ord(source_char)
            if 65 <= ordinal <= 90:
                prepared.values.append(ordinal - 65)
                prepared.slots.append(part_index)
                prepared.uppercase.append(True)
            elif 97 <= ordinal <= 122:
                prepared.values.append(ordinal - 97)
                prepared.slots.append(part_index)
                prepared.uppercase.append(False)
        return prepared

    index = 0
    while index < len(text):
        start = index
        index += 1
        while index < len(text) and _is_mark(text[index]):
            index += 1
        cluster = text[start:index]
        part_index = len(prepared.parts)
        prepared.parts.append(cluster)

        if len(cluster) == 1 and _is_ascii_letter(cluster):
            source_char = cluster
            prepared.values.append(ord(source_char.upper()) - ord("A"))
            prepared.slots.append(part_index)
            prepared.uppercase.append("A" <= source_char <= "Z")
        elif _is_vietnamese_cluster(cluster):
            if strip_diacritics:
                stripped = _strip_vietnamese_cluster(cluster)
                prepared.values.append(ord(stripped.upper()) - ord("A"))
                prepared.slots.append(part_index)
                prepared.uppercase.append("A" <= stripped <= "Z")
            else:
                prepared.accented_count += 1
    return prepared


def _transform_blocks(
    values: list[int], matrix: Matrix
) -> tuple[list[dict[str, list[int]]], list[int] | None]:
    """Transform blocks with small-order fast paths for large Hill text."""

    size = len(matrix)
    if size == 2:
        k00, k01 = matrix[0]
        k10, k11 = matrix[1]
        output_table = [
            (
                (first * k00 + second * k10) % MODULUS,
                (first * k01 + second * k11) % MODULUS,
            )
            for first in range(MODULUS)
            for second in range(MODULUS)
        ]
        blocks = [
            {
                "input": [values[offset], values[offset + 1]],
                "output": list(output_table[values[offset] * MODULUS + values[offset + 1]]),
            }
            for offset in range(0, len(values), 2)
        ]
        return blocks, None

    block_count = len(values) // size
    blocks: list[dict[str, list[int]]] = [None] * block_count  # type: ignore[list-item]
    transformed = [0] * len(values)
    if size == 3:
        k00, k01, k02 = matrix[0]
        k10, k11, k12 = matrix[1]
        k20, k21, k22 = matrix[2]
        for block_index, offset in enumerate(range(0, len(values), 3)):
            first, second, third = values[offset : offset + 3]
            output_0 = (first * k00 + second * k10 + third * k20) % MODULUS
            output_1 = (first * k01 + second * k11 + third * k21) % MODULUS
            output_2 = (first * k02 + second * k12 + third * k22) % MODULUS
            blocks[block_index] = {
                "input": [first, second, third],
                "output": [output_0, output_1, output_2],
            }
            transformed[offset] = output_0
            transformed[offset + 1] = output_1
            transformed[offset + 2] = output_2
        return blocks, transformed

    k00, k01, k02, k03 = matrix[0]
    k10, k11, k12, k13 = matrix[1]
    k20, k21, k22, k23 = matrix[2]
    k30, k31, k32, k33 = matrix[3]
    for block_index, offset in enumerate(range(0, len(values), 4)):
        first, second, third, fourth = values[offset : offset + 4]
        output_0 = (first * k00 + second * k10 + third * k20 + fourth * k30) % MODULUS
        output_1 = (first * k01 + second * k11 + third * k21 + fourth * k31) % MODULUS
        output_2 = (first * k02 + second * k12 + third * k22 + fourth * k32) % MODULUS
        output_3 = (first * k03 + second * k13 + third * k23 + fourth * k33) % MODULUS
        blocks[block_index] = {
            "input": [first, second, third, fourth],
            "output": [output_0, output_1, output_2, output_3],
        }
        transformed[offset] = output_0
        transformed[offset + 1] = output_1
        transformed[offset + 2] = output_2
        transformed[offset + 3] = output_3
    return blocks, transformed


def _validate_text(text: str) -> None:
    if type(text) is not str:
        raise HillError("E11", "Dữ liệu gửi lên không hợp lệ.", {})
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as error:
        raise HillError("E11", "Dữ liệu gửi lên không hợp lệ.", {}) from error


def validate_text_size(text: str, max_bytes: int = MAX_TEXT_BYTES) -> int:
    """Return UTF-8 byte length and reject text above the supplied limit."""

    _validate_text(text)
    actual_bytes = len(text.encode("utf-8"))
    if actual_bytes > max_bytes:
        raise HillError(
            "E06",
            "Văn bản vượt quá giới hạn 5 MiB.",
            {"actualBytes": actual_bytes, "maxBytes": max_bytes},
        )
    return actual_bytes


def _resolve_options(
    strip_diacritics: bool,
    pad_char: str,
    options: Mapping[str, Any] | None,
) -> tuple[bool, str]:
    resolved_strip = strip_diacritics
    resolved_pad = pad_char
    if options is not None:
        if not isinstance(options, Mapping):
            raise HillError("E10", "Tùy chọn Hill không hợp lệ.", {"field": "options"})
        allowed = {"stripDiacritics", "padChar", "strip_diacritics", "pad_char"}
        unknown = next((field for field in options if field not in allowed), None)
        if unknown is not None:
            raise HillError("E10", "Tùy chọn Hill không hợp lệ.", {"field": unknown})
        if "stripDiacritics" in options and "strip_diacritics" in options:
            raise HillError("E10", "Tùy chọn Hill không hợp lệ.", {"field": "stripDiacritics"})
        if "padChar" in options and "pad_char" in options:
            raise HillError("E10", "Tùy chọn Hill không hợp lệ.", {"field": "padChar"})
        if "stripDiacritics" in options:
            resolved_strip = options["stripDiacritics"]
        elif "strip_diacritics" in options:
            resolved_strip = options["strip_diacritics"]
        if "padChar" in options:
            resolved_pad = options["padChar"]
        elif "pad_char" in options:
            resolved_pad = options["pad_char"]

    if type(resolved_strip) is not bool:
        raise HillError("E10", "Tùy chọn Hill không hợp lệ.", {"field": "stripDiacritics"})
    if type(resolved_pad) is not str or len(resolved_pad) != 1 or not "A" <= resolved_pad <= "Z":
        raise HillError("E10", "Tùy chọn Hill không hợp lệ.", {"field": "padChar"})
    return resolved_strip, resolved_pad


def _transform(
    text: str,
    key: Sequence[Sequence[int]] | None,
    operation: Operation,
    *,
    keyword: str | None,
    m: int | None,
    strip_diacritics: bool,
    pad_char: str,
    options: Mapping[str, Any] | None,
) -> TransformResult:
    if operation not in ("encrypt", "decrypt"):
        raise ValueError("operation must be 'encrypt' or 'decrypt'")
    _validate_text(text)
    if not text.strip():
        raise HillError("E01", "Nhập văn bản hoặc tải file .txt để bắt đầu.", {})

    normalized_key = normalize_key(key, keyword=keyword, m=m)
    resolved_strip, resolved_pad = _resolve_options(strip_diacritics, pad_char, options)
    analysis = _analysis_for_matrix(normalized_key)
    prepared = _prepare_text(text, resolved_strip)
    if not prepared.values:
        raise HillError("E02", "Văn bản không có chữ cái nào để mã hóa. Hill chỉ xử lý A-Z.", {})

    matrix = normalized_key
    pad_count = 0
    if operation == "decrypt":
        if len(prepared.values) % len(matrix):
            raise HillError(
                "E05",
                f"Bản mã có {len(prepared.values)} chữ cái, không chia hết cho m = {len(matrix)}.",
                {"n": len(prepared.values), "m": len(matrix)},
            )
        matrix = analysis["inverse"]
    else:
        pad_count = (-len(prepared.values)) % len(matrix)

    values = prepared.values + [ord(resolved_pad) - ord("A")] * pad_count
    blocks, transformed = _transform_blocks(values, matrix)
    if transformed is None:
        output_values = chain.from_iterable(block["output"] for block in blocks)
        original_outputs = islice(output_values, len(prepared.values))
    else:
        output_values = iter(transformed)
        original_outputs = islice(output_values, len(prepared.values))

    for slot, value, uppercase in zip(
        prepared.slots,
        original_outputs,
        prepared.uppercase,
        strict=True,
    ):
        output_char = chr(value + ord("A"))
        prepared.parts[slot] = output_char if uppercase else output_char.lower()

    result = "".join(prepared.parts)
    if pad_count:
        result += "".join(chr(value + ord("A")) for value in islice(output_values, pad_count))
    padding = (
        _detect_padding(prepared, resolved_pad, len(matrix)) if operation == "decrypt" else None
    )

    warnings: list[WarningItem] = []
    if pad_count:
        warnings.append(
            {
                "code": "W01",
                "message": (
                    f"Đã thêm {pad_count} ký tự {resolved_pad} vào cuối để đủ khối "
                    f"{len(matrix)} chữ."
                ),
                "details": {"count": pad_count, "char": resolved_pad, "m": len(matrix)},
            }
        )
    if prepared.accented_count and not resolved_strip:
        warnings.append(
            {
                "code": "W02",
                "message": (
                    f"{prepared.accented_count} chữ có dấu được giữ nguyên. Bật "
                    '"Bỏ dấu tiếng Việt" để mã hóa chúng.'
                ),
                "details": {"count": prepared.accented_count},
            }
        )
    warnings.extend(warnings_for_key(analysis))
    transformed_result = TransformResult(
        {
            "result": result,
            "blocks": blocks,
            "key": analysis,
            "warnings": warnings,
        }
    )
    if padding is not None:
        transformed_result["padding"] = padding
    return transformed_result


def _detect_padding(prepared: _PreparedText, pad_char: str, size: int) -> dict[str, Any]:
    """Find up to ``size - 1`` trailing ``pad_char`` letters in decrypted ``prepared`` text."""

    letter_count = len(prepared.slots)
    count = 0
    while (
        count < min(size - 1, letter_count)
        and prepared.parts[prepared.slots[letter_count - 1 - count]].upper() == pad_char
    ):
        count += 1
    positions = list(range(letter_count - count, letter_count))
    for position in positions:
        prepared.parts[prepared.slots[position]] = ""
    return {"count": count, "positions": positions, "filtered": "".join(prepared.parts)}


def encrypt(
    text: str,
    key: Sequence[Sequence[int]] | None = None,
    *,
    keyword: str | None = None,
    m: int | None = None,
    strip_diacritics: bool = False,
    pad_char: str = "X",
    options: Mapping[str, Any] | None = None,
) -> TransformResult:
    """Encrypt text and return the result, blocks, normalized key, and warnings."""

    return _transform(
        text,
        key,
        "encrypt",
        keyword=keyword,
        m=m,
        strip_diacritics=strip_diacritics,
        pad_char=pad_char,
        options=options,
    )


def decrypt(
    text: str,
    key: Sequence[Sequence[int]] | None = None,
    *,
    keyword: str | None = None,
    m: int | None = None,
    strip_diacritics: bool = False,
    pad_char: str = "X",
    options: Mapping[str, Any] | None = None,
) -> TransformResult:
    """Decrypt text and return the result, blocks, normalized key, and warnings."""

    return _transform(
        text,
        key,
        "decrypt",
        keyword=keyword,
        m=m,
        strip_diacritics=strip_diacritics,
        pad_char=pad_char,
        options=options,
    )


def transform_text(
    text: str,
    key: Sequence[Sequence[int]] | None,
    operation: Operation,
    *,
    keyword: str | None = None,
    m: int | None = None,
    strip_diacritics: bool = False,
    pad_char: str = "X",
    options: Mapping[str, Any] | None = None,
) -> str:
    """Return only the transformed text for parity with the other core modules."""

    return _transform(
        text,
        key,
        operation,
        keyword=keyword,
        m=m,
        strip_diacritics=strip_diacritics,
        pad_char=pad_char,
        options=options,
    )["result"]


def encrypt_text(
    text: str,
    key: Sequence[Sequence[int]] | None,
    **kwargs: Any,
) -> str:
    """Return only encrypted text."""

    return transform_text(text, key, "encrypt", **kwargs)


def decrypt_text(
    text: str,
    key: Sequence[Sequence[int]] | None,
    **kwargs: Any,
) -> str:
    """Return only decrypted text."""

    return transform_text(text, key, "decrypt", **kwargs)
