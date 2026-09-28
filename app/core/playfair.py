"""Pure implementation of the project's canonical 5-by-5 Playfair profile."""

from __future__ import annotations

from typing import Literal

Operation = Literal["encrypt", "decrypt"]
type Matrix = tuple[tuple[str, ...], ...]
type Positions = dict[str, tuple[int, int]]

ALPHABET = "ABCDEFGHIKLMNOPQRSTUVWXYZ"


def _normalize_ascii_letters(value: str) -> str:
    normalized: list[str] = []
    for char in value:
        if "a" <= char <= "z":
            char = chr(ord(char) - 32)
        elif not "A" <= char <= "Z":
            continue
        normalized.append("I" if char == "J" else char)
    return "".join(normalized)


def normalize_keyword(keyword: str) -> str:
    """Normalize a keyword and retain the first occurrence of each letter."""

    letters = _normalize_ascii_letters(keyword)
    if not letters:
        raise ValueError("keyword must contain ASCII letters")
    return "".join(dict.fromkeys(letters))


def normalize_text(text: str) -> str:
    """Normalize Playfair input to uppercase ASCII letters with J mapped to I."""

    return _normalize_ascii_letters(text)


def build_matrix(keyword: str) -> Matrix:
    """Build the row-major key square for a keyword."""

    prefix = normalize_keyword(keyword)
    flattened = prefix + "".join(char for char in ALPHABET if char not in prefix)
    return tuple(tuple(flattened[index : index + 5]) for index in range(0, 25, 5))


def prepare_plaintext(text: str) -> str:
    """Normalize plaintext and split it into deterministic Playfair digraphs."""

    normalized = normalize_text(text)
    if not normalized:
        raise ValueError("plaintext must contain ASCII letters")

    prepared: list[str] = []
    index = 0
    while index < len(normalized):
        current = normalized[index]
        following = normalized[index + 1] if index + 1 < len(normalized) else None

        if following is None or following == current:
            prepared.extend((current, "Q" if current == "X" else "X"))
            index += 1
        else:
            prepared.extend((current, following))
            index += 2

    return "".join(prepared)


def validate_ciphertext(text: str) -> str:
    """Normalize ciphertext and reject streams that cannot form valid digraphs."""

    normalized = normalize_text(text)
    if not normalized:
        raise ValueError("ciphertext must contain ASCII letters")
    if len(normalized) % 2:
        raise ValueError("ciphertext must contain an even number of letters")
    if any(normalized[index] == normalized[index + 1] for index in range(0, len(normalized), 2)):
        raise ValueError("ciphertext must not contain identical-letter digraphs")
    return normalized


def strip_trailing_filler(text: str) -> str:
    """Drop one trailing filler: ``Q`` after ``X``, otherwise a final ``X``."""

    if text.endswith(("XQ", "X")):
        return text[:-1]
    return text


def _matrix_positions(matrix: Matrix) -> Positions:
    return {
        char: (row_index, column_index)
        for row_index, row in enumerate(matrix)
        for column_index, char in enumerate(row)
    }


def _transform_pair(pair: str, matrix: Matrix, positions: Positions, operation: Operation) -> str:
    first_row, first_column = positions[pair[0]]
    second_row, second_column = positions[pair[1]]

    if first_row == second_row:
        direction = 1 if operation == "encrypt" else -1
        return (
            matrix[first_row][(first_column + direction) % 5]
            + matrix[second_row][(second_column + direction) % 5]
        )
    if first_column == second_column:
        direction = 1 if operation == "encrypt" else -1
        return (
            matrix[(first_row + direction) % 5][first_column]
            + matrix[(second_row + direction) % 5][second_column]
        )
    return matrix[first_row][second_column] + matrix[second_row][first_column]


def transform_pair(pair: str, matrix: Matrix, operation: Operation) -> str:
    """Transform one distinct-letter digraph using row, column, or rectangle rules."""

    if operation not in ("encrypt", "decrypt"):
        raise ValueError("operation must be 'encrypt' or 'decrypt'")
    if len(pair) != 2 or pair[0] == pair[1]:
        raise ValueError("pair must contain two distinct letters")
    return _transform_pair(pair, matrix, _matrix_positions(matrix), operation)


def transform_text(text: str, keyword: str, operation: Operation) -> str:
    """Encrypt plaintext or decrypt ciphertext with the canonical Playfair profile."""

    if operation not in ("encrypt", "decrypt"):
        raise ValueError("operation must be 'encrypt' or 'decrypt'")

    matrix = build_matrix(keyword)
    prepared = prepare_plaintext(text) if operation == "encrypt" else validate_ciphertext(text)
    positions = _matrix_positions(matrix)
    result = "".join(
        _transform_pair(prepared[index : index + 2], matrix, positions, operation)
        for index in range(0, len(prepared), 2)
    )
    return strip_trailing_filler(result) if operation == "decrypt" else result
