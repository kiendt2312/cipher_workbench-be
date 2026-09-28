"""Opaque keyset-pagination cursor for the history listing."""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime

from app.errors.exceptions import InvalidHistoryCursorError


@dataclass(frozen=True)
class Cursor:
    """Position just after the last returned row: ``(created_at, id)``."""

    created_at: datetime
    id: int


def encode_cursor(cursor: Cursor) -> str:
    payload = json.dumps(
        {"t": cursor.created_at.isoformat(), "i": cursor.id}, separators=(",", ":")
    )
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def decode_cursor(value: str) -> Cursor:
    """Decode a cursor produced by :func:`encode_cursor`; anything else is rejected."""

    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        created_at = datetime.fromisoformat(payload["t"])
        row_id = payload["i"]
    except (UnicodeEncodeError, binascii.Error, ValueError, TypeError, KeyError) as exc:
        raise InvalidHistoryCursorError() from exc

    if created_at.tzinfo is None or type(row_id) is not int or row_id < 1:
        raise InvalidHistoryCursorError()
    return Cursor(created_at=created_at, id=row_id)
