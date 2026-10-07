"""PostgreSQL 17 → SQLite continuity rehearsal on an explicitly disposable database."""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime

import pytest

from app.history.continuity import (
    datetime_to_epoch_microseconds,
    rows_from_sqlite,
    verify_staging,
)
from app.history.postgres_source import prepare, read_source_snapshot
from tests.conftest import run_sql

pytestmark = pytest.mark.db


def test_postgres_0004_snapshot_preserves_rsa_nulls_and_identity_high_water(
    db_url: str, tmp_path
) -> None:
    created_at = datetime(2026, 10, 7, 1, 2, 3, 456789, tzinfo=UTC)
    run_sql(
        db_url,
        "INSERT INTO cipher_operations "
        "(id, created_at, cipher, operation, source, response_mode, input_length, "
        "output_length, http_status, succeeded, duration_ms) VALUES "
        "(2, '2026-10-07 01:02:03.456789+00', 'caesar', 'encrypt', 'text', NULL, "
        "4, 4, 200, true, 1), "
        "(7, '2026-10-07 01:02:03.456789+00', 'rsa', 'decrypt', 'text', NULL, "
        "NULL, NULL, 422, false, 3)",
    )
    run_sql(db_url, "SELECT setval('public.cipher_operations_id_seq', 100, true)")

    snapshot = asyncio.run(read_source_snapshot(db_url, batch_size=1, snapshot_epoch_us=123456))

    assert snapshot.revision == "0004"
    assert snapshot.identity.last_value == 100
    assert snapshot.identity.is_called is True
    assert snapshot.identity.increment == 1
    assert snapshot.identity.last_issued_high_water == 100
    assert [row.id for row in snapshot.rows] == [2, 7]
    assert {row.created_at for row in snapshot.rows} == {datetime_to_epoch_microseconds(created_at)}
    assert snapshot.rows[1].cipher == "rsa"
    assert snapshot.rows[1].input_length is snapshot.rows[1].output_length is None
    assert snapshot.rows[1].response_mode is None
    assert snapshot.rows[1].succeeded is False

    staging = tmp_path / "staging.sqlite3"
    result = asyncio.run(
        prepare(
            staging,
            tmp_path / "runtime.sqlite3",
            source_url=db_url,
            batch_size=1,
            snapshot_epoch_us=123456,
        )
    )
    report = verify_staging(staging, expected_manifest=result.manifest)
    assert report.sequence == 100
    assert rows_from_sqlite(staging) == snapshot.rows

    with sqlite3.connect(staging) as connection:
        inserted = connection.execute(
            "INSERT INTO cipher_operations "
            "(created_at, cipher, operation, source, http_status, succeeded, duration_ms) "
            "VALUES (?, 'rsa', 'encrypt', 'text', 200, 1, 1)",
            (datetime_to_epoch_microseconds(created_at),),
        )
        connection.commit()
    assert inserted.lastrowid == 101


def test_postgres_never_called_sequence_preserves_is_called_false(
    db_url: str,
) -> None:
    run_sql(db_url, "SELECT setval('public.cipher_operations_id_seq', 50, false)")

    snapshot = asyncio.run(read_source_snapshot(db_url, snapshot_epoch_us=123456))

    assert snapshot.rows == ()
    assert snapshot.identity.last_value == 50
    assert snapshot.identity.is_called is False
    assert snapshot.identity.last_issued_high_water == 49
