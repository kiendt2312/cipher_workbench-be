"""Application assembly for the cipher API service."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.api.history_recorder import OperationHistoryRecorder
from app.api.request_size_guard import MultipartCompletionGuard, RequestSizeGuard
from app.api.routes_additional_file import playfair_file_router, vigenere_file_router
from app.api.routes_additional_text import playfair_router, vigenere_router
from app.api.routes_affine_file import router as affine_file_router
from app.api.routes_affine_text import router as affine_text_router
from app.api.routes_columnar_file import router as columnar_file_router
from app.api.routes_columnar_text import router as columnar_text_router
from app.api.routes_file import router as file_router
from app.api.routes_health import router as health_router
from app.api.routes_history import router as history_router
from app.api.routes_text import router as text_router
from app.db.engine import create_database
from app.errors.handlers import register_exception_handlers
from app.history.retention import purge_periodically

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    retention_days = config.history_retention_days()  # Fail fast on a bad value.
    if config.history_api_enabled():
        logger.warning(
            "HISTORY_API_ENABLED is on: GET /api/history is readable by anyone without "
            "authentication. Turn it off on any shared or public deployment."
        )
    url = config.database_url()
    app.state.db = create_database(url) if url else None
    purge_task = (
        asyncio.create_task(purge_periodically(app.state.db, retention_days))
        if app.state.db is not None
        else None
    )
    try:
        yield
    finally:
        if purge_task is not None:
            purge_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await purge_task
        if app.state.db is not None:
            await app.state.db.engine.dispose()


app = FastAPI(lifespan=lifespan)
app.add_middleware(RequestSizeGuard, max_bytes=config.MAX_REQUEST_BYTES)
app.add_middleware(MultipartCompletionGuard)
# Outside the guards, so requests rejected by them are recorded too.
app.add_middleware(OperationHistoryRecorder)
cors_origins = config.cors_allow_origins()
if cors_origins:
    # Outermost, so guard rejections such as 413 still carry CORS headers.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        expose_headers=["Content-Disposition"],
    )
register_exception_handlers(app)
app.include_router(health_router)
app.include_router(history_router)
app.include_router(text_router)
app.include_router(file_router)
app.include_router(vigenere_router)
app.include_router(playfair_router)
app.include_router(affine_text_router)
app.include_router(affine_file_router)
app.include_router(columnar_text_router)
app.include_router(columnar_file_router)
app.include_router(vigenere_file_router)
app.include_router(playfair_file_router)
