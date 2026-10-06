"""Pure textbook-RSA arithmetic and lossless educational text codecs."""

from __future__ import annotations

import secrets
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from math import isqrt
from typing import Any, Literal

MAX_OPERAND = (1 << 128) - 1
MAX_MANUAL_PRIME = 10**12
MAX_TEXT_CODEPOINTS = 10_000
MAX_BLOCK_CIPHER_ITEMS = 40_000
ALLOWED_KEY_BITS = frozenset({16, 32, 64, 128})


class RsaCoreError(ValueError):
    """A transport-independent domain error with safe interpolation details."""

    def __init__(self, code: str, **details: Any) -> None:
        self.code = code
        self.details = details
        super().__init__(code)


@dataclass(frozen=True)
class KeyMaterial:
    p: int
    q: int
    n: int
    phi: int
    e: int
    d: int
    egcd_steps: tuple[dict[str, int | None], ...]


@dataclass(frozen=True)
class TransformResult:
    blocks: tuple[int, ...]
    values: tuple[int, ...]
    block_size: int | None
    original_utf8_byte_length: int | None
    trace: dict[str, Any] | None


def gcd(a: int, b: int) -> int:
    """Return the non-negative greatest common divisor."""

    while b:
        a, b = b, a % b
    return abs(a)


def extended_euclid_steps(phi: int, e: int) -> tuple[dict[str, int | None], ...]:
    """Return the complete quotient/remainder/coefficient table for ``phi,e``."""

    rows: list[dict[str, int | None]] = [
        {"index": 0, "q": None, "r": phi, "t": 0},
        {"index": 1, "q": None, "r": e, "t": 1},
    ]
    old_r, r = phi, e
    old_t, t = 0, 1
    index = 2
    while r != 0:
        quotient = old_r // r
        old_r, r = r, old_r - quotient * r
        old_t, t = t, old_t - quotient * t
        rows.append({"index": index, "q": quotient, "r": r, "t": t})
        index += 1
    return tuple(rows)


def modular_inverse(value: int, modulus: int) -> int:
    """Return ``value^-1 mod modulus`` or raise when no inverse exists."""

    steps = extended_euclid_steps(modulus, value)
    if len(steps) < 2 or steps[-2]["r"] != 1:
        raise RsaCoreError("NO_INVERSE")
    coefficient = steps[-2]["t"]
    assert isinstance(coefficient, int)
    return coefficient % modulus


def mod_pow(
    base: int, exponent: int, modulus: int, *, collect_steps: bool = False
) -> tuple[int, tuple[dict[str, int], ...]]:
    """Right-to-left square-and-multiply with optional complete bit rows."""

    if modulus <= 0 or exponent < 0:
        raise ValueError("modulus must be positive and exponent nonnegative")
    current_base = base % modulus
    result = 1 % modulus
    remaining = exponent
    index = 0
    rows: list[dict[str, int]] = []
    while remaining:
        bit = remaining & 1
        before = result
        if bit:
            result = (result * current_base) % modulus
        if collect_steps:
            rows.append(
                {
                    "i": index,
                    "bit": bit,
                    "base": current_base,
                    "before": before,
                    "result": result,
                }
            )
        current_base = (current_base * current_base) % modulus
        remaining >>= 1
        index += 1
    return result, tuple(rows)


def is_prime_manual(value: int) -> bool:
    """Trial-division primality for the accepted manual-key domain."""

    if value < 2:
        return False
    if value in (2, 3):
        return True
    if value % 2 == 0:
        return False
    limit = isqrt(value)
    divisor = 3
    while divisor <= limit:
        if value % divisor == 0:
            return False
        divisor += 2
    return True


def is_prime_64(value: int) -> bool:
    """Deterministic Miller-Rabin primality for unsigned 64-bit integers."""

    if value < 2:
        return False
    small_primes = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
    if value in small_primes:
        return True
    if any(value % prime == 0 for prime in small_primes):
        return False

    odd_part = value - 1
    shifts = 0
    while odd_part % 2 == 0:
        shifts += 1
        odd_part //= 2

    # Proven deterministic witness set for n < 2^64.
    for witness in (2, 325, 9375, 28178, 450775, 9780504, 1795265022):
        if witness % value == 0:
            continue
        x = pow(witness, odd_part, value)
        if x in (1, value - 1):
            continue
        for _ in range(shifts - 1):
            x = (x * x) % value
            if x == value - 1:
                break
        else:
            return False
    return True


def suggest_public_exponent(phi: int) -> int:
    candidate = 3
    while candidate < phi:
        if gcd(candidate, phi) == 1:
            return candidate
        candidate += 2
    raise RsaCoreError("E_OUT_OF_RANGE", phi=phi)


def _key_material(p: int, q: int, e: int) -> KeyMaterial:
    n = p * q
    phi = (p - 1) * (q - 1)
    d = modular_inverse(e, phi)
    return KeyMaterial(p, q, n, phi, e, d, extended_euclid_steps(phi, e))


def generate_manual_key(p: int, q: int, e: int) -> KeyMaterial:
    """Validate and generate one manual educational RSA key."""

    if p > MAX_MANUAL_PRIME:
        raise RsaCoreError("PRIME_TOO_LARGE", field="p")
    if q > MAX_MANUAL_PRIME:
        raise RsaCoreError("PRIME_TOO_LARGE", field="q")
    if not is_prime_manual(p):
        raise RsaCoreError("NOT_PRIME", field="p", value=p)
    if not is_prime_manual(q):
        raise RsaCoreError("NOT_PRIME", field="q", value=q)
    if p == q:
        raise RsaCoreError("SAME_PRIME", field="q")
    phi = (p - 1) * (q - 1)
    if not 1 < e < phi:
        raise RsaCoreError("E_OUT_OF_RANGE", field="e", phi=phi)
    common = gcd(e, phi)
    if common != 1:
        raise RsaCoreError(
            "E_NOT_COPRIME",
            field="e",
            e=e,
            phi=phi,
            gcd=common,
            suggestion=suggest_public_exponent(phi),
        )
    return _key_material(p, q, e)


def _random_prime(bits: int, randbits: Callable[[int], int]) -> int:
    while True:
        candidate = randbits(bits) | (1 << (bits - 1)) | 1
        candidate &= (1 << bits) - 1
        if is_prime_64(candidate):
            return candidate


def generate_random_key(
    bits: int, *, randbits: Callable[[int], int] = secrets.randbits
) -> KeyMaterial:
    """Generate a key whose modulus has exactly the requested bit length."""

    if bits not in ALLOWED_KEY_BITS:
        raise RsaCoreError("INVALID_BITS", field="bits")
    p_bits = bits // 2
    q_bits = bits - p_bits
    while True:
        p = _random_prime(p_bits, randbits)
        q = _random_prime(q_bits, randbits)
        if p == q:
            continue
        n = p * q
        if n.bit_length() != bits:
            continue
        phi = (p - 1) * (q - 1)
        e = 65537 if 1 < 65537 < phi and gcd(65537, phi) == 1 else suggest_public_exponent(phi)
        material = _key_material(p, q, e)
        if material.n <= MAX_OPERAND and (material.e * material.d) % material.phi == 1:
            return material


def block_size(n: int) -> int:
    """Return the largest k for which 256**k <= n-1."""

    if n <= 256:
        raise RsaCoreError("N_TOO_SMALL", field="n", block=True)
    size = 0
    power = 1
    while power * 256 <= n - 1:
        power *= 256
        size += 1
    return size


def _validate_text(text: str) -> bytes:
    if text == "":
        raise RsaCoreError("EMPTY_INPUT")
    if len(text) > MAX_TEXT_CODEPOINTS:
        raise RsaCoreError("INPUT_TOO_LARGE", kind="text")
    try:
        return text.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise RsaCoreError("DECODE_FAILED") from exc


def _validate_crypto_operand(value: int) -> None:
    if value < 0 or value > MAX_OPERAND:
        raise RsaCoreError("NUMBER_TOO_LARGE")


def validate_transform_key(exponent: int, n: int, operation: Literal["encrypt", "decrypt"]) -> None:
    _validate_crypto_operand(exponent)
    _validate_crypto_operand(n)
    if n <= 1:
        raise RsaCoreError("N_TOO_SMALL", field="n", block=False)
    if not 1 < exponent < n:
        code = "E_OUT_OF_RANGE" if operation == "encrypt" else "D_OUT_OF_RANGE"
        field = "e" if operation == "encrypt" else "d"
        raise RsaCoreError(code, field=field)


def transform_number(
    value: int,
    exponent: int,
    n: int,
    operation: Literal["encrypt", "decrypt"],
    *,
    trace: bool = False,
) -> TransformResult:
    validate_transform_key(exponent, n, operation)
    _validate_crypto_operand(value)
    if value >= n:
        code = "P_TOO_LARGE" if operation == "encrypt" else "CIPHER_TOO_LARGE"
        raise RsaCoreError(code, value=value, n=n, index=0)
    result, steps = mod_pow(value, exponent, n, collect_steps=trace)
    trace_value = _trace(operation, 0, value, exponent, n, result, steps) if trace else None
    return TransformResult(
        (value if operation == "encrypt" else result,),
        (result,),
        None,
        None,
        trace_value,
    )


def transform_char_encrypt(
    text: str, e: int, n: int, *, trace_index: int | None = None
) -> TransformResult:
    validate_transform_key(e, n, "encrypt")
    encoded = _validate_text(text)
    blocks = tuple(ord(character) for character in text)
    for value in blocks:
        if value >= n:
            raise RsaCoreError("P_TOO_LARGE", value=value, n=n)
    return _transform_many(blocks, e, n, "encrypt", 1, len(encoded), trace_index)


def transform_char_decrypt(
    cipher: Sequence[int], d: int, n: int, *, trace_index: int | None = None
) -> tuple[TransformResult, str]:
    validate_transform_key(d, n, "decrypt")
    if not cipher:
        raise RsaCoreError("EMPTY_INPUT")
    if len(cipher) > MAX_TEXT_CODEPOINTS:
        raise RsaCoreError("INPUT_TOO_LARGE", kind="collection")
    transformed = _transform_many(tuple(cipher), d, n, "decrypt", 1, None, trace_index)
    characters: list[str] = []
    for index, value in enumerate(transformed.blocks):
        if value > 0x10FFFF or 0xD800 <= value <= 0xDFFF:
            raise RsaCoreError("DECODE_FAILED", index=index)
        characters.append(chr(value))
    plaintext = "".join(characters)
    try:
        utf8_length = len(plaintext.encode("utf-8", errors="strict"))
    except UnicodeEncodeError as exc:  # defensive; scalar checks above should make this unreachable
        raise RsaCoreError("DECODE_FAILED") from exc
    result = TransformResult(
        transformed.blocks,
        transformed.values,
        1,
        utf8_length,
        transformed.trace,
    )
    return result, plaintext


def pack_block_text(text: str, n: int) -> tuple[tuple[int, ...], int, int]:
    raw = _validate_text(text)
    size = block_size(n)
    blocks: list[int] = []
    for start in range(0, len(raw), size):
        chunk = raw[start : start + size]
        padded = chunk + b"\x00" * (size - len(chunk))
        blocks.append(int.from_bytes(padded, "big"))
    return tuple(blocks), size, len(raw)


def transform_block_encrypt(
    text: str, e: int, n: int, *, trace_index: int | None = None
) -> TransformResult:
    validate_transform_key(e, n, "encrypt")
    blocks, size, utf8_length = pack_block_text(text, n)
    return _transform_many(blocks, e, n, "encrypt", size, utf8_length, trace_index)


def transform_block_decrypt(
    cipher: Sequence[int],
    d: int,
    n: int,
    original_utf8_byte_length: int,
    *,
    trace_index: int | None = None,
) -> tuple[TransformResult, str]:
    validate_transform_key(d, n, "decrypt")
    size = block_size(n)
    if not cipher:
        raise RsaCoreError("EMPTY_INPUT")
    if len(cipher) > MAX_BLOCK_CIPHER_ITEMS:
        raise RsaCoreError("INPUT_TOO_LARGE", kind="collection")
    if not 1 <= original_utf8_byte_length <= MAX_BLOCK_CIPHER_ITEMS:
        raise RsaCoreError("INVALID_LENGTH_METADATA")
    expected_count = (original_utf8_byte_length + size - 1) // size
    if expected_count != len(cipher):
        raise RsaCoreError("INVALID_LENGTH_METADATA")
    transformed = _transform_many(tuple(cipher), d, n, "decrypt", size, None, trace_index)
    raw_parts: list[bytes] = []
    width_limit = 256**size
    for index, value in enumerate(transformed.blocks):
        if value >= width_limit:
            raise RsaCoreError("DECODE_FAILED", index=index)
        raw_parts.append(value.to_bytes(size, "big"))
    padded = b"".join(raw_parts)
    padding = len(padded) - original_utf8_byte_length
    if padding and any(padded[len(padded) - padding :]):
        raise RsaCoreError("DECODE_FAILED")
    meaningful = padded[:original_utf8_byte_length]
    try:
        plaintext = meaningful.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise RsaCoreError("DECODE_FAILED") from exc
    if len(plaintext) > MAX_TEXT_CODEPOINTS:
        raise RsaCoreError("INPUT_TOO_LARGE", kind="text")
    result = TransformResult(
        transformed.blocks,
        transformed.values,
        size,
        original_utf8_byte_length,
        transformed.trace,
    )
    return result, plaintext


def _transform_many(
    inputs: tuple[int, ...],
    exponent: int,
    n: int,
    operation: Literal["encrypt", "decrypt"],
    size: int,
    utf8_length: int | None,
    trace_index: int | None,
) -> TransformResult:
    for index, value in enumerate(inputs):
        _validate_crypto_operand(value)
        if value >= n:
            code = "P_TOO_LARGE" if operation == "encrypt" else "CIPHER_TOO_LARGE"
            raise RsaCoreError(code, value=value, n=n, index=index)
    if trace_index is not None and not 0 <= trace_index < len(inputs):
        raise RsaCoreError("TRACE_INDEX_OUT_OF_RANGE")
    outputs: list[int] = []
    trace_value: dict[str, Any] | None = None
    for index, value in enumerate(inputs):
        selected = trace_index == index
        result, steps = mod_pow(value, exponent, n, collect_steps=selected)
        outputs.append(result)
        if selected:
            trace_value = _trace(operation, index, value, exponent, n, result, steps)
    blocks = inputs if operation == "encrypt" else tuple(outputs)
    return TransformResult(blocks, tuple(outputs), size, utf8_length, trace_value)


def _trace(
    operation: Literal["encrypt", "decrypt"],
    index: int,
    value: int,
    exponent: int,
    n: int,
    result: int,
    steps: tuple[dict[str, int], ...],
) -> dict[str, Any]:
    return {
        "operation": operation,
        "blockIndex": index,
        "input": value,
        "exponent": exponent,
        "modulus": n,
        "result": result,
        "steps": steps,
    }
