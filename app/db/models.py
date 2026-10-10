"""Tables owned by the application; the schema itself is managed by Alembic."""

from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Index,
    Integer,
    LargeBinary,
    Text,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db.types import Boolean01, EpochMicrosecondUTC

CIPHERS = ("caesar", "vigenere", "playfair", "affine", "columnar", "hill", "des", "rsa", "dh")
OPERATIONS = ("encrypt", "decrypt")
SOURCES = ("text", "file")
RESPONSE_MODES = ("content", "file")
PRIVATE_OPERATIONS = (*OPERATIONS, "sign", "verify")


class PrivateHistoryTimestamp(EpochMicrosecondUTC):
    """Portable 64-bit epoch-microsecond storage for private history.

    The legacy table predates long-lived timestamps and keeps its existing
    ``Integer`` type for SQLite compatibility.  Private rows need the same
    epoch-microsecond semantics on PostgreSQL, where a 32-bit integer cannot
    represent current dates, so this table uses a 64-bit integer explicitly.
    """

    impl = BigInteger
    cache_ok = True


def _one_of(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


class Base(DeclarativeBase):
    pass


class CipherOperation(Base):
    """Metadata of one cipher request; never holds user text, keys or file names."""

    __tablename__ = "cipher_operations"
    __table_args__ = (
        CheckConstraint(_one_of("cipher", CIPHERS), name="ck_cipher_operations_cipher"),
        CheckConstraint(_one_of("operation", OPERATIONS), name="ck_cipher_operations_operation"),
        CheckConstraint(_one_of("source", SOURCES), name="ck_cipher_operations_source"),
        CheckConstraint(
            _one_of("response_mode", RESPONSE_MODES), name="ck_cipher_operations_response_mode"
        ),
        CheckConstraint("input_length >= 0", name="ck_cipher_operations_input_length"),
        CheckConstraint("output_length >= 0", name="ck_cipher_operations_output_length"),
        CheckConstraint("succeeded IN (0, 1)", name="ck_cipher_operations_succeeded"),
        CheckConstraint("duration_ms >= 0", name="ck_cipher_operations_duration_ms"),
        CheckConstraint("id > 0", name="ck_cipher_operations_id_positive"),
        Index(
            "ix_cipher_operations_created_at_id",
            text("created_at DESC"),
            text("id DESC"),
        ),
        Index(
            "ix_cipher_operations_cipher_created_at",
            "cipher",
            text("created_at DESC"),
            text("id DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(EpochMicrosecondUTC(), nullable=False)
    cipher: Mapped[str] = mapped_column(Text, nullable=False)
    operation: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    response_mode: Mapped[str | None] = mapped_column(Text)
    input_length: Mapped[int | None] = mapped_column(Integer)
    output_length: Mapped[int | None] = mapped_column(Integer)
    http_status: Mapped[int] = mapped_column(Integer, nullable=False)
    succeeded: Mapped[bool] = mapped_column(Boolean01(), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)


def _decode_private_value(raw: str | None) -> Any:
    if raw is None:
        return None
    value = json.loads(raw)
    if isinstance(value, dict) and value.get("__history_type__") == "bytes":
        return base64.b64decode(value["value"].encode("ascii"), validate=True)
    if isinstance(value, dict) and value.get("__history_type__") == "numeric":
        return value["value"]
    return value


class PrivateHistoryRecord(Base):
    """Owner-scoped history with an optional, allow-listed RSA payload.

    This table is intentionally separate from ``cipher_operations``.  Existing
    metadata rows therefore remain readable by the legacy API while never
    becoming visible through owner-scoped history.  ``logical_size`` is the
    deterministic UTF-8 size of the canonical history envelope calculated by
    :mod:`app.history.store`; it is not a claim about SQLite/PostgreSQL disk
    allocation.
    """

    __tablename__ = "private_history_records"
    __table_args__ = (
        CheckConstraint(_one_of("cipher", CIPHERS), name="ck_private_history_cipher"),
        CheckConstraint(
            _one_of("operation", PRIVATE_OPERATIONS), name="ck_private_history_operation"
        ),
        CheckConstraint(
            "operation IS NULL OR operation IN ('encrypt', 'decrypt') "
            "OR (cipher = 'rsa' AND operation IN ('sign', 'verify'))",
            name="ck_private_history_rsa_operation",
        ),
        CheckConstraint(_one_of("source", SOURCES), name="ck_private_history_source"),
        CheckConstraint(
            _one_of("response_mode", RESPONSE_MODES),
            name="ck_private_history_response_mode",
        ),
        CheckConstraint(
            "owner_id IS NULL OR length(owner_id) > 0",
            name="ck_private_history_owner_nonempty",
        ),
        CheckConstraint(
            "input_length IS NULL OR input_length >= 0",
            name="ck_private_history_input_length",
        ),
        CheckConstraint(
            "output_length IS NULL OR output_length >= 0",
            name="ck_private_history_output_length",
        ),
        CheckConstraint("succeeded IN (0, 1)", name="ck_private_history_succeeded"),
        CheckConstraint("duration_ms >= 0", name="ck_private_history_duration_ms"),
        CheckConstraint("logical_size >= 0", name="ck_private_history_logical_size"),
        CheckConstraint(
            "validity IS NULL OR validity IN (0, 1)",
            name="ck_private_history_validity",
        ),
        Index(
            "ix_private_history_owner_created_at_id",
            "owner_id",
            text("created_at DESC"),
            text("id DESC"),
        ),
        Index(
            "ix_private_history_created_at_id",
            text("created_at ASC"),
            text("id ASC"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # NULL is reserved for rows imported from a legacy/private pre-owner schema.
    owner_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(PrivateHistoryTimestamp(), nullable=False)
    cipher: Mapped[str] = mapped_column(Text, nullable=False)
    operation: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    response_mode: Mapped[str | None] = mapped_column(Text)
    input_length: Mapped[int | None] = mapped_column(Integer)
    output_length: Mapped[int | None] = mapped_column(Integer)
    http_status: Mapped[int] = mapped_column(Integer, nullable=False)
    succeeded: Mapped[bool] = mapped_column(Boolean01(), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    # These columns are deliberately the complete private payload allow-list.
    # There is no private exponent, private PEM, passphrase, trace, or error
    # column.  JSON fields contain only validated, canonical JSON values.
    content_bytes: Mapped[bytes | None] = mapped_column(LargeBinary)
    content_kind: Mapped[str | None] = mapped_column(Text)
    numeric_input_json: Mapped[str | None] = mapped_column(Text)
    signature_json: Mapped[str | None] = mapped_column(Text)
    public_key_json: Mapped[str | None] = mapped_column(Text)
    result_json: Mapped[str | None] = mapped_column(Text)
    validity: Mapped[bool | None] = mapped_column(Boolean01())
    processing_state: Mapped[str | None] = mapped_column(Text)
    logical_size: Mapped[int] = mapped_column(BigInteger, nullable=False)

    @property
    def payload(self) -> dict[str, Any]:
        """Return the exact allow-listed payload without exposing storage codecs."""

        payload: dict[str, Any] = {}
        if self.content_bytes is not None:
            payload["content"] = (
                self.content_bytes
                if self.content_kind == "bytes"
                else self.content_bytes.decode("utf-8")
            )
        for name, raw in (
            ("numeric_input", self.numeric_input_json),
            ("signature", self.signature_json),
            ("public_key", self.public_key_json),
            ("result", self.result_json),
        ):
            value = _decode_private_value(raw)
            if value is not None:
                payload[name] = value
        if self.validity is not None:
            payload["valid"] = self.validity
        if self.processing_state is not None:
            payload["processing_state"] = self.processing_state
        return payload


PrivateHistory = PrivateHistoryRecord
