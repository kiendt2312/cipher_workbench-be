"""Writes and reads of the ``cipher_operations`` table."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select

from app.db.engine import Database
from app.db.models import CipherOperation
from app.history.cursor import Cursor


@dataclass(frozen=True)
class OperationEntry:
    """Metadata of one cipher request. There is deliberately no field for user content."""

    cipher: str
    source: str
    operation: str | None
    response_mode: str | None
    input_length: int | None
    output_length: int | None
    http_status: int
    succeeded: bool
    duration_ms: int


async def record_operation(database: Database, entry: OperationEntry) -> None:
    async with database.sessions() as session:
        try:
            session.add(CipherOperation(created_at=datetime.now(UTC), **asdict(entry)))
            await session.commit()
        except BaseException:
            with suppress(BaseException):
                await session.rollback()
            with suppress(BaseException):
                await session.invalidate()
            raise


async def list_operations(
    database: Database,
    *,
    limit: int,
    cursor: Cursor | None = None,
    cipher: str | None = None,
    operation: str | None = None,
) -> tuple[list[CipherOperation], Cursor | None]:
    """Return one page, newest first, plus the cursor of the next page if there is one."""

    query = select(CipherOperation).order_by(
        CipherOperation.created_at.desc(), CipherOperation.id.desc()
    )
    if cursor is not None:
        query = query.where(
            or_(
                CipherOperation.created_at < cursor.created_at,
                and_(
                    CipherOperation.created_at == cursor.created_at,
                    CipherOperation.id < cursor.id,
                ),
            )
        )
    if cipher is not None:
        query = query.where(CipherOperation.cipher == cipher)
    if operation is not None:
        query = query.where(CipherOperation.operation == operation)

    async with database.sessions() as session:
        try:
            rows = list((await session.scalars(query.limit(limit + 1))).all())
        except BaseException:
            with suppress(BaseException):
                await session.rollback()
            with suppress(BaseException):
                await session.invalidate()
            raise

    if len(rows) <= limit:
        return rows, None
    page = rows[:limit]
    return page, Cursor(created_at=page[-1].created_at, id=page[-1].id)
