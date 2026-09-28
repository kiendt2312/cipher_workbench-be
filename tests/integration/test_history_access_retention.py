"""History read flag, retention settings and purge scheduling; no PostgreSQL required."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as app_main
from app import config
from app.errors import messages
from app.history import retention
from app.main import app

FAKE_URL = "postgresql+asyncpg://nobody:topsecret@127.0.0.1:1/none"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("value", ["true", "TRUE", " yes ", "1", "on"])
def test_history_flag_accepts_truthy_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("HISTORY_API_ENABLED", value)
    assert config.history_api_enabled() is True


@pytest.mark.parametrize("value", [None, "", "false", "0", "no", "enabled", "tru"])
def test_history_flag_is_off_otherwise(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    if value is None:
        monkeypatch.delenv("HISTORY_API_ENABLED", raising=False)
    else:
        monkeypatch.setenv("HISTORY_API_ENABLED", value)
    assert config.history_api_enabled() is False


@pytest.mark.parametrize(("value", "expected"), [(None, 30), ("", 30), ("1", 1), (" 90 ", 90)])
def test_retention_days_valid(
    monkeypatch: pytest.MonkeyPatch, value: str | None, expected: int
) -> None:
    if value is None:
        monkeypatch.delenv("HISTORY_RETENTION_DAYS", raising=False)
    else:
        monkeypatch.setenv("HISTORY_RETENTION_DAYS", value)
    assert config.history_retention_days() == expected


def test_retention_days_upper_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HISTORY_RETENTION_DAYS", "3650")
    assert config.history_retention_days() == 3650


@pytest.mark.parametrize("value", ["0", "3651", "-1", "abc", "1.5", "\uff13\uff10"])
def test_retention_days_invalid(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("HISTORY_RETENTION_DAYS", value)
    with pytest.raises(ValueError, match="HISTORY_RETENTION_DAYS"):
        config.history_retention_days()


def test_invalid_retention_stops_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HISTORY_RETENTION_DAYS", "0")
    with pytest.raises(ValueError, match="HISTORY_RETENTION_DAYS"), TestClient(app):
        pass


@pytest.fixture
def client_flag_off(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("HISTORY_API_ENABLED", raising=False)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.mark.parametrize("query", ["", "?limit=500", "?cursor=broken", "?cipher=rot13"])
def test_history_is_404_when_disabled(client_flag_off: TestClient, query: str) -> None:
    response = client_flag_off.get(f"/api/history{query}")
    assert response.status_code == 404
    assert response.json() == {"success": False, "message": messages.HISTORY_DISABLED}


def test_health_reports_history_disabled(client_flag_off: TestClient) -> None:
    response = client_flag_off.get("/api/health")
    assert response.status_code == 200
    assert response.json()["result"] == {
        "app": "ok",
        "database": "disabled",
        "history": "disabled",
    }


def test_disabled_flag_still_records(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import history_recorder

    recorded: list[object] = []

    async def fake_record(database: object, entry: object) -> None:
        recorded.append(entry)

    monkeypatch.setattr(history_recorder, "record_operation", fake_record)
    monkeypatch.setenv("DATABASE_URL", FAKE_URL)
    monkeypatch.delenv("HISTORY_API_ENABLED", raising=False)
    with TestClient(app) as client:
        client.post("/api/caesar/encrypt", json={"text": "Hi", "key": 1})
    assert len(recorded) == 1


def test_purge_task_runs_with_database_and_is_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    cancelled = asyncio.Event()

    async def fake_purge_periodically(database: object, days: int) -> None:
        calls.append(days)
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    monkeypatch.setattr(app_main, "purge_periodically", fake_purge_periodically)
    monkeypatch.setenv("DATABASE_URL", FAKE_URL)
    monkeypatch.setenv("HISTORY_RETENTION_DAYS", "7")
    with TestClient(app) as client:
        client.get("/api/health")
    assert calls == [7]
    assert cancelled.is_set()


def test_no_purge_task_without_database(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    async def fake_purge_periodically(database: object, days: int) -> None:
        calls.append(days)

    monkeypatch.setattr(app_main, "purge_periodically", fake_purge_periodically)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(app):
        pass
    assert calls == []


def test_purge_loop_survives_failures(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    attempts: list[int] = []

    async def failing_purge(database: object, days: int) -> int:
        attempts.append(days)
        raise ConnectionError(f"cannot reach {FAKE_URL}")

    monkeypatch.setattr(retention, "purge_expired", failing_purge)

    async def run() -> None:
        task = asyncio.create_task(retention.purge_periodically(object(), 30, 0.01))  # type: ignore[arg-type]
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    with caplog.at_level(logging.WARNING):
        asyncio.run(run())
    assert len(attempts) >= 2
    assert "Could not purge expired cipher operation history" in caplog.text
    assert "topsecret" not in caplog.text


def test_purge_command_requires_database_url() -> None:
    env = {key: value for key, value in os.environ.items() if key != "DATABASE_URL"}
    result = subprocess.run(
        [sys.executable, "-m", "app.history.retention"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "DATABASE_URL must be set" in result.stderr


def test_purge_command_failure_prints_no_connection_details() -> None:
    env = dict(os.environ)
    env["DATABASE_URL"] = "postgresql+asyncpg://nobody:topsecret@127.0.0.1:1/none"
    result = subprocess.run(
        [sys.executable, "-m", "app.history.retention"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert result.stderr.strip() == "Could not purge history rows"
    assert "topsecret" not in result.stdout + result.stderr
