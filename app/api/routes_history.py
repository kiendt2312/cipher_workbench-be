"""Owner-scoped listing, retrieval, download, and deletion of private history."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import Field
from starlette.responses import Response

from app import config
from app.api.history_profile import OWNER_STATE_KEY
from app.api.rsa_schemas import ExactModel
from app.db.engine import app_database
from app.db.models import CIPHERS, PRIVATE_OPERATIONS, PrivateHistoryRecord
from app.errors.exceptions import (
    AppError,
    HistoryDisabledError,
    HistoryUnavailableError,
    InvalidHistoryFilterError,
    InvalidHistoryLimitError,
)
from app.history.cursor import decode_cursor, encode_cursor
from app.history.store import (
    delete_all_operations,
    delete_operation,
    get_operation,
    list_operations,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["History"])

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class HistoryItem(ExactModel):
    id: int
    created_at: datetime = Field(alias="createdAt")
    cipher: str
    operation: str | None
    source: str
    response_mode: str | None = Field(alias="responseMode")
    input_length: int | None = Field(alias="inputLength")
    output_length: int | None = Field(alias="outputLength")
    http_status: int = Field(alias="httpStatus")
    succeeded: bool
    duration_ms: int = Field(alias="durationMs")
    valid: bool | None
    processing_state: str | None = Field(alias="processingState")
    content_available: bool = Field(alias="contentAvailable")
    logical_size: int = Field(alias="logicalSize")


class HistoryDetail(HistoryItem):
    payload: dict[str, Any]


class HistoryPage(ExactModel):
    items: list[HistoryItem]
    next_cursor: str | None = Field(alias="nextCursor")


class HistoryListResponse(ExactModel):
    success: Literal[True]
    result: HistoryPage


class HistoryDetailResponse(ExactModel):
    success: Literal[True]
    result: HistoryDetail


class DeleteResponse(ExactModel):
    success: Literal[True]
    result: dict[str, int | bool]


def _enabled_database(request: Request):
    _require_enabled()
    database = app_database(request.app)
    if database is None:
        raise HistoryUnavailableError()
    return database


def _require_enabled() -> None:
    if not config.history_api_enabled():
        raise HistoryDisabledError()


def _owner(request: Request) -> str:
    owner_id = getattr(request.state, OWNER_STATE_KEY, None)
    if not isinstance(owner_id, str):
        raise HistoryUnavailableError()
    return owner_id


def _parse_limit(raw: str | None) -> int:
    if raw is None:
        return DEFAULT_LIMIT
    limit = config.parse_bounded_int(raw, 1, MAX_LIMIT)
    if limit is None:
        raise InvalidHistoryLimitError()
    return limit


def _parse_choice(raw: str | None, allowed: tuple[str, ...]) -> str | None:
    if raw is not None and raw not in allowed:
        raise InvalidHistoryFilterError()
    return raw


def _item(row: PrivateHistoryRecord) -> HistoryItem:
    return HistoryItem(
        id=row.id,
        createdAt=row.created_at.astimezone(UTC),
        cipher=row.cipher,
        operation=row.operation,
        source=row.source,
        responseMode=row.response_mode,
        inputLength=row.input_length,
        outputLength=row.output_length,
        httpStatus=row.http_status,
        succeeded=row.succeeded,
        durationMs=row.duration_ms,
        valid=row.validity,
        processingState=row.processing_state,
        contentAvailable=row.content_bytes is not None,
        logicalSize=row.logical_size,
    )


def _detail(row: PrivateHistoryRecord) -> HistoryDetail:
    payload = dict(row.payload)
    payload.pop("content", None)
    return HistoryDetail(**_item(row).model_dump(by_alias=True), payload=payload)


def _not_found() -> AppError:
    return AppError(404, "Không tìm thấy bản ghi lịch sử.")


@router.get("/history", response_model=HistoryListResponse, response_model_by_alias=True)
async def list_history(request: Request) -> HistoryListResponse:
    _require_enabled()
    query = request.query_params
    limit = _parse_limit(query.get("limit"))
    raw_cursor = query.get("cursor")
    cursor = decode_cursor(raw_cursor) if raw_cursor is not None else None
    cipher = _parse_choice(query.get("cipher"), CIPHERS)
    operation = _parse_choice(query.get("operation"), PRIVATE_OPERATIONS)
    database = _enabled_database(request)
    try:
        rows, next_cursor = await list_operations(
            database,
            owner_id=_owner(request),
            limit=limit,
            cursor=cursor,
            cipher=cipher,
            operation=operation,
        )
    except Exception as exc:
        logger.warning("Could not read private operation history")
        raise HistoryUnavailableError() from exc
    return HistoryListResponse(
        success=True,
        result=HistoryPage(
            items=[_item(row) for row in rows],
            nextCursor=encode_cursor(next_cursor) if next_cursor else None,
        ),
    )


@router.get(
    "/history/{operation_id}",
    response_model=HistoryDetailResponse,
    response_model_by_alias=True,
)
async def history_detail(request: Request, operation_id: int) -> HistoryDetailResponse:
    database = _enabled_database(request)
    try:
        row = await get_operation(database, owner_id=_owner(request), operation_id=operation_id)
    except Exception as exc:
        logger.warning("Could not read private history detail")
        raise HistoryUnavailableError() from exc
    if row is None:
        raise _not_found()
    return HistoryDetailResponse(success=True, result=_detail(row))


@router.get("/history/{operation_id}/content")
async def history_content(request: Request, operation_id: int) -> Response:
    database = _enabled_database(request)
    try:
        row = await get_operation(database, owner_id=_owner(request), operation_id=operation_id)
    except Exception as exc:
        logger.warning("Could not read private history content")
        raise HistoryUnavailableError() from exc
    if row is None or row.content_bytes is None:
        raise _not_found()
    return Response(
        content=row.content_bytes,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="rsa-history-{row.id}.txt"'},
    )


@router.delete("/history/{operation_id}", response_model=DeleteResponse)
async def delete_history_item(request: Request, operation_id: int) -> DeleteResponse:
    database = _enabled_database(request)
    try:
        deleted = await delete_operation(
            database, owner_id=_owner(request), operation_id=operation_id
        )
    except Exception as exc:
        logger.warning("Could not delete private history item")
        raise HistoryUnavailableError() from exc
    if not deleted:
        raise _not_found()
    return DeleteResponse(success=True, result={"deleted": True})


@router.delete("/history", response_model=DeleteResponse)
async def delete_history(request: Request) -> DeleteResponse:
    database = _enabled_database(request)
    try:
        count = await delete_all_operations(database, owner_id=_owner(request))
    except Exception as exc:
        logger.warning("Could not delete private history")
        raise HistoryUnavailableError() from exc
    return DeleteResponse(success=True, result={"deleted": count})
