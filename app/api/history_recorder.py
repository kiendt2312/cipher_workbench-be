"""ASGI middleware that records metadata of each cipher request after it is answered."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.db.engine import Database
from app.history.routes import match_cipher_route
from app.history.store import OperationEntry, record_operation

logger = logging.getLogger(__name__)

RECORD_TIMEOUT_SECONDS = 0.5
_NOTES_KEY = "history_notes"


def note_history(request: Request, **fields: Any) -> None:
    """Attach metadata the middleware cannot see: operation, response mode and lengths.

    Only ``operation``, ``response_mode``, ``input_length`` and ``output_length`` are
    stored. Callers must pass lengths, never the content itself.
    """

    notes = getattr(request.state, _NOTES_KEY, None)
    if notes is not None:
        notes.update(fields)


class OperationHistoryRecorder:
    """Record one ``cipher_operations`` row per cipher request; never alters the response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        route = (
            match_cipher_route(scope["method"], scope["path"]) if scope["type"] == "http" else None
        )
        database: Database | None = getattr(scope["app"].state, "db", None)
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

        try:
            await self.app(scope, receive, send_with_status)
        finally:
            entry = OperationEntry(
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
            await _record_quietly(database, entry)


async def _record_quietly(database: Database, entry: OperationEntry) -> None:
    try:
        await asyncio.wait_for(record_operation(database, entry), RECORD_TIMEOUT_SECONDS)
    except Exception:
        # The exception text can contain connection details, so it is not logged.
        logger.warning("Could not record cipher operation history")
