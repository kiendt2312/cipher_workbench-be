"""Liveness endpoint reporting application and database status."""

from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.db.engine import Database, ping

router = APIRouter(prefix="/api", tags=["Health"])

DatabaseStatus = Literal["ok", "unavailable", "disabled"]


class HealthResult(BaseModel):
    app: Literal["ok"]
    database: DatabaseStatus


class HealthResponse(BaseModel):
    success: Literal[True]
    result: HealthResult


async def _database_status(database: Database | None) -> DatabaseStatus:
    if database is None:
        return "disabled"
    return "ok" if await ping(database) else "unavailable"


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "Database unavailable"}},
)
async def health(request: Request) -> JSONResponse:
    status = await _database_status(getattr(request.app.state, "db", None))
    body = HealthResponse(success=True, result=HealthResult(app="ok", database=status))
    return JSONResponse(body.model_dump(), status_code=503 if status == "unavailable" else 200)
