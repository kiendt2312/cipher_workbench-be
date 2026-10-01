"""Tables owned by the application; the schema itself is managed by Alembic."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Identity,
    Index,
    Integer,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

CIPHERS = ("caesar", "vigenere", "playfair", "affine", "columnar", "hill", "des")
OPERATIONS = ("encrypt", "decrypt")
SOURCES = ("text", "file")
RESPONSE_MODES = ("content", "file")


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
        CheckConstraint("duration_ms >= 0", name="ck_cipher_operations_duration_ms"),
        Index("ix_cipher_operations_created_at_id", "created_at", "id"),
        Index("ix_cipher_operations_cipher_created_at", "cipher", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    cipher: Mapped[str] = mapped_column(Text, nullable=False)
    operation: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    response_mode: Mapped[str | None] = mapped_column(Text)
    input_length: Mapped[int | None] = mapped_column(Integer)
    output_length: Mapped[int | None] = mapped_column(Integer)
    http_status: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
