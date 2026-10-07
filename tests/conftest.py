"""Shared fixtures: in-memory payloads and an optional migrated PostgreSQL database."""

import asyncio
import os
from pathlib import Path

import pytest
from alembic.config import Config as AlembicConfig
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command as alembic_command
from app import config

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def exact_limit_bytes() -> bytes:
    """Return a five-MiB payload without creating a repository fixture file."""

    return b"A" * config.MAX_FILE_BYTES


@pytest.fixture
def over_limit_bytes() -> bytes:
    """Return the first payload byte beyond the accepted file-size limit."""

    return b"A" * (config.MAX_FILE_BYTES + 1)


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Return a migrated PostgreSQL URL, or skip when ``TEST_DATABASE_URL`` is unset."""

    url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    _run_alembic(url, "upgrade", "head")
    return url


def _run_alembic(url: str, command_name: str, revision: str) -> None:
    alembic_config = AlembicConfig(str(PROJECT_ROOT / "alembic.ini"))
    alembic_config.set_main_option("sqlalchemy.url", url)
    getattr(alembic_command, command_name)(alembic_config, revision)


def run_sql(url: str, statement: str) -> list[tuple]:
    """Execute one SQL statement on a short-lived engine and return its rows."""

    async def execute() -> list[tuple]:
        engine = create_async_engine(url)
        try:
            async with engine.begin() as connection:
                result = await connection.execute(text(statement))
                return [tuple(row) for row in result] if result.returns_rows else []
        finally:
            await engine.dispose()

    return asyncio.run(execute())


@pytest.fixture
def db_url(test_database_url: str) -> str:
    """Return an empty legacy PostgreSQL database for migration/source tests."""

    run_sql(test_database_url, "TRUNCATE cipher_operations RESTART IDENTITY")
    return test_database_url
