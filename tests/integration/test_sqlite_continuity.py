"""Disposable SQLite transfer, backup, publish, and replacement rehearsal."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

import pytest

from app.history import continuity
from app.history.continuity import (
    REPLACEMENT_CONFIRMATION,
    HistoryRow,
    IdentityState,
    Manifest,
    PublicationError,
    VerificationError,
    backup_sqlite_live,
    import_staging,
    main,
    publish_first,
    replace_runtime,
    restore_sqlite_backup,
    rollback_delta_report,
    rows_from_sqlite,
    verify_staging,
)


def _row(row_id: int, *, created_at: int = 1_000_000, cipher: str = "caesar") -> HistoryRow:
    return HistoryRow(
        id=row_id,
        created_at=created_at,
        cipher=cipher,
        operation="encrypt",
        source="text",
        response_mode=None,
        input_length=2,
        output_length=2,
        http_status=200,
        succeeded=True,
        duration_ms=1,
    )


def _import(path: Path, rows: list[HistoryRow]):
    return import_staging(
        path,
        rows,
        IdentityState(last_value=100, is_called=True, increment=1),
        source_revision="postgres-0004",
        schema_revision="sqlite_0001",
        snapshot_epoch_us=7,
    )


def test_full_disposable_transfer_backup_restore_and_replacement(tmp_path: Path) -> None:
    original_rows = [_row(2), _row(7, created_at=2_000_000, cipher="rsa")]
    original = _import(tmp_path / "staging.sqlite3", original_rows)
    backup_path = tmp_path / "recovery.sqlite3"

    backup = backup_sqlite_live(
        original.path,
        backup_path,
        expected_manifest_digest=original.manifest.digest,
    )
    assert backup.verified is True
    assert backup.backup_digest != original.manifest.digest

    restored_path = tmp_path / "restore-rehearsal.sqlite3"
    restored = restore_sqlite_backup(
        backup_path,
        restored_path,
        expected_manifest_digest=backup.backup_digest,
        expected_schema_revision="sqlite_0001",
    )
    assert restored.verified is True
    assert restored.restored_digest == backup.backup_digest
    assert (
        verify_staging(restored_path, expected_manifest_digest=backup.backup_digest).sequence == 100
    )

    runtime = tmp_path / "runtime.sqlite3"
    published = publish_first(
        original.path,
        runtime,
        expected_manifest_digest=original.manifest.digest,
        app_stopped=True,
    )
    assert published.manifest_digest == original.manifest.digest
    assert runtime.exists()
    assert not original.path.exists()

    replacement = _import(
        tmp_path / "replacement.sqlite3",
        [*original_rows, _row(8, created_at=3_000_000, cipher="des")],
    )
    replaced = replace_runtime(
        replacement.path,
        runtime,
        backup_path,
        expected_old_digest=original.manifest.digest,
        expected_new_digest=replacement.manifest.digest,
        expected_backup_digest=backup.backup_digest,
        app_stopped=True,
        confirmation=REPLACEMENT_CONFIRMATION,
        backup_verified=True,
    )
    assert replaced.old_digest == original.manifest.digest
    assert replaced.new_digest == replacement.manifest.digest
    assert backup_path.exists()
    assert (
        verify_staging(runtime, expected_manifest=replacement.manifest).manifest
        == replacement.manifest
    )


def test_backup_and_restore_refuse_overwrite_and_preserve_runtime(tmp_path: Path) -> None:
    original = _import(tmp_path / "source.sqlite3", [_row(1)])
    destination = tmp_path / "backup.sqlite3"
    backup = backup_sqlite_live(
        original.path, destination, expected_manifest_digest=original.manifest.digest
    )
    original_bytes = destination.read_bytes()

    with pytest.raises(FileExistsError):
        backup_sqlite_live(
            original.path, destination, expected_manifest_digest=original.manifest.digest
        )
    assert destination.read_bytes() == original_bytes

    target = tmp_path / "restore.sqlite3"
    restore_sqlite_backup(
        destination,
        target,
        expected_manifest_digest=backup.backup_digest,
    )
    target_bytes = target.read_bytes()
    with pytest.raises(FileExistsError):
        restore_sqlite_backup(
            destination,
            target,
            expected_manifest_digest=backup.backup_digest,
        )
    assert target.read_bytes() == target_bytes


def test_live_backup_recomputes_manifest_after_post_cutover_write(tmp_path: Path) -> None:
    original = _import(tmp_path / "staging.sqlite3", [_row(1, created_at=1_000_000)])
    runtime = tmp_path / "runtime.sqlite3"
    publish_first(
        original.path,
        runtime,
        expected_manifest_digest=original.manifest.digest,
        app_stopped=True,
    )

    def logical_state(path: Path) -> tuple[list[tuple], dict[str, str], int]:
        with sqlite3.connect(path) as connection:
            rows = connection.execute(
                "SELECT id, created_at, cipher, operation, source, response_mode, input_length, "
                "output_length, http_status, succeeded, duration_ms "
                "FROM cipher_operations ORDER BY created_at DESC, id DESC"
            ).fetchall()
            metadata = dict(
                connection.execute(
                    "SELECT key, value FROM history_continuity_meta ORDER BY key"
                ).fetchall()
            )
            sequence = connection.execute(
                "SELECT seq FROM sqlite_sequence WHERE name = 'cipher_operations'"
            ).fetchone()[0]
            return rows, metadata, sequence

    with sqlite3.connect(runtime) as connection:
        connection.execute(
            "INSERT INTO cipher_operations "
            "(created_at, cipher, operation, source, input_length, output_length, "
            "http_status, succeeded, duration_ms) "
            "VALUES (3000000, 'des', 'encrypt', 'text', 3, 3, 200, 1, 1)"
        )
        connection.commit()

    source_before_backup = logical_state(runtime)
    assert source_before_backup[2] == 101
    assert source_before_backup[1]["manifest_digest"] == original.manifest.digest

    backup = backup_sqlite_live(runtime, tmp_path / "live-backup.sqlite3")
    source_after_backup = logical_state(runtime)
    assert source_after_backup == source_before_backup
    assert backup.source_digest is None
    assert backup.backup_digest != original.manifest.digest

    restored = restore_sqlite_backup(
        backup.path,
        tmp_path / "live-restore.sqlite3",
        expected_manifest_digest=backup.backup_digest,
    )
    restored_state = logical_state(restored.path)
    assert restored_state[0] == source_before_backup[0]
    assert restored_state[2] == source_before_backup[2]
    assert restored_state[1]["manifest_digest"] == backup.backup_digest
    assert rows_from_sqlite(restored.path) == rows_from_sqlite(runtime)
    report = verify_staging(restored.path, expected_manifest_digest=backup.backup_digest)
    assert report.sequence == 101
    assert report.manifest.identity_source == "sqlite"
    assert report.manifest.identity_last_issued == 101


def test_live_backup_is_consistent_while_writer_has_uncommitted_row(tmp_path: Path) -> None:
    source = _import(tmp_path / "runtime.sqlite3", [_row(1)])
    writer = sqlite3.connect(source.path)
    try:
        writer.execute("BEGIN IMMEDIATE")
        writer.execute(
            "INSERT INTO cipher_operations "
            "(created_at, cipher, operation, source, input_length, output_length, "
            "http_status, succeeded, duration_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (2_000_000, "rsa", "decrypt", "text", None, 2, 200, 1, 1),
        )

        backup = backup_sqlite_live(source.path, tmp_path / "live-backup.sqlite3")
        backup_report = verify_staging(backup.path, expected_manifest_digest=backup.backup_digest)
        assert backup_report.manifest.count == 1
        assert [row.id for row in rows_from_sqlite(backup.path)] == [1]

        writer.commit()
    finally:
        writer.close()

    assert [row.id for row in rows_from_sqlite(source.path)] == [1, 101]


def test_live_backup_lock_contention_is_bounded_and_leaves_no_destination(tmp_path: Path) -> None:
    source = _import(tmp_path / "runtime.sqlite3", [_row(1)])
    destination = tmp_path / "contended-backup.sqlite3"
    locker = sqlite3.connect(source.path, timeout=0)
    try:
        locker.execute("BEGIN EXCLUSIVE")
        started = time.monotonic()
        with pytest.raises(VerificationError, match="integrity check could not run"):
            backup_sqlite_live(source.path, destination, timeout=0.2)
        elapsed = time.monotonic() - started
    finally:
        locker.rollback()
        locker.close()

    assert elapsed < 0.5
    assert not destination.exists()


def test_cli_live_backup_aborts_when_lock_starts_after_preflight(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _import(tmp_path / "runtime.sqlite3", [_row(1)])
    destination = tmp_path / "late-lock-backup.sqlite3"
    with sqlite3.connect(source.path) as connection:
        connection.execute("CREATE TABLE backup_padding(value BLOB NOT NULL)")
        connection.executemany(
            "INSERT INTO backup_padding(value) VALUES (?)",
            [(b"x" * 65_536,) for _ in range(500)],
        )
        connection.commit()

    lock_acquired = threading.Event()
    release_lock = threading.Event()
    lock_errors: list[Exception] = []

    def hold_lock_after_destination_appears() -> None:
        deadline = time.monotonic() + 2.0
        while not destination.exists() and time.monotonic() < deadline:
            time.sleep(0.001)
        if not destination.exists():
            lock_errors.append(RuntimeError("backup candidate was not created"))
            return
        locker = sqlite3.connect(source.path, timeout=0)
        try:
            while time.monotonic() < deadline:
                try:
                    locker.execute("BEGIN EXCLUSIVE")
                except sqlite3.OperationalError:
                    time.sleep(0.001)
                else:
                    lock_acquired.set()
                    release_lock.wait(0.75)
                    return
            lock_errors.append(RuntimeError("exclusive lock was not acquired"))
        finally:
            locker.rollback()
            locker.close()

    locker_thread = threading.Thread(target=hold_lock_after_destination_appears, daemon=True)
    locker_thread.start()
    started = time.monotonic()
    try:
        result = main(["backup", "--source", str(source.path), "--destination", str(destination)])
    finally:
        release_lock.set()
        locker_thread.join(timeout=1.0)
    elapsed = time.monotonic() - started

    assert result == 2
    assert not locker_thread.is_alive()
    assert lock_acquired.is_set()
    assert not lock_errors
    assert elapsed < 0.5
    assert not destination.exists()
    assert capsys.readouterr().err.strip() == "history continuity command failed"


def test_cli_live_backup_accepts_advanced_runtime_without_old_digest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    original = _import(tmp_path / "staging.sqlite3", [_row(1)])
    runtime = tmp_path / "runtime.sqlite3"
    publish_first(
        original.path,
        runtime,
        expected_manifest_digest=original.manifest.digest,
        app_stopped=True,
    )
    with sqlite3.connect(runtime) as connection:
        connection.execute(
            "INSERT INTO cipher_operations "
            "(created_at, cipher, operation, source, input_length, output_length, "
            "http_status, succeeded, duration_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (2_000_000, "des", "decrypt", "text", 1, 1, 200, 1, 1),
        )
        connection.commit()

    destination = tmp_path / "cli-backup.sqlite3"
    assert main(["backup", "--source", str(runtime), "--destination", str(destination)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True
    assert output["manifestDigest"] != original.manifest.digest
    report = verify_staging(destination, expected_manifest_digest=output["manifestDigest"])
    assert report.manifest.identity_source == "sqlite"
    assert report.manifest.count == 2


def test_cli_verify_publish_restore_replace_delta_and_redacted_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    original = _import(tmp_path / "staging.sqlite3", [_row(1)])

    assert (
        main(
            [
                "verify",
                "--database",
                str(original.path),
                "--expected-manifest-digest",
                original.manifest.digest,
                "--schema-revision",
                "sqlite_0001",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["manifestDigest"] == original.manifest.digest

    backup_path = tmp_path / "backup.sqlite3"
    assert (
        main(
            [
                "backup",
                "--source",
                str(original.path),
                "--destination",
                str(backup_path),
                "--expected-manifest-digest",
                original.manifest.digest,
            ]
        )
        == 0
    )
    backup_digest = json.loads(capsys.readouterr().out)["manifestDigest"]

    restored_path = tmp_path / "restored.sqlite3"
    assert (
        main(
            [
                "restore",
                "--backup",
                str(backup_path),
                "--target",
                str(restored_path),
                "--expected-manifest-digest",
                backup_digest,
                "--schema-revision",
                "sqlite_0001",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["manifestDigest"] == backup_digest

    runtime = tmp_path / "runtime.sqlite3"
    assert (
        main(
            [
                "publish",
                "--staging",
                str(original.path),
                "--runtime",
                str(runtime),
                "--expected-manifest-digest",
                original.manifest.digest,
                "--app-stopped",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["manifestDigest"] == original.manifest.digest

    replacement = _import(tmp_path / "replacement.sqlite3", [_row(1), _row(2)])
    assert (
        main(
            [
                "replace",
                "--staging",
                str(replacement.path),
                "--runtime",
                str(runtime),
                "--backup",
                str(backup_path),
                "--expected-old-digest",
                original.manifest.digest,
                "--expected-new-digest",
                replacement.manifest.digest,
                "--expected-backup-digest",
                backup_digest,
                "--app-stopped",
                "--backup-verified",
                "--confirm",
                REPLACEMENT_CONFIRMATION,
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["manifestDigest"] == replacement.manifest.digest

    assert main(["delta", "--before", str(restored_path), "--after", str(runtime)]) == 0
    delta = json.loads(capsys.readouterr().out)
    assert delta["added_ids"] == [2]

    private_missing = tmp_path / "private-missing.sqlite3"
    assert (
        main(
            [
                "verify",
                "--database",
                str(private_missing),
                "--expected-manifest-digest",
                original.manifest.digest,
            ]
        )
        == 2
    )
    failure = capsys.readouterr().err
    assert failure.strip() == "history continuity command failed"
    assert str(private_missing) not in failure


def test_replacement_missing_evidence_leaves_runtime_unchanged(tmp_path: Path) -> None:
    original = _import(tmp_path / "original.sqlite3", [_row(1)])
    runtime = tmp_path / "runtime.sqlite3"
    publish_first(
        original.path,
        runtime,
        expected_manifest_digest=original.manifest.digest,
        app_stopped=True,
    )
    replacement = _import(tmp_path / "replacement.sqlite3", [_row(1), _row(2)])
    before = verify_staging(runtime, expected_manifest=original.manifest)

    with pytest.raises(PublicationError):
        replace_runtime(
            replacement.path,
            runtime,
            tmp_path / "missing-backup.sqlite3",
            expected_old_digest=original.manifest.digest,
            expected_new_digest=replacement.manifest.digest,
            app_stopped=True,
            confirmation=REPLACEMENT_CONFIRMATION,
            backup_verified=False,
        )

    assert verify_staging(runtime, expected_manifest=original.manifest) == before
    assert replacement.path.exists()


def test_replacement_is_rejected_after_first_runtime_write(tmp_path: Path) -> None:
    original = _import(tmp_path / "original.sqlite3", [_row(1)])
    runtime = tmp_path / "runtime.sqlite3"
    publish_first(
        original.path,
        runtime,
        expected_manifest_digest=original.manifest.digest,
        app_stopped=True,
    )
    backup = backup_sqlite_live(runtime, tmp_path / "backup.sqlite3")
    replacement = _import(tmp_path / "replacement.sqlite3", [_row(1), _row(2)])
    with sqlite3.connect(runtime) as connection:
        inserted = connection.execute(
            "INSERT INTO cipher_operations "
            "(created_at, cipher, operation, source, http_status, succeeded, duration_ms) "
            "VALUES (3000000, 'rsa', 'decrypt', 'text', 200, 1, 1)"
        )
        connection.execute("DELETE FROM cipher_operations WHERE id = ?", (inserted.lastrowid,))
        connection.commit()
    runtime_rows = rows_from_sqlite(runtime)

    with pytest.raises(PublicationError, match="identity advanced"):
        replace_runtime(
            replacement.path,
            runtime,
            backup.path,
            expected_old_digest=original.manifest.digest,
            expected_new_digest=replacement.manifest.digest,
            expected_backup_digest=backup.backup_digest,
            app_stopped=True,
            confirmation=REPLACEMENT_CONFIRMATION,
            backup_verified=True,
        )

    assert rows_from_sqlite(runtime) == runtime_rows
    assert replacement.path.exists()
    assert backup.path.exists()


def test_replacement_is_rejected_while_runtime_retains_new_row(tmp_path: Path) -> None:
    original = _import(tmp_path / "original.sqlite3", [_row(1)])
    runtime = tmp_path / "runtime.sqlite3"
    publish_first(
        original.path,
        runtime,
        expected_manifest_digest=original.manifest.digest,
        app_stopped=True,
    )
    backup = backup_sqlite_live(runtime, tmp_path / "backup.sqlite3")
    replacement = _import(tmp_path / "replacement.sqlite3", [_row(1), _row(2)])
    with sqlite3.connect(runtime) as connection:
        connection.execute(
            "INSERT INTO cipher_operations "
            "(created_at, cipher, operation, source, http_status, succeeded, duration_ms) "
            "VALUES (3000000, 'rsa', 'decrypt', 'text', 200, 1, 1)"
        )
        connection.commit()
    runtime_rows = rows_from_sqlite(runtime)

    with pytest.raises(VerificationError, match="count, range, ID set, or digest"):
        replace_runtime(
            replacement.path,
            runtime,
            backup.path,
            expected_old_digest=original.manifest.digest,
            expected_new_digest=replacement.manifest.digest,
            expected_backup_digest=backup.backup_digest,
            app_stopped=True,
            confirmation=REPLACEMENT_CONFIRMATION,
            backup_verified=True,
        )

    assert rows_from_sqlite(runtime) == runtime_rows
    assert replacement.path.exists()
    assert backup.path.exists()


def test_replacement_reports_post_replace_fsync_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = _import(tmp_path / "original.sqlite3", [_row(1)])
    runtime = tmp_path / "runtime.sqlite3"
    publish_first(
        original.path,
        runtime,
        expected_manifest_digest=original.manifest.digest,
        app_stopped=True,
    )
    backup = backup_sqlite_live(runtime, tmp_path / "backup.sqlite3")
    replacement = _import(tmp_path / "replacement.sqlite3", [_row(1), _row(2)])
    monkeypatch.setattr(
        continuity,
        "_fsync_directory",
        lambda _directory: (_ for _ in ()).throw(OSError("simulated fsync failure")),
    )

    with pytest.raises(PublicationError, match=r"was replaced.*do not retry"):
        replace_runtime(
            replacement.path,
            runtime,
            backup.path,
            expected_old_digest=original.manifest.digest,
            expected_new_digest=replacement.manifest.digest,
            expected_backup_digest=backup.backup_digest,
            app_stopped=True,
            confirmation=REPLACEMENT_CONFIRMATION,
            backup_verified=True,
        )

    assert verify_staging(runtime, expected_manifest=replacement.manifest)
    assert not replacement.path.exists()
    assert backup.path.exists()


def test_replacement_fault_before_replace_keeps_old_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = _import(tmp_path / "original.sqlite3", [_row(1)])
    runtime = tmp_path / "runtime.sqlite3"
    publish_first(
        original.path,
        runtime,
        expected_manifest_digest=original.manifest.digest,
        app_stopped=True,
    )
    backup = backup_sqlite_live(runtime, tmp_path / "backup.sqlite3")
    replacement = _import(tmp_path / "replacement.sqlite3", [_row(1), _row(2)])

    def fail_replace(_source: Path, _destination: Path) -> None:
        raise OSError("simulated pre-replace failure")

    monkeypatch.setattr(continuity.os, "replace", fail_replace)
    with pytest.raises(PublicationError, match="atomic runtime replacement failed"):
        replace_runtime(
            replacement.path,
            runtime,
            backup.path,
            expected_old_digest=original.manifest.digest,
            expected_new_digest=replacement.manifest.digest,
            expected_backup_digest=backup.backup_digest,
            app_stopped=True,
            confirmation=REPLACEMENT_CONFIRMATION,
            backup_verified=True,
        )

    assert verify_staging(runtime, expected_manifest=original.manifest)
    assert replacement.path.exists()
    assert backup.path.exists()


def test_restore_removes_target_when_post_copy_verification_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _import(tmp_path / "source.sqlite3", [_row(1)])
    backup = backup_sqlite_live(source.path, tmp_path / "backup.sqlite3")
    target = tmp_path / "restore.sqlite3"
    real_verify = continuity.verify_staging
    calls = 0

    def fail_second_verify(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise VerificationError("simulated post-copy verification failure")
        return real_verify(*args, **kwargs)

    monkeypatch.setattr(continuity, "verify_staging", fail_second_verify)
    with pytest.raises(VerificationError, match="post-copy"):
        restore_sqlite_backup(
            backup.path,
            target,
            expected_manifest_digest=backup.backup_digest,
        )
    assert not target.exists()


def test_rollback_delta_detects_consumed_identity_after_rows_are_purged(tmp_path: Path) -> None:
    before = import_staging(
        tmp_path / "before.sqlite3",
        [_row(1)],
        IdentityState(last_value=100, is_called=True, increment=1),
        source_revision="postgres-0004",
        schema_revision="sqlite_0001",
        snapshot_epoch_us=7,
    )
    after = import_staging(
        tmp_path / "after.sqlite3",
        [_row(1)],
        IdentityState(last_value=101, is_called=True, increment=1),
        source_revision="postgres-0004",
        schema_revision="sqlite_0001",
        snapshot_epoch_us=7,
    )

    report = rollback_delta_report(before.path, after.path)

    assert report.added_ids == report.removed_ids == report.changed_ids == ()
    assert (report.before_sequence, report.after_sequence) == (100, 101)
    assert report.has_changes is True


def test_existing_sqlite_baseline_can_be_verified_with_injected_manifest(tmp_path: Path) -> None:
    path = tmp_path / "baseline.sqlite3"
    row = _row(1, created_at=123456, cipher="rsa")
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE cipher_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT CHECK(id > 0),
                created_at INTEGER NOT NULL,
                cipher TEXT NOT NULL CHECK(cipher IN
                    ('caesar', 'vigenere', 'playfair', 'affine', 'columnar', 'hill', 'des', 'rsa')),
                operation TEXT CHECK(operation IN ('encrypt', 'decrypt')),
                source TEXT NOT NULL CHECK(source IN ('text', 'file')),
                response_mode TEXT CHECK(response_mode IN ('content', 'file')),
                input_length INTEGER CHECK(input_length >= 0),
                output_length INTEGER CHECK(output_length >= 0),
                http_status INTEGER NOT NULL,
                succeeded INTEGER NOT NULL CHECK(succeeded IN (0, 1)),
                duration_ms INTEGER NOT NULL CHECK(duration_ms >= 0)
            );
            CREATE INDEX ix_cipher_operations_created_at_id
                ON cipher_operations (created_at DESC, id DESC);
            CREATE INDEX ix_cipher_operations_cipher_created_at
                ON cipher_operations (cipher, created_at DESC, id DESC);
            CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);
            INSERT INTO alembic_version(version_num) VALUES ('sqlite_0001');
            """
        )
        connection.execute(
            "INSERT INTO cipher_operations "
            "(id, created_at, cipher, operation, source, input_length, output_length, "
            "http_status, succeeded, duration_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            row.as_sql_values()[:5] + row.as_sql_values()[6:9] + row.as_sql_values()[9:],
        )

    manifest = Manifest.from_rows(
        [row],
        IdentityState(last_value=1, is_called=True, increment=1),
        source_revision="postgres-0004",
        schema_revision="sqlite_0001",
        snapshot_epoch_us=7,
    )
    report = verify_staging(
        path,
        expected_manifest=manifest,
        expected_manifest_digest=manifest.digest,
        expected_schema_revision="sqlite_0001",
    )
    assert report.manifest == manifest


def test_corrupt_backup_is_rejected_without_touching_separate_target(tmp_path: Path) -> None:
    original = _import(tmp_path / "source.sqlite3", [_row(1)])
    backup = tmp_path / "backup.sqlite3"
    evidence = backup_sqlite_live(
        original.path, backup, expected_manifest_digest=original.manifest.digest
    )

    wrong_revision_target = tmp_path / "wrong-revision.sqlite3"
    with pytest.raises(VerificationError):
        restore_sqlite_backup(
            backup,
            wrong_revision_target,
            expected_manifest_digest=evidence.backup_digest,
            expected_schema_revision="sqlite_wrong",
        )
    assert not wrong_revision_target.exists()

    with backup.open("r+b") as stream:
        stream.seek(0)
        stream.write(b"not-a-valid-sqlite")

    target = tmp_path / "restore.sqlite3"
    with pytest.raises(VerificationError):
        restore_sqlite_backup(
            backup,
            target,
            expected_manifest_digest=evidence.backup_digest,
        )
    assert not target.exists()
    assert original.path.exists()
