"""Bounded raw-RSA and interoperable RSA-PSS signature primitives.

The raw helpers intentionally operate on the application's decimal-string
integer domain.  They are useful for the educational/raw-signature contract,
not as a replacement for a padded signature scheme.

The byte helpers load RSA PEM keys and use the fixed wire contract
RSASSA-PSS with SHA-256, MGF1-SHA256, and a SHA-256-sized salt.  ``cryptography``
is loaded lazily so the core package keeps its framework-independent import
boundary; the dependency is still required when a PEM helper is called.
"""

from __future__ import annotations

import base64
import binascii
from importlib import import_module
from typing import Any

MAX_DECIMAL_DIGITS = 128
MAX_OPERAND = (1 << 128) - 1
MAX_EXPONENT_BITS = MAX_OPERAND.bit_length()

_ASCII_DIGITS = frozenset("0123456789")


class RsaSignatureError(ValueError):
    """A safe, transport-independent error for signature-domain failures."""

    def __init__(self, code: str, field: str | None = None) -> None:
        self.code = code
        self.field = field
        self.details = {} if field is None else {"field": field}
        # Do not interpolate key material, passphrases, or third-party error
        # text.  Adapters can safely expose ``code`` and ``field``.
        super().__init__(code)


# Keep the acronym spelling convenient for adapters without creating a second
# exception hierarchy.
RSASignatureError = RsaSignatureError


def parse_decimal(
    value: object,
    field: str = "value",
    *,
    max_value: int = MAX_OPERAND,
    allow_zero: bool = True,
) -> int:
    """Parse one bounded ASCII decimal string without accepting JSON numbers.

    Leading zeroes are accepted at input and removed by the integer parser;
    returned values are ordinary bounded Python integers.  The raw length
    check happens before integer conversion so a hostile digit string cannot
    trigger unbounded parsing or modular exponentiation.
    """

    if type(value) is not str or not value or any(char not in _ASCII_DIGITS for char in value):
        raise RsaSignatureError("NOT_INTEGER", field)
    if len(value) > MAX_DECIMAL_DIGITS:
        raise RsaSignatureError("NUMBER_TOO_LARGE", field)

    parsed = int(value)
    if not allow_zero and parsed == 0:
        raise RsaSignatureError("NOT_INTEGER", field)
    if parsed > max_value:
        raise RsaSignatureError("NUMBER_TOO_LARGE", field)
    return parsed


def serialize_decimal(value: object, field: str = "value") -> str:
    """Serialize one bounded non-negative integer to canonical decimal text."""

    if type(value) is not int or value < 0:
        raise RsaSignatureError("NOT_INTEGER", field)
    if value > MAX_OPERAND:
        raise RsaSignatureError("NUMBER_TOO_LARGE", field)
    return str(value)


parse_canonical_decimal = parse_decimal
serialize_canonical_decimal = serialize_decimal


def _modular_power(base: int, exponent: int, modulus: int) -> int:
    """Run only a bounded three-argument modular exponentiation."""

    if exponent.bit_length() > MAX_EXPONENT_BITS:
        raise RsaSignatureError("NUMBER_TOO_LARGE", "exponent")
    # ``pow(base, exponent)`` would construct an unbounded intermediate.  The
    # three-argument form keeps every intermediate reduced modulo ``modulus``.
    return pow(base, exponent, modulus)


def _parse_modulus(value: object) -> int:
    modulus = _coerce_integer(value, "n")
    if modulus <= 1:
        raise RsaSignatureError("N_TOO_SMALL", "n")
    return modulus


def _coerce_integer(value: object, field: str) -> int:
    """Accept a validated integer or the strict decimal transport form."""

    if type(value) is int:
        if value < 0:
            raise RsaSignatureError("NOT_INTEGER", field)
        if value > MAX_OPERAND:
            raise RsaSignatureError("NUMBER_TOO_LARGE", field)
        return value
    return parse_decimal(value, field)


def _parse_public_exponent(value: object) -> int:
    exponent = _coerce_integer(value, "e")
    if exponent < 1:
        raise RsaSignatureError("EXPONENT_OUT_OF_RANGE", "e")
    return exponent


def _parse_private_exponent(value: object) -> int:
    exponent = _coerce_integer(value, "d")
    if exponent < 1:
        raise RsaSignatureError("EXPONENT_OUT_OF_RANGE", "d")
    return exponent


def _parse_message(value: object, modulus: int) -> int:
    message = _coerce_integer(value, "m")
    if message >= modulus:
        raise RsaSignatureError("MESSAGE_OUT_OF_RANGE", "m")
    return message


def _parse_signature(value: object, modulus: int) -> int:
    signature = _coerce_integer(value, "signature")
    if signature >= modulus:
        raise RsaSignatureError("SIGNATURE_OUT_OF_RANGE", "signature")
    return signature


def sign_integer(
    message: object,
    private_exponent: object,
    public_exponent: object,
    modulus: object,
) -> str:
    """Return ``message ** d mod n`` as a canonical decimal string.

    ``e`` is validated because it is part of the public-key/history record,
    but the raw signing operation itself only needs ``d`` and ``n``.
    """

    modulus_value = _parse_modulus(modulus)
    message_value = _parse_message(message, modulus_value)
    _parse_public_exponent(public_exponent)
    exponent_value = _parse_private_exponent(private_exponent)
    signed = _modular_power(message_value, exponent_value, modulus_value)
    return serialize_decimal(signed, "signature")


def verify_integer(
    message: object,
    signature: object,
    public_exponent: object,
    modulus: object,
) -> bool:
    """Return whether a raw integer signature matches ``message``.

    The signature representative must be in ``[0, n)`` as a request/domain
    bound.  Only an in-range representative that does not recover the message
    returns ``False``.
    """

    modulus_value = _parse_modulus(modulus)
    message_value = _parse_message(message, modulus_value)
    exponent_value = _parse_public_exponent(public_exponent)
    signature_value = _parse_signature(signature, modulus_value)
    recovered = _modular_power(signature_value, exponent_value, modulus_value)
    return recovered == message_value


# Explicit aliases make the raw operation names readable at call sites while
# keeping one implementation and one validation contract.
raw_sign = sign_integer
raw_verify = verify_integer
sign_raw = sign_integer
verify_raw = verify_integer


def _crypto_modules() -> tuple[Any, Any, Any, Any, Any, Any]:
    """Load the small cryptography surface used by the PEM helpers."""

    try:
        serialization = import_module("cryptography.hazmat.primitives.serialization")
        rsa = import_module("cryptography.hazmat.primitives.asymmetric.rsa")
        padding = import_module("cryptography.hazmat.primitives.asymmetric.padding")
        hashes = import_module("cryptography.hazmat.primitives.hashes")
        exceptions = import_module("cryptography.exceptions")
    except ModuleNotFoundError:
        raise RsaSignatureError("CRYPTOGRAPHY_UNAVAILABLE") from None

    return (
        serialization,
        rsa,
        padding,
        hashes,
        exceptions.InvalidSignature,
        exceptions.UnsupportedAlgorithm,
    )


def _octets(value: object, field: str) -> bytes:
    """Coerce bytes-like message/signature input without text normalization."""

    if isinstance(value, bytes):
        return value
    if isinstance(value, (bytearray, memoryview)):
        try:
            return bytes(value)
        except (TypeError, ValueError):
            raise RsaSignatureError("INVALID_BYTES", field) from None
    raise RsaSignatureError("INVALID_BYTES", field)


def _pem_bytes(value: object, field: str) -> bytes:
    if isinstance(value, str):
        try:
            return value.encode("ascii")
        except UnicodeEncodeError:
            raise RsaSignatureError("INVALID_KEY", field) from None
    if isinstance(value, (bytes, bytearray, memoryview)):
        try:
            return bytes(value)
        except (TypeError, ValueError):
            raise RsaSignatureError("INVALID_KEY", field) from None
    raise RsaSignatureError("INVALID_KEY", field)


def _password_bytes(value: object) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return value.encode("utf-8")
        except UnicodeEncodeError:
            raise RsaSignatureError("INVALID_PASSPHRASE", "password") from None
    if isinstance(value, (bytes, bytearray, memoryview)):
        try:
            return bytes(value)
        except (TypeError, ValueError):
            raise RsaSignatureError("INVALID_PASSPHRASE", "password") from None
    raise RsaSignatureError("INVALID_PASSPHRASE", "password")


def _load_private_key(
    private_key_pem: object, password: object
) -> tuple[Any, tuple[Any, Any, Any, Any, Any, Any]]:
    modules = _crypto_modules()
    serialization, rsa, _padding, _hashes, _invalid_signature, unsupported = modules
    pem = _pem_bytes(private_key_pem, "privateKey")
    password_bytes = _password_bytes(password)
    try:
        key = serialization.load_pem_private_key(pem, password=password_bytes)
    except (ValueError, TypeError, unsupported):
        raise RsaSignatureError("INVALID_PRIVATE_KEY", "privateKey") from None
    if not isinstance(key, rsa.RSAPrivateKey):
        raise RsaSignatureError("INVALID_PRIVATE_KEY", "privateKey")
    return key, modules


def _load_public_key(
    public_key_pem: object,
) -> tuple[Any, tuple[Any, Any, Any, Any, Any, Any]]:
    modules = _crypto_modules()
    serialization, rsa, _padding, _hashes, _invalid_signature, unsupported = modules
    pem = _pem_bytes(public_key_pem, "publicKey")
    try:
        key = serialization.load_pem_public_key(pem)
    except (ValueError, TypeError, unsupported):
        raise RsaSignatureError("INVALID_PUBLIC_KEY", "publicKey") from None
    if not isinstance(key, rsa.RSAPublicKey):
        raise RsaSignatureError("INVALID_PUBLIC_KEY", "publicKey")
    return key, modules


def _pss_sha256(modules: tuple[Any, Any, Any, Any, Any, Any]) -> tuple[Any, Any]:
    _serialization, _rsa, padding, hashes, _invalid_signature, _unsupported = modules
    digest = hashes.SHA256()
    return (
        padding.PSS(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        digest,
    )


def _sign_loaded_key(
    message: bytes, key: Any, modules: tuple[Any, Any, Any, Any, Any, Any]
) -> bytes:
    pss, digest = _pss_sha256(modules)
    try:
        return key.sign(message, pss, digest)
    except (ValueError, TypeError, OverflowError, modules[5]):
        raise RsaSignatureError("SIGNING_FAILED", "privateKey") from None


def _subject_public_key_pem(key: Any, modules: tuple[Any, Any, Any, Any, Any, Any]) -> bytes:
    serialization = modules[0]
    try:
        return key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    except (ValueError, TypeError, OverflowError, modules[5]):
        raise RsaSignatureError("SIGNING_FAILED", "privateKey") from None


def sign_bytes(
    message: object,
    private_key_pem: object,
    password: object = None,
) -> bytes:
    """Sign exact message bytes with an RSA PEM private key."""

    message_bytes = _octets(message, "message")
    key, modules = _load_private_key(private_key_pem, password)
    return _sign_loaded_key(message_bytes, key, modules)


def sign_with_public_key(
    message: object,
    private_key_pem: object,
    password: object = None,
) -> tuple[bytes, bytes]:
    """Sign bytes and derive SubjectPublicKeyInfo PEM from the same private key."""

    message_bytes = _octets(message, "message")
    key, modules = _load_private_key(private_key_pem, password)
    signature = _sign_loaded_key(message_bytes, key, modules)
    public_key_pem = _subject_public_key_pem(key, modules)
    return signature, public_key_pem


def verify_bytes(message: object, signature: object, public_key_pem: object) -> bool:
    """Verify exact message bytes with an RSA PEM public key.

    Cryptographic mismatches, including wrong length or wrong-key signatures,
    are ordinary ``False`` results.  Key parsing and input-type failures stay
    typed domain errors for the transport adapter.
    """

    message_bytes = _octets(message, "message")
    signature_bytes = _octets(signature, "signature")
    key, modules = _load_public_key(public_key_pem)
    pss, digest = _pss_sha256(modules)
    try:
        key.verify(signature_bytes, message_bytes, pss, digest)
    except modules[4]:
        return False
    except (ValueError, TypeError):
        # OpenSSL may report a malformed representative as ValueError rather
        # than InvalidSignature on some backend paths; it is still an invalid
        # signature, not a malformed key.
        return False
    except modules[5]:
        raise RsaSignatureError("VERIFICATION_FAILED", "publicKey") from None
    return True


def encode_signature(signature: object) -> str:
    """Encode one non-empty signature byte string as strict standard base64."""

    signature_bytes = _octets(signature, "signature")
    if not signature_bytes:
        raise RsaSignatureError("INVALID_SIGNATURE_ENCODING", "signature")
    return base64.b64encode(signature_bytes).decode("ascii")


def decode_signature(value: object) -> bytes:
    """Decode one canonical standard-base64 signature string."""

    if isinstance(value, str):
        try:
            encoded = value.encode("ascii")
        except UnicodeEncodeError:
            raise RsaSignatureError("INVALID_SIGNATURE_ENCODING", "signature") from None
    elif isinstance(value, (bytes, bytearray, memoryview)):
        try:
            encoded = bytes(value)
        except (TypeError, ValueError):
            raise RsaSignatureError("INVALID_SIGNATURE_ENCODING", "signature") from None
    else:
        raise RsaSignatureError("INVALID_SIGNATURE_ENCODING", "signature")

    if not encoded:
        raise RsaSignatureError("INVALID_SIGNATURE_ENCODING", "signature")
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError, TypeError):
        raise RsaSignatureError("INVALID_SIGNATURE_ENCODING", "signature") from None
    if not decoded or base64.b64encode(decoded) != encoded:
        raise RsaSignatureError("INVALID_SIGNATURE_ENCODING", "signature")
    return decoded


def sign_bytes_base64(
    message: object,
    private_key_pem: object,
    password: object = None,
) -> str:
    """Sign exact bytes and return the API-boundary base64 signature."""

    return encode_signature(sign_bytes(message, private_key_pem, password))


def verify_bytes_base64(message: object, signature: object, public_key_pem: object) -> bool:
    """Decode an API-boundary base64 signature and verify exact message bytes."""

    return verify_bytes(message, decode_signature(signature), public_key_pem)


encode_signature_base64 = encode_signature
decode_signature_base64 = decode_signature
sign_base64 = sign_bytes_base64
verify_base64 = verify_bytes_base64


__all__ = [
    "MAX_DECIMAL_DIGITS",
    "MAX_EXPONENT_BITS",
    "MAX_OPERAND",
    "RSASignatureError",
    "RsaSignatureError",
    "decode_signature",
    "decode_signature_base64",
    "encode_signature",
    "encode_signature_base64",
    "parse_canonical_decimal",
    "parse_decimal",
    "raw_sign",
    "raw_verify",
    "serialize_canonical_decimal",
    "serialize_decimal",
    "sign_base64",
    "sign_bytes",
    "sign_bytes_base64",
    "sign_integer",
    "sign_raw",
    "sign_with_public_key",
    "verify_base64",
    "verify_bytes",
    "verify_bytes_base64",
    "verify_integer",
    "verify_raw",
]
