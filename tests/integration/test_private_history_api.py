"""Browser-profile privacy and RSA history integration coverage."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config as AlembicConfig
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from alembic import command as alembic_command
from app import config
from app.main import app

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _url(path: Path) -> str:
    return f"sqlite+aiosqlite:////{path.as_posix().lstrip('/')}"


def _migrate(url: str) -> None:
    alembic_config = AlembicConfig(str(PROJECT_ROOT / "alembic_sqlite.ini"))
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        alembic_command.upgrade(alembic_config, "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


@pytest.fixture
def private_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")


@pytest.fixture
def history_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[tuple[Path, TestClient]]:
    path = tmp_path / "private-history.sqlite3"
    url = _url(path)
    _migrate(url)
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("HISTORY_API_ENABLED", "true")
    monkeypatch.setenv("HISTORY_COOKIE_SECURE", "false")
    with TestClient(app, raise_server_exceptions=False) as client:
        yield path, client


def _raw_sign(client: TestClient):
    return client.post(
        "/api/rsa/sign/raw",
        json={"m": "65", "d": "2753", "e": "17", "n": "3233"},
    )


def test_profile_isolation_reload_and_delete(history_runtime) -> None:
    _path, owner = history_runtime
    signed = _raw_sign(owner)
    assert signed.status_code == 200
    history_id = signed.json()["history"]["id"]
    assert signed.json()["history"]["saved"] is True

    own_list = owner.get("/api/history")
    assert [item["id"] for item in own_list.json()["result"]["items"]] == [history_id]

    owner_token = owner.cookies.get(config.HISTORY_COOKIE_NAME)
    assert owner_token is not None
    owner.cookies.clear()
    assert owner.get("/api/history").json()["result"]["items"] == []
    assert owner.get(f"/api/history/{history_id}").status_code == 404
    owner.cookies.clear()
    owner.cookies.set(config.HISTORY_COOKIE_NAME, owner_token)

    deleted = owner.delete(f"/api/history/{history_id}")
    assert deleted.status_code == 200
    assert owner.get("/api/history").json()["result"]["items"] == []


def test_profile_cookie_survives_a_new_browser_session(history_runtime) -> None:
    _path, owner = history_runtime
    signed = _raw_sign(owner)
    history_id = signed.json()["history"]["id"]
    token = owner.cookies.get(config.HISTORY_COOKIE_NAME)
    assert token is not None

    with TestClient(app, raise_server_exceptions=False) as reopened:
        reopened.cookies.set(config.HISTORY_COOKIE_NAME, token)
        reopened.headers["X-History-Owner"] = "attacker-chosen-owner"
        page = reopened.get("/api/history")
        assert [item["id"] for item in page.json()["result"]["items"]] == [history_id]


def test_empty_profile_cookie_is_stable_and_tampering_rotates(history_runtime) -> None:
    _path, client = history_runtime
    assert client.get("/api/history").status_code == 200
    token = client.cookies.get(config.HISTORY_COOKIE_NAME)
    assert token is not None

    assert client.get("/api/history").status_code == 200
    assert client.cookies.get(config.HISTORY_COOKIE_NAME) == token

    client.cookies.clear()
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    response = client.get(
        "/api/history", headers={"Cookie": f"{config.HISTORY_COOKIE_NAME}={tampered}"}
    )
    assert response.status_code == 200
    replacement = response.cookies.get(config.HISTORY_COOKIE_NAME)
    assert replacement is not None and replacement != token


def test_exact_file_retrieval_detail_and_delete_all(history_runtime, private_pem: str) -> None:
    _path, client = history_runtime
    content = b"\xef\xbb\xbfA\r\nB\rC\n"
    signed = client.post(
        "/api/rsa/sign",
        data={"privateKeyPem": private_pem},
        files={"file": ("original.txt", content)},
    )
    assert signed.status_code == 200
    history_id = signed.json()["history"]["id"]
    detail = client.get(f"/api/history/{history_id}")
    assert detail.status_code == 200
    payload = detail.json()["result"]["payload"]
    assert "content" not in payload
    assert payload["signature"] == signed.json()["result"]["signature"]
    assert "private" not in detail.text.lower()
    downloaded = client.get(f"/api/history/{history_id}/content")
    assert downloaded.status_code == 200
    assert downloaded.content == content

    deleted = client.delete("/api/history")
    assert deleted.status_code == 200
    assert deleted.json()["result"]["deleted"] >= 1


def test_false_verification_is_saved_as_completed(history_runtime) -> None:
    _path, client = history_runtime
    response = client.post(
        "/api/rsa/verify/raw",
        json={"m": "66", "signature": "588", "e": "17", "n": "3233"},
    )
    assert response.status_code == 200
    assert response.json()["result"]["valid"] is False
    assert response.json()["history"]["saved"] is True
    detail = client.get(f"/api/history/{response.json()['history']['id']}").json()["result"]
    assert detail["valid"] is False
    assert detail["processingState"] == "completed"
    assert detail["succeeded"] is True


def test_invalid_key_does_not_persist_content_or_secret(
    history_runtime,
) -> None:
    path, client = history_runtime
    marker = "do-not-persist-marker"
    before = client.get("/api/history").json()["result"]["items"]
    response = client.post(
        "/api/rsa/sign",
        json={
            "source": "text",
            "text": marker,
            "privateKeyPem": f"-----BEGIN PRIVATE KEY-----\n{marker}\n",
            "passphrase": marker,
        },
    )
    assert response.status_code == 422
    assert client.get("/api/history").json()["result"]["items"] == before
    with sqlite3.connect(path) as connection:
        dumped = "\n".join(connection.iterdump())
    assert marker not in dumped


def test_history_failure_does_not_suppress_result(
    history_runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    _path, client = history_runtime

    async def fail(*_args, **_kwargs):
        raise sqlite3.OperationalError("private marker must not be returned")

    monkeypatch.setattr("app.api.routes_rsa_signatures.save_signature_history", fail)
    response = _raw_sign(client)
    assert response.status_code == 200
    assert response.json()["result"]["signature"] == "588"
    assert response.json()["history"] == {
        "saved": False,
        "id": None,
        "reason": "unavailable",
    }
    assert "private marker" not in response.text


def test_cookie_is_http_only_and_server_generated(history_runtime) -> None:
    _path, client = history_runtime
    response = _raw_sign(client)
    cookie = response.headers.get("set-cookie", "")
    assert config.HISTORY_COOKIE_NAME in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
