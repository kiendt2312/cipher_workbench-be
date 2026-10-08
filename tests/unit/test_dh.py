"""Acceptance tests for the transport-independent Diffie-Hellman core."""

from __future__ import annotations

import itertools
import math

import pytest

from app.core import dh


def test_canonical_decimal_parser_and_serializer() -> None:
    assert dh.parse_decimal("0", "value") == 0
    assert dh.parse_decimal("23", "q") == 23
    assert dh.parse_decimal(str(2**128 - 1), "q") == 2**128 - 1
    assert dh.serialize_decimal(2**128 - 1) == str(2**128 - 1)

    invalid = ("", "+1", "-1", " 1", "1 ", "01", "\uff11\uff12", 1, True, None)
    for value in invalid:
        with pytest.raises(dh.DhCoreError) as caught:
            dh.parse_decimal(value, "q")
        assert caught.value.code == "NOT_INTEGER"

    with pytest.raises(dh.DhCoreError) as caught:
        dh.parse_decimal(str(2**128), "q")
    assert caught.value.code == "NUMBER_TOO_LARGE"

    with pytest.raises(dh.DhCoreError) as caught:
        dh.serialize_decimal(-1)
    assert caught.value.code == "NOT_INTEGER"


def test_left_to_right_mod_pow_has_the_exact_dh_trace() -> None:
    result, rows = dh.mod_pow(3, 97, 353, collect_steps=True)

    assert result == 40
    assert [row["result"] for row in rows] == ["3", "27", "23", "176", "265", "331", "40"]
    assert [row["bit"] for row in rows] == [1, 1, 0, 0, 0, 0, 1]
    assert rows[0] == {
        "index": 0,
        "bit": 1,
        "exponentPrefix": "1",
        "squared": "1",
        "multiplied": "3",
        "result": "3",
    }
    assert rows[2]["multiplied"] is None
    assert all(
        set(row) == {"index", "bit", "exponentPrefix", "squared", "multiplied", "result"}
        for row in rows
    )
    assert len(rows) == 7
    assert result == pow(3, 97, 353)


def test_mod_pow_zero_exponent_and_128_bit_trace_boundary() -> None:
    assert dh.mod_pow(5, 0, 7, collect_steps=True) == (1, ())

    exponent = (1 << 127) + 3
    result, rows = dh.mod_pow(123, exponent, 3233, collect_steps=True)
    assert result == pow(123, exponent, 3233)
    assert len(rows) == 128
    assert rows[0]["index"] == 0
    assert rows[-1]["index"] == 127


@pytest.mark.parametrize("value", [2, 3, 17, 999983, 18446744073709551557, (1 << 127) - 1])
def test_primality_policy_accepts_primes(value: int) -> None:
    assert dh.is_prime(value)


@pytest.mark.parametrize("value", [0, 1, 4, 15, 21, 561, 1105, 1729, 341550071728321, 1 << 64])
def test_primality_policy_rejects_composites(value: int) -> None:
    assert not dh.is_prime(value)


def test_manual_primality_never_claims_to_cover_above_its_cap() -> None:
    assert dh.is_prime_manual(999983)
    assert not dh.is_prime_manual(dh.MAX_MANUAL_PRIME + 1)
    assert dh.MILLER_RABIN_ROUNDS >= 16
    assert "probable" in dh.is_probable_prime.__doc__.lower()


def test_factorization_reconstructs_input_and_returns_distinct_parameters() -> None:
    value = (2**8) * (3**3) * 5 * 1009
    factors = dh.factorize(value)

    assert math.prod(factors) == value
    assert factors == (2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 5, 1009)
    assert dh.distinct_prime_factors(value) == (2, 3, 5, 1009)


def test_pollard_factorization_can_retry_through_injected_entropy() -> None:
    values = itertools.cycle([0, 1, 2, 3, 4, 5, 6, 7])
    value = 1000003 * 1000033
    factors = dh.factorize(value, randbelow=lambda _upper: next(values))

    assert math.prod(factors) == value
    assert factors == (1000003, 1000033)


def test_pollard_brent_respects_tiny_total_polynomial_budget() -> None:
    assert dh._pollard_brent(8051, lambda _upper: 1, max_iterations=1) is None


def test_parameter_validation_checks_all_distinct_factors_and_suggests_alpha() -> None:
    assert dh.is_primitive_root(5, 23)
    assert dh.primitive_root_checks(5, 23)[0]["result"] == "22"
    valid = dh.validate_parameters("23", "5")
    assert valid.q == "23"
    assert valid.alpha == "5"
    assert valid.factors == ("2", "11")
    assert valid.suggested_alpha is None
    assert valid.primitive_root_checks == (
        {"factor": "2", "exponent": "11", "result": "22", "passes": True},
        {"factor": "11", "exponent": "2", "result": "2", "passes": True},
    )

    with pytest.raises(dh.DhCoreError) as caught:
        dh.validate_parameters("23", "4")
    assert caught.value.code == "NOT_PRIMITIVE_ROOT"
    assert caught.value.field == "alpha"
    assert caught.value.details["suggestion"] == 5
    assert caught.value.details["checks"][0]["result"] == "1"


def test_parameter_validation_distinguishes_manual_cap_and_composite_q() -> None:
    with pytest.raises(dh.DhCoreError) as caught:
        dh.validate_parameters("21", "2")
    assert (caught.value.code, caught.value.field) == ("NOT_PRIME", "q")

    with pytest.raises(dh.DhCoreError) as caught:
        dh.validate_parameters(str(dh.MAX_MANUAL_PRIME + 39), "2", manual=True)
    assert (caught.value.code, caught.value.field) == ("Q_OUT_OF_RANGE", "q")

    assert dh.validate_q(23) == 23
    with pytest.raises(dh.DhCoreError) as caught:
        dh.validate_q(2**128)
    assert (caught.value.code, caught.value.field) == ("Q_OUT_OF_RANGE", "q")


def test_generated_safe_prime_has_exact_size_and_smallest_valid_alpha() -> None:
    generated = dh.generate_safe_prime(16)

    assert generated.q_value.bit_length() == 16
    assert generated.q_value == 2 * generated.p_value + 1
    assert dh.is_prime(generated.p_value)
    assert dh.is_prime(generated.q_value)
    assert generated.alpha_value == min(
        candidate
        for candidate in range(2, generated.q_value)
        if dh.is_primitive_root(candidate, generated.q_value, generated.factor_values)
    )

    generated = dh.generate_safe_prime(16, randbits=lambda _bits: 30449)
    assert (generated.p, generated.q) == ("30449", "60899")


@pytest.mark.parametrize("bits", [16, 32, 64, 128])
def test_safe_prime_generation_all_supported_sizes(bits: int) -> None:
    generated = dh.generate_safe_prime(bits)
    assert generated.q_value.bit_length() == bits
    assert generated.q_value == 2 * generated.p_value + 1
    assert dh.is_probable_prime(generated.p_value)
    assert dh.is_probable_prime(generated.q_value)
    assert dh.factorize(generated.q_value - 1) == (2, generated.p_value)
    assert dh.is_primitive_root(generated.alpha_value, generated.q_value, generated.factor_values)


def test_primitive_root_suggestion_has_a_hard_candidate_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def never_valid(*_args, **_kwargs) -> bool:
        nonlocal calls
        calls += 1
        return False

    monkeypatch.setattr(dh, "is_probable_prime", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(dh, "is_primitive_root", never_valid)
    with pytest.raises(dh.DhCoreError) as caught:
        dh.suggest_primitive_root(1_000_000_007, factors=(2,))
    assert caught.value.code == "PRIMITIVE_ROOT_NOT_FOUND"
    assert calls == dh.MAX_PRIMITIVE_ROOT_CANDIDATES


def test_keypair_resamples_weak_random_private_key_and_rejects_manual_weak_key() -> None:
    candidates = iter((9, 2))  # private keys 11 (weak) and 4 (valid)
    pair = dh.generate_key_pair(23, 5, randbelow=lambda _upper: next(candidates))
    assert pair.private_key == 4
    assert pair.public_key == 4
    assert pair.as_dict() == {
        "privateKey": "4",
        "publicKey": "4",
        "steps": list(pair.steps),
    }

    with pytest.raises(dh.DhCoreError) as caught:
        dh.generate_key_pair(23, 5, private_key=11)
    assert (caught.value.code, caught.value.field) == ("PRIVATE_KEY_WEAK", "privateKey")


def test_keypair_and_shared_secret_vectors() -> None:
    pair_a = dh.generate_key_pair(353, 3, private_key=97)
    pair_b = dh.generate_key_pair(353, 3, private_key=233)
    shared_a = dh.shared_secret(353, 97, pair_b.public_key)
    shared_b = dh.shared_secret(353, 233, pair_a.public_key)

    assert pair_a.public_key == 40
    assert pair_b.public_key == 248
    assert (shared_a.shared_key, shared_b.shared_key) == (160, 160)
    assert shared_a.steps[-1]["result"] == "160"

    with pytest.raises(dh.DhCoreError) as caught:
        dh.shared_secret(23, 4, 22)
    assert (caught.value.code, caught.value.field) == ("PUBLIC_KEY_INVALID", "otherPublicKey")


def test_exchange_returns_grouped_traces_and_educational_warning() -> None:
    result = dh.exchange(23, 5, private_key_a=4, private_key_b=3)

    assert result.private_key_a == 4
    assert result.private_key_b == 3
    assert (result.public_key_a, result.public_key_b) == (4, 10)
    assert (result.shared_key_a, result.shared_key_b, result.match) == (18, 18, True)
    assert set(result.steps) == {"publicKeyA", "publicKeyB", "sharedKeyA", "sharedKeyB"}
    assert result.warning == dh.EDUCATIONAL_PRIVATE_KEYS_WARNING
    assert result.as_dict()["privateKeyA"] == "4"

    generated = dh.exchange(23, 5, randbelow=lambda _upper: 2)
    assert generated.match is True
