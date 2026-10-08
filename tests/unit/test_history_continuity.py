"""Unit coverage for the fail-closed history continuity primitives."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.history import continuity
from app.history.continuity import (
    FORMAT_VERSION,
    REPLACEMENT_CONFIRMATION,
    HistoryRow,
    IdentityState,
    InvalidHistoryRow,
    Manifest,
    PublicationError,
    UnsupportedSequenceState,
    VerificationError,
    canonical_row_bytes,
    canonical_rows_bytes,
    datetime_to_epoch_microseconds,
    derive_last_issued_high_water,
    epoch_microseconds_to_datetime,
    id_set_digest,
    import_staging,
    main,
    normalize_history_row,
    publish_first,
    rollback_delta_report,
    row_digest,
    verify_staging,
)


def _row(
    row_id: int,
    *,
    created_at: int = 1_000_000,
    cipher: str = "caesar",
    operation: str | None = "encrypt",
    response_mode: str | None = None,
) -> HistoryRow:
    return HistoryRow(
        id=row_id,
        created_at=created_at,
        cipher=cipher,
        operation=operation,
        source="text",
        response_mode=response_mode,
        input_length=4,
        output_length=None,
        http_status=200,
        succeeded=True,
        duration_ms=2,
    )


def _create_baseline_fixture(
    path: Path,
    *,
    nullable_source: bool = False,
    omit_id_check: bool = False,
    descending_indexes: bool = True,
    weakened_check: str | None = None,
) -> Manifest:
    source_nullability = "" if nullable_source else " NOT NULL"
    if omit_id_check:
        id_check = ""
    elif weakened_check == "id":
        id_check = " CHECK (id > 0 OR 1=1)"
    else:
        id_check = " CHECK (id > 0)"
    input_check = (
        "CHECK(input_length >= 0 OR 1=1)"
        if weakened_check == "input_length"
        else "CHECK(input_length >= 0)"
    )
    direction = "DESC" if descending_indexes else "ASC"
    row = _row(1)
    with sqlite3.connect(path) as connection:
        connection.executescript(
            f"""
            CREATE TABLE cipher_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT{id_check},
                created_at INTEGER NOT NULL,
                cipher TEXT NOT NULL CHECK(cipher IN
                    ('caesar', 'vigenere', 'playfair', 'affine', 'columnar', 'hill', 'des',
                     'rsa', 'dh')),
                operation TEXT CHECK(operation IN ('encrypt', 'decrypt')),
                source TEXT{source_nullability} CHECK(source IN ('text', 'file')),
                response_mode TEXT CHECK(response_mode IN ('content', 'file')),
                input_length INTEGER {input_check},
                output_length INTEGER CHECK(output_length >= 0),
                http_status INTEGER NOT NULL,
                succeeded INTEGER NOT NULL CHECK(succeeded IN (0, 1)),
                duration_ms INTEGER NOT NULL CHECK(duration_ms >= 0)
            );
            CREATE INDEX ix_cipher_operations_created_at_id
                ON cipher_operations (created_at {direction}, id {direction});
            CREATE INDEX ix_cipher_operations_cipher_created_at
                ON cipher_operations (cipher, created_at {direction}, id {direction});
            CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);
            INSERT INTO alembic_version(version_num) VALUES ('sqlite_0002');
            """
        )
        connection.execute(
            "INSERT INTO cipher_operations "
            "(id, created_at, cipher, operation, source, response_mode, input_length, "
            "output_length, http_status, succeeded, duration_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            row.as_sql_values(),
        )
    return Manifest.from_rows(
        [row],
        IdentityState(1, True, 1),
        source_revision="postgres-0004",
        schema_revision="sqlite_0002",
        snapshot_epoch_us=123,
    )


def test_canonical_serializer_has_golden_bytes_and_byte_length_framing() -> None:
    row = HistoryRow(7, -1, "rsa", None, "text", "file", None, 0, 422, False, 3)

    assert canonical_row_bytes(row) == (
        b"R53:i1:7i2:-1s3:rsan0:s4:texts4:filen0:i1:0i3:422b1:0i1:3"
    )
    assert canonical_rows_bytes([row]) == (
        b"cipher-workbench/history-rows/v1\n"
        b"R53:i1:7i2:-1s3:rsan0:s4:texts4:filen0:i1:0i3:422b1:0i1:3"
    )
    assert row_digest([row]) == "9c46348a58ffe9654d0fdc91ecc00fde21cb38dcb88daca0c3ce8566b12ac478"
    assert (
        id_set_digest([row]) == "1064a60579171c34506b6a6a30e0ec8c76ee84c026ad0b8767136dbaf80cbd43"
    )

    changed = HistoryRow(7, -1, "rsa", "encrypt", "text", "file", None, 0, 422, False, 3)
    assert row_digest([changed]) != row_digest([row])
    assert row_digest([_row(1), _row(2)]) != row_digest([_row(1, created_at=2)])


def test_mapping_normalization_preserves_datetime_precision_and_ignores_extra_payload() -> None:
    value = {
        "id": 3,
        "created_at": datetime(1970, 1, 1, 6, 59, 59, 876544, tzinfo=timezone(timedelta(hours=7))),
        "cipher": "rsa",
        "operation": "encrypt",
        "source": "file",
        "response_mode": None,
        "input_length": None,
        "output_length": 8,
        "http_status": 200,
        "succeeded": 1,
        "duration_ms": 0,
        "plaintext": "must never be collected",
        "private_key": "must never be collected",
    }

    normalized = normalize_history_row(value)

    assert normalized.created_at == -123456
    assert normalized.succeeded is True
    assert "plaintext" not in normalized.__slots__
    assert normalized.as_sql_values() == (
        3,
        -123456,
        "rsa",
        "encrypt",
        "file",
        None,
        None,
        8,
        200,
        1,
        0,
    )


def test_dh_rows_are_supported_by_continuity_staging(tmp_path: Path) -> None:
    result = import_staging(
        tmp_path / "dh.sqlite3",
        [_row(1, cipher="dh")],
        IdentityState(1, True, 1),
        source_revision="postgres-0004",
        schema_revision="sqlite_0002",
        snapshot_epoch_us=123,
    )

    with sqlite3.connect(result.path) as connection:
        table_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'cipher_operations'"
        ).fetchone()[0]
        assert "'dh'" in table_sql
        assert connection.execute("SELECT cipher FROM cipher_operations").fetchone() == ("dh",)
    assert result.verification.manifest.count == 1


def test_epoch_codec_is_exact_and_rejects_naive_values() -> None:
    value = datetime(1969, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)
    encoded = datetime_to_epoch_microseconds(value)

    assert encoded == -1
    assert epoch_microseconds_to_datetime(encoded) == value
    assert (
        datetime_to_epoch_microseconds(
            datetime(1970, 1, 1, 7, 0, 0, 1, tzinfo=timezone(timedelta(hours=7)))
        )
        == 1
    )
    with pytest.raises(ValueError):
        datetime_to_epoch_microseconds(datetime(2026, 1, 1))


def test_identity_high_water_handles_called_and_never_called_sequences() -> None:
    assert derive_last_issued_high_water(last_value=100, is_called=True, increment=10) == 100
    assert derive_last_issued_high_water(last_value=100, is_called=False, increment=10) == 90
    assert IdentityState(1, False, 1).last_issued_high_water == 0

    for state in ((100, True, 0), (100, True, -1), (0, True, 1), (100, 2, 1)):
        with pytest.raises(UnsupportedSequenceState):
            IdentityState(*state)


def test_history_rows_and_identity_fail_closed_on_invalid_types_and_values() -> None:
    valid = asdict(_row(1))
    invalid_fields = {
        "id": 0,
        "created_at": True,
        "cipher": "unknown",
        "operation": "sign",
        "source": "socket",
        "response_mode": "stream",
        "input_length": -1,
        "output_length": "2",
        "http_status": False,
        "succeeded": 1,
        "duration_ms": -1,
    }
    for field, invalid_value in invalid_fields.items():
        with pytest.raises(InvalidHistoryRow):
            HistoryRow(**{**valid, field: invalid_value})

    missing = valid.copy()
    del missing["cipher"]
    with pytest.raises(InvalidHistoryRow, match="missing history field"):
        normalize_history_row(missing)
    with pytest.raises(InvalidHistoryRow):
        normalize_history_row([*valid.values()][:-1])
    with pytest.raises(InvalidHistoryRow):
        normalize_history_row(object())  # type: ignore[arg-type]

    with pytest.raises(UnsupportedSequenceState, match="missing identity field"):
        IdentityState.from_mapping({"last_value": 1, "is_called": True})
    for state in (("1", True, 1), (2**63, True, 1), (1, "yes", 1)):
        with pytest.raises(UnsupportedSequenceState):
            IdentityState(*state)  # type: ignore[arg-type]


def test_import_rejects_invalid_revision_and_snapshot_before_creating_file(tmp_path: Path) -> None:
    for source_revision, schema_revision, snapshot_epoch_us in (
        ("", "sqlite_0002", 1),
        ("0004", "sqlite\n0001", 1),
        ("0004", "sqlite_0002", "now"),
    ):
        staging = tmp_path / f"invalid-{len(list(tmp_path.iterdir()))}.sqlite3"
        with pytest.raises((InvalidHistoryRow, ValueError)):
            import_staging(
                staging,
                [_row(1)],
                IdentityState(1, True, 1),
                source_revision=source_revision,
                schema_revision=schema_revision,
                snapshot_epoch_us=snapshot_epoch_us,  # type: ignore[arg-type]
            )
        assert not staging.exists()


def test_import_explicit_ids_and_sequence_seed_preserve_high_water(tmp_path: Path) -> None:
    rows = [_row(9, created_at=20), _row(2, created_at=20, cipher="rsa", operation=None)]
    result = import_staging(
        tmp_path / "staging.sqlite3",
        rows,
        IdentityState(last_value=100, is_called=True, increment=1),
        source_revision="postgres-0004",
        schema_revision="sqlite-injected-revision",
        snapshot_epoch_us=123,
    )

    assert result.manifest.count == 2
    assert (result.manifest.min_id, result.manifest.max_id) == (2, 9)
    assert result.manifest.identity_last_value == 100
    assert result.manifest.identity_is_called is True
    assert result.manifest.identity_increment == 1
    assert result.manifest.identity_last_issued == 100
    assert result.verification.quick_check == "ok"
    assert result.verification.integrity_check == "ok"
    assert result.verification.sequence == 100
    with sqlite3.connect(result.path) as connection:
        assert connection.execute("SELECT id FROM cipher_operations ORDER BY id").fetchall() == [
            (2,),
            (9,),
        ]
        connection.execute(
            "INSERT INTO cipher_operations "
            "(created_at, cipher, operation, source, http_status, succeeded, duration_ms) "
            "VALUES (20, 'des', 'encrypt', 'text', 200, 1, 1)"
        )
        assert connection.execute(
            "SELECT id FROM cipher_operations ORDER BY id DESC LIMIT 1"
        ).fetchone() == (101,)


def test_never_called_identity_seeds_before_next_candidate(tmp_path: Path) -> None:
    result = import_staging(
        tmp_path / "empty.sqlite3",
        [],
        IdentityState(last_value=100, is_called=False, increment=10),
        source_revision="postgres-0004",
        schema_revision="sqlite-revision",
        snapshot_epoch_us=123,
    )

    assert result.manifest.identity_last_issued == 90
    assert result.verification.sequence == 90
    with sqlite3.connect(result.path) as connection:
        connection.execute(
            "INSERT INTO cipher_operations "
            "(created_at, cipher, source, http_status, succeeded, duration_ms) "
            "VALUES (0, 'caesar', 'text', 200, 1, 1)"
        )
        assert connection.execute("SELECT id FROM cipher_operations").fetchone() == (91,)


def test_import_rejects_duplicate_or_invalid_rows_before_writing_staging(tmp_path: Path) -> None:
    duplicate_path = tmp_path / "duplicate.sqlite3"
    with pytest.raises(InvalidHistoryRow):
        import_staging(
            duplicate_path,
            [_row(1), _row(1)],
            IdentityState(1, True, 1),
            source_revision="postgres-0004",
            schema_revision="sqlite-revision",
            snapshot_epoch_us=123,
        )
    assert not duplicate_path.exists()

    invalid_path = tmp_path / "invalid.sqlite3"
    with pytest.raises(InvalidHistoryRow):
        import_staging(
            invalid_path,
            [{**asdict(_row(1)), "cipher": "unknown"}],
            IdentityState(1, True, 1),
            source_revision="postgres-0004",
            schema_revision="sqlite-revision",
            snapshot_epoch_us=123,
        )
    assert not invalid_path.exists()


def test_verify_detects_row_mutation_and_manifest_mismatch(tmp_path: Path) -> None:
    result = import_staging(
        tmp_path / "staging.sqlite3",
        [_row(1)],
        IdentityState(1, True, 1),
        source_revision="postgres-0004",
        schema_revision="sqlite-revision",
        snapshot_epoch_us=123,
    )
    with sqlite3.connect(result.path) as connection:
        connection.execute("UPDATE cipher_operations SET created_at = 999 WHERE id = 1")
        connection.commit()

    with pytest.raises(VerificationError):
        verify_staging(result.path, expected_manifest_digest=result.manifest.digest)


@pytest.mark.parametrize("revision_state", ("missing", "empty", "wrong", "multiple"))
def test_verify_and_publish_require_one_matching_alembic_revision(
    tmp_path: Path, revision_state: str
) -> None:
    result = import_staging(
        tmp_path / "staging.sqlite3",
        [_row(1)],
        IdentityState(1, True, 1),
        source_revision="postgres-0004",
        schema_revision="sqlite_0002",
        snapshot_epoch_us=123,
    )
    with sqlite3.connect(result.path) as connection:
        if revision_state == "missing":
            connection.execute("DROP TABLE alembic_version")
        elif revision_state == "empty":
            connection.execute("DELETE FROM alembic_version")
        elif revision_state == "wrong":
            connection.execute("UPDATE alembic_version SET version_num = 'sqlite_wrong'")
        else:
            connection.execute("INSERT INTO alembic_version(version_num) VALUES ('sqlite_0002')")
        connection.commit()

    with pytest.raises(VerificationError):
        verify_staging(result.path, expected_manifest_digest=result.manifest.digest)

    with pytest.raises(VerificationError):
        publish_first(
            result.path,
            tmp_path / "runtime.sqlite3",
            expected_manifest_digest=result.manifest.digest,
            app_stopped=True,
        )
    assert result.path.exists()


@pytest.mark.parametrize(
    ("variant", "options"),
    (
        ("nullability", {"nullable_source": True}),
        ("check", {"omit_id_check": True}),
        ("index_direction", {"descending_indexes": False}),
    ),
)
def test_verify_and_publish_reject_sqlite_baseline_drift(
    tmp_path: Path, variant: str, options: dict[str, bool]
) -> None:
    staging = tmp_path / f"{variant}.sqlite3"
    manifest = _create_baseline_fixture(staging, **options)

    with pytest.raises(VerificationError):
        verify_staging(
            staging,
            expected_manifest=manifest,
            expected_manifest_digest=manifest.digest,
        )

    with pytest.raises(VerificationError):
        publish_first(
            staging,
            tmp_path / "runtime.sqlite3",
            expected_manifest_digest=manifest.digest,
            app_stopped=True,
        )
    assert staging.exists()


@pytest.mark.parametrize("weakened_check", ("id", "input_length"))
def test_verify_and_publish_reject_logically_weakened_checks(
    tmp_path: Path, weakened_check: str
) -> None:
    staging = tmp_path / f"weakened-{weakened_check}.sqlite3"
    manifest = _create_baseline_fixture(staging, weakened_check=weakened_check)

    with pytest.raises(VerificationError):
        verify_staging(
            staging,
            expected_manifest=manifest,
            expected_manifest_digest=manifest.digest,
        )

    with pytest.raises(VerificationError):
        publish_first(
            staging,
            tmp_path / "runtime.sqlite3",
            expected_manifest_digest=manifest.digest,
            app_stopped=True,
        )
    assert staging.exists()


def test_first_publish_requires_stopped_app_and_never_overwrites_runtime(tmp_path: Path) -> None:
    result = import_staging(
        tmp_path / "staging.sqlite3",
        [_row(1)],
        IdentityState(1, True, 1),
        source_revision="postgres-0004",
        schema_revision="sqlite-revision",
        snapshot_epoch_us=123,
    )
    runtime = tmp_path / "runtime.sqlite3"
    with pytest.raises(PublicationError):
        publish_first(
            result.path,
            runtime,
            expected_manifest_digest=result.manifest.digest,
            app_stopped=False,
        )
    assert result.path.exists()

    runtime.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        publish_first(
            result.path,
            runtime,
            expected_manifest_digest=result.manifest.digest,
            app_stopped=True,
        )
    assert runtime.read_bytes() == b"existing"
    assert result.path.exists()


def test_first_publish_faults_never_overwrite_and_link_cleanup_is_recoverable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = import_staging(
        tmp_path / "staging.sqlite3",
        [_row(1)],
        IdentityState(1, True, 1),
        source_revision="postgres-0004",
        schema_revision="sqlite-revision",
        snapshot_epoch_us=123,
    )
    runtime = tmp_path / "runtime.sqlite3"

    with pytest.raises(VerificationError):
        publish_first(
            result.path,
            runtime,
            expected_manifest_digest="0" * 64,
            app_stopped=True,
        )
    assert result.path.exists()
    assert not runtime.exists()

    with monkeypatch.context() as scoped:
        scoped.setattr(continuity, "_same_filesystem", lambda _source, _parent: False)
        with pytest.raises(PublicationError, match="share a filesystem"):
            publish_first(
                result.path,
                runtime,
                expected_manifest_digest=result.manifest.digest,
                app_stopped=True,
            )
    assert result.path.exists()
    assert not runtime.exists()

    with monkeypatch.context() as scoped:
        scoped.setattr(
            continuity.os,
            "link",
            lambda _source, _target: (_ for _ in ()).throw(OSError("simulated link failure")),
        )
        with pytest.raises(PublicationError, match="no-overwrite publication failed"):
            publish_first(
                result.path,
                runtime,
                expected_manifest_digest=result.manifest.digest,
                app_stopped=True,
            )
    assert result.path.exists()
    assert not runtime.exists()

    original_unlink = Path.unlink

    def interrupted_unlink(path: Path, *args, **kwargs) -> None:
        if path == result.path:
            raise OSError("simulated interruption after link")
        original_unlink(path, *args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "unlink", interrupted_unlink)
        with pytest.raises(PublicationError, match="cleanup was not durable"):
            publish_first(
                result.path,
                runtime,
                expected_manifest_digest=result.manifest.digest,
                app_stopped=True,
            )

    assert result.path.exists() and runtime.exists()
    assert result.path.stat().st_ino == runtime.stat().st_ino
    verify_staging(runtime, expected_manifest_digest=result.manifest.digest)


def test_interrupted_import_requires_a_new_staging_name_and_never_touches_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    failed = tmp_path / "failed-staging.sqlite3"
    retry = tmp_path / "retry-staging.sqlite3"
    runtime = tmp_path / "runtime.sqlite3"
    runtime.write_bytes(b"runtime-sentinel")

    with monkeypatch.context() as scoped:
        scoped.setattr(
            continuity,
            "_set_metadata",
            lambda _connection, _values: (_ for _ in ()).throw(
                OSError("simulated interrupted import")
            ),
        )
        with pytest.raises(OSError, match="interrupted import"):
            import_staging(
                failed,
                [_row(1), _row(2)],
                IdentityState(2, True, 1),
                source_revision="postgres-0004",
                schema_revision="sqlite-revision",
                snapshot_epoch_us=123,
            )

    assert failed.exists()
    assert runtime.read_bytes() == b"runtime-sentinel"
    with pytest.raises(FileExistsError):
        import_staging(
            failed,
            [_row(1), _row(2)],
            IdentityState(2, True, 1),
            source_revision="postgres-0004",
            schema_revision="sqlite-revision",
            snapshot_epoch_us=123,
        )

    result = import_staging(
        retry,
        [_row(1), _row(2)],
        IdentityState(2, True, 1),
        source_revision="postgres-0004",
        schema_revision="sqlite-revision",
        snapshot_epoch_us=123,
    )
    assert [row.id for row in continuity.rows_from_sqlite(result.path)] == [1, 2]
    assert failed.exists()
    assert runtime.read_bytes() == b"runtime-sentinel"


def test_rollback_delta_is_deterministic_and_read_only() -> None:
    before = [_row(1), _row(2)]
    after = [_row(2, created_at=2), _row(3)]

    report = rollback_delta_report(before, after)

    assert report.added_ids == (3,)
    assert report.removed_ids == (1,)
    assert report.changed_ids == (2,)
    assert report.colliding_ids == (2,)
    assert json.loads(report.to_json())["added_ids"] == [3]
    assert report.has_changes is True


def test_cli_failure_is_redacted(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "secret-path.sqlite3"

    assert (
        main(
            [
                "verify",
                "--database",
                str(missing),
                "--expected-manifest-digest",
                "0" * 64,
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert "history continuity command failed" in captured.err
    assert str(missing) not in captured.err
    assert FORMAT_VERSION not in captured.err
    assert REPLACEMENT_CONFIRMATION not in captured.err
