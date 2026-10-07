"""SQLite storage codecs for history values."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import Integer
from sqlalchemy.types import TypeDecorator

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
MIN_INT64 = -(2**63)
MAX_INT64 = 2**63 - 1
MICROSECONDS_PER_SECOND = 1_000_000


def datetime_to_epoch_microseconds(value: datetime) -> int:
    """Convert an aware datetime to a signed 64-bit UTC epoch microsecond value."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")
    try:
        utc_value = value.astimezone(UTC)
        delta = utc_value - EPOCH
        result = (
            delta.days * 86_400 * MICROSECONDS_PER_SECOND
            + delta.seconds * MICROSECONDS_PER_SECOND
            + delta.microseconds
        )
    except (OverflowError, ValueError) as exc:
        raise ValueError("created_at is outside the supported range") from exc
    if not MIN_INT64 <= result <= MAX_INT64:
        raise ValueError("created_at is outside the supported range")
    return result


def epoch_microseconds_to_datetime(value: int) -> datetime:
    """Convert a signed 64-bit UTC epoch microsecond value to an aware datetime."""

    if type(value) is not int or not MIN_INT64 <= value <= MAX_INT64:
        raise ValueError("created_at is outside the supported range")
    try:
        return EPOCH + timedelta(microseconds=value)
    except OverflowError as exc:
        raise ValueError("created_at is outside the supported range") from exc


class EpochMicrosecondUTC(TypeDecorator[datetime]):
    """Store aware UTC datetimes as SQLite INTEGER epoch microseconds."""

    impl = Integer
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: object) -> int | None:
        return None if value is None else datetime_to_epoch_microseconds(value)

    def process_result_value(self, value: int | None, dialect: object) -> datetime | None:
        return None if value is None else epoch_microseconds_to_datetime(value)


class Boolean01(TypeDecorator[bool]):
    """Represent booleans as the explicit SQLite values 0 and 1."""

    impl = Integer
    cache_ok = True

    def process_bind_param(self, value: bool | None, dialect: object) -> int | None:
        return None if value is None else int(bool(value))

    def process_result_value(self, value: int | None, dialect: object) -> bool | None:
        return None if value is None else bool(value)
