"""Deletion of history rows older than the fixed five-hour retention period."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from collections.abc import Sequence
from contextlib import suppress
from datetime import UTC, datetime, timedelta

from sqlalchemy import BigInteger, cast, delete, func, select, text

from app import config
from app.db.engine import Database, create_database
from app.db.models import CipherOperation
from app.history.store import purge_private_expired

logger = logging.getLogger(__name__)

PURGE_INTERVAL_SECONDS = 5 * 60
MAX_CLOCK_SKEW_SECONDS = 60
FIXED_RETENTION_SECONDS = int(getattr(config, "HISTORY_RETENTION_SECONDS", 5 * 60 * 60))


async def _database_now_epoch_us(database: Database) -> int:
    """Read the backend UTC clock in the epoch unit used by private history."""

    async with database.sessions() as session:
        try:
            dialect = session.get_bind().dialect.name
            if dialect == "sqlite":
                expression = cast(func.strftime("%s", "now"), BigInteger) * 1_000_000
            elif dialect == "postgresql":
                expression = cast(func.extract("epoch", func.now()) * 1_000_000, BigInteger)
            else:
                raise RuntimeError("history retention does not support this database backend")
            measured_epoch_us = (await session.execute(select(expression))).scalar_one()
        except BaseException:
            with suppress(BaseException):
                await session.rollback()
            with suppress(BaseException):
                await session.invalidate()
            raise
    try:
        return int(measured_epoch_us)
    except (TypeError, ValueError, OverflowError):
        raise RuntimeError("database UTC clock is unavailable") from None


async def database_clock_skew_seconds(
    database: Database, *, reference_epoch_us: int | None = None
) -> float:
    """Return absolute SQLite UTC-clock skew from the backend process clock."""

    measured_epoch_us = await _database_now_epoch_us(database)
    if reference_epoch_us is None:
        reference_epoch_us = time.time_ns() // 1_000
    if type(reference_epoch_us) is not int:
        raise TypeError("reference_epoch_us must be an integer")
    return abs(measured_epoch_us - reference_epoch_us) / 1_000_000


async def require_database_clock_sync(
    database: Database,
    *,
    max_skew_seconds: int = MAX_CLOCK_SKEW_SECONDS,
    reference_epoch_us: int | None = None,
) -> float:
    """Fail the rollout preflight when SQLite/process UTC clocks differ too much."""

    if type(max_skew_seconds) is not int or max_skew_seconds < 0:
        raise ValueError("max_skew_seconds must be a non-negative integer")
    skew = await database_clock_skew_seconds(database, reference_epoch_us=reference_epoch_us)
    if skew > max_skew_seconds:
        raise RuntimeError("SQLite UTC clock skew exceeds the rollout limit")
    return skew


async def purge_expired(database: Database, retention: int | float | None = None) -> int:
    """Purge both history tables at the fixed five-hour original-time cutoff.

    ``retention`` remains an ignored compatibility parameter for the previous
    maintenance-call signature. Retention is intentionally no longer caller
    configurable: private and ownerless legacy rows have one fixed policy.
    The cutoff comes from the backend UTC clock and is reused for both tables.
    """

    del retention
    database_now_epoch_us = await _database_now_epoch_us(database)
    database_now = datetime.fromtimestamp(database_now_epoch_us / 1_000_000, UTC)
    private_deleted = await purge_private_expired(database, now=database_now)

    cutoff = database_now - timedelta(seconds=FIXED_RETENTION_SECONDS)
    async with database.sessions() as session:
        try:
            if session.get_bind().dialect.name == "postgresql":
                # The legacy PostgreSQL table stores created_at as timestamptz,
                # while SQLite stores the same logical value as epoch INTEGER.
                result = await session.execute(
                    text("DELETE FROM cipher_operations WHERE created_at <= :cutoff"),
                    {"cutoff": cutoff},
                )
            else:
                result = await session.execute(
                    delete(CipherOperation).where(CipherOperation.created_at <= cutoff)
                )
            await session.commit()
        except BaseException:
            with suppress(BaseException):
                await session.rollback()
            with suppress(BaseException):
                await session.invalidate()
            raise
    return private_deleted + (result.rowcount or 0)


async def purge_periodically(
    database: Database,
    retention: int | float,
    interval_seconds: float | None = None,
) -> None:
    """Purge now and then every ``interval_seconds``; failures are logged, never raised."""

    if interval_seconds is None:
        interval_seconds = PURGE_INTERVAL_SECONDS

    while True:
        try:
            await purge_expired(database, retention)
        except Exception:
            # The exception text can contain connection details, so it is not logged.
            logger.warning("Could not purge expired cipher operation history")
        await asyncio.sleep(interval_seconds)


def _cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SQLite history retention maintenance")
    parser.add_argument(
        "--check-clock-only",
        action="store_true",
        help="check the SQLite/process UTC clock skew without deleting history",
    )
    return parser


async def _main(argv: Sequence[str] = ()) -> int:
    args = _cli_parser().parse_args(list(argv))
    try:
        url = config.database_url()
        if args.check_clock_only:
            retention = None
            retention_label = None
        else:
            retention = FIXED_RETENTION_SECONDS
            retention_label = f"{retention // 3600} hours"
    except ValueError:
        print("Could not purge history rows", file=sys.stderr)
        return 1
    if url is None:
        print("DATABASE_URL must be set", file=sys.stderr)
        return 1
    database = create_database(url)
    try:
        if args.check_clock_only:
            skew = await require_database_clock_sync(database)
        else:
            assert retention is not None
            deleted = await purge_expired(database, retention)
    except Exception:
        # Exception text can contain connection details, so it is not printed.
        action = "check SQLite clock" if args.check_clock_only else "purge history rows"
        print(f"Could not {action}", file=sys.stderr)
        return 1
    finally:
        await database.engine.dispose()
    if args.check_clock_only:
        print(f"SQLite clock preflight passed ({skew:.3f}s skew)")
        return 0
    print(f"Deleted {deleted} history rows older than {retention_label}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(sys.argv[1:])))
