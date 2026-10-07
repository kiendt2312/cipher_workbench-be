"""Deletion of history rows older than the configured retention period."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from collections.abc import Sequence
from contextlib import suppress

from sqlalchemy import BigInteger, cast, delete, func, select

from app import config
from app.db.engine import Database, create_database
from app.db.models import CipherOperation

logger = logging.getLogger(__name__)

PURGE_INTERVAL_SECONDS = 6 * 60 * 60
MAX_CLOCK_SKEW_SECONDS = 60


async def database_clock_skew_seconds(
    database: Database, *, reference_epoch_us: int | None = None
) -> float:
    """Return absolute SQLite UTC-clock skew from the backend process clock."""

    database_now = cast(func.strftime("%s", "now"), BigInteger) * 1_000_000
    async with database.sessions() as session:
        try:
            measured_epoch_us = (await session.execute(select(database_now))).scalar_one()
        except BaseException:
            with suppress(BaseException):
                await session.rollback()
            with suppress(BaseException):
                await session.invalidate()
            raise
    if type(measured_epoch_us) is not int:
        raise RuntimeError("SQLite UTC clock is unavailable")
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


async def purge_expired(database: Database, days: int) -> int:
    """Delete rows older than ``days`` days and return how many were removed."""

    # `%s` is the long-supported UTC Unix-seconds form.  Multiplying into the
    # table's epoch-microsecond unit avoids requiring SQLite's newer `subsec`
    # modifier while keeping the cutoff on the database clock.
    database_now = cast(func.strftime("%s", "now"), BigInteger) * 1_000_000
    cutoff = database_now - days * 86_400 * 1_000_000
    async with database.sessions() as session:
        try:
            result = await session.execute(
                delete(CipherOperation).where(CipherOperation.created_at < cutoff)
            )
            await session.commit()
        except BaseException:
            with suppress(BaseException):
                await session.rollback()
            with suppress(BaseException):
                await session.invalidate()
            raise
    return result.rowcount or 0


async def purge_periodically(
    database: Database, days: int, interval_seconds: float = PURGE_INTERVAL_SECONDS
) -> None:
    """Purge now and then every ``interval_seconds``; failures are logged, never raised."""

    while True:
        try:
            await purge_expired(database, days)
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
        days = None if args.check_clock_only else config.history_retention_days()
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
            assert days is not None
            deleted = await purge_expired(database, days)
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
    print(f"Deleted {deleted} history rows older than {days} days")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(sys.argv[1:])))
