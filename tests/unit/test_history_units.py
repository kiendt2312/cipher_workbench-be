"""Database-free tests for configuration, route matching and history cursors."""

from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app import config
from app.db.engine import create_database, ping
from app.errors.exceptions import InvalidHistoryCursorError
from app.history.cursor import Cursor, decode_cursor, encode_cursor
from app.history.routes import CIPHER_ROUTES, match_cipher_route


@pytest.mark.parametrize("value", [None, "", "   "])
def test_database_url_is_disabled_when_unset_or_blank(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    if value is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", value)
    assert config.database_url() is None


def test_database_url_is_read_and_trimmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", " postgresql+asyncpg://u:p@h/db ")
    assert config.database_url() == "postgresql+asyncpg://u:p@h/db"


def test_engine_is_lazy_and_ping_reports_unreachable_database() -> None:
    database = create_database("postgresql+asyncpg://nobody:secret@127.0.0.1:1/none")

    async def check() -> bool:
        try:
            return await ping(database)
        finally:
            await database.engine.dispose()

    assert asyncio.run(check()) is False


def test_exactly_twenty_cipher_routes_are_recorded() -> None:
    assert len(CIPHER_ROUTES) == 20
    assert "/api/hill/encrypt" in CIPHER_ROUTES
    assert "/api/hill/decrypt" in CIPHER_ROUTES
    assert "/api/hill/file" not in CIPHER_ROUTES
    assert "/api/hill/key/analyze" not in CIPHER_ROUTES
    assert {"/api/des/encrypt", "/api/des/decrypt", "/api/des/file"} <= CIPHER_ROUTES.keys()
    assert "/api/des/trace" not in CIPHER_ROUTES
    route = match_cipher_route("POST", "/api/affine/file")
    assert route is not None
    assert (route.cipher, route.source, route.operation) == ("affine", "file", None)
    route = match_cipher_route("POST", "/api/playfair/decrypt")
    assert route is not None
    assert (route.cipher, route.source, route.operation) == ("playfair", "text", "decrypt")


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/"),
        ("GET", "/static/app.js"),
        ("GET", "/docs"),
        ("GET", "/api/health"),
        ("GET", "/api/history"),
        ("GET", "/api/caesar/encrypt"),
        ("POST", "/api/caesar/encrypt/"),
        ("POST", "/api/rot13/encrypt"),
    ],
)
def test_non_cipher_requests_are_not_recorded(method: str, path: str) -> None:
    assert match_cipher_route(method, path) is None


@pytest.mark.parametrize(
    "created_at",
    [
        datetime(2026, 9, 28, 1, 2, 3, 456789, tzinfo=UTC),
        datetime(2026, 9, 28, 8, 0, tzinfo=timezone(timedelta(hours=7))),
    ],
)
def test_cursor_round_trips(created_at: datetime) -> None:
    cursor = Cursor(created_at=created_at, id=42)
    encoded = encode_cursor(cursor)
    assert "=" not in encoded
    assert decode_cursor(encoded) == cursor


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not base64!",
        "ộ",
        _b64(b"not json"),
        _b64(b"[]"),
        _b64(b'{"t": "2026-09-28T00:00:00+00:00"}'),
        _b64(b'{"t": "yesterday", "i": 1}'),
        _b64(b'{"t": "2026-09-28T00:00:00", "i": 1}'),
        _b64(b'{"t": "2026-09-28T00:00:00+00:00", "i": "1"}'),
        _b64(b'{"t": "2026-09-28T00:00:00+00:00", "i": true}'),
        _b64(b'{"t": "2026-09-28T00:00:00+00:00", "i": 0}'),
        _b64(b'{"t": "2026-09-28T00:00:00+00:00", "i": 9223372036854775808}'),
        _b64(b'{"t": 5, "i": 1}'),
    ],
)
def test_malformed_cursor_is_rejected(value: str) -> None:
    with pytest.raises(InvalidHistoryCursorError):
        decode_cursor(value)
