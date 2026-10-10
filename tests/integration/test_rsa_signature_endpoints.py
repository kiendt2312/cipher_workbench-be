"""End-to-end transport coverage for RSA signature routes without persistence."""

from __future__ import annotations

import base64
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app import config
from app.main import app


@pytest.fixture(scope="module")
def rsa_material() -> dict[str, str]:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    password = b"test-only password"
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    encrypted_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(password),
    )
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return {
        "private": private_pem.decode("ascii"),
        "encrypted": encrypted_pem.decode("ascii"),
        "password": password.decode("ascii"),
        "public": public_pem.decode("ascii"),
    }


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("HISTORY_COOKIE_SECURE", "false")
    with TestClient(app, raise_server_exceptions=False) as value:
        yield value


def test_raw_sign_and_true_false_verification(client: TestClient) -> None:
    signed = client.post("/api/rsa/sign/raw", json={"m": "65", "d": "2753", "e": "17", "n": "3233"})
    assert signed.status_code == 200
    body = signed.json()
    assert body["result"]["signature"] == "588"
    assert body["result"]["publicKey"] == {"e": "17", "n": "3233"}
    assert body["result"]["trace"]["result"] == "588"
    assert body["history"] == {"saved": False, "id": None, "reason": "disabled"}

    valid = client.post(
        "/api/rsa/verify/raw",
        json={"m": "65", "signature": "588", "e": "17", "n": "3233"},
    )
    invalid = client.post(
        "/api/rsa/verify/raw",
        json={"m": "66", "signature": "588", "e": "17", "n": "3233"},
    )
    assert valid.status_code == invalid.status_code == 200
    assert valid.json()["result"]["valid"] is True
    assert invalid.json()["result"]["valid"] is False


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"m": "1", "d": "1", "e": "1", "n": "1"}, "n"),
        ({"m": "2", "d": "1", "e": "1", "n": "2"}, "m"),
        ({"m": "1", "d": "0", "e": "1", "n": "2"}, "d"),
    ],
)
def test_raw_bounds(client: TestClient, payload: dict[str, str], field: str) -> None:
    response = client.post("/api/rsa/sign/raw", json=payload)
    assert response.status_code == 422
    assert response.json()["field"] == field


def test_raw_out_of_range_signature_is_request_error(client: TestClient) -> None:
    response = client.post(
        "/api/rsa/verify/raw",
        json={"m": "1", "signature": "3233", "e": "17", "n": "3233"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "SIGNATURE_OUT_OF_RANGE"


@pytest.mark.parametrize("encrypted", [False, True])
def test_standard_text_sign_verify_and_invalid_result(
    client: TestClient, rsa_material: dict[str, str], encrypted: bool
) -> None:
    text = " \ufeffA\r\nế\n "
    payload = {
        "source": "text",
        "text": text,
        "privateKeyPem": rsa_material["encrypted" if encrypted else "private"],
    }
    if encrypted:
        payload["passphrase"] = rsa_material["password"]
    signed = client.post("/api/rsa/sign", json=payload)
    assert signed.status_code == 200
    result = signed.json()["result"]
    assert result["contentBytes"] == len(text.encode("utf-8"))
    assert result["algorithm"]["saltLength"] == 32

    verified = client.post(
        "/api/rsa/verify",
        json={
            "source": "text",
            "text": text,
            "signature": result["signature"],
            "publicKeyPem": result["publicKeyPem"],
        },
    )
    wrong = client.post(
        "/api/rsa/verify",
        json={
            "source": "text",
            "text": text + "x",
            "signature": result["signature"],
            "publicKeyPem": result["publicKeyPem"],
        },
    )
    assert verified.status_code == wrong.status_code == 200
    assert verified.json()["result"]["valid"] is True
    assert wrong.json()["result"]["valid"] is False


def test_file_preserves_bom_and_newlines(client: TestClient, rsa_material: dict[str, str]) -> None:
    original = b"\xef\xbb\xbfA\r\nB\rC\n"
    signed = client.post(
        "/api/rsa/sign",
        data={"privateKeyPem": rsa_material["private"]},
        files={"file": ("proof.TXT", original, "application/octet-stream")},
    )
    assert signed.status_code == 200
    result = signed.json()["result"]
    assert result["contentBytes"] == len(original)
    verified = client.post(
        "/api/rsa/verify",
        data={"signature": result["signature"], "publicKeyPem": result["publicKeyPem"]},
        files={"file": ("proof.txt", original, "ignored/type")},
    )
    normalized = client.post(
        "/api/rsa/verify",
        data={"signature": result["signature"], "publicKeyPem": result["publicKeyPem"]},
        files={"file": ("proof.txt", original.replace(b"\r\n", b"\n"))},
    )
    assert verified.json()["result"]["valid"] is True
    assert normalized.json()["result"]["valid"] is False


def test_typed_text_preserves_unicode_normalization_form(
    client: TestClient, rsa_material: dict[str, str]
) -> None:
    signed = client.post(
        "/api/rsa/sign",
        json={"source": "text", "text": "é", "privateKeyPem": rsa_material["private"]},
    ).json()["result"]
    decomposed = client.post(
        "/api/rsa/verify",
        json={
            "source": "text",
            "text": "e\u0301",
            "signature": signed["signature"],
            "publicKeyPem": signed["publicKeyPem"],
        },
    )
    assert decomposed.status_code == 200
    assert decomposed.json()["result"]["valid"] is False


def test_empty_rejected_and_whitespace_accepted(
    client: TestClient, rsa_material: dict[str, str]
) -> None:
    empty = client.post(
        "/api/rsa/sign",
        data={"privateKeyPem": rsa_material["private"]},
        files={"file": ("empty.txt", b"")},
    )
    empty_text = client.post(
        "/api/rsa/sign",
        json={"source": "text", "text": "", "privateKeyPem": rsa_material["private"]},
    )
    whitespace = client.post(
        "/api/rsa/sign",
        json={"source": "text", "text": " \r\n\t", "privateKeyPem": rsa_material["private"]},
    )
    assert empty.status_code == 422
    assert empty_text.status_code == 422
    assert whitespace.status_code == 200


def test_exact_file_limit_and_first_byte_over(
    client: TestClient, rsa_material: dict[str, str]
) -> None:
    exact = client.post(
        "/api/rsa/sign",
        data={"privateKeyPem": rsa_material["private"]},
        files={"file": ("exact.txt", b"A" * config.MAX_FILE_BYTES)},
    )
    over = client.post(
        "/api/rsa/sign",
        data={"privateKeyPem": rsa_material["private"]},
        files={"file": ("over.txt", b"A" * (config.MAX_FILE_BYTES + 1))},
    )
    well_over = client.post(
        "/api/rsa/sign",
        data={"privateKeyPem": rsa_material["private"]},
        files={"file": ("well-over.txt", b"A" * (config.MAX_FILE_BYTES + 65_536))},
    )
    assert exact.status_code == 200
    assert exact.json()["result"]["contentBytes"] == config.MAX_FILE_BYTES
    assert over.status_code == 413
    assert well_over.status_code == 413


def test_typed_text_limit_counts_utf8_bytes(
    client: TestClient, rsa_material: dict[str, str]
) -> None:
    exact_text = "é" * (config.MAX_FILE_BYTES // 2)
    exact = client.post(
        "/api/rsa/sign",
        json={
            "source": "text",
            "text": exact_text,
            "privateKeyPem": rsa_material["private"],
        },
    )
    over = client.post(
        "/api/rsa/sign",
        json={
            "source": "text",
            "text": exact_text + "A",
            "privateKeyPem": rsa_material["private"],
        },
    )
    assert exact.status_code == 200
    assert exact.json()["result"]["contentBytes"] == config.MAX_FILE_BYTES
    assert over.status_code == 413


def test_file_rejects_non_utf8_bytes(client: TestClient, rsa_material: dict[str, str]) -> None:
    response = client.post(
        "/api/rsa/sign",
        data={"privateKeyPem": rsa_material["private"]},
        files={"file": ("invalid.txt", b"\xff")},
    )
    assert response.status_code == 415
    assert response.json()["code"] == "INVALID_TEXT_ENCODING"


def test_invalid_key_error_does_not_echo_secret(client: TestClient) -> None:
    marker = "owner-secret-marker"
    response = client.post(
        "/api/rsa/sign",
        json={
            "source": "text",
            "text": "message",
            "privateKeyPem": f"-----BEGIN PRIVATE KEY-----\n{marker}\n",
            "passphrase": marker,
        },
    )
    assert response.status_code == 422
    assert marker not in response.text


@pytest.mark.skipif(shutil.which("openssl") is None, reason="OpenSSL CLI is unavailable")
def test_api_signature_verifies_with_openssl(
    client: TestClient, rsa_material: dict[str, str], tmp_path: Path
) -> None:
    content = b"OpenSSL interoperability\r\n"
    signed = client.post(
        "/api/rsa/sign",
        data={"privateKeyPem": rsa_material["private"]},
        files={"file": ("interop.txt", content)},
    )
    assert signed.status_code == 200
    result = signed.json()["result"]
    (tmp_path / "content.txt").write_bytes(content)
    (tmp_path / "public.pem").write_text(result["publicKeyPem"], encoding="ascii")
    (tmp_path / "signature.bin").write_bytes(base64.b64decode(result["signature"]))
    completed = subprocess.run(
        [
            "openssl",
            "dgst",
            "-sha256",
            "-verify",
            str(tmp_path / "public.pem"),
            "-signature",
            str(tmp_path / "signature.bin"),
            "-sigopt",
            "rsa_padding_mode:pss",
            "-sigopt",
            "rsa_pss_saltlen:32",
            "-sigopt",
            "rsa_mgf1_md:sha256",
            str(tmp_path / "content.txt"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Verified OK" in completed.stdout

    (tmp_path / "private.pem").write_text(rsa_material["private"], encoding="ascii")
    external_signature = tmp_path / "external-signature.bin"
    created = subprocess.run(
        [
            "openssl",
            "dgst",
            "-sha256",
            "-sign",
            str(tmp_path / "private.pem"),
            "-out",
            str(external_signature),
            "-sigopt",
            "rsa_padding_mode:pss",
            "-sigopt",
            "rsa_pss_saltlen:32",
            "-sigopt",
            "rsa_mgf1_md:sha256",
            str(tmp_path / "content.txt"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    external = client.post(
        "/api/rsa/verify",
        data={
            "signature": base64.b64encode(external_signature.read_bytes()).decode("ascii"),
            "publicKeyPem": rsa_material["public"],
        },
        files={"file": ("external.txt", content)},
    )
    assert external.status_code == 200
    assert external.json()["result"]["valid"] is True
