"""History against a real PostgreSQL; runs only when ``TEST_DATABASE_URL`` is set."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.main import app
from tests.conftest import _run_alembic, run_sql
from tests.integration.history_cases import SENSITIVE_VALUES, cipher_requests

pytestmark = pytest.mark.db

EXPECTED_COLUMNS = {
    "id",
    "created_at",
    "cipher",
    "operation",
    "source",
    "response_mode",
    "input_length",
    "output_length",
    "http_status",
    "succeeded",
    "duration_ms",
}


def _insert_rows(url: str, count: int, cipher: str = "caesar", operation: str = "encrypt") -> None:
    run_sql(
        url,
        "INSERT INTO cipher_operations "
        "(created_at, cipher, operation, source, http_status, succeeded, duration_ms) "
        f"SELECT now() - make_interval(secs => n), '{cipher}', '{operation}', 'text', 200, "
        "true, 1 FROM generate_series(1, "
        f"{count}) AS n",
    )


def test_schema_matches_spec(db_url: str) -> None:
    columns = {
        row[0]
        for row in run_sql(
            db_url,
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'cipher_operations'",
        )
    }
    indexes = {
        row[0]
        for row in run_sql(
            db_url, "SELECT indexname FROM pg_indexes WHERE tablename = 'cipher_operations'"
        )
    }
    checks = {
        row[0]
        for row in run_sql(
            db_url,
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid = 'cipher_operations'::regclass AND contype = 'c'",
        )
    }

    assert columns == EXPECTED_COLUMNS
    assert {"ix_cipher_operations_created_at_id", "ix_cipher_operations_cipher_created_at"} <= (
        indexes
    )
    assert len(checks) == 7


def test_hill_migration_preserves_rows_and_allows_hill(db_url: str) -> None:
    _run_alembic(db_url, "downgrade", "0001")
    _insert_rows(db_url, 1, cipher="caesar")
    _run_alembic(db_url, "upgrade", "head")
    run_sql(
        db_url,
        "INSERT INTO cipher_operations "
        "(cipher, operation, source, http_status, succeeded, duration_ms) "
        "VALUES ('hill', 'encrypt', 'text', 200, true, 1)",
    )

    assert run_sql(db_url, "SELECT cipher FROM cipher_operations ORDER BY id") == [
        ("caesar",),
        ("hill",),
    ]
    with pytest.raises(IntegrityError):
        run_sql(
            db_url,
            "INSERT INTO cipher_operations "
            "(cipher, operation, source, http_status, succeeded, duration_ms) "
            "VALUES ('unknown', 'encrypt', 'text', 200, true, 1)",
        )


def test_hill_rows_must_be_removed_before_migration_downgrade(db_url: str) -> None:
    run_sql(
        db_url,
        "INSERT INTO cipher_operations "
        "(cipher, operation, source, http_status, succeeded, duration_ms) "
        "VALUES ('hill', 'encrypt', 'text', 200, true, 1)",
    )
    try:
        with pytest.raises(DBAPIError):
            _run_alembic(db_url, "downgrade", "0001")
        run_sql(db_url, "DELETE FROM cipher_operations WHERE cipher = 'hill'")
        _run_alembic(db_url, "downgrade", "0001")
    finally:
        _run_alembic(db_url, "upgrade", "head")


def test_downgrade_removes_table_and_upgrade_restores_it(db_url: str) -> None:
    exists = "SELECT count(*) FROM pg_tables WHERE tablename = 'cipher_operations'"
    try:
        _run_alembic(db_url, "downgrade", "base")
        assert run_sql(db_url, exists) == [(0,)]
    finally:
        _run_alembic(db_url, "upgrade", "head")
    assert run_sql(db_url, exists) == [(1,)]


def test_every_cipher_route_is_recorded_without_user_content(db_url: str) -> None:
    cases = cipher_requests()
    with TestClient(app) as client:
        for case in cases:
            assert client.post(case.path, **case.kwargs).status_code == 200

    rows = run_sql(db_url, "SELECT cipher, source, operation FROM cipher_operations ORDER BY id")
    assert rows == [(case.cipher, case.source, case.operation) for case in cases]

    dumped = " ".join(
        row[0] for row in run_sql(db_url, "SELECT row_to_json(c)::text FROM cipher_operations c")
    )
    for value in SENSITIVE_VALUES:
        assert value.lower() not in dumped.lower()


def test_failed_request_is_stored(db_url: str) -> None:
    with TestClient(app) as client:
        client.post("/api/vigenere/encrypt", json={"text": "hi", "key": "LE MON"})

    assert run_sql(
        db_url, "SELECT operation, http_status, succeeded, output_length FROM cipher_operations"
    ) == [("encrypt", 422, False, None)]


def test_history_pages_newest_first_without_overlap(db_url: str) -> None:
    _insert_rows(db_url, 25)
    with TestClient(app) as client:
        first = client.get("/api/history").json()["result"]
        second = client.get(f"/api/history?cursor={first['nextCursor']}").json()["result"]

    assert len(first["items"]) == 20
    assert first["nextCursor"] is not None
    assert len(second["items"]) == 5
    assert second["nextCursor"] is None

    items = first["items"] + second["items"]
    assert len({item["id"] for item in items}) == 25
    created = [item["createdAt"] for item in items]
    assert created == sorted(created, reverse=True)
    assert set(items[0]) == {
        "id",
        "createdAt",
        "cipher",
        "operation",
        "source",
        "responseMode",
        "inputLength",
        "outputLength",
        "httpStatus",
        "succeeded",
        "durationMs",
    }


def test_history_limit_and_filters(db_url: str) -> None:
    _insert_rows(db_url, 3, cipher="playfair", operation="decrypt")
    _insert_rows(db_url, 4, cipher="playfair", operation="encrypt")
    _insert_rows(db_url, 2, cipher="caesar", operation="decrypt")
    with TestClient(app) as client:
        filtered = client.get("/api/history?cipher=playfair&operation=decrypt").json()["result"]
        limited = client.get("/api/history?limit=2").json()["result"]

    assert len(filtered["items"]) == 3
    assert all(
        (item["cipher"], item["operation"]) == ("playfair", "decrypt") for item in filtered["items"]
    )
    assert len(limited["items"]) == 2
    assert limited["nextCursor"] is not None


def test_history_filter_returns_only_hill_text_rows(db_url: str) -> None:
    with TestClient(app) as client:
        client.post("/api/caesar/encrypt", json={"text": "Hi", "key": 1})
        client.post("/api/hill/encrypt", json={"text": "HELP", "key": [[3, 3], [2, 5]]})
        page = client.get("/api/history?cipher=hill").json()["result"]

    assert len(page["items"]) == 1
    assert (page["items"][0]["cipher"], page["items"][0]["source"]) == ("hill", "text")


def test_health_reports_ok(db_url: str) -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["result"] == {"app": "ok", "database": "ok", "history": "enabled"}


def _insert_aged(url: str, days_old: list[int]) -> None:
    for age in days_old:
        run_sql(
            url,
            "INSERT INTO cipher_operations "
            "(created_at, cipher, operation, source, http_status, succeeded, duration_ms) "
            f"VALUES (now() - make_interval(days => {age}), 'caesar', 'encrypt', 'text', 200, "
            "true, 1)",
        )


def test_purge_removes_only_expired_rows(db_url: str) -> None:
    import asyncio

    from app.db.engine import create_database
    from app.history.retention import purge_expired

    _insert_aged(db_url, [0, 29, 31, 45])

    async def purge() -> int:
        database = create_database(db_url)
        try:
            return await purge_expired(database, 30)
        finally:
            await database.engine.dispose()

    assert asyncio.run(purge()) == 2
    remaining = run_sql(
        db_url,
        "SELECT count(*) FROM cipher_operations WHERE created_at > now() - interval '30 days'",
    )
    assert run_sql(db_url, "SELECT count(*) FROM cipher_operations") == remaining == [(2,)]


def test_purge_command_reports_deleted_rows(db_url: str) -> None:
    import os
    import subprocess
    import sys
    from pathlib import Path

    _insert_aged(db_url, [1, 40, 50])
    result = subprocess.run(
        [sys.executable, "-m", "app.history.retention"],
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "DATABASE_URL": db_url, "HISTORY_RETENTION_DAYS": "30"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Deleted 2 history rows older than 30 days" in result.stdout
    assert run_sql(db_url, "SELECT count(*) FROM cipher_operations") == [(1,)]
