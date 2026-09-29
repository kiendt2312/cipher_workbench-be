"""Async PostgreSQL engine and session factory owned by the application lifespan."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

PING_TIMEOUT_SECONDS = 1.0


@dataclass(frozen=True)
class Database:
    """The engine plus the session factory built on it."""

    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]


def app_database(app: Any) -> Database | None:
    """Return the database the lifespan attached to ``app``, or ``None`` when disabled."""

    return getattr(app.state, "db", None)


def create_database(url: str) -> Database:
    """Build a lazy engine; no connection is opened until the first query."""

    engine = create_async_engine(url, pool_size=5, max_overflow=5, pool_pre_ping=True)
    return Database(engine=engine, sessions=async_sessionmaker(engine, expire_on_commit=False))


async def ping(database: Database) -> bool:
    """Return whether ``SELECT 1`` succeeds within the health timeout."""

    async def _select_one() -> None:
        async with database.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    try:
        await asyncio.wait_for(_select_one(), PING_TIMEOUT_SECONDS)
    except Exception:
        return False
    return True
