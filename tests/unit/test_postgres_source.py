"""Database-free tests for the read-only PostgreSQL history source adapter."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.history import postgres_source
from app.history.continuity import (
    HistoryRow,
    IdentityState,
    Manifest,
    datetime_to_epoch_microseconds,
)

SOURCE_URL = "postgresql+asyncpg://legacy:secret@db.invalid/cipher_workbench"


class FakeResult:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows
        self.closed = False

    def mappings(self) -> FakeResult:
        return self

    def all(self) -> list[object]:
        return list(self.rows)

    def fetchmany(self, _size: int) -> list[object]:
        return list(self.rows)

    def close(self) -> None:
        self.closed = True


class FakeTransaction:
    def __init__(self) -> None:
        self.entered = False
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> FakeTransaction:
        self.entered = True
        return self

    async def __aexit__(self, exc_type: object, _exc: object, _traceback: object) -> bool:
        if exc_type is None:
            self.committed = True
        else:
            self.rolled_back = True
        return False


class FakeConnection:
    def __init__(
        self,
        *,
        revision: str = "0004",
        columns: tuple[str, ...] = postgres_source.HISTORY_COLUMNS,
        identity: dict[str, object] | None = None,
        rows: tuple[dict[str, object], ...] = (),
    ) -> None:
        self.revision = revision
        self.columns = columns
        self.identity = identity or {
            "last_value": 100,
            "is_called": False,
            "increment": 10,
        }
        self.rows = rows
        self.calls: list[tuple[str, dict[str, object] | None]] = []
        self.transaction = FakeTransaction()

    def begin(self) -> FakeTransaction:
        return self.transaction

    async def execute(
        self,
        statement: object,
        params: dict[str, object] | None = None,
    ) -> FakeResult:
        sql = str(statement)
        self.calls.append((sql, params))
        if sql == postgres_source.READ_ONLY_TRANSACTION_SQL:
            return FakeResult([])
        if sql == postgres_source.REVISION_SQL:
            return FakeResult([{"version_num": self.revision}])
        if sql == postgres_source.TABLE_TYPE_SQL:
            return FakeResult([{"table_type": "BASE TABLE"}])
        if sql == postgres_source.COLUMNS_SQL:
            return FakeResult([{"column_name": column} for column in self.columns])
        if sql == postgres_source.SEQUENCE_SQL:
            return FakeResult([self.identity])
        if sql == postgres_source.HISTORY_ROWS_SQL:
            assert params is not None
            after_id = params["after_id"]
            batch_size = params["batch_size"]
            batch = [row for row in self.rows if row["id"] > after_id][:batch_size]
            return FakeResult(batch)
        raise AssertionError(f"unexpected fixed statement: {sql}")


class FakeConnectContext:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, _exc_type: object, _exc: object, _traceback: object) -> bool:
        return False


class FakeEngine:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection
        self.disposed = False

    def connect(self) -> FakeConnectContext:
        return FakeConnectContext(self.connection)

    async def dispose(self) -> None:
        self.disposed = True


def _row(row_id: int, created_at: datetime, *, rsa: bool = False) -> dict[str, object]:
    return {
        "id": row_id,
        "created_at": created_at,
        "cipher": "rsa" if rsa else "caesar",
        "operation": "encrypt",
        "source": "file" if rsa else "text",
        "response_mode": None,
        "input_length": None if rsa else 4,
        "output_length": 8 if rsa else None,
        "http_status": 200,
        "succeeded": not rsa,
        "duration_ms": 3,
    }


def _factory_for(
    connection: FakeConnection,
) -> tuple[Any, dict[str, object]]:
    captured: dict[str, object] = {}
    engine = FakeEngine(connection)

    def factory(url: str, **kwargs: object) -> FakeEngine:
        captured["url"] = url
        captured.update(kwargs)
        return engine

    captured["engine"] = engine
    return factory, captured


def test_url_validation_is_strict_and_reads_only_explicit_or_legacy_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert postgres_source.validate_legacy_url(SOURCE_URL) == SOURCE_URL
    assert postgres_source.validate_legacy_url(f"{SOURCE_URL}?sslmode=disable")

    monkeypatch.setenv(postgres_source.LEGACY_DATABASE_URL_ENV, SOURCE_URL)
    assert postgres_source.resolve_legacy_url() == SOURCE_URL
    assert postgres_source.resolve_legacy_url("postgresql+asyncpg://u:p@host/db") == (
        "postgresql+asyncpg://u:p@host/db"
    )

    for invalid in (
        "postgres://legacy:secret@db.invalid/db",
        "postgresql://legacy:secret@db.invalid/db",
        "postgresql+psycopg://legacy:secret@db.invalid/db",
        "postgresql+asyncpg://legacy:secret@db.invalid",
        "postgresql+asyncpg://legacy:secret@db.invalid/db secret",
    ):
        with pytest.raises(postgres_source.InvalidLegacyURL) as error:
            postgres_source.validate_legacy_url(invalid)
        assert "secret" not in str(error.value)
        assert invalid not in str(error.value)


def test_missing_legacy_url_fails_closed_without_reading_runtime_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(postgres_source.LEGACY_DATABASE_URL_ENV, raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:////runtime/secret.sqlite3")

    with pytest.raises(postgres_source.InvalidLegacyURL):
        postgres_source.resolve_legacy_url()


def test_driver_failures_are_redacted() -> None:
    def failing_factory(url: str, **_kwargs: object) -> object:
        raise RuntimeError(f"connection failed for {url} with password=secret")

    with pytest.raises(postgres_source.SourceReadError) as error:
        asyncio.run(
            postgres_source.read_source_snapshot(
                SOURCE_URL,
                engine_factory=failing_factory,
            )
        )

    assert SOURCE_URL not in str(error.value)
    assert "secret" not in str(error.value)


def test_snapshot_uses_fixed_read_only_transaction_and_ascending_batches() -> None:
    source_rows = (
        _row(
            2,
            datetime(2026, 10, 7, 8, 0, 0, 123456, tzinfo=timezone(timedelta(hours=7))),
        ),
        _row(7, datetime(2026, 10, 7, 1, 0, 0, 654321, tzinfo=UTC), rsa=True),
        _row(9, datetime(2026, 10, 7, 1, 0, 1, 654321, tzinfo=UTC)),
    )
    connection = FakeConnection(rows=source_rows)
    factory, captured = _factory_for(connection)

    snapshot = asyncio.run(
        postgres_source.read_source_snapshot(
            SOURCE_URL,
            batch_size=2,
            snapshot_epoch_us=123,
            engine_factory=factory,
        )
    )

    assert captured["url"] == SOURCE_URL
    assert captured["isolation_level"] == postgres_source.TRANSACTION_ISOLATION_LEVEL
    assert captured["echo"] is False
    assert connection.transaction.entered is True
    assert connection.transaction.committed is True
    assert captured["engine"].disposed is True  # type: ignore[index]
    assert snapshot.revision == "0004"
    assert snapshot.identity.is_called is False
    assert snapshot.identity.last_issued_high_water == 90
    assert [row.id for row in snapshot.rows] == [2, 7, 9]
    assert snapshot.rows[0].created_at == datetime_to_epoch_microseconds(
        source_rows[0]["created_at"]
    )
    assert snapshot.rows[1].succeeded is False
    assert snapshot.rows[1].response_mode is None
    assert snapshot.rows[1].cipher == "rsa"

    statements = [sql for sql, _params in connection.calls]
    assert statements[0] == postgres_source.READ_ONLY_TRANSACTION_SQL
    assert all(
        token not in re.findall(r"[A-Z]+", statement.upper())
        for statement in statements
        for token in ("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "TRUNCATE")
    )
    row_calls = [
        params for sql, params in connection.calls if sql == postgres_source.HISTORY_ROWS_SQL
    ]
    assert row_calls == [
        {"after_id": 0, "batch_size": 2},
        {"after_id": 7, "batch_size": 2},
    ]
    assert "SELECT *" not in postgres_source.HISTORY_ROWS_SQL
    assert "pg_get_sequence_data" not in postgres_source.SEQUENCE_SQL
    assert "pg_sequences" not in postgres_source.SEQUENCE_SQL
    assert "FROM public.cipher_operations_id_seq" in postgres_source.SEQUENCE_SQL
    assert "identity_sequence.is_called" in postgres_source.SEQUENCE_SQL
    assert "pg_catalog.pg_sequence" in postgres_source.SEQUENCE_SQL
    assert "pg_catalog.pg_get_serial_sequence" in postgres_source.SEQUENCE_SQL
    assert "sequence_catalog.seqincrement" in postgres_source.SEQUENCE_SQL
    assert "pg_catalog.has_sequence_privilege" in postgres_source.SEQUENCE_SQL
    assert all(
        column in postgres_source.HISTORY_ROWS_SQL for column in postgres_source.HISTORY_COLUMNS
    )
    assert "plaintext" not in postgres_source.HISTORY_ROWS_SQL
    assert "private_key" not in postgres_source.HISTORY_ROWS_SQL


@pytest.mark.parametrize(
    ("revision", "columns"),
    [
        ("0003", postgres_source.HISTORY_COLUMNS),
        ("0004", postgres_source.HISTORY_COLUMNS[:-1]),
    ],
)
def test_revision_or_exact_column_mismatch_fails_before_rows(
    revision: str,
    columns: tuple[str, ...],
) -> None:
    connection = FakeConnection(revision=revision, columns=columns)
    factory, captured = _factory_for(connection)

    with pytest.raises(postgres_source.SourceSchemaError):
        asyncio.run(
            postgres_source.read_source_snapshot(
                SOURCE_URL,
                engine_factory=factory,
                snapshot_epoch_us=123,
            )
        )

    assert captured["engine"].disposed is True  # type: ignore[index]
    assert not any(sql == postgres_source.HISTORY_ROWS_SQL for sql, _params in connection.calls)


@pytest.mark.parametrize("increment", [0, -1])
def test_non_positive_sequence_increment_fails_closed(increment: int) -> None:
    connection = FakeConnection(
        identity={"last_value": 100, "is_called": True, "increment": increment}
    )
    factory, _captured = _factory_for(connection)

    with pytest.raises(postgres_source.SourceSchemaError):
        asyncio.run(
            postgres_source.read_source_snapshot(
                SOURCE_URL,
                engine_factory=factory,
                snapshot_epoch_us=123,
            )
        )


def test_prepare_requires_new_non_colliding_staging_and_does_not_touch_runtime(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "staging.sqlite3"
    runtime = tmp_path / "runtime.sqlite3"
    staging.write_bytes(b"keep")
    connection = FakeConnection()
    factory, captured = _factory_for(connection)

    with pytest.raises(postgres_source.PreparePreflightError) as error:
        asyncio.run(
            postgres_source.prepare(
                staging,
                runtime,
                source_url=SOURCE_URL,
                engine_factory=factory,
            )
        )

    assert "staging.sqlite3" not in str(error.value)
    assert staging.read_bytes() == b"keep"
    assert captured["engine"] is not None
    assert not connection.calls

    with pytest.raises(postgres_source.PreparePreflightError):
        asyncio.run(
            postgres_source.prepare(
                runtime,
                runtime,
                source_url=SOURCE_URL,
                engine_factory=factory,
            )
        )
    assert not runtime.exists()


def test_prepare_calls_continuity_with_fake_source_and_explicit_schema_revision(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "new-staging.sqlite3"
    runtime = tmp_path / "runtime.sqlite3"
    connection = FakeConnection(rows=(_row(4, datetime(2026, 10, 7, tzinfo=UTC)),))
    factory, _captured = _factory_for(connection)

    result = asyncio.run(
        postgres_source.prepare(
            staging,
            runtime,
            source_url=SOURCE_URL,
            schema_revision="sqlite_0001",
            snapshot_epoch_us=123,
            engine_factory=factory,
        )
    )

    assert result.path == staging
    assert result.manifest.source_revision == "0004"
    assert result.manifest.schema_revision == "sqlite_0001"
    assert result.manifest.count == 1
    assert result.manifest.identity_last_issued == 90
    assert result.verification.sequence == 90
    assert staging.exists()
    assert not runtime.exists()


def test_cli_success_and_failure_output_never_contains_sensitive_inputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    row = HistoryRow(1, 123, "rsa", "encrypt", "file", None, None, 8, 200, True, 1)
    manifest = Manifest.from_rows(
        [row],
        IdentityState(100, False, 10),
        source_revision="0004",
        schema_revision="sqlite_0001",
        snapshot_epoch_us=123,
    )

    async def fake_prepare(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(manifest=manifest)

    monkeypatch.setattr(postgres_source, "prepare", fake_prepare)
    staging = tmp_path / "sensitive-staging.sqlite3"
    runtime = tmp_path / "runtime.sqlite3"
    assert (
        postgres_source.main(
            [
                "prepare",
                "--source-url",
                SOURCE_URL,
                "--staging",
                str(staging),
                "--runtime",
                str(runtime),
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    evidence = json.loads(output)
    assert evidence["ok"] is True
    assert evidence["manifestDigest"] == manifest.digest
    assert str(staging) not in output
    assert SOURCE_URL not in output
    assert "secret" not in output

    async def failing_prepare(*_args: object, **_kwargs: object) -> SimpleNamespace:
        raise RuntimeError(f"{SOURCE_URL} {staging} plaintext-secret")

    monkeypatch.setattr(postgres_source, "prepare", failing_prepare)
    assert (
        postgres_source.main(
            [
                "prepare",
                "--source-url",
                SOURCE_URL,
                "--staging",
                str(staging),
                "--runtime",
                str(runtime),
            ]
        )
        == 2
    )
    failure_capture = capsys.readouterr()
    failure_output = failure_capture.out + failure_capture.err
    assert SOURCE_URL not in failure_output
    assert str(staging) not in failure_output
    assert "plaintext-secret" not in failure_output
    assert failure_output.strip() == "history continuity command failed"
