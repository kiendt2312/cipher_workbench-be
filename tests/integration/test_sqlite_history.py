"""Disposable-file SQLite migration and history integration coverage."""

from __future__ import annotations

import asyncio
import os
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config as AlembicConfig
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from alembic import command as alembic_command
from app.db.engine import create_database
from app.db.types import datetime_to_epoch_microseconds
from app.history import retention, store
from app.history.cursor import Cursor, encode_cursor
from app.history.retention import purge_expired, require_database_clock_sync
from app.history.store import OperationEntry, list_operations, record_operation
from app.main import app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_COLUMNS = [
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
]


def _url(path: Path) -> str:
    return f"sqlite+aiosqlite:////{path.as_posix().lstrip('/')}"


def _migrate(url: str, operation: str, revision: str) -> None:
    alembic_config = AlembicConfig(str(PROJECT_ROOT / "alembic_sqlite.ini"))
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        getattr(alembic_command, operation)(alembic_config, revision)
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


@pytest.fixture
def migrated_sqlite(tmp_path: Path) -> tuple[Path, str]:
    path = tmp_path / "history.sqlite3"
    url = _url(path)
    _migrate(url, "upgrade", "head")
    return path, url


def test_sqlite_history_has_exact_schema_and_is_repeatable(migrated_sqlite) -> None:
    path, url = migrated_sqlite
    with sqlite3.connect(path) as connection:
        table_info = list(connection.execute("PRAGMA table_info(cipher_operations)"))
        columns = [row[1] for row in table_info]
        not_null = {row[1]: bool(row[3]) for row in table_info}
        indexes = {
            row[1]
            for row in connection.execute("PRAGMA index_list(cipher_operations)")
            if row[1].startswith("ix_cipher_operations_")
        }
        table_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='cipher_operations'"
        ).fetchone()[0]
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "sqlite_0002",
        )
    assert columns == EXPECTED_COLUMNS
    assert not_null == {
        "id": False,
        "created_at": True,
        "cipher": True,
        "operation": False,
        "source": True,
        "response_mode": False,
        "input_length": False,
        "output_length": False,
        "http_status": True,
        "succeeded": True,
        "duration_ms": True,
    }
    assert indexes == {
        "ix_cipher_operations_created_at_id",
        "ix_cipher_operations_cipher_created_at",
    }
    assert "INTEGER PRIMARY KEY AUTOINCREMENT" in table_sql
    assert all(cipher in table_sql for cipher in ("caesar", "hill", "des", "rsa", "dh"))
    for constraint in (
        "operation IN ('encrypt', 'decrypt')",
        "source IN ('text', 'file')",
        "response_mode IN ('content', 'file')",
        "input_length >= 0",
        "output_length >= 0",
        "succeeded IN (0, 1)",
        "duration_ms >= 0",
        "id > 0",
    ):
        assert constraint in table_sql

    _migrate(url, "upgrade", "head")
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO cipher_operations "
            "(created_at, cipher, operation, source, http_status, succeeded, duration_ms) "
            "VALUES (0, 'caesar', 'encrypt', 'text', 200, 1, 1)"
        )
        connection.commit()
        connection.execute("DELETE FROM cipher_operations")
        connection.execute(
            "INSERT INTO cipher_operations "
            "(created_at, cipher, operation, source, http_status, succeeded, duration_ms) "
            "VALUES (0, 'rsa', 'encrypt', 'text', 200, 1, 1)"
        )
        assert connection.execute("SELECT id FROM cipher_operations").fetchone() == (2,)


def test_dh_migration_preserves_rows_indexes_sequence_and_guards_downgrade(
    tmp_path: Path,
) -> None:
    path = tmp_path / "dh-migration.sqlite3"
    url = _url(path)
    _migrate(url, "upgrade", "sqlite_0001")

    with sqlite3.connect(path) as connection:
        connection.executemany(
            "INSERT INTO cipher_operations "
            "(id, created_at, cipher, operation, source, http_status, succeeded, duration_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (4, 10, "caesar", "encrypt", "text", 200, 1, 1),
                (9, 20, "rsa", "decrypt", "file", 422, 0, 2),
            ],
        )
        connection.execute("UPDATE sqlite_sequence SET seq = 77 WHERE name = 'cipher_operations'")
        connection.commit()

    _migrate(url, "upgrade", "head")
    with sqlite3.connect(path) as connection:
        old_rows = connection.execute(
            "SELECT id, created_at, cipher, operation, source, response_mode, input_length, "
            "output_length, http_status, succeeded, duration_ms "
            "FROM cipher_operations ORDER BY id"
        ).fetchall()
        old_indexes = connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'index' "
            "AND name LIKE 'ix_cipher_operations_%' ORDER BY name"
        ).fetchall()
        old_columns = [row[1] for row in connection.execute("PRAGMA table_info(cipher_operations)")]
        assert connection.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = 'cipher_operations'"
        ).fetchone() == (77,)
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "sqlite_0002",
        )
        assert (
            "'dh'"
            in connection.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'cipher_operations'"
            ).fetchone()[0]
        )
        connection.execute(
            "INSERT INTO cipher_operations "
            "(created_at, cipher, operation, source, http_status, succeeded, duration_ms) "
            "VALUES (30, 'dh', NULL, 'text', 200, 1, 3)"
        )
        connection.commit()
        failed_downgrade_state = (
            connection.execute("SELECT * FROM cipher_operations ORDER BY id").fetchall(),
            connection.execute(
                "SELECT name, sql FROM sqlite_master WHERE type = 'index' "
                "AND name LIKE 'ix_cipher_operations_%' ORDER BY name"
            ).fetchall(),
            connection.execute(
                "SELECT seq FROM sqlite_sequence WHERE name = 'cipher_operations'"
            ).fetchone(),
            connection.execute("SELECT version_num FROM alembic_version").fetchone(),
        )

    with pytest.raises(RuntimeError, match="DH rows"):
        _migrate(url, "downgrade", "sqlite_0001")

    with sqlite3.connect(path) as connection:
        assert (
            connection.execute("SELECT * FROM cipher_operations ORDER BY id").fetchall(),
            connection.execute(
                "SELECT name, sql FROM sqlite_master WHERE type = 'index' "
                "AND name LIKE 'ix_cipher_operations_%' ORDER BY name"
            ).fetchall(),
            connection.execute(
                "SELECT seq FROM sqlite_sequence WHERE name = 'cipher_operations'"
            ).fetchone(),
            connection.execute("SELECT version_num FROM alembic_version").fetchone(),
        ) == failed_downgrade_state
        connection.execute("DELETE FROM cipher_operations WHERE cipher = 'dh'")
        connection.commit()

    _migrate(url, "downgrade", "sqlite_0001")
    with sqlite3.connect(path) as connection:
        assert [row[1] for row in connection.execute("PRAGMA table_info(cipher_operations)")] == (
            old_columns
        )
        assert (
            connection.execute(
                "SELECT id, created_at, cipher, operation, source, response_mode, input_length, "
                "output_length, http_status, succeeded, duration_ms "
                "FROM cipher_operations ORDER BY id"
            ).fetchall()
            == old_rows
        )
        assert (
            connection.execute(
                "SELECT name, sql FROM sqlite_master WHERE type = 'index' "
                "AND name LIKE 'ix_cipher_operations_%' ORDER BY name"
            ).fetchall()
            == old_indexes
        )
        assert connection.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = 'cipher_operations'"
        ).fetchone() == (78,)
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "sqlite_0001",
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO cipher_operations "
                "(created_at, cipher, operation, source, http_status, succeeded, duration_ms) "
                "VALUES (40, 'dh', NULL, 'text', 200, 1, 1)"
            )


def test_empty_sqlite_baseline_can_downgrade_and_reupgrade(tmp_path: Path) -> None:
    path = tmp_path / "migration-roundtrip.sqlite3"
    url = _url(path)

    _migrate(url, "upgrade", "head")
    _migrate(url, "downgrade", "base")
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM sqlite_master WHERE type = 'table' AND name = 'cipher_operations'"
        ).fetchone() == (0,)

    _migrate(url, "upgrade", "head")
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "sqlite_0002",
        )
        assert connection.execute(
            "SELECT count(*) FROM sqlite_master WHERE type = 'table' AND name = 'cipher_operations'"
        ).fetchone() == (1,)


def test_runtime_uses_one_pool_and_configures_conservative_sqlite_pragmas(migrated_sqlite) -> None:
    _, url = migrated_sqlite
    database = create_database(url)

    async def inspect() -> tuple[object, object, object, object]:
        try:
            async with database.engine.connect() as connection:
                values = []
                for pragma in ("journal_mode", "synchronous", "busy_timeout"):
                    values.append((await connection.execute(text(f"PRAGMA {pragma}"))).scalar())
                return tuple(values)  # type: ignore[return-value]
        finally:
            await database.engine.dispose()

    values = asyncio.run(inspect())
    assert type(database.engine.sync_engine.pool).__name__ == "AsyncAdaptedQueuePool"
    assert database.engine.sync_engine.pool.size() == 1
    assert database.engine.sync_engine.pool._max_overflow == 0
    assert database.engine.sync_engine.pool._timeout == 0.2
    assert values == ("delete", 2, 200)


def test_history_write_preserves_tied_utc_microseconds_across_engine_restart(
    migrated_sqlite, monkeypatch
) -> None:
    _, url = migrated_sqlite
    timestamp = datetime(2026, 10, 7, 1, 2, 3, 456789, tzinfo=UTC)

    class FrozenDateTime:
        @classmethod
        def now(cls, timezone):
            assert timezone is UTC
            return timestamp

    monkeypatch.setattr(store, "datetime", FrozenDateTime)
    entry = OperationEntry(
        cipher="rsa",
        source="text",
        operation="encrypt",
        response_mode=None,
        input_length=4,
        output_length=8,
        http_status=200,
        succeeded=True,
        duration_ms=3,
    )

    async def write_then_restart() -> list:
        writer = create_database(url)
        try:
            await record_operation(writer, entry)
            await record_operation(writer, entry)
        finally:
            await writer.engine.dispose()

        reader = create_database(url)
        try:
            rows, cursor = await list_operations(reader, limit=20)
            assert cursor is None
            return rows
        finally:
            await reader.engine.dispose()

    rows = asyncio.run(write_then_restart())
    assert [row.id for row in rows] == [2, 1]
    assert [row.created_at for row in rows] == [timestamp, timestamp]
    assert all(row.created_at.tzinfo is UTC for row in rows)
    assert all(
        (row.cipher, row.response_mode, row.input_length, row.output_length, row.duration_ms)
        == ("rsa", None, 4, 8, 3)
        for row in rows
    )


def test_locked_and_cancelled_writes_recover_the_single_connection_pool(migrated_sqlite) -> None:
    path, url = migrated_sqlite
    database = create_database(url)
    entry = OperationEntry(
        cipher="caesar",
        source="text",
        operation="encrypt",
        response_mode=None,
        input_length=2,
        output_length=2,
        http_status=200,
        succeeded=True,
        duration_ms=1,
    )

    async def exercise() -> tuple[float, list[int]]:
        locker = sqlite3.connect(path, timeout=0)
        try:
            # Create and return the sole async connection before taking the external lock.
            async with database.engine.connect():
                pass

            locker.execute("BEGIN EXCLUSIVE")
            started = time.monotonic()
            with pytest.raises(OperationalError):
                await record_operation(database, entry)
            locked_elapsed = time.monotonic() - started
            locker.rollback()

            await record_operation(database, entry)

            locker.execute("BEGIN EXCLUSIVE")
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(record_operation(database, entry), timeout=0.05)
            locker.rollback()

            await record_operation(database, entry)
            rows, _ = await list_operations(database, limit=20)
            return locked_elapsed, [row.id for row in rows]
        finally:
            locker.rollback()
            locker.close()
            await database.engine.dispose()

    locked_elapsed, row_ids = asyncio.run(exercise())
    assert locked_elapsed < 0.5
    assert row_ids == [2, 1]


def test_exclusive_lock_keeps_health_bounded_and_cipher_response_available(
    migrated_sqlite, monkeypatch, caplog
) -> None:
    path, url = migrated_sqlite
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("HISTORY_API_ENABLED", "true")
    locker = sqlite3.connect(path, timeout=0)
    try:
        locker.execute("BEGIN EXCLUSIVE")
        with TestClient(app, raise_server_exceptions=False) as client:
            started = time.monotonic()
            health = client.get("/api/health")
            elapsed = time.monotonic() - started
            cipher = client.post("/api/caesar/encrypt", json={"text": "Hi", "key": 1})
    finally:
        locker.rollback()
        locker.close()

    assert elapsed < 1.0
    assert health.status_code == 503
    assert health.json()["result"]["database"] == "unavailable"
    assert cipher.status_code == 200
    assert cipher.json() == {"success": True, "result": "Ij"}
    assert str(path) not in caplog.text


def test_missing_file_is_not_created_and_cipher_remains_available(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "not-created.sqlite3"
    monkeypatch.setenv("DATABASE_URL", _url(path))
    monkeypatch.setenv("HISTORY_API_ENABLED", "true")
    with TestClient(app, raise_server_exceptions=False) as client:
        health = client.get("/api/health")
        cipher = client.post("/api/caesar/encrypt", json={"text": "Hi", "key": 1})
        history = client.get("/api/history")
    assert health.status_code == 503
    assert health.json()["result"]["database"] == "unavailable"
    assert cipher.status_code == 200
    assert history.status_code == 503
    assert not path.exists()


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses POSIX file write permissions")
def test_read_only_file_keeps_reads_and_cipher_available_but_drops_history_write(
    migrated_sqlite, monkeypatch, caplog
) -> None:
    path, url = migrated_sqlite
    path.chmod(0o400)
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("HISTORY_API_ENABLED", "true")
    try:
        with caplog.at_level("WARNING"), TestClient(app, raise_server_exceptions=False) as client:
            health = client.get("/api/health")
            cipher = client.post("/api/caesar/encrypt", json={"text": "Hi", "key": 1})
            history = client.get("/api/history")
    finally:
        path.chmod(0o600)

    assert health.status_code == 200
    assert health.json()["result"]["database"] == "ok"
    assert cipher.status_code == 200
    assert history.status_code == 200
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM cipher_operations").fetchone() == (0,)
    assert "Could not record cipher operation history" in caplog.text
    assert str(path) not in caplog.text


def test_wrong_revision_is_not_modified_and_cipher_remains_available(
    migrated_sqlite, monkeypatch
) -> None:
    path, url = migrated_sqlite
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE alembic_version SET version_num = 'sqlite_wrong'")
        connection.commit()

    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("HISTORY_API_ENABLED", "true")
    with TestClient(app, raise_server_exceptions=False) as client:
        health = client.get("/api/health")
        cipher = client.post("/api/caesar/encrypt", json={"text": "Hi", "key": 1})
        history = client.get("/api/history")

    assert health.status_code == 503
    assert health.json()["result"]["database"] == "unavailable"
    assert cipher.status_code == 200
    assert history.status_code == 503
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "sqlite_wrong",
        )


def test_history_keyset_pagination_preserves_tied_timestamp_order(
    migrated_sqlite, monkeypatch
) -> None:
    path, url = migrated_sqlite
    timestamp = datetime(2026, 10, 7, 0, 0, 0, 123456, tzinfo=UTC)
    encoded_timestamp = datetime_to_epoch_microseconds(timestamp)
    with sqlite3.connect(path) as connection:
        connection.executemany(
            "INSERT INTO cipher_operations "
            "(id, created_at, cipher, operation, source, http_status, succeeded, duration_ms) "
            "VALUES (?, ?, 'rsa', 'encrypt', 'text', 200, 1, 1)",
            [(row_id, encoded_timestamp) for row_id in range(1, 26)],
        )
        connection.commit()

    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("HISTORY_API_ENABLED", "true")
    with TestClient(app) as client:
        first = client.get("/api/history?limit=20").json()["result"]
        second = client.get(f"/api/history?limit=20&cursor={first['nextCursor']}").json()["result"]
    assert [item["id"] for item in first["items"]] == list(range(25, 5, -1))
    assert [item["id"] for item in second["items"]] == list(range(5, 0, -1))
    assert all(item["createdAt"].endswith("Z") for item in first["items"] + second["items"])
    assert second["nextCursor"] is None


def test_postgres_era_wire_cursor_continues_on_sqlite(migrated_sqlite, monkeypatch) -> None:
    path, url = migrated_sqlite
    timestamp = datetime(2026, 10, 7, 0, 0, 0, 123456, tzinfo=UTC)
    encoded_timestamp = datetime_to_epoch_microseconds(timestamp)
    with sqlite3.connect(path) as connection:
        connection.executemany(
            "INSERT INTO cipher_operations "
            "(id, created_at, cipher, operation, source, http_status, succeeded, duration_ms) "
            "VALUES (?, ?, 'caesar', 'encrypt', 'text', 200, 1, 1)",
            [
                (1, encoded_timestamp - 1),
                (2, encoded_timestamp),
                (3, encoded_timestamp + 1),
            ],
        )
        connection.commit()

    postgres_era_cursor = encode_cursor(Cursor(created_at=timestamp, id=2))
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("HISTORY_API_ENABLED", "true")
    with TestClient(app) as client:
        response = client.get("/api/history", params={"limit": 20, "cursor": postgres_era_cursor})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["result"]["items"]] == [1]


def test_history_cursor_ignores_newer_interleaved_insert_and_filters_persisted_rows(
    migrated_sqlite, monkeypatch
) -> None:
    path, url = migrated_sqlite
    base = datetime_to_epoch_microseconds(datetime(2026, 10, 7, tzinfo=UTC))
    with sqlite3.connect(path) as connection:
        connection.executemany(
            "INSERT INTO cipher_operations "
            "(id, created_at, cipher, operation, source, http_status, succeeded, duration_ms) "
            "VALUES (?, ?, ?, ?, 'text', 200, 1, 1)",
            [
                (1, base + 1, "caesar", "encrypt"),
                (2, base + 2, "rsa", "encrypt"),
                (3, base + 3, "rsa", "decrypt"),
            ],
        )
        connection.commit()

    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("HISTORY_API_ENABLED", "true")
    with TestClient(app) as client:
        first = client.get("/api/history?limit=2").json()["result"]
        with sqlite3.connect(path) as connection:
            connection.execute(
                "INSERT INTO cipher_operations "
                "(id, created_at, cipher, operation, source, http_status, succeeded, duration_ms) "
                "VALUES (?, ?, 'rsa', 'encrypt', 'text', 200, 1, 1)",
                (4, base + 4),
            )
            connection.commit()
        second_response = client.get(
            "/api/history", params={"limit": 2, "cursor": first["nextCursor"]}
        )
        assert second_response.status_code == 200, second_response.json()
        second = second_response.json()["result"]
        filtered = client.get("/api/history?cipher=rsa&operation=encrypt").json()["result"]

    assert [item["id"] for item in first["items"]] == [3, 2]
    assert [item["id"] for item in second["items"]] == [1]
    assert [item["id"] for item in filtered["items"]] == [4, 2]


def test_sqlite_persists_rsa_metadata_without_payload_and_excludes_keygen_and_trace(
    migrated_sqlite, monkeypatch
) -> None:
    path, url = migrated_sqlite
    marker = "RSA-SENSITIVE-SQLITE-MARKER"
    filename = "rsa-sensitive-name.txt"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("HISTORY_API_ENABLED", "true")

    with TestClient(app) as client:
        json_response = client.post(
            "/api/rsa/encrypt",
            json={
                "e": "3",
                "n": "67591",
                "inputType": "text",
                "mode": "block",
                "data": marker,
            },
        )
        file_response = client.post(
            "/api/rsa/encrypt",
            data={"e": "3", "n": "67591", "mode": "block"},
            files={"file": (filename, b"file marker", "text/plain")},
        )
        assert json_response.status_code == file_response.status_code == 200
        assert (
            client.post("/api/rsa/keys", json={"p": "17", "q": "11", "e": "7"}).status_code == 200
        )
        assert client.post("/api/rsa/keys/random", json={"bits": 16}).status_code == 200
        assert (
            client.post(
                "/api/des/trace",
                json={"block": "0123456789ABCDEF", "key": "133457799BBCDFF1"},
            ).status_code
            == 200
        )
        page = client.get("/api/history?cipher=rsa").json()["result"]

    assert sorted((item["source"], item["operation"]) for item in page["items"]) == [
        ("file", "encrypt"),
        ("text", "encrypt"),
    ]
    assert all(item["responseMode"] is None for item in page["items"])
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM cipher_operations").fetchone() == (2,)
        dumped = " ".join(
            row[0]
            for row in connection.execute(
                "SELECT quote(id) || ' ' || quote(created_at) || ' ' || quote(cipher) || ' ' || "
                "quote(operation) || ' ' || quote(source) || ' ' || quote(response_mode) || ' ' || "
                "quote(input_length) || ' ' || quote(output_length) || ' ' || "
                "quote(http_status) || ' ' || quote(succeeded) || ' ' || quote(duration_ms) "
                "FROM cipher_operations"
            )
        )
    assert marker not in dumped
    assert filename not in dumped


def test_retention_uses_sqlite_utc_database_clock(migrated_sqlite) -> None:
    path, url = migrated_sqlite
    with sqlite3.connect(path) as connection:
        connection.executemany(
            "INSERT INTO cipher_operations "
            "(created_at, cipher, operation, source, http_status, succeeded, duration_ms) "
            "VALUES (CAST(strftime('%s', 'now') AS INTEGER) * 1000000 - ?, "
            "'caesar', 'encrypt', 'text', 200, 1, 1)",
            [
                (29 * 86_400 * 1_000_000,),
                (30 * 86_400 * 1_000_000,),
                (31 * 86_400 * 1_000_000,),
            ],
        )
        connection.commit()

    database = create_database(url)

    async def purge() -> int:
        try:
            return await purge_expired(database, 30)
        finally:
            await database.engine.dispose()

    previous_timezone = os.environ.get("TZ")
    os.environ["TZ"] = "America/New_York"
    if hasattr(time, "tzset"):
        time.tzset()
    try:
        assert asyncio.run(purge()) == 1
    finally:
        if previous_timezone is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous_timezone
        if hasattr(time, "tzset"):
            time.tzset()
    with sqlite3.connect(path) as connection:
        remaining_ages = [
            row[0]
            for row in connection.execute(
                "SELECT (CAST(strftime('%s', 'now') AS INTEGER) * 1000000 - created_at) "
                "/ 86400000000 FROM cipher_operations ORDER BY created_at DESC"
            )
        ]
    assert remaining_ages == [29, 30]


def test_rollout_clock_preflight_enforces_sixty_second_limit(migrated_sqlite) -> None:
    _, url = migrated_sqlite
    database = create_database(url)

    async def check() -> tuple[float, str]:
        try:
            current_epoch_us = time.time_ns() // 1_000
            accepted = await require_database_clock_sync(
                database, reference_epoch_us=current_epoch_us
            )
            with pytest.raises(RuntimeError, match="clock skew exceeds") as error:
                await require_database_clock_sync(
                    database,
                    reference_epoch_us=current_epoch_us + 61_000_000,
                )
            return accepted, str(error.value)
        finally:
            await database.engine.dispose()

    accepted_skew, failure = asyncio.run(check())
    assert accepted_skew <= 1
    assert "sqlite" not in failure.lower() or "clock" in failure.lower()


def test_retention_cli_uses_sqlite_runtime_and_redacts_configuration_errors(
    migrated_sqlite, monkeypatch, capsys
) -> None:
    path, url = migrated_sqlite
    old_timestamp = datetime_to_epoch_microseconds(datetime.now(UTC) - timedelta(days=31))
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO cipher_operations "
            "(created_at, cipher, operation, source, http_status, succeeded, duration_ms) "
            "VALUES (?, 'caesar', 'encrypt', 'text', 200, 1, 1)",
            (old_timestamp,),
        )
        connection.commit()

    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("HISTORY_RETENTION_DAYS", "30")
    assert asyncio.run(retention._main(["--check-clock-only"])) == 0
    assert capsys.readouterr().out.startswith("SQLite clock preflight passed (")
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM cipher_operations").fetchone() == (1,)

    assert asyncio.run(retention._main()) == 0
    assert capsys.readouterr().out == "Deleted 1 history rows older than 30 days\n"

    private_value = "postgresql+asyncpg://operator:secret@private.invalid/history"
    monkeypatch.setenv("DATABASE_URL", private_value)
    assert asyncio.run(retention._main()) == 1
    failure = capsys.readouterr().err
    assert failure == "Could not purge history rows\n"
    assert private_value not in failure

    monkeypatch.delenv("DATABASE_URL")
    assert asyncio.run(retention._main()) == 1
    assert capsys.readouterr().err == "DATABASE_URL must be set\n"
