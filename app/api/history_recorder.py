"""ASGI middleware that records metadata of each cipher request after it is answered."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.db.engine import Database, app_database
from app.history.routes import match_cipher_route
from app.history.store import OperationEntry, record_operation

logger = logging.getLogger(__name__)

RECORD_TIMEOUT_SECONDS = 0.5
_NOTES_KEY = "history_notes"


def note_history(
    request: Request,
    *,
    operation: str | None = None,
    response_mode: str | None = None,
    input_length: int | None = None,
    output_length: int | None = None,
) -> None:
    """Attach metadata the middleware cannot see; arguments left as ``None`` are kept.

    Callers must pass lengths, never the content itself.
    """

    notes = getattr(request.state, _NOTES_KEY, None)
    if notes is None:
        return
    fields = {
        "operation": operation,
        "response_mode": response_mode,
        "input_length": input_length,
        "output_length": output_length,
    }
    notes.update({name: value for name, value in fields.items() if value is not None})


class OperationHistoryRecorder:
    """Record one ``cipher_operations`` row per cipher request; never alters the response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        content_type = next(
            (
                value.decode("latin-1")
                for name, value in scope.get("headers", [])
                if name.lower() == b"content-type"
            ),
            None,
        )
        route = (
            match_cipher_route(scope["method"], scope["path"], content_type)
            if scope["type"] == "http"
            else None
        )
        database = app_database(scope["app"])
        if route is None or database is None:
            await self.app(scope, receive, send)
            return

        notes: dict[str, Any] = {}
        scope.setdefault("state", {})[_NOTES_KEY] = notes
        status = 500
        started = time.perf_counter()

        async def send_with_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        def entry() -> OperationEntry:
            return OperationEntry(
                cipher=route.cipher,
                source=route.source,
                operation=route.operation or notes.get("operation"),
                response_mode=notes.get("response_mode"),
                input_length=notes.get("input_length"),
                output_length=notes.get("output_length"),
                http_status=status,
                succeeded=200 <= status < 300,
                duration_ms=round((time.perf_counter() - started) * 1000),
            )

        try:
            await self.app(scope, receive, send_with_status)
        except BaseException:
            # ServerErrorMiddleware sends the 500 only after this re-raise, so the
            # write must not hold it back.
            _record_in_background(database, entry())
            raise
        await _record_quietly(database, entry())


_background_records: set[asyncio.Task[None]] = set()


def _record_in_background(database: Database, entry: OperationEntry) -> None:
    task = asyncio.create_task(_record_quietly(database, entry))
    _background_records.add(task)
    task.add_done_callback(_background_records.discard)


async def _record_quietly(database: Database, entry: OperationEntry) -> None:
    try:
        await asyncio.wait_for(record_operation(database, entry), RECORD_TIMEOUT_SECONDS)
    except Exception:
        # The exception text can contain connection details, so it is not logged.
        logger.warning("Could not record cipher operation history")
