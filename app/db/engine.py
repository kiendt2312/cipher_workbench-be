"""Async SQLite engine and session factory owned by the application lifespan."""

from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app import config

PING_TIMEOUT_SECONDS = 1.0
BUSY_TIMEOUT_SECONDS = 0.2
BUSY_TIMEOUT_MILLISECONDS = 200


@dataclass(frozen=True)
class Database:
    """The engine plus the session factory built on it."""

    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]


def app_database(app: Any) -> Database | None:
    """Return the database the lifespan attached to ``app``, or ``None`` when disabled."""

    return getattr(app.state, "db", None)


def create_database(url: str) -> Database:
    """Build a lazy SQLite engine; no connection is opened until the first query."""

    path = config.sqlite_database_path(url)
    engine_url = config.sqlite_runtime_url(path)
    engine = create_async_engine(
        engine_url,
        connect_args={
            "autocommit": sqlite3.LEGACY_TRANSACTION_CONTROL,
            "timeout": BUSY_TIMEOUT_SECONDS,
        },
        pool_size=1,
        max_overflow=0,
        pool_timeout=BUSY_TIMEOUT_SECONDS,
        pool_pre_ping=True,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _configure_connection(dbapi_connection: Any, _connection_record: Any) -> None:
        async def configure_async(connection: Any) -> None:
            async def pragma_value(statement: str) -> Any:
                async with connection.execute(statement) as cursor:
                    row = await cursor.fetchone()
                return row[0] if row is not None else None

            await pragma_value(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MILLISECONDS}")
            busy_timeout = await pragma_value("PRAGMA busy_timeout")
            journal_mode = await pragma_value("PRAGMA journal_mode = DELETE")
            await connection.commit()
            await pragma_value("PRAGMA synchronous = FULL")
            synchronous = await pragma_value("PRAGMA synchronous")
            if busy_timeout != BUSY_TIMEOUT_MILLISECONDS:
                raise RuntimeError("SQLite busy timeout could not be configured")
            if str(journal_mode).lower() != "delete":
                raise RuntimeError("SQLite rollback journal could not be configured")
            if synchronous != 2:
                raise RuntimeError("SQLite full synchronous mode could not be configured")
            async with connection.execute("SELECT version_num FROM alembic_version") as cursor:
                revisions = {row[0] async for row in cursor}
            if revisions != {config.SQLITE_SCHEMA_REVISION}:
                raise RuntimeError("SQLite schema is not at the supported revision")
            async with connection.execute(
                "SELECT id, created_at, cipher, operation, source, response_mode, "
                "input_length, output_length, http_status, succeeded, duration_ms "
                "FROM cipher_operations LIMIT 1"
            ) as cursor:
                await cursor.fetchone()

        dbapi_connection.run_async(configure_async)

    return Database(engine=engine, sessions=async_sessionmaker(engine, expire_on_commit=False))


async def ping(database: Database) -> bool:
    """Return whether ``SELECT 1`` succeeds within the health timeout."""

    async def _select_one() -> None:
        async with database.engine.connect() as connection:
            revision = await connection.execute(text("SELECT version_num FROM alembic_version"))
            if {row[0] for row in revision} != {config.SQLITE_SCHEMA_REVISION}:
                raise RuntimeError("SQLite schema is not at the supported revision")
            await connection.execute(
                text(
                    "SELECT id, created_at, cipher, operation, source, response_mode, "
                    "input_length, output_length, http_status, succeeded, duration_ms "
                    "FROM cipher_operations LIMIT 1"
                )
            )

    try:
        await asyncio.wait_for(_select_one(), PING_TIMEOUT_SECONDS)
    except Exception:
        return False
    return True
