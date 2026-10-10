"""Raw RSA signature validation and interoperable PEM/PSS vectors."""

from __future__ import annotations

import shutil
import subprocess

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding

from app.core import rsa_signatures as signatures

# Fixed test material.  The implementation never generates or persists keys.
PRIVATE_KEY = b"""-----BEGIN PRIVATE KEY-----
MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQCx4FpJZOpIF7DV
Alt7zbMJXv0oIO/DGvGrY5uy8MkF6Npi77ra1m5pXzLyqgW0oWSNpVhu/2W5K5Co
H9eK0MrgEhepeM66oZ8J/OWIKKFSYbXwOTtWmxAYXkZGRzT+JQm0yfKvXhYS5S3l
8Xoy8Zg/TYtj+v02U6mCqkUCeuk5qP7mz575W8E4VCQUAmlHl7GsH/VKoTjqKyaD
Gd1K8OLNmWU6HVvfb4hGW8eO9f6nLezWUaCk7TSrlxckKaWG2nsxDXKBfRZzs5DD
E9WNkUPil2aMViW1EpJVjvNIWmYaTbrb7jd4p5lqp2ScN9cTuWO/2SG7biyKebbE
6d0sUHuHAgMBAAECggEAMScsC+gFDZLuXI5gNV/sP4SuNC6V0rZZXeESn2oGQsnL
v1c7rUlgDWIvM/tjxDxtCu9L9rBAreCqAqt55nQ3+59ERqKJje0ng50M2IlRuvAh
VJacHRyQYAt9I+J9dFVLz1eW5nr7YpFOE6KdAALe7W9CO4iZ/C82QlNG6p6IYFQp
Xvh+ncgR96jYnynpt3DdCYxHqwX8injgGFNIiFG6YkVsibQPkzKdB343Do00ktpr
4kElzvF+vX0PPLWhQhC0hKdkZasuRWaRFWtpF36D4THnIhIX/M822ZYbCAS0MYan
F/LAJzQK+6fyUq27H/fhiV4SNpa09mZ1+lsZ7S3poQKBgQD6HgEDf/LbJ7g/7HfT
XG0Y4y4JM/n4W8EHVtziRTeulXgMVHX5334jH6lAlkKgKX/iAtP6oPDneLKn6zqj
RUOLQymkAOpskbxJD1e6A44VBxsMNcVVJXJsBrVXMV+3hFcpoRX1i3KYYqtnP37e
MCVP2w0CdE9fEvwMTkUe+0n1LwKBgQC2D2ADrgN94ziulFn5YzMgy00cBNGb+vxr
bsxrPP2rBE+d1fRgdI+ZpnCBTmqqrqkc01z3LqhIWbZQJ7Q0RepqTFGK3ISywHPA
3+qbdKUE2Ym/v79K4TqaRGBCTBPBhknnR8RhkDDCuYRt2KowXLyR2stzGBAxR0R+
xa0FxXt5KQKBgDXnOXiznnc0vDSqlbhrdueiLk21ce3geF1IjxoEqNdrRxABM9vC
GsEfFa7hs0IpL3JaAa1F+iUokfg2bdC6ILBmrRa3S85SKi3krJdeJMTLXzzmabzL
8TjuyS4dae93CgHiwYTFpNDKkv4RZRolbiUjpE4fGuv2f3N3etYOegXpAoGAGuKe
XSy/W0HIxw8lUkyx6i/bjT2w7oXb7MmJ6nQxSaXzU+2ajvvnkNshVhcMbXQpiRY1
blM3iqek4qVaWTXR7iyjBgyWlAcTkPIAJUDOda7iRqy8RQSJsOpUBLZTXIrGMx9I
AthWOwtGYSpTx5yKREe5L5/oFD7gAJCUgnutRjECgYB5QKyegEHgVp3LYR3Vrhpo
ZLm6MpakpRlNU9l4sIyX82NHu0k+/QOTivFvhgjFrzD68OZSFSD4314s7/qjhsRS
u6tiqz9QVoogm73zHATa77hKqkLfSPYvtD9bmIsVKnGMP9YheXXi7u2w7ucd7aII
BZf/nGfVUjZCpej5gvXw1A==
-----END PRIVATE KEY-----
"""

ENCRYPTED_PRIVATE_KEY = b"""-----BEGIN ENCRYPTED PRIVATE KEY-----
MIIFNTBfBgkqhkiG9w0BBQ0wUjAxBgkqhkiG9w0BBQwwJAQQhDaG85O3OD7idv2W
RdAXxwICCAAwDAYIKoZIhvcNAgkFADAdBglghkgBZQMEASoEEEhMfhCa2cVM1EfY
d15wD/UEggTQd9kZQG3cC3SOkgeko5QqAbC7auNkYNbjaygBH9zSPHRFRLcJl6su
9PJS5PlO63dmBiwHZHrgKhUH3leMTOpi5v0Aejuo/NtjG9w0cFyDlInPjBokTJAz
y9LjqelMkqyewIhwpqu6aUGpF2g9npNbkjric/KrBJEaQX4Q6Dv5SVYQeQRyX+4c
rtdoRCI1SgNyiRZ9MwCpKDpnV2J//wVnHs0W1CL+rX2MCNUEBnMQGNt/efHS3sQk
/gIQkM7kzQvMylVCXUebpyGNUUNGYhcMFIfKQdNOyMUk7gtPje4fB9nn+VoI5E3J
cTYTL9Df13y2xj2RniZOw83ea9QdyEL93y6Ld08/qF3hWlpKxcF6UQg+KcFySnz0
xp4OqLP0/VpabnkvFPkcokaoztXgDMqd26XOp991RG36xQYeS3TEplEq5zlxp8Ac
iKt6KGxJM25CFkrSXa5iAX4FGWS25D5FFRZy/znGbKhoTwnpubDGUdjR9IeGlocH
m6b6uRxeGMchJN+uFJ1iIHE+C8w6kw5Q6vhuQluelqf4+CBNpVZm/jJF3s0/nIRS
leWeSu5K25SZen/1T1tPc30IDCADDlYyST1WzNhtUPg+W8lw2gf5g5Uj2mTStAGk
S766mqceNQM9L0bAn5VXs1uwCPjpuSt5V7XTAi5e3C3k/UrJLIz/q45b1xXQk+Dh
A5xA2hwCXHROokAo6HkvBpeeIY5ffzxXunU5+xIe2hzP+TOZTwpxxRAr3CV+9ooy
p10nRrE1eg6oLe57q/oPgtB2jRKqiMBWfX8WS1F8yaiyQ5VyqvdhVWori6wXcNFz
FnDPk0sJ4mvniUvFTm7mdlc/6FHxGKZye810bNnv1APCZEHl7sd6QWpUtZXqyj4e
HlEso5A0Cile7hOloB9FdiDyvmqCk97nvA2JmV9TrH+j5fpK9XRSN+gNZh4YiY2l
Ko4zaoIWEFY+hxd81r8yLfrUF5DdBbWmlk2tfDLcVnxUZ/P6+wiFGZYrWACKlom+
lmkpJY9NGFbhKYwXvtvRmfrA4NbCeTZXRuoqWeEwo2gS8ZA+uiMm0dc3Sp0dV3Rg
+WLjzAsXYDnWRAYga2x95JDlYZdXgJcDFwoxera0bN9fN42Jn/XYnHVQ+rJDFFRU
r0hVkHghl1EzYBj2uoicPBq3vIouUoWK6M5tyFPS56T5I35qrY6fKOjtzl6x0oWY
8nRMm7HT6cdL5baFSXQSGh/pmdUAa2ToNTU9UsHtO6sNiijiSaIlNhVzhLkDHcnb
j/dFnteZCb51OMoYGIEcjrWrxGsU2H7BjsZb9IRVKSideka9h2iUkkOAPCqJBYbi
Srpa+kt7OU/Vn6K/Fj0tx3ANORWJVRKvsDyxJt33pSvFS03X00sqMkLn26fqM51T
XIo+aKQUfyQoGh+rEpxhnQMFmRVdO6tVnSm3p4mHqgopvvikmx+8YQq3rycEOOCi
YO4hLpJ9y63XfxwSSE0yhExu0+1IAgjjsqKCrvdaGLjsHID7t1dLl8pe32liwPLe
pAxhQ+x78kPNgP2GshVe+bpIiLQwGIC4cV2bggTcUxisRcOFncTgsLwxjN4EH+XA
pck+GUpWcrzIG1OBukdryH1392Zx0eLaO7gbiCeSJZVbAQGqzfaV/x8=
-----END ENCRYPTED PRIVATE KEY-----
"""

PUBLIC_KEY = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAseBaSWTqSBew1QJbe82z
CV79KCDvwxrxq2ObsvDJBejaYu+62tZuaV8y8qoFtKFkjaVYbv9luSuQqB/XitDK
4BIXqXjOuqGfCfzliCihUmG18Dk7VpsQGF5GRkc0/iUJtMnyr14WEuUt5fF6MvGY
P02LY/r9NlOpgqpFAnrpOaj+5s+e+VvBOFQkFAJpR5exrB/1SqE46ismgxndSvDi
zZllOh1b32+IRlvHjvX+py3s1lGgpO00q5cXJCmlhtp7MQ1ygX0Wc7OQwxPVjZFD
4pdmjFYltRKSVY7zSFpmGk262+43eKeZaqdknDfXE7ljv9khu24sinm2xOndLFB7
hwIDAQAB
-----END PUBLIC KEY-----
"""

PASSWORD = b"test-passphrase"
MESSAGE_CASES = (
    b"exact bytes",
    b"\xef\xbb\xbfBOM\r\nline\n",
    b"",
)


def test_decimal_domain_is_strict_bounded_and_canonical() -> None:
    assert signatures.parse_decimal("00065", "message") == 65
    assert signatures.serialize_decimal(65, "signature") == "65"
    assert signatures.parse_canonical_decimal(str(signatures.MAX_OPERAND), "n") == (
        signatures.MAX_OPERAND
    )

    for value in (
        "",
        "+1",
        "-1",
        " 1",
        "1 ",
        "1.0",
        "1e3",
        "1_0",
        "\uff11\uff12\uff13",
        1,
        True,
        None,
    ):
        with pytest.raises(signatures.RsaSignatureError) as caught:
            signatures.parse_decimal(value, "n")
        assert caught.value.code == "NOT_INTEGER"

    with pytest.raises(signatures.RsaSignatureError) as caught:
        signatures.parse_decimal("0" * (signatures.MAX_DECIMAL_DIGITS + 1), "n")
    assert caught.value.code == "NUMBER_TOO_LARGE"
    with pytest.raises(signatures.RsaSignatureError) as caught:
        signatures.serialize_decimal(signatures.MAX_OPERAND + 1, "signature")
    assert caught.value.code == "NUMBER_TOO_LARGE"


def test_raw_integer_sign_verify_and_invalid_signature_results() -> None:
    signed = signatures.sign_integer("00065", "2753", "17", "3233")
    assert signed == "588"
    assert signatures.verify_integer("65", signed, "17", "3233") is True
    assert signatures.raw_verify("65", "589", "17", "3233") is False
    with pytest.raises(signatures.RsaSignatureError) as caught:
        signatures.verify_raw("65", str(3233), "17", "3233")
    assert (caught.value.code, caught.value.field) == ("SIGNATURE_OUT_OF_RANGE", "signature")
    assert signatures.sign_raw("65", "2753", "17", "3233") == signed

    # Both exponents are positive and bounded; d need not be less than n.
    assert signatures.sign_integer("65", "3233", "3233", "3233") == str(pow(65, 3233, 3233))

    with pytest.raises(signatures.RsaSignatureError) as caught:
        signatures.sign_integer("3233", "2753", "17", "3233")
    assert (caught.value.code, caught.value.field) == ("MESSAGE_OUT_OF_RANGE", "m")

    for args, code, field in (
        (("65", "2753", "17", "1"), "N_TOO_SMALL", "n"),
        (("65", "2753", "0", "3233"), "EXPONENT_OUT_OF_RANGE", "e"),
        (("65", "0", "17", "3233"), "EXPONENT_OUT_OF_RANGE", "d"),
        (("65", str(signatures.MAX_OPERAND + 1), "17", "3233"), "NUMBER_TOO_LARGE", "d"),
    ):
        with pytest.raises(signatures.RsaSignatureError) as caught:
            signatures.sign_integer(*args)
        assert (caught.value.code, caught.value.field) == (code, field)

    with pytest.raises(signatures.RsaSignatureError) as caught:
        signatures.verify_integer("65", "3233", "17", "3233")
    assert (caught.value.code, caught.value.field) == ("SIGNATURE_OUT_OF_RANGE", "signature")

    for malformed in ("", "+1", "1.0", "\u0661"):
        with pytest.raises(signatures.RsaSignatureError) as caught:
            signatures.verify_integer("65", malformed, "17", "3233")
        assert caught.value.code == "NOT_INTEGER"


@pytest.mark.parametrize("message", MESSAGE_CASES)
def test_pem_sign_verify_preserves_exact_bytes(message: bytes) -> None:
    signature = signatures.sign_bytes(message, PRIVATE_KEY)
    assert signatures.verify_bytes(message, signature, PUBLIC_KEY) is True
    assert signatures.verify_bytes(message + b"\x00", signature, PUBLIC_KEY) is False
    assert signatures.verify_bytes(message, signature[:-1], PUBLIC_KEY) is False


def test_encrypted_private_key_accepts_bytes_or_text_password_and_redacts_errors() -> None:
    first = signatures.sign_bytes(b"encrypted", ENCRYPTED_PRIVATE_KEY, PASSWORD)
    second = signatures.sign_bytes(b"encrypted", ENCRYPTED_PRIVATE_KEY, PASSWORD.decode())
    assert signatures.verify_bytes(b"encrypted", first, PUBLIC_KEY) is True
    assert signatures.verify_bytes(b"encrypted", second, PUBLIC_KEY) is True

    with pytest.raises(signatures.RsaSignatureError) as caught:
        signatures.sign_bytes(b"encrypted", ENCRYPTED_PRIVATE_KEY, b"wrong-passphrase")
    assert caught.value.code == "INVALID_PRIVATE_KEY"
    assert "wrong-passphrase" not in str(caught.value)
    assert "ENCRYPTED PRIVATE KEY" not in str(caught.value)


def test_sign_with_public_key_derives_subject_public_key_info_from_loaded_key() -> None:
    message = b"derive once\r\n\xef\xbb\xbf"
    signature, derived_public_key = signatures.sign_with_public_key(
        message, ENCRYPTED_PRIVATE_KEY, PASSWORD
    )

    assert signatures.verify_bytes(message, signature, derived_public_key) is True
    assert derived_public_key.startswith(b"-----BEGIN PUBLIC KEY-----")

    private_key = serialization.load_pem_private_key(ENCRYPTED_PRIVATE_KEY, password=PASSWORD)
    expected_public_key = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    assert derived_public_key == expected_public_key


def test_malformed_keys_and_non_rsa_keys_are_typed_without_secret_text() -> None:
    for function, key, code, field in (
        (signatures.sign_bytes, b"not a key", "INVALID_PRIVATE_KEY", "privateKey"),
        (signatures.verify_bytes, b"not a key", "INVALID_PUBLIC_KEY", "publicKey"),
    ):
        with pytest.raises(signatures.RsaSignatureError) as caught:
            if function is signatures.sign_bytes:
                function(b"message", key, PASSWORD)
            else:
                function(b"message", b"signature", key)
        assert (caught.value.code, caught.value.field) == (code, field)
        assert "message" not in str(caught.value)
        assert "passphrase" not in str(caught.value)

    with pytest.raises(signatures.RsaSignatureError) as caught:
        signatures.sign_bytes("text must not be normalized", PRIVATE_KEY)
    assert caught.value.code == "INVALID_BYTES"


def test_base64_boundary_is_canonical_and_malformed_values_raise() -> None:
    signature = signatures.sign_bytes(b"base64", PRIVATE_KEY)
    encoded = signatures.encode_signature(signature)
    assert encoded == signatures.encode_signature_base64(signature)
    assert signatures.decode_signature(encoded) == signature
    assert signatures.decode_signature_base64(encoded) == signature
    assert signatures.verify_bytes_base64(b"base64", encoded, PUBLIC_KEY) is True
    altered = ("A" if encoded[0] != "A" else "B") + encoded[1:]
    assert signatures.verify_base64(b"base64", altered, PUBLIC_KEY) is False

    for malformed in ("", "not base64", "====", encoded + " ", "\u00e9"):
        with pytest.raises(signatures.RsaSignatureError) as caught:
            signatures.decode_signature(malformed)
        assert caught.value.code == "INVALID_SIGNATURE_ENCODING"
    with pytest.raises(signatures.RsaSignatureError) as caught:
        signatures.encode_signature(b"")
    assert caught.value.code == "INVALID_SIGNATURE_ENCODING"


def test_boundary_helpers_cover_bytes_integer_and_key_type_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(signatures.RsaSignatureError, match="NOT_INTEGER"):
        signatures.parse_decimal("0", allow_zero=False)
    with pytest.raises(signatures.RsaSignatureError, match="NUMBER_TOO_LARGE"):
        signatures.parse_decimal("2", max_value=1)
    for invalid in (-1, True, "1"):
        with pytest.raises(signatures.RsaSignatureError, match="NOT_INTEGER"):
            signatures.serialize_decimal(invalid)
    for invalid in (-1, signatures.MAX_OPERAND + 1):
        with pytest.raises(signatures.RsaSignatureError):
            signatures.sign_integer(0, invalid, 1, 2)
    with pytest.raises(signatures.RsaSignatureError, match="NUMBER_TOO_LARGE"):
        signatures._modular_power(1, 1 << signatures.MAX_EXPONENT_BITS, 2)

    assert signatures._octets(bytearray(b"a"), "message") == b"a"
    assert signatures._octets(memoryview(b"b"), "message") == b"b"
    with pytest.raises(signatures.RsaSignatureError, match="INVALID_BYTES"):
        signatures._octets("not-bytes", "message")
    assert signatures._pem_bytes(bytearray(PUBLIC_KEY), "publicKey") == PUBLIC_KEY
    with pytest.raises(signatures.RsaSignatureError, match="INVALID_KEY"):
        signatures._pem_bytes("ế", "publicKey")
    with pytest.raises(signatures.RsaSignatureError, match="INVALID_KEY"):
        signatures._pem_bytes(1, "publicKey")
    assert signatures._password_bytes(None) is None
    assert signatures._password_bytes(bytearray(PASSWORD)) == PASSWORD
    with pytest.raises(signatures.RsaSignatureError, match="INVALID_PASSPHRASE"):
        signatures._password_bytes("\ud800")
    with pytest.raises(signatures.RsaSignatureError, match="INVALID_PASSPHRASE"):
        signatures._password_bytes(1)

    ec_private = ec.generate_private_key(ec.SECP256R1())
    ec_private_pem = ec_private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    ec_public_pem = ec_private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    with pytest.raises(signatures.RsaSignatureError, match="INVALID_PRIVATE_KEY"):
        signatures.sign_bytes(b"message", ec_private_pem)
    with pytest.raises(signatures.RsaSignatureError, match="INVALID_PUBLIC_KEY"):
        signatures.verify_bytes(b"message", b"signature", ec_public_pem)

    original_import = signatures.import_module

    def missing_crypto(name: str):
        if name.startswith("cryptography"):
            raise ModuleNotFoundError
        return original_import(name)

    monkeypatch.setattr(signatures, "import_module", missing_crypto)
    with pytest.raises(signatures.RsaSignatureError, match="CRYPTOGRAPHY_UNAVAILABLE"):
        signatures._crypto_modules()


def test_backend_failures_are_typed_and_base64_accepts_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    modules = signatures._crypto_modules()

    class BrokenPrivate:
        def sign(self, *_args):
            raise ValueError("backend details")

        def public_key(self):
            return self

        def public_bytes(self, **_kwargs):
            raise ValueError("backend details")

    with pytest.raises(signatures.RsaSignatureError, match="SIGNING_FAILED"):
        signatures._sign_loaded_key(b"message", BrokenPrivate(), modules)
    with pytest.raises(signatures.RsaSignatureError, match="SIGNING_FAILED"):
        signatures._subject_public_key_pem(BrokenPrivate(), modules)

    class MalformedVerifier:
        def verify(self, *_args):
            raise ValueError("malformed representative")

    monkeypatch.setattr(
        signatures,
        "_load_public_key",
        lambda _value: (MalformedVerifier(), modules),
    )
    assert signatures.verify_bytes(b"message", b"signature", PUBLIC_KEY) is False

    encoded = signatures.sign_bytes_base64(b"wrapped", PRIVATE_KEY)
    assert signatures.decode_signature(bytearray(encoded.encode("ascii")))
    assert signatures.decode_signature(memoryview(encoded.encode("ascii")))
    with pytest.raises(signatures.RsaSignatureError, match="INVALID_SIGNATURE_ENCODING"):
        signatures.decode_signature(123)


def test_cryptography_primitives_interoperate_in_both_directions() -> None:
    private_key = serialization.load_pem_private_key(PRIVATE_KEY, password=None)
    public_key = serialization.load_pem_public_key(PUBLIC_KEY)
    message = b"cryptography oracle\r\n\xef\xbb\xbf"
    pss = padding.PSS(
        mgf=padding.MGF1(hashes.SHA256()),
        salt_length=padding.PSS.DIGEST_LENGTH,
    )

    ours = signatures.sign_bytes(message, PRIVATE_KEY)
    public_key.verify(ours, message, pss, hashes.SHA256())

    external = private_key.sign(message, pss, hashes.SHA256())
    assert signatures.verify_bytes(message, external, PUBLIC_KEY) is True


@pytest.mark.skipif(shutil.which("openssl") is None, reason="OpenSSL CLI is unavailable")
def test_openssl_pss_digest_salt_interoperability(tmp_path) -> None:
    message_path = tmp_path / "message.bin"
    private_path = tmp_path / "private.pem"
    encrypted_path = tmp_path / "encrypted-private.pem"
    public_path = tmp_path / "public.pem"
    ours_path = tmp_path / "ours.sig"
    openssl_path = tmp_path / "openssl.sig"
    message = b"OpenSSL exact bytes\r\n\xef\xbb\xbf"

    message_path.write_bytes(message)
    private_path.write_bytes(PRIVATE_KEY)
    encrypted_path.write_bytes(ENCRYPTED_PRIVATE_KEY)
    public_path.write_bytes(PUBLIC_KEY)
    ours_path.write_bytes(signatures.sign_bytes(message, ENCRYPTED_PRIVATE_KEY, PASSWORD))

    pss_options = (
        "-digest",
        "sha256",
        "-pkeyopt",
        "rsa_padding_mode:pss",
        "-pkeyopt",
        "rsa_pss_saltlen:-1",
    )
    subprocess.run(
        [
            "openssl",
            "pkeyutl",
            "-verify",
            "-rawin",
            "-in",
            str(message_path),
            "-inkey",
            str(public_path),
            "-pubin",
            "-sigfile",
            str(ours_path),
            *pss_options,
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "openssl",
            "pkeyutl",
            "-sign",
            "-rawin",
            "-in",
            str(message_path),
            "-inkey",
            str(encrypted_path),
            "-passin",
            "pass:test-passphrase",
            "-out",
            str(openssl_path),
            *pss_options,
        ],
        check=True,
        capture_output=True,
    )
    assert signatures.verify_bytes(message, openssl_path.read_bytes(), PUBLIC_KEY) is True
