"""History storage primitives.

The original ``cipher_operations`` API remains metadata-only and keeps its
existing behavior when no ``owner_id`` is supplied. Owner-scoped writes use a
separate Alembic-managed table so legacy metadata rows remain compatible while
private history gets its own ownership, payload, retention, and quota rules.
"""

from __future__ import annotations

import base64
import json
import math
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, func, or_, select, text

from app import config
from app.db.engine import Database
from app.db.models import (
    CIPHERS,
    DH_OPERATIONS,
    PRIVATE_OPERATIONS,
    RSA_OPERATIONS,
    CipherOperation,
    PrivateHistoryRecord,
)
from app.history.cursor import Cursor

_DATETIME_TYPE = datetime
PRIVATE_HISTORY_TTL = timedelta(seconds=getattr(config, "HISTORY_RETENTION_SECONDS", 5 * 60 * 60))
PRIVATE_HISTORY_TTL_SECONDS = int(PRIVATE_HISTORY_TTL.total_seconds())
PROFILE_HISTORY_QUOTA_BYTES = getattr(config, "HISTORY_PROFILE_LIMIT_BYTES", 50 * 1024 * 1024)
GLOBAL_HISTORY_QUOTA_BYTES = getattr(config, "HISTORY_SYSTEM_LIMIT_BYTES", 500 * 1024 * 1024)

# Compatibility aliases for callers that use the shorter quota vocabulary.
PROFILE_QUOTA_BYTES = PROFILE_HISTORY_QUOTA_BYTES
GLOBAL_QUOTA_BYTES = GLOBAL_HISTORY_QUOTA_BYTES

_MAX_OWNER_ID_BYTES = 512
_MAX_PROCESSING_STATE_BYTES = 64
_PRIVATE_KEY_TEXT_MARKERS = (
    "-----begin private key-----",
    "-----begin rsa private key-----",
    "-----begin openssh private key-----",
)
_FORBIDDEN_PAYLOAD_KEYS = {
    "d",
    "p",
    "q",
    "private",
    "privatekey",
    "privatepem",
    "privatekeypem",
    "passphrase",
    "password",
    "secret",
    "trace",
    "traces",
    "step",
    "steps",
    "warning",
    "warnings",
    "key",
}
_PAYLOAD_ALIASES = {
    "content": "content",
    "contentbytes": "content",
    "originalcontent": "content",
    "originalcontentbytes": "content",
    "numericinput": "numeric_input",
    "number": "numeric_input",
    "input": "numeric_input",
    "signature": "signature",
    "publickey": "public_key",
    "result": "result",
    "valid": "valid",
    "validity": "valid",
    "isvalid": "valid",
    "processingstate": "processing_state",
    "state": "processing_state",
}


class PrivateHistoryError(RuntimeError):
    """Base class for owner-scoped history failures."""


class HistoryQuotaExceededError(PrivateHistoryError):
    """The candidate row cannot fit in either logical history quota."""


@dataclass(frozen=True)
class OperationEntry:
    """Metadata of one cipher request.

    Keep this public shape stable: the request recorder intentionally knows
    nothing about ownership or private RSA payloads.
    """

    cipher: str
    source: str
    operation: str | None
    response_mode: str | None
    input_length: int | None
    output_length: int | None
    http_status: int
    succeeded: bool
    duration_ms: int


@dataclass(frozen=True, slots=True)
class PrivateHistoryPayload:
    """Allow-listed payload accepted for an RSA sign/verify history row.

    A mapping with the same field names is also accepted by the write API for
    easy integration with request adapters. ``content`` and ``signature``
    preserve bytes exactly; strings are preserved as UTF-8 text.
    """

    content: bytes | str | None = None
    numeric_input: Any = None
    signature: bytes | str | None = None
    public_key: Any = None
    result: Any = None
    valid: bool | None = None
    processing_state: str | None = None


HistoryPayload = PrivateHistoryPayload
PrivateOperationEntry = OperationEntry


@dataclass(frozen=True, slots=True)
class _StoredPayload:
    content_bytes: bytes | None
    content_kind: str | None
    numeric_input_json: str | None
    signature_json: str | None
    public_key_json: str | None
    result_json: str | None
    validity: bool | None
    processing_state: str | None
    logical_payload: dict[str, Any]


def _key_token(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _reject_forbidden_key(key: str) -> None:
    if _key_token(key) in _FORBIDDEN_PAYLOAD_KEYS or "private" in _key_token(key):
        raise ValueError("private history payload contains a forbidden field")


def _json_value(value: Any) -> Any:
    """Convert an allow-listed value to deterministic JSON-compatible data."""

    if isinstance(value, bytes):
        return {
            "__history_type__": "bytes",
            "value": base64.b64encode(value).decode("ascii"),
        }
    if isinstance(value, bytearray | memoryview):
        return _json_value(bytes(value))
    if value is None or isinstance(value, str | int | bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("private history payload contains a non-finite number")
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, nested in value.items():
            if not isinstance(key, str):
                raise ValueError("private history payload keys must be strings")
            _reject_forbidden_key(key)
            result[key] = _json_value(nested)
        return result
    if isinstance(value, list | tuple):
        return [_json_value(nested) for nested in value]
    raise ValueError("private history payload contains an unsupported value")


def _reject_private_key_text(value: Any) -> None:
    """Reject private-key PEM material even when hidden under an allowed field."""

    if isinstance(value, str) and any(
        marker in value.casefold() for marker in _PRIVATE_KEY_TEXT_MARKERS
    ):
        raise ValueError("private history payload contains private key material")
    if isinstance(value, Mapping):
        for nested in value.values():
            _reject_private_key_text(nested)
    elif isinstance(value, list | tuple):
        for nested in value:
            _reject_private_key_text(nested)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _json_value(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _validate_owner_id(owner_id: str) -> str:
    if type(owner_id) is not str or not owner_id:
        raise ValueError("owner_id must be a non-empty string")
    if len(owner_id.encode("utf-8")) > _MAX_OWNER_ID_BYTES:
        raise ValueError("owner_id is too long")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in owner_id):
        raise ValueError("owner_id contains a control character")
    return owner_id


def _validate_created_at(created_at: datetime) -> datetime:
    if (
        not isinstance(created_at, _DATETIME_TYPE)
        or created_at.tzinfo is None
        or created_at.utcoffset() is None
    ):
        raise ValueError("created_at must be timezone-aware")
    return created_at.astimezone(UTC)


def _validate_entry(entry: OperationEntry, *, private: bool = False) -> None:
    if entry.cipher not in CIPHERS:
        raise ValueError("cipher is not supported")
    allowed_operations = PRIVATE_OPERATIONS if private else (*DH_OPERATIONS, "encrypt", "decrypt")
    if entry.operation is not None and entry.operation not in allowed_operations:
        raise ValueError("operation is not supported")
    if entry.operation in DH_OPERATIONS and entry.cipher != "dh":
        raise ValueError("Diffie-Hellman history operations require DH")
    if entry.operation in RSA_OPERATIONS and entry.cipher != "rsa":
        raise ValueError("sign and verify history operations require RSA")
    if entry.source not in ("text", "file"):
        raise ValueError("source is not supported")
    if entry.response_mode not in (None, "content", "file"):
        raise ValueError("response_mode is not supported")
    for name, value in (
        ("input_length", entry.input_length),
        ("output_length", entry.output_length),
        ("duration_ms", entry.duration_ms),
    ):
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError(f"{name} must be a non-negative integer")
    if type(entry.http_status) is not int:
        raise ValueError("http_status must be an integer")
    if type(entry.succeeded) is not bool:
        raise ValueError("succeeded must be a boolean")


def _payload_mapping(payload: PrivateHistoryPayload | Mapping[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, PrivateHistoryPayload):
        return {name: value for name, value in asdict(payload).items() if value is not None}
    if not isinstance(payload, Mapping):
        raise TypeError("payload must be a mapping or PrivateHistoryPayload")
    normalized: dict[str, Any] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            raise ValueError("private history payload keys must be strings")
        canonical = _PAYLOAD_ALIASES.get(_key_token(key))
        if canonical is None:
            _reject_forbidden_key(key)
            raise ValueError("private history payload contains an unsupported field")
        if canonical in normalized:
            raise ValueError("private history payload contains duplicate aliases")
        normalized[canonical] = value
    return normalized


def _normalize_payload(
    cipher: str, payload: PrivateHistoryPayload | Mapping[str, Any] | None
) -> _StoredPayload:
    values = _payload_mapping(payload)
    if cipher != "rsa" and values:
        raise ValueError("only RSA history records may contain a payload")
    if not values:
        return _StoredPayload(None, None, None, None, None, None, None, None, {})

    content = values.get("content")
    if content is not None and not isinstance(content, (bytes, str, bytearray, memoryview)):
        raise ValueError("content must be bytes or text")
    if content is None:
        content_bytes = None
    elif isinstance(content, str):
        content_bytes = content.encode("utf-8")
    else:
        content_bytes = bytes(content)
    content_kind = None if content is None else "text" if isinstance(content, str) else "bytes"

    numeric_input = values.get("numeric_input")
    if numeric_input is not None:
        if isinstance(numeric_input, bool):
            raise ValueError("numeric_input must not be boolean")
        if not isinstance(numeric_input, (int, str, Mapping, list, tuple)):
            raise ValueError("numeric_input must be numeric JSON data")
        _json_value(numeric_input)

    signature = values.get("signature")
    if signature is not None and not isinstance(signature, (bytes, str, bytearray, memoryview)):
        raise ValueError("signature must be bytes or text")
    valid = values.get("valid")
    if valid is not None and type(valid) is not bool:
        raise ValueError("valid must be a boolean")
    processing_state = values.get("processing_state")
    if processing_state is not None:
        if type(processing_state) is not str or not processing_state:
            raise ValueError("processing_state must be a non-empty string")
        if len(processing_state.encode("utf-8")) > _MAX_PROCESSING_STATE_BYTES:
            raise ValueError("processing_state is too long")

    # Validate nested public key/result data before anything is written. The
    # same recursive guard rejects d/private PEM/passphrases/traces anywhere.
    public_key = values.get("public_key")
    result = values.get("result")
    if public_key is not None:
        _reject_private_key_text(public_key)
        _json_value(public_key)
    if result is not None:
        _reject_private_key_text(result)
        _json_value(result)

    logical_payload: dict[str, Any] = {}
    if content is not None:
        logical_payload["content"] = content
    if numeric_input is not None:
        logical_payload["numeric_input"] = numeric_input
    if signature is not None:
        logical_payload["signature"] = signature
    if public_key is not None:
        logical_payload["public_key"] = public_key
    if result is not None:
        logical_payload["result"] = result
    if valid is not None:
        logical_payload["valid"] = valid
    if processing_state is not None:
        logical_payload["processing_state"] = processing_state

    return _StoredPayload(
        content_bytes=content_bytes,
        content_kind=content_kind,
        numeric_input_json=None if numeric_input is None else _canonical_json(numeric_input),
        signature_json=None if signature is None else _canonical_json(signature),
        public_key_json=None if public_key is None else _canonical_json(public_key),
        result_json=None if result is None else _canonical_json(result),
        validity=valid,
        processing_state=processing_state,
        logical_payload=logical_payload,
    )


def logical_history_bytes(
    *, owner_id: str, created_at: datetime, entry: OperationEntry, payload: Mapping[str, Any]
) -> int:
    """Return the exact logical byte accounting used by both quota checks.

    The accounted representation is a canonical UTF-8 JSON envelope containing
    the owner, normalized original timestamp, all metadata values (including
    explicit ``null`` values), and the allow-listed payload. Database identity,
    indexes, page overhead, and free-space/VACUUM effects are deliberately not
    counted. A byte value is represented by a deterministic base64 marker in
    this logical envelope, while retrieval still returns the original bytes.
    """

    normalized_created_at = _validate_created_at(created_at)
    envelope = {
        "owner_id": owner_id,
        "created_at": normalized_created_at.isoformat(),
        "cipher": entry.cipher,
        "operation": entry.operation,
        "source": entry.source,
        "response_mode": entry.response_mode,
        "input_length": entry.input_length,
        "output_length": entry.output_length,
        "http_status": entry.http_status,
        "succeeded": entry.succeeded,
        "duration_ms": entry.duration_ms,
        "payload": payload,
    }
    return len(_canonical_json(envelope).encode("utf-8"))


def _expiry_cutoff(now: datetime) -> datetime:
    return _validate_created_at(now) - PRIVATE_HISTORY_TTL


async def _begin_serialized_transaction(session: Any) -> None:
    """Serialize quota reads and evictions on the supported database backends."""

    dialect = session.get_bind().dialect.name
    if dialect == "sqlite":
        # SQLite's RESERVED writer lock makes the sum/evict/insert sequence one
        # writer at a time, including when multiple Database objects share a file.
        await session.execute(text("BEGIN IMMEDIATE"))
    else:
        # PostgreSQL's serializable transaction retries are the caller's
        # responsibility; no partial write is committed on a serialization error.
        await session.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))


async def _rollback_and_invalidate(session: Any) -> None:
    with suppress(BaseException):
        await session.rollback()
    with suppress(BaseException):
        await session.invalidate()


async def _sum_bytes(session: Any, *, owner_id: str | None = None) -> int:
    query = select(func.coalesce(func.sum(PrivateHistoryRecord.logical_size), 0))
    if owner_id is not None:
        query = query.where(PrivateHistoryRecord.owner_id == owner_id)
    value = (await session.execute(query)).scalar_one()
    return int(value)


async def _evict_oldest(session: Any, *, owner_id: str | None = None, required_bytes: int) -> None:
    query = select(PrivateHistoryRecord).order_by(
        PrivateHistoryRecord.created_at.asc(), PrivateHistoryRecord.id.asc()
    )
    if owner_id is not None:
        query = query.where(PrivateHistoryRecord.owner_id == owner_id)
    query = query.with_for_update()
    current = await _sum_bytes(session, owner_id=owner_id)
    if current <= required_bytes:
        return
    rows = list((await session.scalars(query)).all())
    for row in rows:
        await session.delete(row)
        current -= row.logical_size
        if current <= required_bytes:
            break


async def record_operation(
    database: Database,
    entry: OperationEntry,
    *,
    owner_id: str | None = None,
    payload: PrivateHistoryPayload | Mapping[str, Any] | None = None,
    created_at: datetime | None = None,
) -> PrivateHistoryRecord | None:
    """Record metadata, or an owner-scoped private row when ``owner_id`` is set.

    The ownerless call is the unchanged legacy metadata path. The private path
    raises write/validation/quota errors to its caller; it never degrades to a
    silently unsaved result.
    """

    _validate_entry(entry, private=owner_id is not None)

    if owner_id is None and payload is None:
        timestamp = _validate_created_at(created_at or datetime.now(UTC))
        async with database.sessions() as session:
            try:
                session.add(CipherOperation(created_at=timestamp, **asdict(entry)))
                await session.commit()
            except BaseException:
                await _rollback_and_invalidate(session)
                raise
        return None

    if owner_id is None:
        raise ValueError("owner_id is required for private history")
    _validate_owner_id(owner_id)
    timestamp = _validate_created_at(created_at or datetime.now(UTC))
    stored_payload = _normalize_payload(entry.cipher, payload)
    logical_size = logical_history_bytes(
        owner_id=owner_id,
        created_at=timestamp,
        entry=entry,
        payload=stored_payload.logical_payload,
    )
    if logical_size > PROFILE_HISTORY_QUOTA_BYTES or logical_size > GLOBAL_HISTORY_QUOTA_BYTES:
        raise HistoryQuotaExceededError("history row exceeds the configured logical quota")

    async with database.sessions() as session:
        try:
            await _begin_serialized_transaction(session)
            # A caller may provide an historical ``created_at`` for imports or
            # deterministic tests. Expiry is still measured from the current
            # read/write time, never from a newly supplied historical timestamp.
            cutoff = _expiry_cutoff(datetime.now(UTC))
            await session.execute(
                delete(PrivateHistoryRecord).where(PrivateHistoryRecord.created_at <= cutoff)
            )

            await _evict_oldest(
                session,
                owner_id=owner_id,
                required_bytes=PROFILE_HISTORY_QUOTA_BYTES - logical_size,
            )
            profile_total = await _sum_bytes(session, owner_id=owner_id)
            if profile_total + logical_size > PROFILE_HISTORY_QUOTA_BYTES:
                raise HistoryQuotaExceededError("profile history quota cannot be satisfied")

            await _evict_oldest(
                session,
                required_bytes=GLOBAL_HISTORY_QUOTA_BYTES - logical_size,
            )
            global_total = await _sum_bytes(session)
            if global_total + logical_size > GLOBAL_HISTORY_QUOTA_BYTES:
                raise HistoryQuotaExceededError("global history quota cannot be satisfied")

            row = PrivateHistoryRecord(
                owner_id=owner_id,
                created_at=timestamp,
                cipher=entry.cipher,
                source=entry.source,
                operation=entry.operation,
                response_mode=entry.response_mode,
                input_length=entry.input_length,
                output_length=entry.output_length,
                http_status=entry.http_status,
                succeeded=entry.succeeded,
                duration_ms=entry.duration_ms,
                content_bytes=stored_payload.content_bytes,
                content_kind=stored_payload.content_kind,
                numeric_input_json=stored_payload.numeric_input_json,
                signature_json=stored_payload.signature_json,
                public_key_json=stored_payload.public_key_json,
                result_json=stored_payload.result_json,
                validity=stored_payload.validity,
                processing_state=stored_payload.processing_state,
                logical_size=logical_size,
            )
            session.add(row)
            await session.flush()
            await session.commit()
            return row
        except BaseException:
            await _rollback_and_invalidate(session)
            raise


async def record_private_operation(
    database: Database,
    entry: OperationEntry,
    *,
    owner_id: str,
    payload: PrivateHistoryPayload | Mapping[str, Any] | None = None,
    created_at: datetime | None = None,
) -> PrivateHistoryRecord:
    row = await record_operation(
        database,
        entry,
        owner_id=owner_id,
        payload=payload,
        created_at=created_at,
    )
    assert row is not None
    return row


record_private_history = record_private_operation


async def purge_private_expired(database: Database, *, now: datetime | None = None) -> int:
    """Delete owner-scoped rows at the five-hour boundary, using original timestamps."""

    cutoff = _expiry_cutoff(now or datetime.now(UTC))
    async with database.sessions() as session:
        try:
            result = await session.execute(
                delete(PrivateHistoryRecord).where(PrivateHistoryRecord.created_at <= cutoff)
            )
            await session.commit()
            return result.rowcount or 0
        except BaseException:
            await _rollback_and_invalidate(session)
            raise


async def list_operations(
    database: Database,
    *,
    limit: int,
    cursor: Cursor | None = None,
    cipher: str | None = None,
    operation: str | None = None,
    owner_id: str | None = None,
    now: datetime | None = None,
) -> tuple[list[CipherOperation] | list[PrivateHistoryRecord], Cursor | None]:
    """List legacy metadata or owner-scoped private records, newest first."""

    if owner_id is not None:
        return await list_private_operations(
            database,
            owner_id=owner_id,
            limit=limit,
            cursor=cursor,
            cipher=cipher,
            operation=operation,
            now=now,
        )

    cutoff = _expiry_cutoff(now or datetime.now(UTC))
    query = (
        select(CipherOperation)
        .where(CipherOperation.created_at > cutoff)
        .order_by(CipherOperation.created_at.desc(), CipherOperation.id.desc())
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
            await _rollback_and_invalidate(session)
            raise

    if len(rows) <= limit:
        return rows, None
    page = rows[:limit]
    return page, Cursor(created_at=page[-1].created_at, id=page[-1].id)


async def list_private_operations(
    database: Database,
    *,
    owner_id: str,
    limit: int,
    cursor: Cursor | None = None,
    cipher: str | None = None,
    operation: str | None = None,
    now: datetime | None = None,
) -> tuple[list[PrivateHistoryRecord], Cursor | None]:
    """List only non-expired rows owned by ``owner_id``."""

    _validate_owner_id(owner_id)
    if type(limit) is not int or limit < 1:
        raise ValueError("limit must be a positive integer")
    cutoff = _expiry_cutoff(now or datetime.now(UTC))
    async with database.sessions() as session:
        try:
            query = select(PrivateHistoryRecord).where(
                PrivateHistoryRecord.owner_id == owner_id,
                PrivateHistoryRecord.created_at > cutoff,
            )
            if cursor is not None:
                query = query.where(
                    or_(
                        PrivateHistoryRecord.created_at < cursor.created_at,
                        and_(
                            PrivateHistoryRecord.created_at == cursor.created_at,
                            PrivateHistoryRecord.id < cursor.id,
                        ),
                    )
                )
            if cipher is not None:
                query = query.where(PrivateHistoryRecord.cipher == cipher)
            if operation is not None:
                query = query.where(PrivateHistoryRecord.operation == operation)
            query = query.order_by(
                PrivateHistoryRecord.created_at.desc(), PrivateHistoryRecord.id.desc()
            )
            rows = list((await session.scalars(query.limit(limit + 1))).all())
        except BaseException:
            await _rollback_and_invalidate(session)
            raise
    if len(rows) <= limit:
        return rows, None
    page = rows[:limit]
    return page, Cursor(created_at=page[-1].created_at, id=page[-1].id)


list_private_history = list_private_operations


async def get_operation(
    database: Database,
    *,
    owner_id: str,
    operation_id: int,
    now: datetime | None = None,
) -> PrivateHistoryRecord | None:
    """Return one non-expired row only when it belongs to ``owner_id``."""

    _validate_owner_id(owner_id)
    cutoff = _expiry_cutoff(now or datetime.now(UTC))
    async with database.sessions() as session:
        try:
            row = (
                await session.scalars(
                    select(PrivateHistoryRecord).where(
                        PrivateHistoryRecord.id == operation_id,
                        PrivateHistoryRecord.owner_id == owner_id,
                        PrivateHistoryRecord.created_at > cutoff,
                    )
                )
            ).first()
            return row
        except BaseException:
            await _rollback_and_invalidate(session)
            raise


get_private_operation = get_operation


async def get_operation_payload(
    database: Database,
    *,
    owner_id: str,
    operation_id: int,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    row = await get_operation(database, owner_id=owner_id, operation_id=operation_id, now=now)
    return None if row is None else row.payload


get_private_operation_payload = get_operation_payload


async def delete_operation(
    database: Database,
    *,
    owner_id: str,
    operation_id: int,
    now: datetime | None = None,
) -> bool:
    """Delete one owned row; another owner's row is indistinguishable from absent."""

    _validate_owner_id(owner_id)
    cutoff = _expiry_cutoff(now or datetime.now(UTC))
    async with database.sessions() as session:
        try:
            result = await session.execute(
                delete(PrivateHistoryRecord).where(
                    PrivateHistoryRecord.id == operation_id,
                    PrivateHistoryRecord.owner_id == owner_id,
                    PrivateHistoryRecord.created_at > cutoff,
                )
            )
            await session.commit()
            return bool(result.rowcount)
        except BaseException:
            await _rollback_and_invalidate(session)
            raise


delete_private_operation = delete_operation


async def delete_all_operations(
    database: Database, *, owner_id: str, now: datetime | None = None
) -> int:
    """Delete all rows for one owner and return the number removed."""

    _validate_owner_id(owner_id)
    del now
    async with database.sessions() as session:
        try:
            result = await session.execute(
                delete(PrivateHistoryRecord).where(PrivateHistoryRecord.owner_id == owner_id)
            )
            await session.commit()
            return result.rowcount or 0
        except BaseException:
            await _rollback_and_invalidate(session)
            raise


delete_all_private_operations = delete_all_operations


async def owner_exists(database: Database, owner_id: str, *, now: datetime | None = None) -> bool:
    """Return whether an owner has at least one non-expired private row."""

    _validate_owner_id(owner_id)
    cutoff = _expiry_cutoff(now or datetime.now(UTC))
    async with database.sessions() as session:
        try:
            result = await session.execute(
                select(PrivateHistoryRecord.id)
                .where(
                    PrivateHistoryRecord.owner_id == owner_id,
                    PrivateHistoryRecord.created_at > cutoff,
                )
                .limit(1)
            )
            found = result.first() is not None
            return found
        except BaseException:
            await _rollback_and_invalidate(session)
            raise
