"""Read-only listing of recorded cipher operation metadata."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app import config
from app.db.engine import Database
from app.db.models import CIPHERS, OPERATIONS, CipherOperation
from app.errors import messages
from app.errors.exceptions import (
    HistoryDisabledError,
    HistoryUnavailableError,
    InvalidHistoryFilterError,
    InvalidHistoryLimitError,
)
from app.history.cursor import decode_cursor, encode_cursor
from app.history.store import list_operations

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["History"])

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class HistoryItem(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: int
    created_at: datetime
    cipher: str
    operation: str | None
    source: str
    response_mode: str | None
    input_length: int | None
    output_length: int | None
    http_status: int
    succeeded: bool
    duration_ms: int


class HistoryPage(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    items: list[HistoryItem]
    next_cursor: str | None


class HistoryResponse(BaseModel):
    success: Literal[True]
    result: HistoryPage


_ERROR_CONTENT = {
    "type": "object",
    "required": ["success", "message"],
    "properties": {
        "success": {"type": "boolean", "const": False},
        "message": {"type": "string"},
    },
}


def _parse_limit(raw: str | None) -> int:
    if raw is None:
        return DEFAULT_LIMIT
    if not raw.isascii() or not raw.isdigit() or not 1 <= int(raw) <= MAX_LIMIT:
        raise InvalidHistoryLimitError()
    return int(raw)


def _parse_choice(raw: str | None, allowed: tuple[str, ...]) -> str | None:
    if raw is not None and raw not in allowed:
        raise InvalidHistoryFilterError()
    return raw


def _item(row: CipherOperation) -> HistoryItem:
    return HistoryItem(
        id=row.id,
        created_at=row.created_at.astimezone(UTC),
        cipher=row.cipher,
        operation=row.operation,
        source=row.source,
        response_mode=row.response_mode,
        input_length=row.input_length,
        output_length=row.output_length,
        http_status=row.http_status,
        succeeded=row.succeeded,
        duration_ms=row.duration_ms,
    )


@router.get(
    "/history",
    response_model=HistoryResponse,
    response_model_by_alias=True,
    responses={
        404: {
            "description": messages.HISTORY_DISABLED,
            "content": {"application/json": {"schema": _ERROR_CONTENT}},
        },
        422: {
            "description": messages.INVALID_HISTORY_FILTER,
            "content": {"application/json": {"schema": _ERROR_CONTENT}},
        },
        503: {
            "description": messages.HISTORY_UNAVAILABLE,
            "content": {"application/json": {"schema": _ERROR_CONTENT}},
        },
    },
)
async def list_history(request: Request) -> HistoryResponse:
    if not config.history_api_enabled():
        raise HistoryDisabledError()
    query = request.query_params
    limit = _parse_limit(query.get("limit"))
    raw_cursor = query.get("cursor")
    cursor = decode_cursor(raw_cursor) if raw_cursor is not None else None
    cipher = _parse_choice(query.get("cipher"), CIPHERS)
    operation = _parse_choice(query.get("operation"), OPERATIONS)

    database: Database | None = getattr(request.app.state, "db", None)
    if database is None:
        raise HistoryUnavailableError()
    try:
        rows, next_cursor = await list_operations(
            database, limit=limit, cursor=cursor, cipher=cipher, operation=operation
        )
    except Exception as exc:
        logger.warning("Could not read cipher operation history")
        raise HistoryUnavailableError() from exc

    return HistoryResponse(
        success=True,
        result=HistoryPage(
            items=[_item(row) for row in rows],
            next_cursor=encode_cursor(next_cursor) if next_cursor else None,
        ),
    )
