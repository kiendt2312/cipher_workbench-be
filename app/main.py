"""Application assembly for the Caesar Cipher service and same-origin UI."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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
from app.errors import messages
from app.errors.handlers import register_exception_handlers
from app.history.retention import purge_periodically


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    retention_days = config.history_retention_days()  # Fail fast on a bad value.
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
# Outermost, so requests rejected by the guards above are recorded too.
app.add_middleware(OperationHistoryRecorder)
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
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "max_file_bytes": config.MAX_FILE_BYTES,
            "ui_messages": {
                "file_type": messages.UNSUPPORTED_FILE_TYPE,
                "file_size": messages.FILE_TOO_LARGE,
                "file_empty": messages.EMPTY_FILE,
                "key_missing": messages.MISSING_KEY,
                "key_invalid": messages.INVALID_KEY,
                "system": messages.UNEXPECTED_FAILURE,
            },
            "cipher_messages": {
                "textEmpty": messages.TEXT_EMPTY,
                "keyMissing": messages.MISSING_KEY,
                "caesarKey": messages.INVALID_KEY,
                "vigenereKey": messages.INVALID_VIGENERE_KEY,
                "playfairKey": messages.INVALID_PLAYFAIR_KEY,
                "playfairText": messages.PLAYFAIR_TEXT_EMPTY,
                "columnarKey": messages.INVALID_COLUMNAR_KEY,
                "affineMissingA": messages.MISSING_AFFINE_MULTIPLIER,
                "affineInvalidA": messages.INVALID_AFFINE_MULTIPLIER,
                "affineNonInvertible": messages.NON_INVERTIBLE_AFFINE_MULTIPLIER,
                "affineMissingB": messages.MISSING_AFFINE_SHIFT,
                "affineInvalidB": messages.INVALID_AFFINE_SHIFT,
            },
        },
    )
