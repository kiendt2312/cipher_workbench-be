"""Transport-independent educational Diffie-Hellman arithmetic.

The module deliberately keeps the arithmetic separate from HTTP adapters.  It
accepts Python integers at arithmetic seams, while the public result objects
also expose the canonical decimal-string representation used by the API.

Primality for values up to :data:`MAX_MANUAL_PRIME` uses trial division and
never performs trial division outside that cap.  Larger values through 128
bits use a small-prime prefilter followed by Miller-Rabin with
:data:`MILLER_RABIN_ROUNDS` independent CSPRNG-selected witnesses.  The
Miller-Rabin result is therefore a probable-prime result; the usual
per-round composite error bound is at most ``4 ** -rounds`` under the
independent-witness assumption.  The fixed screening witnesses below are a
cheap prefilter and are not a deterministic 128-bit proof.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from math import gcd, isqrt
from typing import Any

MAX_OPERAND = (1 << 128) - 1
MAX_MANUAL_PRIME = 10**12
ALLOWED_KEY_BITS = frozenset({16, 32, 64, 128})
MILLER_RABIN_ROUNDS = 32
MR_ROUNDS = MILLER_RABIN_ROUNDS
MAX_GENERATION_ATTEMPTS = 1_000_000
MAX_POLLARD_ITERATIONS = 100_000
MAX_PRIMITIVE_ROOT_CANDIDATES = 10_000

type RandBits = Callable[[int], int]
type RandBelow = Callable[[int], int]
type TraceRow = dict[str, str | int | None]

_MR_SCREENING_WITNESSES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)


class DhCoreError(ValueError):
    """A transport-independent DH domain error.

    ``code`` is stable for adapters and tests.  ``field`` is the canonical
    transport field name when the error belongs to one input.  ``details``
    contains safe arithmetic metadata only; callers must not put secrets in
    it.
    """

    def __init__(self, code: str, field: str | None = None, **details: Any) -> None:
        self.code = code
        self.field = field
        if field is not None:
            details.setdefault("field", field)
        self.details = details
        super().__init__(code)


# Common spelling aliases keep the core convenient to use without changing
# the canonical class name used by the adapters.
DHCoreError = DhCoreError
DiffieHellmanError = DhCoreError


def _invalid_integer(field: str) -> DhCoreError:
    return DhCoreError("NOT_INTEGER", field, value_field=field)


def parse_decimal(
    value: object,
    field: str = "value",
    *,
    max_value: int | None = MAX_OPERAND,
    allow_zero: bool = True,
) -> int:
    """Parse one canonical ASCII decimal string.

    Signs, whitespace, Unicode digits, leading zeroes, booleans and JSON
    numeric values are rejected.  ``"0"`` is the only zero spelling; callers
    that require a positive value can pass ``allow_zero=False``.
    """

    if type(value) is not str or not value or any(char < "0" or char > "9" for char in value):
        raise _invalid_integer(field)
    if len(value) > 1 and value[0] == "0":
        raise _invalid_integer(field)
    if not allow_zero and value == "0":
        raise _invalid_integer(field)

    if max_value is not None:
        max_text = str(max_value)
        if len(value) > len(max_text) or (len(value) == len(max_text) and value > max_text):
            raise DhCoreError("NUMBER_TOO_LARGE", field, value_field=field)
    return int(value)


def serialize_decimal(
    value: object,
    field: str = "value",
    *,
    max_value: int | None = MAX_OPERAND,
) -> str:
    """Serialize a non-negative integer to its canonical decimal spelling."""

    if type(value) is not int or value < 0:
        raise _invalid_integer(field)
    if max_value is not None and value > max_value:
        raise DhCoreError("NUMBER_TOO_LARGE", field, value_field=field)
    return str(value)


parse_canonical_decimal = parse_decimal
canonical_decimal = serialize_decimal
serialize_canonical_decimal = serialize_decimal


def _coerce_integer(
    value: object,
    field: str,
    *,
    max_value: int | None = MAX_OPERAND,
) -> int:
    if type(value) is str:
        return parse_decimal(value, field, max_value=max_value)
    if type(value) is int and value >= 0:
        if max_value is not None and value > max_value:
            raise DhCoreError("NUMBER_TOO_LARGE", field, value_field=field)
        return value
    raise _invalid_integer(field)


def _coerce_unbounded(value: object, field: str) -> int:
    return _coerce_integer(value, field, max_value=None)


def _resolve_randbits(
    randbits: RandBits | None,
    rng: Any | None,
) -> RandBits:
    if randbits is not None:
        return randbits
    if rng is not None:
        candidate = getattr(rng, "randbits", None)
        if candidate is None:
            candidate = getattr(rng, "getrandbits", None)
        if candidate is not None:
            return candidate
    return secrets.randbits


def _randbelow_from_randbits(randbits: RandBits, upper: int) -> int:
    if upper <= 0:
        raise ValueError("upper must be positive")
    width = upper.bit_length()
    while True:
        candidate = randbits(width)
        if type(candidate) is int and 0 <= candidate < upper:
            return candidate


def _resolve_randbelow(
    randbelow: RandBelow | None,
    randbits: RandBits | None,
    rng: Any | None,
) -> RandBelow:
    if randbelow is not None:
        return randbelow
    if rng is not None:
        candidate = getattr(rng, "randbelow", None)
        if candidate is not None:
            return candidate
        candidate = getattr(rng, "randrange", None)
        if candidate is not None:
            return candidate
    if randbits is not None:
        return lambda upper: _randbelow_from_randbits(randbits, upper)
    if rng is not None:
        candidate = getattr(rng, "randbits", None)
        if candidate is None:
            candidate = getattr(rng, "getrandbits", None)
        if candidate is not None:
            return lambda upper: _randbelow_from_randbits(candidate, upper)
    return secrets.randbelow


def _draw_below(source: RandBelow, upper: int) -> int:
    if upper <= 0:
        raise ValueError("upper must be positive")
    candidate = source(upper)
    if type(candidate) is not int or not 0 <= candidate < upper:
        raise DhCoreError("RNG_INVALID")
    return candidate


def _draw_bits(source: RandBits, bits: int) -> int:
    candidate = source(bits)
    if type(candidate) is not int or candidate < 0:
        raise DhCoreError("RNG_INVALID")
    return candidate & ((1 << bits) - 1)


def _miller_rabin_witness(value: int, witness: int, odd_part: int, shifts: int) -> bool:
    witness %= value
    if witness in (0, 1):
        return True
    current = pow(witness, odd_part, value)
    if current in (1, value - 1):
        return True
    for _ in range(shifts - 1):
        current = (current * current) % value
        if current == value - 1:
            return True
    return False


def is_prime_manual(value: object) -> bool:
    """Return trial-division primality only inside the ``10**12`` cap."""

    number = _coerce_unbounded(value, "value")
    if number < 2 or number > MAX_MANUAL_PRIME:
        return False
    if number in (2, 3):
        return True
    if number % 2 == 0:
        return False
    limit = isqrt(number)
    divisor = 3
    while divisor <= limit:
        if number % divisor == 0:
            return False
        divisor += 2
    return True


def is_probable_prime(
    value: object,
    *,
    randbelow: RandBelow | None = None,
    randbits: RandBits | None = None,
    rng: Any | None = None,
) -> bool:
    """Return manual or Miller-Rabin probable-prime status through 128 bits.

    Values above the manual cap use the fixed screening witnesses plus
    ``MILLER_RABIN_ROUNDS`` CSPRNG witnesses.  ``randbelow``/``randbits`` or
    ``rng`` are injectable solely as deterministic test seams.
    """

    number = _coerce_unbounded(value, "value")
    if number < 2:
        return False
    if number > MAX_OPERAND:
        raise DhCoreError("NUMBER_TOO_LARGE", "value", value_field="value")
    if number <= MAX_MANUAL_PRIME:
        return is_prime_manual(number)

    if number in _SMALL_PRIMES:
        return True
    if any(number % prime == 0 for prime in _SMALL_PRIMES):
        return False

    odd_part = number - 1
    shifts = 0
    while odd_part % 2 == 0:
        odd_part //= 2
        shifts += 1

    for witness in _MR_SCREENING_WITNESSES:
        if witness < number and not _miller_rabin_witness(number, witness, odd_part, shifts):
            return False

    source = _resolve_randbelow(randbelow, randbits, rng)
    for _ in range(MILLER_RABIN_ROUNDS):
        witness = _draw_below(source, number - 3) + 2
        if not _miller_rabin_witness(number, witness, odd_part, shifts):
            return False
    return True


is_prime = is_probable_prime
is_prime_128 = is_probable_prime


def _make_small_primes(limit: int) -> tuple[int, ...]:
    sieve = bytearray(b"\x01") * (limit + 1)
    sieve[:2] = b"\x00\x00"
    for candidate in range(2, isqrt(limit) + 1):
        if sieve[candidate]:
            sieve[candidate * candidate : limit + 1 : candidate] = b"\x00" * (
                ((limit - candidate * candidate) // candidate) + 1
            )
    return tuple(index for index, present in enumerate(sieve) if present)


_SMALL_PRIMES = _make_small_primes(1000)


def _pollard_brent(
    value: int,
    source: RandBelow,
    *,
    max_iterations: int = MAX_POLLARD_ITERATIONS,
) -> int | None:
    """Find a non-trivial factor using bounded Pollard-Brent retries."""

    if value % 2 == 0:
        return 2
    if value % 3 == 0:
        return 3

    for attempt in range(32):
        # Adding the attempt number preserves retry progress even when a
        # deterministic test source intentionally returns the same value.
        y = (_draw_below(source, value - 1) + 1 + attempt) % value
        c = (_draw_below(source, value - 1) + 1 + 2 * attempt) % value
        if y == 0:
            y = 1
        if c == 0:
            c = 1

        def polynomial(current: int, constant: int = c) -> int:
            return (current * current + constant) % value

        size = 128
        factor = 1
        sequence_length = 1
        iterations = 0
        saved = y

        while factor == 1 and iterations < max_iterations:
            x = y
            for _ in range(sequence_length):
                if iterations >= max_iterations:
                    break
                y = polynomial(y)
                iterations += 1
            if iterations >= max_iterations:
                break
            block = 0
            product = 1
            while block < sequence_length and factor == 1 and iterations < max_iterations:
                saved = y
                for _ in range(min(size, sequence_length - block, max_iterations - iterations)):
                    y = polynomial(y)
                    product = (product * abs(x - y)) % value
                    iterations += 1
                factor = gcd(product, value)
                block += size
            sequence_length <<= 1

        if factor == value:
            factor = 1
            while factor == 1 and iterations < max_iterations:
                saved = polynomial(saved)
                factor = gcd(abs(x - saved), value)
                iterations += 1
        if 1 < factor < value:
            return factor
    return None


def _pollard_rho(
    value: int,
    source: RandBelow,
    *,
    max_iterations: int = MAX_POLLARD_ITERATIONS,
) -> int | None:
    """Floyd fallback for a Pollard-Brent retry that did not split."""

    for attempt in range(32):
        constant = (_draw_below(source, value - 1) + 1 + attempt) % value or 1
        x = (_draw_below(source, value - 2) + 2 + attempt) % value
        if x == 0:
            x = 2
        y = x
        for _ in range(max_iterations):
            x = (x * x + constant) % value
            y = (y * y + constant) % value
            y = (y * y + constant) % value
            factor = gcd(abs(x - y), value)
            if 1 < factor < value:
                return factor
            if factor == value:
                break
    return None


pollard_brent = _pollard_brent
pollard_rho = _pollard_rho


def factorize(
    value: object,
    *,
    randbelow: RandBelow | None = None,
    randbits: RandBits | None = None,
    rng: Any | None = None,
) -> tuple[int, ...]:
    """Return all prime factors, including multiplicity, in sorted order."""

    number = _coerce_integer(value, "value")
    if number < 1:
        raise DhCoreError("FACTOR_OUT_OF_RANGE", "value")
    if number == 1:
        return ()

    source = _resolve_randbelow(randbelow, randbits, rng)
    remaining = number
    factors: list[int] = []
    for prime in _SMALL_PRIMES:
        while remaining % prime == 0:
            factors.append(prime)
            remaining //= prime
        if remaining == 1:
            break

    def split(candidate: int) -> None:
        if candidate == 1:
            return
        if is_probable_prime(candidate, randbelow=source):
            factors.append(candidate)
            return
        divisor = _pollard_brent(candidate, source)
        if divisor in (None, 1, candidate):
            divisor = _pollard_rho(candidate, source)
        if divisor in (None, 1, candidate):
            raise DhCoreError("FACTORIZATION_FAILED", "value", value=candidate)
        split(divisor)
        split(candidate // divisor)

    split(remaining)
    return tuple(sorted(factors))


prime_factorization = factorize
factorization = factorize


def distinct_prime_factors(
    value: object,
    *,
    randbelow: RandBelow | None = None,
    randbits: RandBits | None = None,
    rng: Any | None = None,
) -> tuple[int, ...]:
    """Return sorted distinct prime factors of ``value``."""

    return tuple(dict.fromkeys(factorize(value, randbelow=randbelow, randbits=randbits, rng=rng)))


factor_distinct = distinct_prime_factors
prime_factors = distinct_prime_factors


def _primitive_root_checks(
    alpha: int,
    q: int,
    factors: tuple[int, ...],
) -> tuple[TraceRow, ...]:
    checks: list[TraceRow] = []
    for factor in factors:
        exponent = (q - 1) // factor
        result = pow(alpha, exponent, q)
        checks.append(
            {
                "factor": serialize_decimal(factor, "factor"),
                "exponent": serialize_decimal(exponent, "exponent"),
                "result": serialize_decimal(result, "result"),
                "passes": result != 1,
            }
        )
    return tuple(checks)


def primitive_root_checks(
    alpha: object,
    q: object,
    factors: tuple[int, ...] | tuple[str, ...] | None = None,
    *,
    randbelow: RandBelow | None = None,
    randbits: RandBits | None = None,
    rng: Any | None = None,
) -> tuple[TraceRow, ...]:
    """Return exact primitive-root check rows for the supplied factors."""

    alpha_value = _coerce_unbounded(alpha, "alpha")
    q_value = _coerce_unbounded(q, "q")
    if factors is None:
        factor_values = distinct_prime_factors(
            q_value - 1, randbelow=randbelow, randbits=randbits, rng=rng
        )
    else:
        factor_values = tuple(sorted(_coerce_unbounded(factor, "factor") for factor in factors))
    return _primitive_root_checks(alpha_value, q_value, tuple(dict.fromkeys(factor_values)))


def is_primitive_root(
    alpha: object,
    q: object,
    factors: tuple[int, ...] | tuple[str, ...] | None = None,
    *,
    randbelow: RandBelow | None = None,
    randbits: RandBits | None = None,
    rng: Any | None = None,
) -> bool:
    """Return whether ``alpha`` passes every distinct-factor check."""

    checks = primitive_root_checks(
        alpha,
        q,
        factors,
        randbelow=randbelow,
        randbits=randbits,
        rng=rng,
    )
    return all(bool(row["passes"]) for row in checks)


def suggest_primitive_root(
    q: object,
    factors: tuple[int, ...] | tuple[str, ...] | None = None,
    *,
    randbelow: RandBelow | None = None,
    randbits: RandBits | None = None,
    rng: Any | None = None,
) -> int:
    """Return the smallest primitive root for a prime ``q``."""

    q_value = _coerce_unbounded(q, "q")
    if q_value < 5 or q_value > MAX_OPERAND:
        raise DhCoreError("Q_OUT_OF_RANGE", "q", q=q_value)
    source = _resolve_randbelow(randbelow, randbits, rng)
    if not is_probable_prime(q_value, randbelow=source):
        raise DhCoreError("NOT_PRIME", "q", q=q_value, value=q_value)
    factor_values = (
        distinct_prime_factors(q_value - 1, randbelow=source)
        if factors is None
        else tuple(sorted(dict.fromkeys(_coerce_unbounded(factor, "factor") for factor in factors)))
    )
    stop = min(q_value, 2 + MAX_PRIMITIVE_ROOT_CANDIDATES)
    for candidate in range(2, stop):
        if is_primitive_root(candidate, q_value, factor_values):
            return candidate
    raise DhCoreError("PRIMITIVE_ROOT_NOT_FOUND", "q", q=q_value)


@dataclass(frozen=True, slots=True)
class _MappingResult(Mapping[str, Any]):
    """Small mapping facade for result objects used by adapters and tests."""

    def as_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    def __getitem__(self, key: str) -> Any:
        return self.as_dict()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.as_dict())

    def __len__(self) -> int:
        return len(self.as_dict())


@dataclass(frozen=True, slots=True)
class ParameterResult(_MappingResult):
    q: str
    alpha: str | None
    factors: tuple[str, ...]
    primitive_root_checks: tuple[TraceRow, ...]
    suggested_alpha: str | None

    @property
    def q_value(self) -> int:
        return int(self.q)

    @property
    def alpha_value(self) -> int | None:
        return None if self.alpha is None else int(self.alpha)

    @property
    def factor_values(self) -> tuple[int, ...]:
        return tuple(map(int, self.factors))

    @property
    def checks(self) -> tuple[TraceRow, ...]:
        return self.primitive_root_checks

    @property
    def primitiveRootChecks(self) -> tuple[TraceRow, ...]:  # noqa: N802
        return self.primitive_root_checks

    @property
    def suggestedAlpha(self) -> str | None:  # noqa: N802
        return self.suggested_alpha

    def as_dict(self) -> dict[str, Any]:
        return {
            "q": self.q,
            "alpha": self.alpha,
            "factors": list(self.factors),
            "primitiveRootChecks": [dict(row) for row in self.primitive_root_checks],
            "suggestedAlpha": self.suggested_alpha,
        }


@dataclass(frozen=True, slots=True)
class GeneratedParameters(ParameterResult):
    p: str

    @property
    def p_value(self) -> int:
        return int(self.p)

    def as_dict(self) -> dict[str, Any]:
        result = ParameterResult.as_dict(self)
        result["p"] = self.p
        return result


SafePrimeParameters = GeneratedParameters


def _validate_q(
    q: object,
    *,
    manual: bool,
    randbelow: RandBelow,
) -> int:
    q_value = _coerce_unbounded(q, "q")
    upper = MAX_MANUAL_PRIME if manual else MAX_OPERAND
    if q_value < 5 or q_value > upper:
        raise DhCoreError("Q_OUT_OF_RANGE", "q", q=q_value, manual=manual)
    if not is_probable_prime(q_value, randbelow=randbelow):
        raise DhCoreError("NOT_PRIME", "q", q=q_value, value=q_value)
    return q_value


def validate_q(
    q: object,
    *,
    manual: bool = False,
    randbelow: RandBelow | None = None,
    randbits: RandBits | None = None,
    rng: Any | None = None,
) -> int:
    """Validate a standalone q for downstream operations."""

    source = _resolve_randbelow(randbelow, randbits, rng)
    return _validate_q(q, manual=manual, randbelow=source)


def validate_parameters(
    q: object,
    alpha: object | None = None,
    *,
    manual: bool = False,
    randbelow: RandBelow | None = None,
    randbits: RandBits | None = None,
    rng: Any | None = None,
) -> ParameterResult:
    """Validate DH parameters and return canonical educational details."""

    source = _resolve_randbelow(randbelow, randbits, rng)
    q_value = _validate_q(q, manual=manual, randbelow=source)
    alpha_value: int | None
    if alpha is None:
        alpha_value = None
    else:
        alpha_value = _coerce_unbounded(alpha, "alpha")
        if not 1 < alpha_value < q_value:
            raise DhCoreError("ALPHA_OUT_OF_RANGE", "alpha", q=q_value, alpha=alpha_value)

    factor_values = distinct_prime_factors(q_value - 1, randbelow=source)
    if alpha_value is None:
        suggestion = suggest_primitive_root(q_value, factor_values, randbelow=source)
        checks: tuple[TraceRow, ...] = ()
        suggestion_text: str | None = serialize_decimal(suggestion, "suggestedAlpha")
    else:
        checks = _primitive_root_checks(alpha_value, q_value, factor_values)
        if not all(bool(row["passes"]) for row in checks):
            suggestion = suggest_primitive_root(q_value, factor_values, randbelow=source)
            raise DhCoreError(
                "NOT_PRIMITIVE_ROOT",
                "alpha",
                q=q_value,
                alpha=alpha_value,
                factors=tuple(serialize_decimal(value, "factor") for value in factor_values),
                checks=checks,
                suggestion=suggestion,
            )
        suggestion_text = None

    return ParameterResult(
        serialize_decimal(q_value, "q"),
        None if alpha_value is None else serialize_decimal(alpha_value, "alpha"),
        tuple(serialize_decimal(value, "factor") for value in factor_values),
        checks,
        suggestion_text,
    )


check_parameters = validate_parameters
validate_dh_parameters = validate_parameters


def generate_safe_prime(
    bits: int,
    *,
    randbits: RandBits | None = None,
    randbelow: RandBelow | None = None,
    rng: Any | None = None,
    max_attempts: int = MAX_GENERATION_ATTEMPTS,
) -> GeneratedParameters:
    """Generate a CSPRNG-backed safe-prime group at an approved bit size."""

    if type(bits) is not int or bits not in ALLOWED_KEY_BITS:
        raise DhCoreError("BITS_INVALID", "bits")
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")

    bit_source = _resolve_randbits(randbits, rng)
    below_source = _resolve_randbelow(randbelow, randbits, rng)
    p_bits = bits - 1
    mask = (1 << p_bits) - 1
    high_bit = 1 << (p_bits - 1)

    for _ in range(max_attempts):
        p_value = (_draw_bits(bit_source, p_bits) | high_bit | 1) & mask
        q_value = 2 * p_value + 1
        if q_value.bit_length() != bits:
            continue
        if not is_probable_prime(p_value, randbelow=below_source):
            continue
        if not is_probable_prime(q_value, randbelow=below_source):
            continue
        factor_values = (2, p_value)
        alpha_value = suggest_primitive_root(q_value, factor_values, randbelow=below_source)
        checks = _primitive_root_checks(alpha_value, q_value, factor_values)
        return GeneratedParameters(
            q=serialize_decimal(q_value, "q"),
            alpha=serialize_decimal(alpha_value, "alpha"),
            factors=tuple(serialize_decimal(value, "factor") for value in factor_values),
            primitive_root_checks=checks,
            suggested_alpha=None,
            p=serialize_decimal(p_value, "p"),
        )
    raise DhCoreError("GENERATION_FAILED", "bits", bits=bits)


generate_parameters = generate_safe_prime
generate_random_parameters = generate_safe_prime


def mod_pow(
    base: object,
    exponent: object,
    modulus: object,
    *,
    collect_steps: bool = False,
    trace: bool | None = None,
) -> tuple[int, tuple[TraceRow, ...]]:
    """Compute modular exponentiation with an optional left-to-right trace."""

    if trace is not None:
        collect_steps = trace
    base_value = _coerce_integer(base, "base")
    exponent_value = _coerce_integer(exponent, "exponent")
    modulus_value = _coerce_integer(modulus, "modulus")
    if modulus_value <= 0:
        raise DhCoreError("MODULUS_OUT_OF_RANGE", "modulus")

    result = 1 % modulus_value
    current_exponent = exponent_value.bit_length()
    current_result = result
    rows: list[TraceRow] = []
    for index in range(current_exponent - 1, -1, -1):
        bit = (exponent_value >> index) & 1
        squared = (current_result * current_result) % modulus_value
        multiplied: int | None = None
        current_result = squared
        if bit:
            multiplied = (squared * base_value) % modulus_value
            current_result = multiplied
        if collect_steps:
            processed_prefix = exponent_value >> index
            rows.append(
                {
                    "index": current_exponent - index - 1,
                    "bit": bit,
                    "exponentPrefix": serialize_decimal(processed_prefix, "exponentPrefix"),
                    "squared": serialize_decimal(squared, "squared"),
                    "multiplied": (
                        None if multiplied is None else serialize_decimal(multiplied, "multiplied")
                    ),
                    "result": serialize_decimal(current_result, "result"),
                }
            )
    return current_result, tuple(rows)


mod_pow_left_to_right = mod_pow
mod_pow_with_trace = mod_pow


@dataclass(frozen=True, slots=True)
class KeyPair(_MappingResult):
    private_key: int
    public_key: int
    steps: tuple[TraceRow, ...]

    @property
    def privateKey(self) -> str:  # noqa: N802
        return serialize_decimal(self.private_key, "privateKey")

    @property
    def publicKey(self) -> str:  # noqa: N802
        return serialize_decimal(self.public_key, "publicKey")

    def as_dict(self) -> dict[str, Any]:
        return {
            "privateKey": self.privateKey,
            "publicKey": self.publicKey,
            "steps": [dict(row) for row in self.steps],
        }


def _key_pair_for_validated(
    q_value: int,
    alpha_value: int,
    private_key: object | None,
    source: RandBelow,
    *,
    max_attempts: int,
    private_field: str = "privateKey",
) -> KeyPair:
    if private_key is not None:
        private_value = _coerce_unbounded(private_key, private_field)
        if not 2 <= private_value <= q_value - 2:
            raise DhCoreError(
                "PRIVATE_KEY_OUT_OF_RANGE",
                private_field,
                q=q_value,
                privateKey=private_value,
            )
        public_value, steps = mod_pow(alpha_value, private_value, q_value, collect_steps=True)
        if public_value in (1, q_value - 1):
            raise DhCoreError(
                "PRIVATE_KEY_WEAK",
                private_field,
                privateKey=private_value,
                publicKey=public_value,
            )
        return KeyPair(private_value, public_value, steps)

    for _ in range(max_attempts):
        candidate = _draw_below(source, q_value - 3) + 2
        public_value, steps = mod_pow(alpha_value, candidate, q_value, collect_steps=True)
        if public_value in (1, q_value - 1):
            continue
        return KeyPair(candidate, public_value, steps)
    raise DhCoreError("GENERATION_FAILED", private_field, q=q_value)


def generate_key_pair(
    q: object,
    alpha: object,
    private_key: object | None = None,
    *,
    randbelow: RandBelow | None = None,
    randbits: RandBits | None = None,
    rng: Any | None = None,
    max_attempts: int = MAX_GENERATION_ATTEMPTS,
) -> KeyPair:
    """Validate a group and return one composable DH key pair."""

    source = _resolve_randbelow(randbelow, randbits, rng)
    params = validate_parameters(q, alpha, randbelow=source)
    return _key_pair_for_validated(
        params.q_value,
        params.alpha_value or 0,
        private_key,
        source,
        max_attempts=max_attempts,
    )


generate_keypair = generate_key_pair
create_key_pair = generate_key_pair
key_pair = generate_key_pair


@dataclass(frozen=True, slots=True)
class SharedSecretResult(_MappingResult):
    shared_key: int
    steps: tuple[TraceRow, ...]

    @property
    def sharedKey(self) -> str:  # noqa: N802
        return serialize_decimal(self.shared_key, "sharedKey")

    def as_dict(self) -> dict[str, Any]:
        return {"sharedKey": self.sharedKey, "steps": [dict(row) for row in self.steps]}


def _shared_secret_for_validated(
    q_value: int,
    private_key: object,
    other_public_key: object,
) -> SharedSecretResult:
    private_value = _coerce_unbounded(private_key, "privateKey")
    if not 2 <= private_value <= q_value - 2:
        raise DhCoreError(
            "PRIVATE_KEY_OUT_OF_RANGE",
            "privateKey",
            q=q_value,
            privateKey=private_value,
        )
    public_value = _coerce_unbounded(other_public_key, "otherPublicKey")
    if not 2 <= public_value <= q_value - 2:
        raise DhCoreError(
            "PUBLIC_KEY_INVALID",
            "otherPublicKey",
            q=q_value,
            otherPublicKey=public_value,
        )
    shared_value, steps = mod_pow(public_value, private_value, q_value, collect_steps=True)
    return SharedSecretResult(shared_value, steps)


def shared_secret(
    q: object,
    private_key: object,
    other_public_key: object,
    *,
    randbelow: RandBelow | None = None,
    randbits: RandBits | None = None,
    rng: Any | None = None,
) -> SharedSecretResult:
    """Validate q and calculate one side of the DH shared secret."""

    source = _resolve_randbelow(randbelow, randbits, rng)
    q_value = _validate_q(q, manual=False, randbelow=source)
    return _shared_secret_for_validated(q_value, private_key, other_public_key)


compute_shared_secret = shared_secret
calculate_shared_secret = shared_secret


EDUCATIONAL_PRIVATE_KEYS_WARNING = {
    "code": "EDUCATIONAL_PRIVATE_KEYS",
    "message": (
        "Chỉ dùng để học: response có khóa riêng; hệ thống thật không được gửi hoặc lưu khóa riêng."
    ),
}


@dataclass(frozen=True, slots=True)
class ExchangeResult(_MappingResult):
    private_key_a: int
    private_key_b: int
    public_key_a: int
    public_key_b: int
    shared_key_a: int
    shared_key_b: int
    match: bool
    steps: dict[str, tuple[TraceRow, ...]]
    warning: dict[str, str]

    @property
    def privateKeyA(self) -> str:  # noqa: N802
        return serialize_decimal(self.private_key_a, "privateKeyA")

    @property
    def privateKeyB(self) -> str:  # noqa: N802
        return serialize_decimal(self.private_key_b, "privateKeyB")

    @property
    def publicKeyA(self) -> str:  # noqa: N802
        return serialize_decimal(self.public_key_a, "publicKeyA")

    @property
    def publicKeyB(self) -> str:  # noqa: N802
        return serialize_decimal(self.public_key_b, "publicKeyB")

    @property
    def sharedKeyA(self) -> str:  # noqa: N802
        return serialize_decimal(self.shared_key_a, "sharedKeyA")

    @property
    def sharedKeyB(self) -> str:  # noqa: N802
        return serialize_decimal(self.shared_key_b, "sharedKeyB")

    def as_dict(self) -> dict[str, Any]:
        return {
            "privateKeyA": self.privateKeyA,
            "privateKeyB": self.privateKeyB,
            "publicKeyA": self.publicKeyA,
            "publicKeyB": self.publicKeyB,
            "sharedKeyA": self.sharedKeyA,
            "sharedKeyB": self.sharedKeyB,
            "match": self.match,
            "steps": {key: [dict(row) for row in rows] for key, rows in self.steps.items()},
            "warning": dict(self.warning),
        }


def exchange(
    q: object,
    alpha: object,
    private_key_a: object | None = None,
    private_key_b: object | None = None,
    *,
    randbelow: RandBelow | None = None,
    randbits: RandBits | None = None,
    rng: Any | None = None,
    max_attempts: int = MAX_GENERATION_ATTEMPTS,
) -> ExchangeResult:
    """Run both DH sides and return grouped educational traces."""

    source = _resolve_randbelow(randbelow, randbits, rng)
    params = validate_parameters(q, alpha, randbelow=source)
    q_value = params.q_value
    alpha_value = params.alpha_value or 0
    pair_a = _key_pair_for_validated(
        q_value,
        alpha_value,
        private_key_a,
        source,
        max_attempts=max_attempts,
        private_field="privateKeyA",
    )
    pair_b = _key_pair_for_validated(
        q_value,
        alpha_value,
        private_key_b,
        source,
        max_attempts=max_attempts,
        private_field="privateKeyB",
    )
    shared_a = _shared_secret_for_validated(q_value, pair_a.private_key, pair_b.public_key)
    shared_b = _shared_secret_for_validated(q_value, pair_b.private_key, pair_a.public_key)
    steps = {
        "publicKeyA": pair_a.steps,
        "publicKeyB": pair_b.steps,
        "sharedKeyA": shared_a.steps,
        "sharedKeyB": shared_b.steps,
    }
    return ExchangeResult(
        pair_a.private_key,
        pair_b.private_key,
        pair_a.public_key,
        pair_b.public_key,
        shared_a.shared_key,
        shared_b.shared_key,
        shared_a.shared_key == shared_b.shared_key,
        steps,
        dict(EDUCATIONAL_PRIVATE_KEYS_WARNING),
    )


exchange_keys = exchange


__all__ = [
    "ALLOWED_KEY_BITS",
    "EDUCATIONAL_PRIVATE_KEYS_WARNING",
    "MAX_MANUAL_PRIME",
    "MAX_OPERAND",
    "MAX_PRIMITIVE_ROOT_CANDIDATES",
    "MILLER_RABIN_ROUNDS",
    "MR_ROUNDS",
    "DHCoreError",
    "DhCoreError",
    "DiffieHellmanError",
    "ExchangeResult",
    "GeneratedParameters",
    "KeyPair",
    "ParameterResult",
    "SafePrimeParameters",
    "SharedSecretResult",
    "TraceRow",
    "calculate_shared_secret",
    "canonical_decimal",
    "check_parameters",
    "compute_shared_secret",
    "create_key_pair",
    "distinct_prime_factors",
    "exchange",
    "exchange_keys",
    "factor_distinct",
    "factorization",
    "factorize",
    "generate_key_pair",
    "generate_keypair",
    "generate_parameters",
    "generate_random_parameters",
    "generate_safe_prime",
    "is_prime",
    "is_prime_128",
    "is_prime_manual",
    "is_primitive_root",
    "is_probable_prime",
    "key_pair",
    "mod_pow",
    "mod_pow_left_to_right",
    "mod_pow_with_trace",
    "parse_canonical_decimal",
    "parse_decimal",
    "pollard_brent",
    "pollard_rho",
    "prime_factorization",
    "prime_factors",
    "primitive_root_checks",
    "serialize_canonical_decimal",
    "serialize_decimal",
    "shared_secret",
    "suggest_primitive_root",
    "validate_dh_parameters",
    "validate_parameters",
    "validate_q",
]
