"""Opt-in CORS: off by default, exact allowlist from ``CORS_ALLOW_ORIGINS`` when set."""

from __future__ import annotations

import importlib
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.main as app_main
from app import config

FE_ORIGIN = "https://fe.example.com"


def _reload_app(monkeypatch: pytest.MonkeyPatch, origins: str | None) -> FastAPI:
    if origins is None:
        monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("CORS_ALLOW_ORIGINS", origins)
    return importlib.reload(app_main).app


@pytest.fixture(autouse=True)
def restore_app_module() -> Iterator[None]:
    yield
    with pytest.MonkeyPatch.context() as patch:
        patch.delenv("CORS_ALLOW_ORIGINS", raising=False)
        importlib.reload(app_main)


@pytest.fixture
def cors_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    app = _reload_app(monkeypatch, f" {FE_ORIGIN} , http://localhost:5173 ")
    with TestClient(app) as client:
        yield client


def test_no_cors_headers_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _reload_app(monkeypatch, None)
    with TestClient(app) as client:
        response = client.post(
            "/api/caesar/encrypt", json={"text": "Hi", "key": 1}, headers={"Origin": FE_ORIGIN}
        )
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_allowed_origin_gets_cors_headers(cors_client: TestClient) -> None:
    response = cors_client.post(
        "/api/caesar/encrypt", json={"text": "Hi", "key": 1}, headers={"Origin": FE_ORIGIN}
    )
    assert response.json() == {"success": True, "result": "Ij"}
    assert response.headers["access-control-allow-origin"] == FE_ORIGIN
    assert response.headers["access-control-expose-headers"] == "Content-Disposition"
    assert "access-control-allow-credentials" not in response.headers


def test_preflight_allows_only_get_post_and_content_type(cors_client: TestClient) -> None:
    response = cors_client.options(
        "/api/caesar/encrypt",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert set(response.headers["access-control-allow-methods"].split(", ")) == {"GET", "POST"}

    rejected = cors_client.options(
        "/api/caesar/encrypt",
        headers={"Origin": FE_ORIGIN, "Access-Control-Request-Method": "DELETE"},
    )
    assert rejected.status_code == 400


def test_other_origins_get_no_cors_headers(cors_client: TestClient) -> None:
    response = cors_client.post(
        "/api/caesar/encrypt",
        json={"text": "Hi", "key": 1},
        headers={"Origin": "https://evil.example.com"},
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_guard_rejection_still_carries_cors_headers(cors_client: TestClient) -> None:
    response = cors_client.post(
        "/api/caesar/encrypt",
        content=b"{}",
        headers={
            "Origin": FE_ORIGIN,
            "content-type": "application/json",
            "content-length": str(64 * 1024 * 1024 + 1),
        },
    )
    assert response.status_code == 413
    assert response.headers["access-control-allow-origin"] == FE_ORIGIN


@pytest.mark.parametrize(
    "value",
    ["*", "https://*.example.com", "fe.example.com", "https://fe.example.com/", "ftp://fe.example"],
)
def test_invalid_origin_list_fails_fast(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", value)
    with pytest.raises(ValueError):
        config.cors_allow_origins()


def test_blank_origin_list_disables_cors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", " , ")
    assert config.cors_allow_origins() == ()
