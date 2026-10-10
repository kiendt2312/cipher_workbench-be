"""Storage-boundary tests for owner-scoped private history."""

from __future__ import annotations

import asyncio
import os
import shutil
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config as AlembicConfig
from sqlalchemy import text

from alembic import command as alembic_command
from app.db.engine import create_database
from app.history import store as history_store
from app.history.continuity import (
    VerificationError,
    backup_sqlite_live,
    restore_sqlite_backup,
    verify_staging,
)
from app.history.retention import purge_expired
from app.history.store import (
    HistoryQuotaExceededError,
    OperationEntry,
    delete_all_operations,
    delete_operation,
    get_operation,
    list_operations,
    logical_history_bytes,
    owner_exists,
    record_operation,
)

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
def migrated_private_history(tmp_path: Path):
    path = tmp_path / "private-history.sqlite3"
    url = _url(path)
    _migrate(url)
    database = create_database(url)
    try:
        yield database
    finally:
        asyncio.run(database.engine.dispose())


def _entry() -> OperationEntry:
    return OperationEntry(
        cipher="rsa",
        source="text",
        operation="verify",
        response_mode=None,
        input_length=3,
        output_length=None,
        http_status=200,
        succeeded=True,
        duration_ms=1,
    )


def test_private_history_is_owner_scoped_and_expires_from_original_timestamp(
    migrated_private_history,
) -> None:
    database = migrated_private_history
    created_at = datetime(2026, 10, 11, 8, 0, tzinfo=UTC)

    async def exercise() -> None:
        await record_operation(
            database,
            _entry(),
            owner_id="opaque-owner-a",
            created_at=created_at,
            payload={
                "content": b"abc",
                "signature": b"sig",
                "public_key": {"e": "17", "n": "3233"},
                "result": "verified",
                "valid": True,
                "processing_state": "completed",
            },
        )
        await record_operation(
            database,
            _entry(),
            owner_id="opaque-owner-b",
            created_at=created_at + timedelta(seconds=1),
        )

        rows, cursor = await list_operations(
            database,
            owner_id="opaque-owner-a",
            limit=20,
            now=created_at + timedelta(hours=4, minutes=59),
        )
        assert cursor is None
        assert len(rows) == 1
        assert rows[0].owner_id == "opaque-owner-a"
        assert rows[0].payload["content"] == b"abc"
        assert rows[0].payload["valid"] is True
        assert await owner_exists(
            database, "opaque-owner-a", now=created_at + timedelta(hours=4, minutes=59)
        )
        assert (
            await get_operation(
                database,
                owner_id="opaque-owner-b",
                operation_id=rows[0].id,
                now=created_at + timedelta(hours=4, minutes=59),
            )
            is None
        )

        expired, _ = await list_operations(
            database,
            owner_id="opaque-owner-a",
            limit=20,
            now=created_at + timedelta(hours=5),
        )
        assert expired == []
        assert not await owner_exists(
            database, "opaque-owner-a", now=created_at + timedelta(hours=5)
        )

    asyncio.run(exercise())


def test_legacy_rows_are_ownerless_hidden_and_purged_at_the_fixed_cutoff(
    migrated_private_history,
) -> None:
    database = migrated_private_history
    current = datetime.now(UTC).replace(microsecond=0)
    old = current - timedelta(hours=6)
    legacy_entry = OperationEntry(
        cipher="caesar",
        source="text",
        operation="encrypt",
        response_mode=None,
        input_length=3,
        output_length=3,
        http_status=200,
        succeeded=True,
        duration_ms=1,
    )

    async def exercise() -> None:
        await record_operation(database, legacy_entry, created_at=old)
        await record_operation(
            database,
            _entry(),
            owner_id="owner-a",
            created_at=old,
            payload={"content": b"legacy-private"},
        )
        await record_operation(database, legacy_entry, created_at=current)

        # The shared purge removes both old rows using their original
        # created_at values; a fresh legacy row remains in the legacy API.
        assert await purge_expired(database) == 2
        private_rows, _ = await list_operations(database, owner_id="owner-a", limit=20, now=current)
        assert private_rows == []
        legacy_rows, _ = await list_operations(database, limit=20, now=current)
        assert len(legacy_rows) == 1

    asyncio.run(exercise())


def test_backup_restore_keeps_original_expiry_and_does_not_resurrect_access(
    migrated_private_history, tmp_path: Path
) -> None:
    database = migrated_private_history
    current = datetime.now(UTC).replace(microsecond=0)
    expired_at = current - timedelta(hours=6)

    async def seed() -> None:
        await record_operation(
            database,
            replace(_entry(), operation="encrypt"),
            created_at=current,
        )
        await record_operation(
            database,
            _entry(),
            owner_id="restore-owner",
            created_at=expired_at,
            payload={"content": b"expired payload"},
        )

    asyncio.run(seed())
    source_path = Path(database.engine.url.database.removeprefix("file:"))
    source_path = Path(str(source_path).split("?", 1)[0])
    backup_path = tmp_path / "history-backup.sqlite3"
    restored_path = tmp_path / "history-restored.sqlite3"
    evidence = backup_sqlite_live(
        source_path,
        backup_path,
        source_revision="runtime-sqlite",
        schema_revision="sqlite_0003",
        timeout=2,
    )
    tampered_path = tmp_path / "history-backup-tampered.sqlite3"
    shutil.copyfile(backup_path, tampered_path)
    with sqlite3.connect(tampered_path) as connection:
        connection.execute("DELETE FROM private_history_records")
        connection.commit()
    with pytest.raises(VerificationError, match="private history"):
        verify_staging(
            tampered_path,
            expected_manifest_digest=evidence.backup_digest,
            expected_schema_revision="sqlite_0003",
        )
    restore_sqlite_backup(
        backup_path,
        restored_path,
        expected_manifest_digest=evidence.backup_digest,
        expected_schema_revision="sqlite_0003",
    )

    restored = create_database(_url(restored_path))

    async def verify() -> None:
        try:
            rows, _ = await list_operations(
                restored,
                owner_id="restore-owner",
                limit=20,
                now=current,
            )
            assert rows == []
            assert await purge_expired(restored) == 1
        finally:
            await restored.engine.dispose()

    asyncio.run(verify())
    with sqlite3.connect(restored_path) as connection:
        assert connection.execute("SELECT count(*) FROM private_history_records").fetchone() == (0,)


def test_completed_invalid_verification_preserves_exact_allowlisted_payload(
    migrated_private_history,
) -> None:
    database = migrated_private_history
    created_at = datetime.now(UTC).replace(microsecond=0)

    async def exercise() -> None:
        row = await record_operation(
            database,
            _entry(),
            owner_id="owner-invalid",
            created_at=created_at,
            payload={
                "content": "message",
                "numeric_input": {"m": "65"},
                "signature": b"\x00\xff",
                "public_key": {"e": "17", "n": "3233"},
                "result": {"mode": "standard", "reason": "mismatch"},
                "valid": False,
                "processing_state": "completed",
            },
        )
        assert row.payload == {
            "content": "message",
            "numeric_input": {"m": "65"},
            "signature": b"\x00\xff",
            "public_key": {"e": "17", "n": "3233"},
            "result": {"mode": "standard", "reason": "mismatch"},
            "valid": False,
            "processing_state": "completed",
        }
        listed, _ = await list_operations(
            database, owner_id="owner-invalid", limit=20, now=created_at + timedelta(minutes=1)
        )
        assert listed[0].payload == row.payload

    asyncio.run(exercise())


def test_private_payload_rejects_secret_fields_and_schema_has_no_secret_columns(
    migrated_private_history,
) -> None:
    database = migrated_private_history
    created_at = datetime.now(UTC).replace(microsecond=0)

    async def exercise() -> None:
        for payload in (
            {"private_pem": "-----BEGIN PRIVATE KEY-----"},
            {"public_key": {"d": "private-exponent"}},
            {"public_key": "-----BEGIN PRIVATE KEY-----"},
            {"result": {"trace": ["private trace"]}},
            {"passphrase": "do-not-store"},
        ):
            with pytest.raises(ValueError):
                await record_operation(
                    database,
                    _entry(),
                    owner_id="owner-secrets",
                    created_at=created_at,
                    payload=payload,
                )

        async with database.sessions() as session:
            result = await session.execute(text("PRAGMA table_info(private_history_records)"))
            columns = {row[1] for row in result}
        assert not columns.intersection(
            {"d", "private_pem", "private_key_pem", "passphrase", "trace", "traces"}
        )

    asyncio.run(exercise())


def test_storage_validation_rejects_malformed_metadata_and_payloads() -> None:
    entry = _entry()
    for owner_id in ("", 1, "x\n", "x" * 513):
        with pytest.raises(ValueError):
            history_store._validate_owner_id(owner_id)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="timezone-aware"):
        history_store._validate_created_at(datetime.now())

    for malformed in (
        replace(entry, cipher="unknown"),
        replace(entry, operation="unknown"),
        replace(entry, cipher="caesar", operation="sign"),
        replace(entry, source="number"),
        replace(entry, response_mode="download"),
        replace(entry, input_length=-1),
        replace(entry, output_length=True),
        replace(entry, duration_ms=-1),
        replace(entry, http_status=True),
        replace(entry, succeeded=1),
    ):
        with pytest.raises(ValueError):
            history_store._validate_entry(malformed)

    assert history_store._json_value(bytearray(b"x"))["value"] == "eA=="
    assert history_store._json_value([1, 2.5, None]) == [1, 2.5, None]
    for value in (float("nan"), {1: "bad-key"}, object()):
        with pytest.raises(ValueError):
            history_store._json_value(value)

    for payload in (
        "not-a-mapping",
        {1: "bad-key"},
        {"unknown": "field"},
        {"content": "a", "contentBytes": "b"},
    ):
        with pytest.raises((TypeError, ValueError)):
            history_store._payload_mapping(payload)  # type: ignore[arg-type]

    for payload in (
        {"content": 1},
        {"numeric_input": True},
        {"numeric_input": 1.5},
        {"signature": 1},
        {"valid": 1},
        {"processing_state": ""},
        {"processing_state": "x" * 65},
    ):
        with pytest.raises(ValueError):
            history_store._normalize_payload("rsa", payload)
    with pytest.raises(ValueError, match="only RSA"):
        history_store._normalize_payload("caesar", {"content": "payload"})

    normalized = history_store._normalize_payload(
        "rsa",
        {
            "content": bytearray(b"x"),
            "numeric_input": [1, "2"],
            "signature": memoryview(b"sig"),
            "public_key": {"e": "17", "n": "3233"},
            "result": ["completed"],
            "valid": False,
            "processing_state": "completed",
        },
    )
    assert normalized.content_bytes == b"x"
    assert normalized.validity is False


def test_per_profile_fifo_eviction_uses_deterministic_logical_bytes(
    migrated_private_history, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = migrated_private_history
    created_at = datetime.now(UTC).replace(microsecond=0)

    async def exercise() -> None:
        first = await record_operation(
            database, _entry(), owner_id="owner-a", created_at=created_at
        )
        second_size = logical_history_bytes(
            owner_id="owner-a",
            created_at=created_at + timedelta(seconds=1),
            entry=_entry(),
            payload={},
        )
        monkeypatch.setattr(
            history_store,
            "PROFILE_HISTORY_QUOTA_BYTES",
            first.logical_size + second_size - 1,
        )
        monkeypatch.setattr(history_store, "GLOBAL_HISTORY_QUOTA_BYTES", 10 * 1024 * 1024)
        second = await record_operation(
            database,
            _entry(),
            owner_id="owner-a",
            created_at=created_at + timedelta(seconds=1),
        )
        rows, _ = await list_operations(
            database, owner_id="owner-a", limit=20, now=created_at + timedelta(minutes=1)
        )
        assert [row.id for row in rows] == [second.id]
        assert second.logical_size == second_size

    asyncio.run(exercise())


def test_global_fifo_eviction_can_remove_another_owner_without_exposure(
    migrated_private_history, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = migrated_private_history
    created_at = datetime.now(UTC).replace(microsecond=0)

    async def exercise() -> None:
        oldest = await record_operation(
            database, _entry(), owner_id="owner-a", created_at=created_at
        )
        retained = await record_operation(
            database,
            _entry(),
            owner_id="owner-b",
            created_at=created_at + timedelta(seconds=1),
        )
        incoming_size = logical_history_bytes(
            owner_id="owner-c",
            created_at=created_at + timedelta(seconds=2),
            entry=_entry(),
            payload={},
        )
        monkeypatch.setattr(history_store, "PROFILE_HISTORY_QUOTA_BYTES", 10 * 1024 * 1024)
        monkeypatch.setattr(
            history_store,
            "GLOBAL_HISTORY_QUOTA_BYTES",
            oldest.logical_size + retained.logical_size + incoming_size - 1,
        )
        incoming = await record_operation(
            database,
            _entry(),
            owner_id="owner-c",
            created_at=created_at + timedelta(seconds=2),
        )
        oldest_rows, _ = await list_operations(
            database, owner_id="owner-a", limit=20, now=created_at + timedelta(minutes=1)
        )
        retained_rows, _ = await list_operations(
            database, owner_id="owner-b", limit=20, now=created_at + timedelta(minutes=1)
        )
        incoming_rows, _ = await list_operations(
            database, owner_id="owner-c", limit=20, now=created_at + timedelta(minutes=1)
        )
        assert oldest_rows == []
        assert [row.id for row in retained_rows] == [retained.id]
        assert [row.id for row in incoming_rows] == [incoming.id]

    asyncio.run(exercise())


def test_concurrent_writers_never_exceed_the_global_logical_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "concurrent-history.sqlite3"
    url = _url(path)
    _migrate(url)
    first_database = create_database(url)
    second_database = create_database(url)
    created_at = datetime.now(UTC).replace(microsecond=0)
    row_size = logical_history_bytes(
        owner_id="owner-0",
        created_at=created_at,
        entry=_entry(),
        payload={},
    )
    monkeypatch.setattr(history_store, "PROFILE_HISTORY_QUOTA_BYTES", 10 * 1024 * 1024)
    monkeypatch.setattr(history_store, "GLOBAL_HISTORY_QUOTA_BYTES", row_size)

    async def exercise() -> list[object]:
        try:
            return await asyncio.gather(
                *(
                    record_operation(
                        first_database if index % 2 == 0 else second_database,
                        _entry(),
                        owner_id=f"owner-{index}",
                        created_at=created_at,
                    )
                    for index in range(8)
                ),
                return_exceptions=True,
            )
        finally:
            await first_database.engine.dispose()
            await second_database.engine.dispose()

    results = asyncio.run(exercise())
    assert any(not isinstance(result, BaseException) for result in results)
    with sqlite3.connect(path) as connection:
        count, total = connection.execute(
            "SELECT count(*), coalesce(sum(logical_size), 0) FROM private_history_records"
        ).fetchone()
    assert count <= 1
    assert total <= row_size


def test_manual_delete_one_and_delete_all_are_owner_scoped(
    migrated_private_history,
) -> None:
    database = migrated_private_history
    created_at = datetime.now(UTC).replace(microsecond=0)

    async def exercise() -> None:
        first = await record_operation(
            database, _entry(), owner_id="owner-a", created_at=created_at
        )
        second = await record_operation(
            database,
            _entry(),
            owner_id="owner-a",
            created_at=created_at + timedelta(seconds=1),
        )
        other = await record_operation(
            database,
            _entry(),
            owner_id="owner-b",
            created_at=created_at + timedelta(seconds=2),
        )
        read_at = created_at + timedelta(minutes=1)
        assert not await delete_operation(
            database, owner_id="owner-b", operation_id=first.id, now=read_at
        )
        assert await get_operation(database, owner_id="owner-a", operation_id=first.id, now=read_at)
        assert await delete_operation(
            database, owner_id="owner-a", operation_id=first.id, now=read_at
        )
        assert await delete_all_operations(database, owner_id="owner-a", now=read_at) == 1
        assert await get_operation(database, owner_id="owner-b", operation_id=other.id, now=read_at)
        assert (
            await get_operation(database, owner_id="owner-a", operation_id=second.id, now=read_at)
            is None
        )

    asyncio.run(exercise())


def test_quota_write_failure_is_surfaced_without_a_partial_row(
    migrated_private_history, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = migrated_private_history
    created_at = datetime.now(UTC).replace(microsecond=0)

    async def exercise() -> None:
        logical_size = logical_history_bytes(
            owner_id="owner-quota",
            created_at=created_at,
            entry=_entry(),
            payload={},
        )
        monkeypatch.setattr(history_store, "PROFILE_HISTORY_QUOTA_BYTES", logical_size - 1)
        monkeypatch.setattr(history_store, "GLOBAL_HISTORY_QUOTA_BYTES", logical_size - 1)
        with pytest.raises(HistoryQuotaExceededError):
            await record_operation(
                database,
                _entry(),
                owner_id="owner-quota",
                created_at=created_at,
            )
        rows, _ = await list_operations(
            database, owner_id="owner-quota", limit=20, now=created_at + timedelta(minutes=1)
        )
        assert rows == []

    asyncio.run(exercise())


def test_runtime_rejects_pre_private_schema_revision(tmp_path: Path) -> None:
    path = tmp_path / "old-history.sqlite3"
    url = _url(path)
    _migrate(url)
    alembic_config = AlembicConfig(str(PROJECT_ROOT / "alembic_sqlite.ini"))
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        alembic_command.downgrade(alembic_config, "sqlite_0002")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous

    database = create_database(url)

    async def check() -> bool:
        from app.db.engine import ping

        try:
            return await ping(database)
        finally:
            await database.engine.dispose()

    assert asyncio.run(check()) is False
