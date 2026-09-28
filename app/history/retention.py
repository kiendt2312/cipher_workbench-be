"""Deletion of history rows older than the configured retention period."""

from __future__ import annotations

import asyncio
import logging
import sys

from sqlalchemy import delete, func

from app import config
from app.db.engine import Database, create_database
from app.db.models import CipherOperation

logger = logging.getLogger(__name__)

PURGE_INTERVAL_SECONDS = 6 * 60 * 60


async def purge_expired(database: Database, days: int) -> int:
    """Delete rows older than ``days`` days and return how many were removed."""

    cutoff = func.now() - func.make_interval(0, 0, 0, days)
    async with database.sessions() as session:
        result = await session.execute(
            delete(CipherOperation).where(CipherOperation.created_at < cutoff)
        )
        await session.commit()
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


async def _main() -> int:
    url = config.database_url()
    if url is None:
        print("DATABASE_URL must be set", file=sys.stderr)
        return 1
    days = config.history_retention_days()
    database = create_database(url)
    try:
        deleted = await purge_expired(database, days)
    except Exception:
        # The exception text can contain connection details, so it is not printed.
        print("Could not purge history rows", file=sys.stderr)
        return 1
    finally:
        await database.engine.dispose()
    print(f"Deleted {deleted} history rows older than {days} days")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
