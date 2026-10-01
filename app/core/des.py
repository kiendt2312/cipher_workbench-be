"""DES (FIPS 46-3) implemented from its tables for teaching, with ECB/CBC and PKCS#7.

Bits are numbered from 1 at the most significant end, as in the lecture tables:
entry ``i`` of a permutation table names the input bit that becomes output bit ``i``.
The canonical tables below are the single source of truth. The fast block path
uses lookup tables derived from them at import time; :func:`trace_block` walks
the canonical tables step by step so every intermediate value can be shown.
"""

from __future__ import annotations

import re
import struct
from collections.abc import Callable
from typing import Any, Literal

Mode = Literal["ECB", "CBC"]
Operation = Literal["encrypt", "decrypt"]

ASCII_WHITESPACE = " \t\r\n\f\v"
BLOCK_BYTES = 8
KEY_HEX_LENGTH = 16

PC1 = (
    57, 49, 41, 33, 25, 17, 9,
    1, 58, 50, 42, 34, 26, 18,
    10, 2, 59, 51, 43, 35, 27,
    19, 11, 3, 60, 52, 44, 36,
    63, 55, 47, 39, 31, 23, 15,
    7, 62, 54, 46, 38, 30, 22,
    14, 6, 61, 53, 45, 37, 29,
    21, 13, 5, 28, 20, 12, 4,
)  # fmt: skip
PC2 = (
    14, 17, 11, 24, 1, 5,
    3, 28, 15, 6, 21, 10,
    23, 19, 12, 4, 26, 8,
    16, 7, 27, 20, 13, 2,
    41, 52, 31, 37, 47, 55,
    30, 40, 51, 45, 33, 48,
    44, 49, 39, 56, 34, 53,
    46, 42, 50, 36, 29, 32,
)  # fmt: skip
LS = (1, 1, 2, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 2, 1)
IP = (
    58, 50, 42, 34, 26, 18, 10, 2,
    60, 52, 44, 36, 28, 20, 12, 4,
    62, 54, 46, 38, 30, 22, 14, 6,
    64, 56, 48, 40, 32, 24, 16, 8,
    57, 49, 41, 33, 25, 17, 9, 1,
    59, 51, 43, 35, 27, 19, 11, 3,
    61, 53, 45, 37, 29, 21, 13, 5,
    63, 55, 47, 39, 31, 23, 15, 7,
)  # fmt: skip
IP_INV = (
    40, 8, 48, 16, 56, 24, 64, 32,
    39, 7, 47, 15, 55, 23, 63, 31,
    38, 6, 46, 14, 54, 22, 62, 30,
    37, 5, 45, 13, 53, 21, 61, 29,
    36, 4, 44, 12, 52, 20, 60, 28,
    35, 3, 43, 11, 51, 19, 59, 27,
    34, 2, 42, 10, 50, 18, 58, 26,
    33, 1, 41, 9, 49, 17, 57, 25,
)  # fmt: skip
E = (
    32, 1, 2, 3, 4, 5,
    4, 5, 6, 7, 8, 9,
    8, 9, 10, 11, 12, 13,
    12, 13, 14, 15, 16, 17,
    16, 17, 18, 19, 20, 21,
    20, 21, 22, 23, 24, 25,
    24, 25, 26, 27, 28, 29,
    28, 29, 30, 31, 32, 1,
)  # fmt: skip
P = (
    16, 7, 20, 21, 29, 12, 28, 17,
    1, 15, 23, 26, 5, 18, 31, 10,
    2, 8, 24, 14, 32, 27, 3, 9,
    19, 13, 30, 6, 22, 11, 4, 25,
)  # fmt: skip
SBOXES = (
    (
        (14, 4, 13, 1, 2, 15, 11, 8, 3, 10, 6, 12, 5, 9, 0, 7),
        (0, 15, 7, 4, 14, 2, 13, 1, 10, 6, 12, 11, 9, 5, 3, 8),
        (4, 1, 14, 8, 13, 6, 2, 11, 15, 12, 9, 7, 3, 10, 5, 0),
        (15, 12, 8, 2, 4, 9, 1, 7, 5, 11, 3, 14, 10, 0, 6, 13),
    ),
    (
        (15, 1, 8, 14, 6, 11, 3, 4, 9, 7, 2, 13, 12, 0, 5, 10),
        (3, 13, 4, 7, 15, 2, 8, 14, 12, 0, 1, 10, 6, 9, 11, 5),
        (0, 14, 7, 11, 10, 4, 13, 1, 5, 8, 12, 6, 9, 3, 2, 15),
        (13, 8, 10, 1, 3, 15, 4, 2, 11, 6, 7, 12, 0, 5, 14, 9),
    ),
    (
        (10, 0, 9, 14, 6, 3, 15, 5, 1, 13, 12, 7, 11, 4, 2, 8),
        (13, 7, 0, 9, 3, 4, 6, 10, 2, 8, 5, 14, 12, 11, 15, 1),
        (13, 6, 4, 9, 8, 15, 3, 0, 11, 1, 2, 12, 5, 10, 14, 7),
        (1, 10, 13, 0, 6, 9, 8, 7, 4, 15, 14, 3, 11, 5, 2, 12),
    ),
    (
        (7, 13, 14, 3, 0, 6, 9, 10, 1, 2, 8, 5, 11, 12, 4, 15),
        (13, 8, 11, 5, 6, 15, 0, 3, 4, 7, 2, 12, 1, 10, 14, 9),
        (10, 6, 9, 0, 12, 11, 7, 13, 15, 1, 3, 14, 5, 2, 8, 4),
        (3, 15, 0, 6, 10, 1, 13, 8, 9, 4, 5, 11, 12, 7, 2, 14),
    ),
    (
        (2, 12, 4, 1, 7, 10, 11, 6, 8, 5, 3, 15, 13, 0, 14, 9),
        (14, 11, 2, 12, 4, 7, 13, 1, 5, 0, 15, 10, 3, 9, 8, 6),
        (4, 2, 1, 11, 10, 13, 7, 8, 15, 9, 12, 5, 6, 3, 0, 14),
        (11, 8, 12, 7, 1, 14, 2, 13, 6, 15, 0, 9, 10, 4, 5, 3),
    ),
    (
        (12, 1, 10, 15, 9, 2, 6, 8, 0, 13, 3, 4, 14, 7, 5, 11),
        (10, 15, 4, 2, 7, 12, 9, 5, 6, 1, 13, 14, 0, 11, 3, 8),
        (9, 14, 15, 5, 2, 8, 12, 3, 7, 0, 4, 10, 1, 13, 11, 6),
        (4, 3, 2, 12, 9, 5, 15, 10, 11, 14, 1, 7, 6, 0, 8, 13),
    ),
    (
        (4, 11, 2, 14, 15, 0, 8, 13, 3, 12, 9, 7, 5, 10, 6, 1),
        (13, 0, 11, 7, 4, 9, 1, 10, 14, 3, 5, 12, 2, 15, 8, 6),
        (1, 4, 11, 13, 12, 3, 7, 14, 10, 15, 6, 8, 0, 5, 9, 2),
        (6, 11, 13, 8, 1, 4, 10, 7, 9, 5, 0, 15, 14, 2, 3, 12),
    ),
    (
        (13, 2, 8, 4, 6, 15, 11, 1, 10, 9, 3, 14, 5, 0, 12, 7),
        (1, 15, 13, 8, 10, 3, 7, 4, 12, 5, 6, 11, 0, 14, 9, 2),
        (7, 11, 4, 1, 9, 12, 14, 2, 0, 6, 10, 13, 15, 3, 5, 8),
        (2, 1, 14, 7, 4, 10, 8, 13, 15, 12, 9, 0, 3, 5, 6, 11),
    ),
)

_PARITY_MASK = 0xFEFEFEFEFEFEFEFE
_WEAK_KEYS = frozenset(
    key & _PARITY_MASK
    for key in (0x0101010101010101, 0xFEFEFEFEFEFEFEFE, 0xE0E0E0E0F1F1F1F1, 0x1F1F1F1F0E0E0E0E)
)
_SEMI_WEAK_KEYS = frozenset(
    key & _PARITY_MASK
    for key in (
        0x011F011F010E010E,
        0x1F011F010E010E01,
        0x01E001E001F101F1,
        0xE001E001F101F101,
        0x01FE01FE01FE01FE,
        0xFE01FE01FE01FE01,
        0x1FE01FE00EF10EF1,
        0xE01FE01FF10EF10E,
        0x1FFE1FFE0EFE0EFE,
        0xFE1FFE1FFE0EFE0E,
        0xE0FEE0FEF1FEF1FE,
        0xFEE0FEE0FEF1FEF1,
    )
)
_WHITESPACE_TABLE = str.maketrans("", "", ASCII_WHITESPACE)
_HEX = re.compile(r"[0-9A-Fa-f]*")  # ASCII ranges only; rejects "0x", "_" and Unicode digits.


class DesError(ValueError):
    """A DES domain error identified by its scope code (E01-E09), never carrying user data."""

    def __init__(self, code: str, count: int | None = None) -> None:
        self.code = code
        self.count = count
        super().__init__(code)


# --- canonical bit operations --------------------------------------------------


def permute(value: int, table: tuple[int, ...], width: int) -> int:
    """Apply a 1-based permutation table to the ``width``-bit integer ``value``."""

    result = 0
    for position in table:
        result = (result << 1) | ((value >> (width - position)) & 1)
    return result


def rotate_left(half: int, shift: int) -> int:
    """Rotate a 28-bit key half left by ``shift`` bits."""

    return ((half << shift) | (half >> (28 - shift))) & 0xFFFFFFF


def _key_steps(key: int) -> list[tuple[int, int, int]]:
    """Return ``(Cn, Dn, Kn)`` for n = 1..16."""

    k56 = permute(key, PC1, 64)
    c, d = k56 >> 28, k56 & 0xFFFFFFF
    steps = []
    for shift in LS:
        c, d = rotate_left(c, shift), rotate_left(d, shift)
        steps.append((c, d, permute((c << 28) | d, PC2, 56)))
    return steps


def key_schedule(key: int) -> tuple[int, ...]:
    """Return the sixteen 48-bit subkeys K1..K16 of a 64-bit key."""

    return tuple(subkey for _, _, subkey in _key_steps(key))


def _sbox_lookup(index: int, six_bits: int) -> tuple[int, int, int]:
    row = ((six_bits >> 4) & 0b10) | (six_bits & 1)
    col = (six_bits >> 1) & 0xF
    return row, col, SBOXES[index][row][col]


def _substitute(x48: int) -> tuple[int, list[tuple[int, int, int]]]:
    output = 0
    lookups = []
    for index in range(8):
        row, col, value = _sbox_lookup(index, (x48 >> (42 - 6 * index)) & 0x3F)
        lookups.append((row, col, value))
        output = (output << 4) | value
    return output, lookups


def f_function(right: int, subkey: int) -> int:
    """The round function f(R, K) = P(S(E(R) xor K)) on canonical tables."""

    substituted, _ = _substitute(permute(right, E, 32) ^ subkey)
    return permute(substituted, P, 32)


# --- fast block path (lookup tables derived from the canonical ones) -------------


def _sp_table(index: int) -> tuple[int, ...]:
    shift = 28 - 4 * index
    return tuple(permute(_sbox_lookup(index, bits)[2] << shift, P, 32) for bits in range(64))


def _byte_tables(table: tuple[int, ...]) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(permute(value << (56 - 8 * byte), table, 64) for value in range(256))
        for byte in range(8)
    )


_SP = tuple(_sp_table(index) for index in range(8))
_IP_BYTES = _byte_tables(IP)
_FP_BYTES = _byte_tables(IP_INV)


def _round_keys(key: int, operation: Operation) -> tuple[tuple[int, ...], ...]:
    subkeys = key_schedule(key)
    if operation == "decrypt":
        subkeys = subkeys[::-1]
    return tuple(tuple((subkey >> (42 - 6 * i)) & 0x3F for i in range(8)) for subkey in subkeys)


def _block_function(round_keys: tuple[tuple[int, ...], ...]) -> Callable[[int], int]:
    """Build a closure transforming one 64-bit block with locals bound for speed."""

    ip0, ip1, ip2, ip3, ip4, ip5, ip6, ip7 = _IP_BYTES
    fp0, fp1, fp2, fp3, fp4, fp5, fp6, fp7 = _FP_BYTES
    s0, s1, s2, s3, s4, s5, s6, s7 = _SP

    def transform(block: int) -> int:
        t = (
            ip0[block >> 56]
            | ip1[(block >> 48) & 0xFF]
            | ip2[(block >> 40) & 0xFF]
            | ip3[(block >> 32) & 0xFF]
            | ip4[(block >> 24) & 0xFF]
            | ip5[(block >> 16) & 0xFF]
            | ip6[(block >> 8) & 0xFF]
            | ip7[block & 0xFF]
        )
        left = t >> 32
        right = t & 0xFFFFFFFF
        for k0, k1, k2, k3, k4, k5, k6, k7 in round_keys:
            # E(R) as a 34-bit window R32 R1..R32 R1; each S-box reads six bits of it.
            x = ((right & 1) << 33) | (right << 1) | (right >> 31)
            left, right = (
                right,
                left
                ^ (
                    s0[((x >> 28) & 0x3F) ^ k0]
                    | s1[((x >> 24) & 0x3F) ^ k1]
                    | s2[((x >> 20) & 0x3F) ^ k2]
                    | s3[((x >> 16) & 0x3F) ^ k3]
                    | s4[((x >> 12) & 0x3F) ^ k4]
                    | s5[((x >> 8) & 0x3F) ^ k5]
                    | s6[((x >> 4) & 0x3F) ^ k6]
                    | s7[(x & 0x3F) ^ k7]
                ),
            )
        t = (right << 32) | left
        return (
            fp0[t >> 56]
            | fp1[(t >> 48) & 0xFF]
            | fp2[(t >> 40) & 0xFF]
            | fp3[(t >> 32) & 0xFF]
            | fp4[(t >> 24) & 0xFF]
            | fp5[(t >> 16) & 0xFF]
            | fp6[(t >> 8) & 0xFF]
            | fp7[t & 0xFF]
        )

    return transform


def _blocks(data: bytes) -> tuple[int, ...]:
    return struct.unpack(f">{len(data) // BLOCK_BYTES}Q", data)


def _pack(blocks: list[int]) -> bytes:
    return struct.pack(f">{len(blocks)}Q", *blocks)


def encrypt_bytes(data: bytes, key: int, mode: Mode, iv: int | None) -> bytes:
    """Encrypt whole 8-byte blocks in ECB or CBC (``iv`` required for CBC)."""

    transform = _block_function(_round_keys(key, "encrypt"))
    if mode == "ECB":
        return _pack([transform(block) for block in _blocks(data)])
    previous = iv
    output = []
    for block in _blocks(data):
        previous = transform(block ^ previous)
        output.append(previous)
    return _pack(output)


def decrypt_bytes(data: bytes, key: int, mode: Mode, iv: int | None) -> bytes:
    """Decrypt whole 8-byte blocks in ECB or CBC (``iv`` required for CBC)."""

    transform = _block_function(_round_keys(key, "decrypt"))
    blocks = _blocks(data)
    if mode == "ECB":
        return _pack([transform(block) for block in blocks])
    previous = (iv, *blocks)[:-1]
    return _pack(
        [transform(block) ^ chained for block, chained in zip(blocks, previous, strict=True)]
    )


# --- padding, encoding and parsing -------------------------------------------------


def pkcs7_pad(data: bytes) -> bytes:
    """Append 1-8 bytes of value n; a full final block still gets a padding block."""

    count = BLOCK_BYTES - len(data) % BLOCK_BYTES
    return data + bytes([count]) * count


def pkcs7_unpad(data: bytes) -> bytes:
    """Remove PKCS#7 padding or raise E07."""

    if not data:
        raise DesError("E07")
    count = data[-1]
    if not 1 <= count <= BLOCK_BYTES or data[-count:] != bytes([count]) * count:
        raise DesError("E07")
    return data[:-count]


def decode_utf8(data: bytes) -> str:
    """Strictly decode UTF-8 or raise E08."""

    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise DesError("E08") from None


def strip_whitespace(value: str) -> str:
    """Remove ASCII whitespace (space, tab, CR, LF, FF, VT) anywhere in ``value``."""

    return value.translate(_WHITESPACE_TABLE)


def _is_hex(value: str) -> bool:
    return _HEX.fullmatch(value) is not None


def parse_key(value: str) -> int:
    """Normalize a 16-hex key; E02 empty, E03 non-hex, E04 wrong length."""

    normalized = strip_whitespace(value)
    if normalized == "":
        raise DesError("E02")
    if not _is_hex(normalized):
        raise DesError("E03")
    if len(normalized) != KEY_HEX_LENGTH:
        raise DesError("E04", len(normalized))
    return int(normalized, 16)


def parse_iv(value: str) -> int:
    """Normalize a 16-hex CBC IV or raise E09."""

    normalized = strip_whitespace(value)
    if len(normalized) != KEY_HEX_LENGTH or not _is_hex(normalized):
        raise DesError("E09")
    return int(normalized, 16)


def parse_hex(value: str) -> bytes:
    """Normalize hex data of whole blocks; E01 empty, E05 non-hex, E06 not a multiple of 16."""

    normalized = strip_whitespace(value)
    if normalized == "":
        raise DesError("E01")
    if not _is_hex(normalized):
        raise DesError("E05")
    if len(normalized) % KEY_HEX_LENGTH:
        raise DesError("E06", len(normalized))
    return bytes.fromhex(normalized)


def parse_block(value: str) -> int:
    """Normalize exactly one 16-hex block for tracing or raise E13."""

    normalized = strip_whitespace(value)
    if len(normalized) != KEY_HEX_LENGTH or not _is_hex(normalized):
        raise DesError("E13")
    return int(normalized, 16)


def key_strength(key: int) -> Literal["weak", "semi_weak"] | None:
    """Classify a key against the weak and semi-weak lists, ignoring parity bits."""

    masked = key & _PARITY_MASK
    if masked in _WEAK_KEYS:
        return "weak"
    if masked in _SEMI_WEAK_KEYS:
        return "semi_weak"
    return None


def repeated_blocks(data: bytes) -> int:
    """Count 8-byte blocks that repeat an earlier block."""

    blocks = _blocks(data)
    return len(blocks) - len(set(blocks))


# --- step-by-step trace ------------------------------------------------------------


def _hex(value: int, digits: int) -> str:
    return f"{value:0{digits}X}"


def trace_block(key: int, block: int, operation: Operation) -> dict[str, Any]:
    """Every intermediate value of one block, computed on the canonical tables."""

    steps = _key_steps(key)
    order = range(16) if operation == "encrypt" else range(15, -1, -1)
    t = permute(block, IP, 64)
    left, right = t >> 32, t & 0xFFFFFFFF
    rounds = []
    for n, index in enumerate(order, start=1):
        expansion = permute(right, E, 32)
        mixed = expansion ^ steps[index][2]
        substituted, lookups = _substitute(mixed)
        f_value = permute(substituted, P, 32)
        left, right = right, left ^ f_value
        rounds.append(
            {
                "n": n,
                "subkey": index + 1,
                "expansion": _hex(expansion, 12),
                "xorKey": _hex(mixed, 12),
                "sbox": [{"row": row, "col": col, "value": value} for row, col, value in lookups],
                "sboxOutput": _hex(substituted, 8),
                "f": _hex(f_value, 8),
                "l": _hex(left, 8),
                "r": _hex(right, 8),
            }
        )
    pre_output = (right << 32) | left
    return {
        "operation": operation,
        "input": _hex(block, 16),
        "key": _hex(key, 16),
        "pc1": _hex(permute(key, PC1, 64), 14),
        "subkeys": [
            {"n": n, "shift": shift, "c": _hex(c, 7), "d": _hex(d, 7), "k": _hex(k, 12)}
            for n, (shift, (c, d, k)) in enumerate(zip(LS, steps, strict=True), start=1)
        ],
        "ip": _hex(t, 16),
        "l0": _hex(t >> 32, 8),
        "r0": _hex(t & 0xFFFFFFFF, 8),
        "rounds": rounds,
        "preOutput": _hex(pre_output, 16),
        "result": _hex(permute(pre_output, IP_INV, 64), 16),
    }
