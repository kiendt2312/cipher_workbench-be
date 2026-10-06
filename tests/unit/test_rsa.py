"""Pure arithmetic, key generation and lossless codec tests for textbook RSA."""

from __future__ import annotations

import pytest

from app.core import rsa


def test_gcd_egcd_inverse_and_key_vectors() -> None:
    assert rsa.gcd(160, 7) == 1
    assert rsa.gcd(-10, 160) == 10
    steps = rsa.extended_euclid_steps(160, 7)
    assert steps == (
        {"index": 0, "q": None, "r": 160, "t": 0},
        {"index": 1, "q": None, "r": 7, "t": 1},
        {"index": 2, "q": 22, "r": 6, "t": -22},
        {"index": 3, "q": 1, "r": 1, "t": 23},
        {"index": 4, "q": 6, "r": 0, "t": -160},
    )
    assert rsa.modular_inverse(7, 160) == 23
    assert (rsa.generate_manual_key(17, 11, 7).n, rsa.generate_manual_key(61, 53, 17).d) == (
        187,
        2753,
    )


def test_modular_inverse_rejects_non_coprime() -> None:
    with pytest.raises(rsa.RsaCoreError, match="NO_INVERSE"):
        rsa.modular_inverse(10, 160)


def test_mod_pow_vectors_and_full_128_bit_trace() -> None:
    assert rsa.mod_pow(88, 7, 187)[0] == 11
    assert rsa.mod_pow(11, 23, 187)[0] == 88
    exponent = (1 << 127) + 3
    result, rows = rsa.mod_pow(123, exponent, 3233, collect_steps=True)
    assert result == pow(123, exponent, 3233)
    assert len(rows) == 128
    assert rows[0] == {"i": 0, "bit": 1, "base": 123, "before": 1, "result": 123}
    assert rows[-1]["i"] == 127
    assert rsa.mod_pow(5, 0, 7, collect_steps=True) == (1, ())


@pytest.mark.parametrize("value", [2, 3, 17, 999983, 18446744073709551557])
def test_primality_accepts_primes(value: int) -> None:
    checker = rsa.is_prime_manual if value <= rsa.MAX_MANUAL_PRIME else rsa.is_prime_64
    assert checker(value)


@pytest.mark.parametrize("value", [0, 1, 4, 15, 561, 1105, 1729, 3215031751, 341550071728321])
def test_primality_rejects_composites_and_pseudoprimes(value: int) -> None:
    assert not rsa.is_prime_64(value)


@pytest.mark.parametrize(
    ("args", "code", "details"),
    [
        ((15, 11, 7), "NOT_PRIME", {"field": "p"}),
        ((17, 15, 7), "NOT_PRIME", {"field": "q"}),
        ((11, 11, 7), "SAME_PRIME", {"field": "q"}),
        ((17, 11, 200), "E_OUT_OF_RANGE", {"field": "e", "phi": 160}),
        ((17, 11, 10), "E_NOT_COPRIME", {"suggestion": 3, "gcd": 10}),
        ((10**12 + 1, 11, 7), "PRIME_TOO_LARGE", {"field": "p"}),
        ((17, 10**12 + 1, 7), "PRIME_TOO_LARGE", {"field": "q"}),
    ],
)
def test_manual_key_validation(args: tuple[int, int, int], code: str, details: dict) -> None:
    with pytest.raises(rsa.RsaCoreError) as caught:
        rsa.generate_manual_key(*args)
    assert caught.value.code == code
    assert caught.value.details.items() >= details.items()


@pytest.mark.parametrize("bits", [16, 32, 64, 128])
def test_random_keys_have_exact_modulus_size_and_invariants(bits: int) -> None:
    key = rsa.generate_random_key(bits)
    assert key.n.bit_length() == bits
    assert key.p != key.q
    assert rsa.is_prime_64(key.p) and rsa.is_prime_64(key.q)
    assert rsa.gcd(key.e, key.phi) == 1
    assert (key.e * key.d) % key.phi == 1
    assert key.e == (65537 if key.phi > 65537 else rsa.suggest_public_exponent(key.phi))


def test_random_key_rejects_unapproved_size() -> None:
    with pytest.raises(rsa.RsaCoreError, match="INVALID_BITS"):
        rsa.generate_random_key(24)


def test_random_key_uses_injected_entropy_and_fallback_exponent() -> None:
    candidates = iter((251, 239))
    key = rsa.generate_random_key(16, randbits=lambda _bits: next(candidates))
    assert (key.p, key.q, key.n, key.e) == (251, 239, 59989, 3)


def test_manual_prime_cap_precedes_primality(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rsa, "is_prime_manual", lambda _value: pytest.fail("must not test prime"))
    with pytest.raises(rsa.RsaCoreError, match="PRIME_TOO_LARGE"):
        rsa.generate_manual_key(rsa.MAX_MANUAL_PRIME + 1, 11, 7)


def test_number_vectors_and_trace() -> None:
    encrypted = rsa.transform_number(65, 17, 3233, "encrypt", trace=True)
    assert encrypted.blocks == (65,)
    assert encrypted.values == (2790,)
    assert encrypted.trace is not None
    assert encrypted.trace["result"] == 2790
    decrypted = rsa.transform_number(11, 23, 187, "decrypt")
    assert decrypted.blocks == (88,)


def test_char_reference_round_trip_and_lossless_inputs() -> None:
    key = rsa.generate_manual_key(101, 113, 3533)
    text = "Xin chào Việt Nam"
    encrypted = rsa.transform_char_encrypt(text, key.e, key.n)
    assert encrypted.values == (
        1191,
        4861,
        8266,
        5410,
        9661,
        4909,
        11155,
        6070,
        5410,
        8077,
        4861,
        6970,
        7780,
        5410,
        4334,
        290,
        10050,
    )
    result, plaintext = rsa.transform_char_decrypt(encrypted.values, key.d, key.n)
    assert plaintext == text
    assert result.original_utf8_byte_length == len(text.encode())

    for value in (" é ", "e\u0301", "A\r\nB\n", "A\x00"):
        encrypted = rsa.transform_char_encrypt(value, key.e, key.n)
        assert rsa.transform_char_decrypt(encrypted.values, key.d, key.n)[1] == value
    bom = rsa.transform_char_encrypt("\ufeffA", 3, 67591)
    assert rsa.transform_char_decrypt(bom.values, 44715, 67591)[1] == "\ufeffA"


def test_char_rejects_surrogate_and_codepoint_over_modulus() -> None:
    with pytest.raises(rsa.RsaCoreError, match="DECODE_FAILED"):
        rsa.transform_char_encrypt("\ud800", 7, 65537)
    with pytest.raises(rsa.RsaCoreError, match="P_TOO_LARGE"):
        rsa.transform_char_encrypt("Việt", 7, 187)
    surrogate_cipher = pow(0xD800, 43691, 65537)
    with pytest.raises(rsa.RsaCoreError, match="DECODE_FAILED"):
        rsa.transform_char_decrypt([surrogate_cipher], 3, 65537)


def test_block_reference_lossless_bom_and_trailing_nul() -> None:
    assert rsa.block_size(67591) == 2
    assert rsa.pack_block_text("Hi!", 67591) == ((18537, 8448), 2, 3)
    encrypted = rsa.transform_block_encrypt("Hi!", 3, 67591)
    assert encrypted.values == (37222, 6468)
    assert rsa.transform_block_decrypt(encrypted.values, 44715, 67591, 3)[1] == "Hi!"

    for value in ("A\x00", "\ufeffA", "é漢", " A\r\nB\n "):
        encrypted = rsa.transform_block_encrypt(value, 3, 67591)
        _, plaintext = rsa.transform_block_decrypt(
            encrypted.values, 44715, 67591, len(value.encode())
        )
        assert plaintext == value


def test_block_boundaries_and_package_validation() -> None:
    with pytest.raises(rsa.RsaCoreError, match="N_TOO_SMALL"):
        rsa.block_size(256)
    assert rsa.block_size(257) == 1
    encrypted = rsa.transform_block_encrypt("ABC", 3, 67591)
    with pytest.raises(rsa.RsaCoreError, match="INVALID_LENGTH_METADATA"):
        rsa.transform_block_decrypt(encrypted.values, 44715, 67591, 2)
    with pytest.raises(rsa.RsaCoreError, match="TRACE_INDEX_OUT_OF_RANGE"):
        rsa.transform_block_encrypt("ABC", 3, 67591, trace_index=5)

    bad_padding = pow(0x4101, 3, 67591)
    with pytest.raises(rsa.RsaCoreError, match="DECODE_FAILED"):
        rsa.transform_block_decrypt([bad_padding], 44715, 67591, 1)
    bad_utf8 = pow(0xFF00, 3, 67591)
    with pytest.raises(rsa.RsaCoreError, match="DECODE_FAILED"):
        rsa.transform_block_decrypt([bad_utf8], 44715, 67591, 1)


def test_block_decrypt_applies_post_decode_codepoint_cap() -> None:
    encrypted = rsa.transform_block_encrypt("A" * 10_000, 3, 67591)
    extra = pow(0x4100, 3, 67591)
    cipher = (*encrypted.values, extra)
    with pytest.raises(rsa.RsaCoreError, match="INPUT_TOO_LARGE"):
        rsa.transform_block_decrypt(cipher, 44715, 67591, 10_001)


def test_collection_and_text_caps_happen_before_transform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rsa, "mod_pow", lambda *args, **kwargs: pytest.fail("must not transform"))
    with pytest.raises(rsa.RsaCoreError, match="INPUT_TOO_LARGE"):
        rsa.transform_char_decrypt([0] * 10_001, 3, 257)
    with pytest.raises(rsa.RsaCoreError, match="INPUT_TOO_LARGE"):
        rsa.transform_block_decrypt([0] * 40_001, 3, 257, 40_001)
    with pytest.raises(rsa.RsaCoreError, match="INPUT_TOO_LARGE"):
        rsa.transform_char_encrypt("A" * 10_001, 3, 257)
