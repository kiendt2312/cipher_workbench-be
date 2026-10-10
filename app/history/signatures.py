"""High-level persistence adapter for completed RSA signature operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.db.engine import Database
from app.history.store import (
    HistoryQuotaExceededError,
    OperationEntry,
    PrivateHistoryPayload,
    record_private_operation,
)


class HistoryCapacityError(RuntimeError):
    """The logical history caps could not admit a record."""


@dataclass(frozen=True)
class SignatureRecord:
    operation: Literal["sign", "verify"]
    mode: Literal["raw-integer", "standard"]
    source: Literal["number", "text", "file"]
    content: bytes | None
    numeric_input: Any
    signature: str
    public_key: Any
    result: Any
    valid: bool | None
    duration_ms: int = 0


async def save_signature_history(database: Database, owner_id: str, record: SignatureRecord) -> int:
    """Persist one completed signature operation and return its history id."""

    entry = OperationEntry(
        cipher="rsa",
        source="file" if record.source == "file" else "text",
        operation=record.operation,
        response_mode="content",
        input_length=(
            len(record.content)
            if record.content is not None
            else len(str(record.numeric_input).encode("utf-8"))
        ),
        output_length=len(record.signature.encode("utf-8")),
        http_status=200,
        succeeded=True,
        duration_ms=record.duration_ms,
    )
    payload = PrivateHistoryPayload(
        content=record.content,
        numeric_input=record.numeric_input,
        signature=record.signature,
        public_key=record.public_key,
        result={"mode": record.mode, **record.result},
        valid=record.valid,
        processing_state="completed",
    )
    try:
        row = await record_private_operation(
            database,
            entry,
            owner_id=owner_id,
            payload=payload,
        )
    except HistoryQuotaExceededError as exc:
        raise HistoryCapacityError from exc
    return row.id
