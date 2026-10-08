"""Read-only PostgreSQL source adapter for the history continuity transfer.

The application runtime does not import this module.  It is intentionally a
small command-side boundary: it validates an explicitly supplied legacy URL,
opens one repeatable-read/read-only snapshot, and hands normalized history rows
to :mod:`app.history.continuity` for staging.

No identifier in the SQL below is derived from a URL, command-line argument, or
environment variable.  The source schema is the fixed public schema owned by
the legacy application; values such as the batch cursor are bound parameters.
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.history.continuity import (
    HISTORY_COLUMNS,
    HistoryRow,
    IdentityState,
    ImportResult,
    PathInput,
    datetime_to_epoch_microseconds,
    import_staging,
    normalize_history_row,
)

LEGACY_DATABASE_URL_ENV: Final = "LEGACY_DATABASE_URL"
LEGACY_DRIVER: Final = "postgresql+asyncpg"
LEGACY_ALEMBIC_REVISION: Final = "0004"
DEFAULT_SQLITE_SCHEMA_REVISION: Final = "sqlite_0002"
TRANSACTION_ISOLATION_LEVEL: Final = "REPEATABLE READ"
DEFAULT_BATCH_SIZE: Final = 500
MAX_BATCH_SIZE: Final = 10_000

# These statements deliberately use fixed schema/table/column names.  The only
# values supplied at execution time are ordinary data parameters.
READ_ONLY_TRANSACTION_SQL: Final = "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
REVISION_SQL: Final = "SELECT version_num FROM public.alembic_version"
TABLE_TYPE_SQL: Final = (
    "SELECT table_type "
    "FROM information_schema.tables "
    "WHERE table_schema = 'public' AND table_name = 'cipher_operations'"
)
COLUMNS_SQL: Final = (
    "SELECT column_name "
    "FROM information_schema.columns "
    "WHERE table_schema = 'public' AND table_name = 'cipher_operations' "
    "ORDER BY ordinal_position ASC"
)

# PostgreSQL's schema-0004 identity has the fixed relation name below.  Reading
# that relation directly preserves the exact last_value/is_called pair,
# including setval(..., false) state.  The catalog checks below make the fixed
# relation fail closed unless it is still the sequence owned by the fixed id
# column, has the expected persistent sequence metadata, and is readable.
SEQUENCE_SQL: Final = """
SELECT
    identity_sequence.last_value,
    identity_sequence.is_called,
    sequence_catalog.seqincrement AS increment
FROM public.cipher_operations_id_seq AS identity_sequence
JOIN pg_catalog.pg_sequence AS sequence_catalog
  ON sequence_catalog.seqrelid = 'public.cipher_operations_id_seq'::regclass
JOIN pg_catalog.pg_class AS sequence_relation
  ON sequence_relation.oid = sequence_catalog.seqrelid
WHERE sequence_catalog.seqrelid = pg_catalog.to_regclass(
    pg_catalog.pg_get_serial_sequence('public.cipher_operations', 'id')
)
  AND sequence_relation.oid = 'public.cipher_operations_id_seq'::regclass
  AND sequence_relation.relkind = 'S'
  AND sequence_relation.relpersistence = 'p'
  AND pg_catalog.has_sequence_privilege(sequence_catalog.seqrelid, 'SELECT')
""".strip()

HISTORY_ROWS_SQL: Final = """
SELECT
    id,
    created_at,
    cipher,
    operation,
    source,
    response_mode,
    input_length,
    output_length,
    http_status,
    succeeded,
    duration_ms
FROM public.cipher_operations
WHERE id > :after_id
ORDER BY id ASC
LIMIT :batch_size
""".strip()


class PostgresSourceError(RuntimeError):
    """Base class for redacted, fail-closed source errors."""


class InvalidLegacyURLError(PostgresSourceError, ValueError):
    """The source URL is absent or is not a PostgreSQL asyncpg URL."""


class SourceSchemaError(PostgresSourceError):
    """The legacy source is not the exact supported schema snapshot."""


class SourceReadError(PostgresSourceError):
    """The source could not be read without exposing driver details."""


class PreparePreflightError(PostgresSourceError):
    """A prepare path or schema-revision precondition failed."""


InvalidLegacyURL = InvalidLegacyURLError


@dataclass(frozen=True, slots=True)
class PostgresSnapshot:
    """Rows and identity evidence from one consistent source snapshot."""

    revision: str
    identity: IdentityState
    rows: tuple[HistoryRow, ...]
    snapshot_epoch_us: int


def _safe_error(message: str, error_type: type[PostgresSourceError] = SourceReadError) -> None:
    """Raise a source error without including URL, path, SQL, or row values."""

    raise error_type(message) from None


def validate_legacy_url(value: str) -> str:
    """Validate and return a PostgreSQL URL using only the asyncpg driver."""

    if type(value) is not str or not value.strip():
        _safe_error("legacy source URL is required", InvalidLegacyURL)
    candidate = value.strip()
    if any(character.isspace() or ord(character) < 0x20 for character in candidate):
        _safe_error("legacy source URL is invalid", InvalidLegacyURL)
    try:
        parsed = make_url(candidate)
        if parsed.drivername != LEGACY_DRIVER or not parsed.host or not parsed.database:
            _safe_error("legacy source URL is invalid", InvalidLegacyURL)
    except Exception:
        _safe_error("legacy source URL is invalid", InvalidLegacyURL)
    return candidate


def resolve_legacy_url(explicit_url: str | None = None) -> str:
    """Resolve a command URL, falling back only to ``LEGACY_DATABASE_URL``."""

    if explicit_url is None:
        explicit_url = os.environ.get(LEGACY_DATABASE_URL_ENV)
    if explicit_url is None:
        _safe_error("legacy source URL is required", InvalidLegacyURL)
    return validate_legacy_url(explicit_url)


def _validate_batch_size(value: int) -> int:
    if type(value) is not int or not 1 <= value <= MAX_BATCH_SIZE:
        _safe_error("batch size is invalid", PreparePreflightError)
    return value


def _validate_schema_revision(value: str) -> str:
    if type(value) is not str or not value or len(value) > 128:
        _safe_error("SQLite schema revision is invalid", PreparePreflightError)
    if not value.isascii() or any(
        not (character.isalnum() or character in "_.-") for character in value
    ):
        _safe_error("SQLite schema revision is invalid", PreparePreflightError)
    return value


def _preflight_paths(staging_path: PathInput, runtime_path: PathInput) -> tuple[Path, Path]:
    try:
        staging = Path(staging_path)
        runtime = Path(runtime_path)
        if staging.resolve(strict=False) == runtime.resolve(strict=False):
            _safe_error("staging and runtime paths must be distinct", PreparePreflightError)
        if staging.exists() or staging.is_symlink():
            _safe_error("staging path must not already exist", PreparePreflightError)
        if not staging.parent.is_dir():
            _safe_error("staging parent is unavailable", PreparePreflightError)
    except PreparePreflightError:
        raise
    except (OSError, RuntimeError, TypeError, ValueError):
        _safe_error("prepare path preflight failed", PreparePreflightError)
    return staging, runtime


def _row_mapping(value: object) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    mapping = getattr(value, "_mapping", None)
    if isinstance(mapping, Mapping):
        return mapping
    return None


def _row_value(value: object, name: str, position: int) -> object:
    mapping = _row_mapping(value)
    if mapping is not None:
        try:
            return mapping[name]
        except (KeyError, TypeError):
            pass
    try:
        return value[position]  # type: ignore[index]
    except (IndexError, KeyError, TypeError):
        _safe_error("legacy source result shape is invalid")
    raise AssertionError("unreachable")


def _mapping_result(result: object) -> object:
    mappings = getattr(result, "mappings", None)
    return mappings() if callable(mappings) else result


def _result_all(result: object) -> tuple[object, ...]:
    mapped = _mapping_result(result)
    all_rows = getattr(mapped, "all", None)
    if callable(all_rows):
        return tuple(all_rows())
    fetch_all = getattr(mapped, "fetchall", None)
    if callable(fetch_all):
        return tuple(fetch_all())
    try:
        return tuple(mapped)  # type: ignore[arg-type]
    except TypeError:
        _safe_error("legacy source result shape is invalid")
    raise AssertionError("unreachable")


async def _result_fetchmany(result: object, size: int) -> tuple[object, ...]:
    mapped = _mapping_result(result)
    fetch_many = getattr(mapped, "fetchmany", None)
    if not callable(fetch_many):
        _safe_error("legacy source result shape is invalid")
    rows = fetch_many(size)
    if inspect.isawaitable(rows):
        rows = await rows
    try:
        return tuple(rows)
    except TypeError:
        _safe_error("legacy source result shape is invalid")
    raise AssertionError("unreachable")


def _close_result(result: object) -> None:
    close = getattr(result, "close", None)
    if callable(close):
        close()


async def _execute_all(connection: object, statement: str) -> tuple[object, ...]:
    try:
        result = await connection.execute(text(statement))  # type: ignore[attr-defined]
    except Exception:
        _safe_error("legacy source query failed")
    try:
        return _result_all(result)
    finally:
        _close_result(result)


async def _read_revision(connection: object) -> str:
    rows = await _execute_all(connection, REVISION_SQL)
    if len(rows) != 1 or _row_value(rows[0], "version_num", 0) != LEGACY_ALEMBIC_REVISION:
        _safe_error("legacy source revision is unsupported", SourceSchemaError)
    return LEGACY_ALEMBIC_REVISION


async def _check_source_schema(connection: object) -> None:
    table_rows = await _execute_all(connection, TABLE_TYPE_SQL)
    if len(table_rows) != 1 or _row_value(table_rows[0], "table_type", 0) != "BASE TABLE":
        _safe_error("legacy history table is unsupported", SourceSchemaError)

    column_rows = await _execute_all(connection, COLUMNS_SQL)
    columns = tuple(_row_value(row, "column_name", 0) for row in column_rows)
    if columns != HISTORY_COLUMNS:
        _safe_error("legacy history columns are unsupported", SourceSchemaError)


async def _read_identity(connection: object) -> IdentityState:
    rows = await _execute_all(connection, SEQUENCE_SQL)
    if len(rows) != 1:
        _safe_error("legacy history identity is unavailable", SourceSchemaError)
    try:
        return IdentityState(
            last_value=_row_value(rows[0], "last_value", 0),  # type: ignore[arg-type]
            is_called=_row_value(rows[0], "is_called", 1),  # type: ignore[arg-type]
            increment=_row_value(rows[0], "increment", 2),  # type: ignore[arg-type]
        )
    except (TypeError, ValueError):
        _safe_error("legacy history identity is unsupported", SourceSchemaError)
    raise AssertionError("unreachable")


async def _read_history_rows(
    connection: object,
    *,
    batch_size: int,
) -> tuple[HistoryRow, ...]:
    rows: list[HistoryRow] = []
    last_id = 0
    while True:
        try:
            result = await connection.execute(  # type: ignore[attr-defined]
                text(HISTORY_ROWS_SQL),
                {"after_id": last_id, "batch_size": batch_size},
            )
        except Exception:
            _safe_error("legacy history rows are unavailable")
        try:
            batch = await _result_fetchmany(result, batch_size)
        finally:
            _close_result(result)
        if len(batch) > batch_size:
            _safe_error("legacy history batch is invalid", SourceSchemaError)
        if not batch:
            break
        for value in batch:
            try:
                row = normalize_history_row(value)
            except Exception:
                _safe_error("legacy history row is invalid", SourceSchemaError)
            if row.id <= last_id:
                _safe_error("legacy history rows are not strictly ascending", SourceSchemaError)
            rows.append(row)
            last_id = row.id
        if len(batch) < batch_size:
            break
    return tuple(rows)


async def _maybe_await(value: object) -> object:
    if inspect.isawaitable(value):
        return await value
    return value


async def read_source_snapshot(
    source_url: str | None = None,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    snapshot_epoch_us: int | None = None,
    engine_factory: Callable[..., Any] | None = None,
) -> PostgresSnapshot:
    """Read the supported legacy source inside one read-only snapshot."""

    source = resolve_legacy_url(source_url)
    batch_size = _validate_batch_size(batch_size)
    factory = create_async_engine if engine_factory is None else engine_factory
    engine: Any = None
    body_failed = False
    try:
        try:
            engine = factory(
                source,
                isolation_level=TRANSACTION_ISOLATION_LEVEL,
                echo=False,
            )
            async with engine.connect() as connection, connection.begin():
                await connection.execute(text(READ_ONLY_TRANSACTION_SQL))
                if snapshot_epoch_us is None:
                    snapshot_epoch_us = datetime_to_epoch_microseconds(datetime.now(UTC))
                revision = await _read_revision(connection)
                await _check_source_schema(connection)
                identity = await _read_identity(connection)
                rows = await _read_history_rows(connection, batch_size=batch_size)
            result = PostgresSnapshot(
                revision=revision,
                identity=identity,
                rows=rows,
                snapshot_epoch_us=snapshot_epoch_us,
            )
        except PostgresSourceError:
            body_failed = True
            raise
        except Exception:
            body_failed = True
            _safe_error("legacy PostgreSQL source read failed")
        return result
    finally:
        if engine is not None:
            try:
                await _maybe_await(engine.dispose())
            except Exception:
                if not body_failed:
                    _safe_error("legacy PostgreSQL source cleanup failed")


async def read_snapshot(
    source_url: str | None = None,
    **kwargs: Any,
) -> PostgresSnapshot:
    """Compatibility spelling for :func:`read_source_snapshot`."""

    return await read_source_snapshot(source_url, **kwargs)


async def prepare(
    staging_path: PathInput,
    runtime_path: PathInput,
    *,
    source_url: str | None = None,
    schema_revision: str = DEFAULT_SQLITE_SCHEMA_REVISION,
    batch_size: int = DEFAULT_BATCH_SIZE,
    snapshot_epoch_us: int | None = None,
    engine_factory: Callable[..., Any] | None = None,
) -> ImportResult:
    """Prepare a new staging file from a safe PostgreSQL source snapshot."""

    source = resolve_legacy_url(source_url)
    schema_revision = _validate_schema_revision(schema_revision)
    batch_size = _validate_batch_size(batch_size)
    staging, _runtime = _preflight_paths(staging_path, runtime_path)
    snapshot = await read_source_snapshot(
        source,
        batch_size=batch_size,
        snapshot_epoch_us=snapshot_epoch_us,
        engine_factory=engine_factory,
    )
    try:
        return import_staging(
            staging,
            snapshot.rows,
            snapshot.identity,
            source_revision=snapshot.revision,
            schema_revision=schema_revision,
            snapshot_epoch_us=snapshot.snapshot_epoch_us,
        )
    except PostgresSourceError:
        raise
    except Exception:
        _safe_error("history staging import failed")
    raise AssertionError("unreachable")


def _positive_batch_size(value: str) -> int:
    try:
        parsed = int(value, 10)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("batch size is invalid") from None
    if not 1 <= parsed <= MAX_BATCH_SIZE:
        raise argparse.ArgumentTypeError("batch size is invalid")
    return parsed


def _cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare a read-only history SQLite staging file")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument(
        "--source-url",
        "--source",
        "--legacy-database-url",
        dest="source_url",
    )
    prepare_parser.add_argument("--staging", required=True)
    prepare_parser.add_argument("--runtime", required=True)
    prepare_parser.add_argument(
        "--schema-revision",
        default=DEFAULT_SQLITE_SCHEMA_REVISION,
    )
    prepare_parser.add_argument(
        "--batch-size",
        type=_positive_batch_size,
        default=DEFAULT_BATCH_SIZE,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run only the non-destructive source prepare command."""

    args = _cli_parser().parse_args(argv)
    try:
        result = asyncio.run(
            prepare(
                args.staging,
                args.runtime,
                source_url=args.source_url,
                schema_revision=args.schema_revision,
                batch_size=args.batch_size,
            )
        )
        # Manifest evidence is deliberately path/URL/payload free.  In
        # particular, do not serialize ImportResult.path or verification.path.
        print(
            json.dumps(
                {
                    "ok": True,
                    "manifest": result.manifest.to_dict(),
                    "manifestDigest": result.manifest.digest,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    except Exception:
        print("history continuity command failed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "COLUMNS_SQL",
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_SQLITE_SCHEMA_REVISION",
    "HISTORY_COLUMNS",
    "HISTORY_ROWS_SQL",
    "LEGACY_ALEMBIC_REVISION",
    "LEGACY_DATABASE_URL_ENV",
    "LEGACY_DRIVER",
    "READ_ONLY_TRANSACTION_SQL",
    "REVISION_SQL",
    "SEQUENCE_SQL",
    "TABLE_TYPE_SQL",
    "TRANSACTION_ISOLATION_LEVEL",
    "InvalidLegacyURL",
    "InvalidLegacyURLError",
    "PostgresSnapshot",
    "PostgresSourceError",
    "PreparePreflightError",
    "SourceReadError",
    "SourceSchemaError",
    "main",
    "prepare",
    "read_snapshot",
    "read_source_snapshot",
    "resolve_legacy_url",
    "validate_legacy_url",
]
