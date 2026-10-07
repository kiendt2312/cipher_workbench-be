"""Fail-closed continuity tooling for the history SQLite transfer.

This module deliberately has no dependency on the application's database engine or
on a PostgreSQL driver.  A future source reader can supply mappings or
``HistoryRow`` values to :func:`import_staging`; keeping that boundary abstract
makes the transfer logic usable with disposable fixtures and prevents an
implementation test from accidentally touching an operator database.

The SQLite schema here is the stable transfer schema: it contains the eleven
logical ``cipher_operations`` fields, plus a small metadata table used to make a
staging file self-describing.  The runtime migration can provide its exact
revision name through ``schema_revision``; this module intentionally does not
guess one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from collections.abc import Iterable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final
from urllib.parse import quote

MAX_ROW_ID: Final = 2**63 - 1
MIN_INT64: Final = -(2**63)
MAX_INT64: Final = 2**63 - 1
FORMAT_VERSION: Final = "history-continuity-v1"
REPLACEMENT_CONFIRMATION: Final = "REPLACE_RUNTIME"
BUSY_TIMEOUT_SECONDS: Final = 0.2

HISTORY_COLUMNS: Final = (
    "id",
    "created_at",
    "cipher",
    "operation",
    "source",
    "response_mode",
    "input_length",
    "output_length",
    "http_status",
    "succeeded",
    "duration_ms",
)
CIPHERS: Final = ("caesar", "vigenere", "playfair", "affine", "columnar", "hill", "des", "rsa")
OPERATIONS: Final = ("encrypt", "decrypt")
SOURCES: Final = ("text", "file")
RESPONSE_MODES: Final = ("content", "file")

ROWS_STREAM_HEADER: Final = b"cipher-workbench/history-rows/v1\n"
IDS_STREAM_HEADER: Final = b"cipher-workbench/history-id-set/v1\n"

# The table intentionally uses INTEGER PRIMARY KEY AUTOINCREMENT.  It is not
# enough to rely on SQLite affinity for transfer validation, so every value also
# has an explicit typeof/check constraint.
STAGING_SCHEMA_SQL: Final = """
CREATE TABLE cipher_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT
        CHECK(typeof(id) = 'integer' AND id >= 1 AND id <= 9223372036854775807),
    created_at INTEGER NOT NULL
        CHECK(typeof(created_at) = 'integer'),
    cipher TEXT NOT NULL
        CHECK(typeof(cipher) = 'text' AND cipher IN
            ('caesar', 'vigenere', 'playfair', 'affine', 'columnar', 'hill', 'des', 'rsa')),
    operation TEXT
        CHECK(operation IS NULL OR
            (typeof(operation) = 'text' AND operation IN ('encrypt', 'decrypt'))),
    source TEXT NOT NULL
        CHECK(typeof(source) = 'text' AND source IN ('text', 'file')),
    response_mode TEXT
        CHECK(response_mode IS NULL OR
            (typeof(response_mode) = 'text' AND response_mode IN ('content', 'file'))),
    input_length INTEGER
        CHECK(input_length IS NULL OR
            (typeof(input_length) = 'integer' AND input_length >= 0)),
    output_length INTEGER
        CHECK(output_length IS NULL OR
            (typeof(output_length) = 'integer' AND output_length >= 0)),
    http_status INTEGER NOT NULL
        CHECK(typeof(http_status) = 'integer'),
    succeeded INTEGER NOT NULL
        CHECK(typeof(succeeded) = 'integer' AND succeeded IN (0, 1)),
    duration_ms INTEGER NOT NULL
        CHECK(typeof(duration_ms) = 'integer' AND duration_ms >= 0)
);

CREATE INDEX ix_cipher_operations_created_at_id
    ON cipher_operations (created_at DESC, id DESC);
CREATE INDEX ix_cipher_operations_cipher_created_at
    ON cipher_operations (cipher, created_at DESC, id DESC);

CREATE TABLE history_continuity_meta (
    key TEXT PRIMARY KEY
        CHECK(typeof(key) = 'text' AND length(key) > 0),
    value TEXT NOT NULL
        CHECK(typeof(value) = 'text')
);

CREATE TABLE alembic_version (
    version_num VARCHAR(255) NOT NULL
);
"""


class ContinuityError(RuntimeError):
    """Base class for safe, fail-closed continuity errors."""


class InvalidHistoryRowError(ContinuityError, ValueError):
    """An input row cannot be represented by the eleven-field schema."""


class UnsupportedSequenceStateError(ContinuityError, ValueError):
    """The source identity state is not a supported positive increment state."""


class VerificationError(ContinuityError):
    """A staging/backup file failed an integrity or reconciliation check."""


class PublicationError(ContinuityError):
    """A publication or replacement precondition failed."""


InvalidHistoryRow = InvalidHistoryRowError
UnsupportedSequenceState = UnsupportedSequenceStateError

type HistoryInput = HistoryRow | Mapping[str, Any] | Sequence[Any]
type PathInput = str | os.PathLike[str]


def _validate_revision(value: str, label: str) -> str:
    if type(value) is not str or not value or len(value) > 128:
        raise ValueError(f"{label} must be a non-empty short string")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        raise ValueError(f"{label} contains a control character")
    return value


def _validate_int(value: object, label: str, *, minimum: int | None = None) -> int:
    if type(value) is not int:
        raise InvalidHistoryRow(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        raise InvalidHistoryRow(f"{label} is out of range")
    if not MIN_INT64 <= value <= MAX_INT64:
        raise InvalidHistoryRow(f"{label} is outside SQLite's signed integer range")
    return value


def datetime_to_epoch_microseconds(value: datetime) -> int:
    """Convert an aware datetime to exact UTC epoch microseconds.

    No floating-point timestamp conversion is used, so a PostgreSQL microsecond
    value survives the transfer unchanged.  Naive datetimes are rejected rather
    than silently interpreted in the process timezone.
    """

    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")
    normalized = value.astimezone(UTC)
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    delta = normalized - epoch
    result = delta.days * 86_400 * 1_000_000 + delta.seconds * 1_000_000 + delta.microseconds
    if not MIN_INT64 <= result <= MAX_INT64:
        raise ValueError("created_at is outside the signed epoch-microsecond range")
    return result


def epoch_microseconds_to_datetime(value: int) -> datetime:
    """Convert a signed epoch-microsecond value to an aware UTC datetime."""

    value = _validate_int(value, "created_at")
    seconds, microseconds = divmod(value, 1_000_000)
    try:
        return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
            seconds=seconds, microseconds=microseconds
        )
    except OverflowError as exc:
        raise ValueError("created_at cannot be represented as a Python datetime") from exc


def _coerce_created_at(value: object) -> int:
    if isinstance(value, datetime):
        return datetime_to_epoch_microseconds(value)
    return _validate_int(value, "created_at")


def _coerce_optional_int(value: object, label: str, *, minimum: int | None = None) -> int | None:
    if value is None:
        return None
    return _validate_int(value, label, minimum=minimum)


def _coerce_bool(value: object, label: str) -> bool:
    if type(value) is bool:
        return value
    if type(value) is int and value in (0, 1):
        return bool(value)
    raise InvalidHistoryRow(f"{label} must be boolean 0 or 1")


def _coerce_text(value: object, label: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if type(value) is not str:
        raise InvalidHistoryRow(f"{label} must be text")
    return value


@dataclass(frozen=True, slots=True)
class HistoryRow:
    """The exact eleven logical fields transferred between engines.

    ``created_at`` is always a signed UTC epoch-microsecond integer in this
    boundary.  It is deliberately not a ``datetime`` so that a source reader
    must make timezone/precision conversion explicit.
    """

    id: int
    created_at: int
    cipher: str
    operation: str | None
    source: str
    response_mode: str | None
    input_length: int | None
    output_length: int | None
    http_status: int
    succeeded: bool
    duration_ms: int

    def __post_init__(self) -> None:
        if type(self.id) is not int or not 1 <= self.id <= MAX_ROW_ID:
            raise InvalidHistoryRow("id must be in 1..2^63-1")
        if type(self.created_at) is not int or not MIN_INT64 <= self.created_at <= MAX_INT64:
            raise InvalidHistoryRow("created_at must be a signed epoch-microsecond integer")
        if self.cipher not in CIPHERS:
            raise InvalidHistoryRow("cipher is not supported")
        if self.operation is not None and self.operation not in OPERATIONS:
            raise InvalidHistoryRow("operation is not supported")
        if self.source not in SOURCES:
            raise InvalidHistoryRow("source is not supported")
        if self.response_mode is not None and self.response_mode not in RESPONSE_MODES:
            raise InvalidHistoryRow("response_mode is not supported")
        for value, label in (
            (self.input_length, "input_length"),
            (self.output_length, "output_length"),
        ):
            if value is not None and (type(value) is not int or not 0 <= value <= MAX_INT64):
                raise InvalidHistoryRow(f"{label} must be a non-negative integer or null")
        if type(self.http_status) is not int or not MIN_INT64 <= self.http_status <= MAX_INT64:
            raise InvalidHistoryRow("http_status must be an integer")
        if type(self.succeeded) is not bool:
            raise InvalidHistoryRow("succeeded must be boolean")
        if type(self.duration_ms) is not int or not 0 <= self.duration_ms <= MAX_INT64:
            raise InvalidHistoryRow("duration_ms must be a non-negative integer")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> HistoryRow:
        """Create a row from stable source column names.

        Extra mapping fields are ignored, which lets a source query carry
        driver-specific bookkeeping without allowing payload fields into the
        continuity artifact.
        """

        def get(name: str) -> Any:
            try:
                return value[name]
            except (KeyError, TypeError) as exc:
                raise InvalidHistoryRow(f"missing history field: {name}") from exc

        return cls(
            id=_validate_int(get("id"), "id", minimum=1),
            created_at=_coerce_created_at(get("created_at")),
            cipher=_coerce_text(get("cipher"), "cipher"),  # type: ignore[arg-type]
            operation=_coerce_text(get("operation"), "operation", nullable=True),
            source=_coerce_text(get("source"), "source"),  # type: ignore[arg-type]
            response_mode=_coerce_text(get("response_mode"), "response_mode", nullable=True),
            input_length=_coerce_optional_int(get("input_length"), "input_length", minimum=0),
            output_length=_coerce_optional_int(get("output_length"), "output_length", minimum=0),
            http_status=_validate_int(get("http_status"), "http_status"),
            succeeded=_coerce_bool(get("succeeded"), "succeeded"),
            duration_ms=_validate_int(get("duration_ms"), "duration_ms", minimum=0),
        )

    @classmethod
    def from_sequence(cls, value: Sequence[Any]) -> HistoryRow:
        if isinstance(value, (str, bytes, bytearray)) or len(value) != len(HISTORY_COLUMNS):
            raise InvalidHistoryRow("a history sequence must contain exactly eleven fields")
        return cls.from_mapping(dict(zip(HISTORY_COLUMNS, value, strict=True)))

    def as_sql_values(self) -> tuple[object, ...]:
        return (
            self.id,
            self.created_at,
            self.cipher,
            self.operation,
            self.source,
            self.response_mode,
            self.input_length,
            self.output_length,
            self.http_status,
            int(self.succeeded),
            self.duration_ms,
        )


def _row_mapping(value: object) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    mapping = getattr(value, "_mapping", None)
    if isinstance(mapping, Mapping):
        return mapping
    keys = getattr(value, "keys", None)
    if callable(keys):
        try:
            return {key: value[key] for key in keys()}
        except (KeyError, TypeError, IndexError):
            return None
    return None


def normalize_history_row(value: HistoryInput) -> HistoryRow:
    """Normalize a mapping, eleven-value sequence, or existing row."""

    if isinstance(value, HistoryRow):
        return value
    mapping = _row_mapping(value)
    if mapping is not None:
        return HistoryRow.from_mapping(mapping)
    if isinstance(value, Sequence):
        return HistoryRow.from_sequence(value)
    raise InvalidHistoryRow("history input must be a HistoryRow, mapping, or sequence")


def normalize_history_rows(rows: Iterable[HistoryInput]) -> tuple[HistoryRow, ...]:
    normalized = tuple(sorted((normalize_history_row(row) for row in rows), key=lambda row: row.id))
    ids = [row.id for row in normalized]
    if len(ids) != len(set(ids)):
        raise InvalidHistoryRow("duplicate history id")
    return normalized


@dataclass(frozen=True, slots=True)
class IdentityState:
    """The PostgreSQL identity values needed to preserve the ID high-water mark."""

    last_value: int
    is_called: bool
    increment: int

    def __post_init__(self) -> None:
        last_value = _validate_sequence_int(self.last_value, "last_value")
        increment = _validate_sequence_int(self.increment, "increment")
        is_called = _coerce_sequence_bool(self.is_called)
        if not 1 <= last_value <= MAX_ROW_ID:
            raise UnsupportedSequenceState("last_value is outside the positive identity range")
        if not 1 <= increment <= MAX_ROW_ID:
            raise UnsupportedSequenceState("only positive identity increments are supported")
        object.__setattr__(self, "last_value", last_value)
        object.__setattr__(self, "increment", increment)
        object.__setattr__(self, "is_called", is_called)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> IdentityState:
        try:
            return cls(
                last_value=value["last_value"],
                is_called=value["is_called"],
                increment=value["increment"],
            )
        except KeyError as exc:
            raise UnsupportedSequenceState(f"missing identity field: {exc.args[0]}") from exc

    @property
    def last_issued_high_water(self) -> int:
        return derive_last_issued_high_water(
            last_value=self.last_value,
            is_called=self.is_called,
            increment=self.increment,
        )


def _validate_sequence_int(value: object, label: str) -> int:
    if type(value) is not int:
        raise UnsupportedSequenceState(f"{label} must be an integer")
    if not MIN_INT64 <= value <= MAX_INT64:
        raise UnsupportedSequenceState(f"{label} is outside the signed integer range")
    return value


def _coerce_sequence_bool(value: object) -> bool:
    if type(value) is bool:
        return value
    if type(value) is int and value in (0, 1):
        return bool(value)
    raise UnsupportedSequenceState("is_called must be boolean 0 or 1")


def derive_last_issued_high_water(*, last_value: int, is_called: bool, increment: int) -> int:
    """Derive the greatest identity value actually issued by PostgreSQL.

    PostgreSQL stores the next value in ``last_value`` while ``is_called`` is
    false.  Therefore a never-called sequence's last issued value is
    ``last_value - increment``; treating ``last_value`` itself as issued would
    skip a valid first ID.  Unsupported/negative increments are rejected.
    """

    state = IdentityState(last_value=last_value, is_called=is_called, increment=increment)
    return state.last_value if state.is_called else state.last_value - state.increment


def _canonical_integer(value: int) -> bytes:
    if type(value) is not int:
        raise TypeError("canonical integer must be an integer")
    return str(value).encode("ascii")


def _frame(type_tag: bytes, payload: bytes) -> bytes:
    if len(type_tag) != 1 or type_tag not in b"Risbnt":
        raise ValueError("invalid canonical type tag")
    return type_tag + _canonical_integer(len(payload)) + b":" + payload


def _field_frame(name: str, value: object) -> bytes:
    if value is None:
        return _frame(b"n", b"")
    if name == "succeeded":
        if type(value) is not bool:
            raise TypeError("succeeded must be boolean before canonicalization")
        return _frame(b"b", b"1" if value else b"0")
    if name in {"id", "created_at", "input_length", "output_length", "http_status", "duration_ms"}:
        if type(value) is not int:
            raise TypeError(f"{name} must be integer before canonicalization")
        return _frame(b"i", _canonical_integer(value))
    if type(value) is not str:
        raise TypeError(f"{name} must be text before canonicalization")
    return _frame(b"s", value.encode("utf-8"))


def canonical_row_bytes(row: HistoryRow | Mapping[str, Any] | Sequence[Any]) -> bytes:
    """Return one versioned, unambiguous canonical row frame."""

    normalized = normalize_history_row(row)
    fields = tuple(getattr(normalized, name) for name in HISTORY_COLUMNS)
    return _frame(
        b"R",
        b"".join(
            _field_frame(name, value) for name, value in zip(HISTORY_COLUMNS, fields, strict=True)
        ),
    )


def canonical_rows_bytes(rows: Iterable[HistoryInput]) -> bytes:
    """Return the versioned canonical stream used by the row digest."""

    normalized = normalize_history_rows(rows)
    return ROWS_STREAM_HEADER + b"".join(canonical_row_bytes(row) for row in normalized)


def canonical_id_set_bytes(ids: Iterable[int]) -> bytes:
    """Return the versioned canonical stream used by the ID-set digest."""

    normalized = sorted(_validate_int(value, "id", minimum=1) for value in ids)
    if len(normalized) != len(set(normalized)):
        raise InvalidHistoryRow("duplicate history id")
    return IDS_STREAM_HEADER + b"".join(
        _frame(b"i", _canonical_integer(value)) for value in normalized
    )


def row_digest(rows: Iterable[HistoryInput]) -> str:
    return hashlib.sha256(canonical_rows_bytes(rows)).hexdigest()


def id_set_digest(rows_or_ids: Iterable[HistoryInput] | Iterable[int]) -> str:
    values = tuple(rows_or_ids)
    if all(isinstance(value, int) and type(value) is not bool for value in values):
        ids = values
    else:
        ids = tuple(normalize_history_row(value).id for value in values)  # type: ignore[arg-type]
    return hashlib.sha256(canonical_id_set_bytes(ids)).hexdigest()


def _validate_digest(value: str, label: str = "digest") -> str:
    if type(value) is not str or len(value) != 64:
        raise ValueError(f"{label} must be a SHA-256 hex digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{label} must be a SHA-256 hex digest") from exc
    return value.lower()


@dataclass(frozen=True, slots=True)
class Manifest:
    """Reconciliation evidence for one immutable source snapshot."""

    source_revision: str | None
    schema_revision: str | None
    snapshot_epoch_us: int
    count: int
    min_id: int | None
    max_id: int | None
    identity_last_value: int
    identity_is_called: bool
    identity_increment: int
    identity_last_issued: int
    id_set_digest: str
    row_digest: str
    format_version: str = FORMAT_VERSION
    identity_source: str = "postgresql"

    def __post_init__(self) -> None:
        if self.source_revision is not None:
            _validate_revision(self.source_revision, "source_revision")
        if self.schema_revision is not None:
            _validate_revision(self.schema_revision, "schema_revision")
        if self.format_version != FORMAT_VERSION:
            raise ValueError("unsupported continuity manifest format")
        if self.identity_source not in {"postgresql", "sqlite"}:
            raise ValueError("unsupported continuity identity source")
        _validate_int(self.snapshot_epoch_us, "snapshot_epoch_us")
        if type(self.count) is not int or self.count < 0:
            raise ValueError("manifest count must be non-negative")
        if self.count == 0:
            if self.min_id is not None or self.max_id is not None:
                raise ValueError("empty manifest must not have an ID range")
        else:
            if (
                type(self.min_id) is not int
                or type(self.max_id) is not int
                or not 1 <= self.min_id <= self.max_id <= MAX_ROW_ID
            ):
                raise ValueError("manifest ID range is invalid")
        minimum_identity = 0 if self.identity_source == "sqlite" else 1
        if not minimum_identity <= self.identity_last_value <= MAX_ROW_ID:
            raise ValueError("manifest identity last_value is invalid")
        if type(self.identity_is_called) is not bool:
            raise ValueError("manifest identity is_called is invalid")
        if not 1 <= self.identity_increment <= MAX_ROW_ID:
            raise ValueError("manifest identity increment is invalid")
        minimum_last_issued = 0 if self.identity_source == "sqlite" else MIN_INT64
        if not minimum_last_issued <= self.identity_last_issued <= MAX_ROW_ID:
            raise ValueError("manifest identity last-issued value is invalid")
        _validate_digest(self.id_set_digest, "id_set_digest")
        _validate_digest(self.row_digest, "row_digest")

    @classmethod
    def from_rows(
        cls,
        rows: Iterable[HistoryInput],
        identity: IdentityState | Mapping[str, Any],
        *,
        source_revision: str,
        schema_revision: str,
        snapshot_epoch_us: int,
    ) -> Manifest:
        normalized = normalize_history_rows(rows)
        state = (
            identity
            if isinstance(identity, IdentityState)
            else IdentityState.from_mapping(identity)
        )
        return cls(
            source_revision=_validate_revision(source_revision, "source_revision"),
            schema_revision=_validate_revision(schema_revision, "schema_revision"),
            snapshot_epoch_us=_validate_int(snapshot_epoch_us, "snapshot_epoch_us"),
            count=len(normalized),
            min_id=normalized[0].id if normalized else None,
            max_id=normalized[-1].id if normalized else None,
            identity_last_value=state.last_value,
            identity_is_called=state.is_called,
            identity_increment=state.increment,
            identity_last_issued=state.last_issued_high_water,
            id_set_digest=id_set_digest(normalized),
            row_digest=row_digest(normalized),
        )

    @classmethod
    def from_sqlite_snapshot(
        cls,
        rows: Iterable[HistoryInput],
        sequence: int,
        *,
        source_revision: str | None,
        schema_revision: str | None,
        snapshot_epoch_us: int,
        identity_source: str = "sqlite",
    ) -> Manifest:
        """Build a manifest from a completed SQLite snapshot.

        ``sqlite_sequence`` is represented as the identity high-water with an
        explicit ``identity_source`` marker.  It is never presented as a
        PostgreSQL sequence state.
        """

        normalized = normalize_history_rows(rows)
        if type(sequence) is not int or not 0 <= sequence <= MAX_ROW_ID:
            raise VerificationError("SQLite sequence is outside the supported range")
        return cls(
            source_revision=source_revision,
            schema_revision=schema_revision,
            snapshot_epoch_us=_validate_int(snapshot_epoch_us, "snapshot_epoch_us"),
            count=len(normalized),
            min_id=normalized[0].id if normalized else None,
            max_id=normalized[-1].id if normalized else None,
            identity_last_value=sequence,
            identity_is_called=sequence > 0,
            identity_increment=1,
            identity_last_issued=sequence,
            id_set_digest=id_set_digest(normalized),
            row_digest=row_digest(normalized),
            identity_source=identity_source,
        )

    @property
    def digest(self) -> str:
        """Digest the manifest evidence, excluding the digest itself."""

        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "format_version": self.format_version,
            "source_revision": self.source_revision,
            "schema_revision": self.schema_revision,
            "snapshot_epoch_us": self.snapshot_epoch_us,
            "count": self.count,
            "min_id": self.min_id,
            "max_id": self.max_id,
            "identity": {
                "source": self.identity_source,
                "last_value": self.identity_last_value,
                "is_called": self.identity_is_called,
                "increment": self.identity_increment,
                "last_issued": self.identity_last_issued,
            },
            "id_set_digest": self.id_set_digest,
            "row_digest": self.row_digest,
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Manifest:
        try:
            identity = value["identity"]
            if not isinstance(identity, Mapping):
                raise ValueError("manifest identity must be an object")
            return cls(
                format_version=value["format_version"],
                source_revision=value.get("source_revision"),
                schema_revision=value.get("schema_revision"),
                snapshot_epoch_us=value["snapshot_epoch_us"],
                count=value["count"],
                min_id=value["min_id"],
                max_id=value["max_id"],
                identity_last_value=identity["last_value"],
                identity_is_called=identity["is_called"],
                identity_increment=identity["increment"],
                identity_last_issued=identity["last_issued"],
                id_set_digest=value["id_set_digest"],
                row_digest=value["row_digest"],
                identity_source=identity.get("source", "postgresql"),
            )
        except (KeyError, TypeError) as exc:
            raise VerificationError("manifest metadata is incomplete") from exc


@dataclass(frozen=True, slots=True)
class VerificationReport:
    path: Path
    manifest: Manifest
    sequence: int
    quick_check: str
    integrity_check: str


@dataclass(frozen=True, slots=True)
class ImportResult:
    path: Path
    manifest: Manifest
    verification: VerificationReport


@dataclass(frozen=True, slots=True)
class BackupEvidence:
    source_digest: str | None
    backup_digest: str
    path: Path
    verified: bool


@dataclass(frozen=True, slots=True)
class RestoreEvidence:
    backup_digest: str
    restored_digest: str
    path: Path
    verified: bool


@dataclass(frozen=True, slots=True)
class PublicationResult:
    path: Path
    manifest_digest: str


@dataclass(frozen=True, slots=True)
class ReplacementResult:
    path: Path
    old_digest: str
    new_digest: str
    backup_digest: str


@dataclass(frozen=True, slots=True)
class RollbackDeltaReport:
    """Read-only deterministic difference between two history snapshots."""

    before_count: int
    after_count: int
    added_ids: tuple[int, ...]
    removed_ids: tuple[int, ...]
    changed_ids: tuple[int, ...]
    before_id_digest: str
    after_id_digest: str
    before_row_digest: str
    after_row_digest: str
    before_sequence: int | None
    after_sequence: int | None

    @property
    def has_changes(self) -> bool:
        return bool(
            self.added_ids
            or self.removed_ids
            or self.changed_ids
            or (
                self.before_sequence is not None
                and self.after_sequence is not None
                and self.before_sequence != self.after_sequence
            )
        )

    @property
    def colliding_ids(self) -> tuple[int, ...]:
        """IDs present on both sides with different canonical rows."""

        return self.changed_ids

    def to_dict(self) -> dict[str, object]:
        return {
            "before_count": self.before_count,
            "after_count": self.after_count,
            "added_ids": list(self.added_ids),
            "removed_ids": list(self.removed_ids),
            "changed_ids": list(self.changed_ids),
            "before_id_digest": self.before_id_digest,
            "after_id_digest": self.after_id_digest,
            "before_row_digest": self.before_row_digest,
            "after_row_digest": self.after_row_digest,
            "before_sequence": self.before_sequence,
            "after_sequence": self.after_sequence,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def _path(value: PathInput) -> Path:
    return Path(value)


def _ensure_parent(path: Path) -> None:
    if not path.parent.exists() or not path.parent.is_dir():
        raise FileNotFoundError("continuity target parent does not exist")


def _ensure_new_file(path: Path) -> None:
    _ensure_absent(path)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    descriptor = os.open(path, flags, 0o600)
    os.close(descriptor)


def _ensure_absent(path: Path) -> None:
    _ensure_parent(path)
    if path.exists() or path.is_symlink():
        raise FileExistsError("continuity target already exists")


def _ensure_existing_file(path: Path) -> None:
    if path.is_symlink() or not path.exists() or not path.is_file():
        raise FileNotFoundError("continuity database file is missing or not a regular file")


def _connect(
    path: Path,
    *,
    read_only: bool = False,
    timeout: float = BUSY_TIMEOUT_SECONDS,
) -> sqlite3.Connection:
    if read_only:
        _ensure_existing_file(path)
        uri = f"file:{quote(str(path.resolve()), safe='/')}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=timeout, isolation_level=None)
    else:
        connection = sqlite3.connect(str(path), timeout=timeout, isolation_level=None)
    connection.execute(f"PRAGMA busy_timeout = {int(timeout * 1000)}")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _same_filesystem(first: Path, second_parent: Path) -> bool:
    try:
        return os.stat(first).st_dev == os.stat(second_parent).st_dev
    except OSError as exc:
        raise PublicationError("could not establish same-filesystem publication") from exc


def _create_schema(
    connection: sqlite3.Connection,
    *,
    schema_revision: str,
    source_revision: str,
) -> None:
    connection.executescript(STAGING_SCHEMA_SQL)
    connection.execute("INSERT INTO alembic_version(version_num) VALUES (?)", (schema_revision,))
    _set_metadata(
        connection,
        {
            "format_version": FORMAT_VERSION,
            "schema_revision": schema_revision,
            "source_revision": source_revision,
        },
    )


def _set_metadata(connection: sqlite3.Connection, values: Mapping[str, str]) -> None:
    connection.executemany(
        "INSERT OR REPLACE INTO history_continuity_meta(key, value) VALUES (?, ?)", values.items()
    )


def _read_metadata(connection: sqlite3.Connection) -> dict[str, str]:
    table_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'history_continuity_meta'"
    ).fetchone()
    if table_exists is None:
        return {}
    try:
        rows = connection.execute("SELECT key, value FROM history_continuity_meta").fetchall()
    except sqlite3.Error as exc:
        raise VerificationError("continuity metadata is unavailable") from exc
    result = {str(key): str(value) for key, value in rows}
    if len(result) != len(rows):
        raise VerificationError("continuity metadata contains duplicate keys")
    return result


def _manifest_from_metadata_unverified(metadata: Mapping[str, str]) -> Manifest | None:
    """Read provenance without treating an old row digest as current evidence."""

    raw_manifest = metadata.get("manifest_json")
    if raw_manifest is None:
        return None
    try:
        return Manifest.from_dict(json.loads(raw_manifest))
    except (json.JSONDecodeError, TypeError, ValueError, VerificationError):
        return None


def _read_alembic_revision(connection: sqlite3.Connection) -> str | None:
    table_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'alembic_version'"
    ).fetchone()
    if table_exists is None:
        return None
    rows = connection.execute("SELECT version_num FROM alembic_version").fetchall()
    if len(rows) != 1 or type(rows[0][0]) is not str or not rows[0][0]:
        return None
    return rows[0][0]


def _read_sqlite_sequence(connection: sqlite3.Connection) -> int:
    table_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_sequence'"
    ).fetchone()
    if table_exists is None:
        return 0
    row = connection.execute(
        "SELECT seq FROM sqlite_sequence WHERE name = 'cipher_operations'"
    ).fetchone()
    if row is None:
        return 0
    sequence = row[0]
    if type(sequence) is not int or not 0 <= sequence <= MAX_ROW_ID:
        raise VerificationError("SQLite sequence is outside the supported range")
    return sequence


def _set_sqlite_sequence(connection: sqlite3.Connection, sequence: int) -> None:
    if type(sequence) is not int or not 0 <= sequence <= MAX_ROW_ID:
        raise VerificationError("SQLite sequence is outside the supported range")
    table_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_sequence'"
    ).fetchone()
    if table_exists is None:
        raise VerificationError("SQLite sequence table is missing")
    updated = connection.execute(
        "UPDATE sqlite_sequence SET seq = ? WHERE name = 'cipher_operations'", (sequence,)
    ).rowcount
    if updated != 1:
        connection.execute(
            "INSERT INTO sqlite_sequence(name, seq) VALUES ('cipher_operations', ?)", (sequence,)
        )


def _snapshot_provenance(
    connection: sqlite3.Connection,
    *,
    fallback_manifest: Manifest | None = None,
    source_revision: str | None = None,
    schema_revision: str | None = None,
) -> tuple[str | None, str | None, Manifest | None]:
    metadata = _read_metadata(connection)
    persisted = _manifest_from_metadata_unverified(metadata)
    current_source_revision = (
        source_revision
        if source_revision is not None
        else (
            fallback_manifest.source_revision
            if fallback_manifest is not None and fallback_manifest.source_revision is not None
            else persisted.source_revision
            if persisted is not None
            else None
        )
    )
    current_schema_revision = (
        schema_revision
        if schema_revision is not None
        else (
            fallback_manifest.schema_revision
            if fallback_manifest is not None and fallback_manifest.schema_revision is not None
            else persisted.schema_revision
            if persisted is not None and persisted.schema_revision is not None
            else _read_alembic_revision(connection)
        )
    )
    return current_source_revision, current_schema_revision, persisted


def _write_manifest_metadata(connection: sqlite3.Connection, manifest: Manifest) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS history_continuity_meta (
            key TEXT PRIMARY KEY CHECK(typeof(key) = 'text' AND length(key) > 0),
            value TEXT NOT NULL CHECK(typeof(value) = 'text')
        )
        """
    )
    connection.execute(
        "DELETE FROM history_continuity_meta WHERE key IN "
        "('format_version', 'source_revision', 'schema_revision', "
        "'manifest_digest', 'manifest_json')"
    )
    values = {
        "format_version": manifest.format_version,
        "manifest_digest": manifest.digest,
        "manifest_json": manifest.canonical_bytes().decode("utf-8"),
    }
    if manifest.source_revision is not None:
        values["source_revision"] = manifest.source_revision
    if manifest.schema_revision is not None:
        values["schema_revision"] = manifest.schema_revision
    _set_metadata(connection, values)


def _check_revision_presence(connection: sqlite3.Connection, manifest: Manifest) -> None:
    """Check an existing Alembic revision table when it is available."""

    if manifest.schema_revision is None:
        return
    table_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'alembic_version'"
    ).fetchone()
    if table_exists is None:
        return
    revisions = {
        row[0] for row in connection.execute("SELECT version_num FROM alembic_version").fetchall()
    }
    if manifest.schema_revision not in revisions:
        raise VerificationError("SQLite revision does not match the injected manifest")


def _check_pragma(connection: sqlite3.Connection, pragma: str) -> str:
    try:
        result = connection.execute(f"PRAGMA {pragma}").fetchall()
    except sqlite3.Error as exc:
        raise VerificationError("SQLite integrity check could not run") from exc
    if result != [("ok",)]:
        raise VerificationError("SQLite integrity check failed")
    return "ok"


def _check_schema(connection: sqlite3.Connection) -> None:
    try:
        columns = connection.execute("PRAGMA table_info(cipher_operations)").fetchall()
        meta_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'history_continuity_meta'"
        ).fetchone()
        meta_columns = (
            connection.execute("PRAGMA table_info(history_continuity_meta)").fetchall()
            if meta_exists
            else []
        )
        index_rows = connection.execute("PRAGMA index_list(cipher_operations)").fetchall()
        sql_row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'cipher_operations'"
        ).fetchone()
    except sqlite3.Error as exc:
        raise VerificationError("SQLite schema inspection failed") from exc
    expected_types = {
        "id": "INTEGER",
        "created_at": "INTEGER",
        "cipher": "TEXT",
        "operation": "TEXT",
        "source": "TEXT",
        "response_mode": "TEXT",
        "input_length": "INTEGER",
        "output_length": "INTEGER",
        "http_status": "INTEGER",
        "succeeded": "INTEGER",
        "duration_ms": "INTEGER",
    }
    if [row[1] for row in columns] != list(HISTORY_COLUMNS):
        raise VerificationError("history schema columns do not match the eleven-field contract")
    for row in columns:
        _, name, type_name, _not_null, _default, primary_key = row
        if type_name.upper() != expected_types[name] or (name == "id" and primary_key != 1):
            raise VerificationError("history schema column type or primary key is invalid")
    if meta_exists and [row[1] for row in meta_columns] != ["key", "value"]:
        raise VerificationError("continuity metadata schema is invalid")
    names = {row[1] for row in index_rows}
    expected_indexes = {
        "ix_cipher_operations_created_at_id",
        "ix_cipher_operations_cipher_created_at",
    }
    if not expected_indexes <= names:
        raise VerificationError("history schema indexes are incomplete")
    expected_index_columns = {
        "ix_cipher_operations_created_at_id": ("created_at", "id"),
        "ix_cipher_operations_cipher_created_at": ("cipher", "created_at", "id"),
    }
    for index_name, expected in expected_index_columns.items():
        rows = connection.execute(f'PRAGMA index_info("{index_name}")').fetchall()
        if tuple(row[2] for row in sorted(rows, key=lambda row: row[0])) != expected:
            raise VerificationError("history schema index columns are invalid")
    if not sql_row or not isinstance(sql_row[0], str):
        raise VerificationError("history table definition is missing")
    definition = sql_row[0].upper()
    for marker in ("AUTOINCREMENT", "RSA", "CHECK", "SUCCEEDED", "DURATION_MS"):
        if marker not in definition:
            raise VerificationError("history table constraints are incomplete")


def _rows_from_connection(connection: sqlite3.Connection) -> tuple[HistoryRow, ...]:
    try:
        values = connection.execute(
            "SELECT id, created_at, cipher, operation, source, response_mode, input_length, "
            "output_length, http_status, succeeded, duration_ms "
            "FROM cipher_operations ORDER BY id ASC"
        ).fetchall()
    except sqlite3.Error as exc:
        raise VerificationError("history rows are unavailable") from exc
    try:
        return normalize_history_rows(values)
    except (InvalidHistoryRow, TypeError, ValueError) as exc:
        raise VerificationError("history row violates the continuity contract") from exc


def _manifest_from_metadata(metadata: Mapping[str, str]) -> Manifest:
    try:
        manifest = Manifest.from_dict(json.loads(metadata["manifest_json"]))
        stored_digest = _validate_digest(metadata["manifest_digest"], "manifest_digest")
    except (KeyError, json.JSONDecodeError, ValueError, TypeError) as exc:
        raise VerificationError("continuity manifest metadata is invalid") from exc
    if manifest.digest != stored_digest:
        raise VerificationError("continuity manifest digest does not match its evidence")
    if metadata.get("format_version") != manifest.format_version:
        raise VerificationError("continuity manifest format does not match schema metadata")
    if metadata.get("source_revision") != manifest.source_revision:
        raise VerificationError("continuity source revision does not match manifest")
    if metadata.get("schema_revision") != manifest.schema_revision:
        raise VerificationError("continuity schema revision does not match manifest")
    return manifest


def verify_staging(
    path: PathInput,
    *,
    expected_manifest: Manifest | None = None,
    expected_manifest_digest: str | None = None,
    expected_schema_revision: str | None = None,
) -> VerificationReport:
    """Verify SQLite integrity, schema metadata, rows, digests, and sequence."""

    target = _path(path)
    _ensure_existing_file(target)
    if expected_manifest_digest is not None:
        expected_manifest_digest = _validate_digest(expected_manifest_digest)
    if expected_schema_revision is not None:
        _validate_revision(expected_schema_revision, "expected_schema_revision")
    try:
        connection = _connect(target, read_only=True)
    except (OSError, sqlite3.Error) as exc:
        raise VerificationError("could not open SQLite staging") from exc
    try:
        quick_check = _check_pragma(connection, "quick_check")
        integrity_check = _check_pragma(connection, "integrity_check")
        _check_schema(connection)
        metadata = _read_metadata(connection)
        if metadata:
            manifest = _manifest_from_metadata(metadata)
        elif expected_manifest is not None:
            manifest = expected_manifest
        else:
            raise VerificationError("continuity manifest evidence is missing")
        _check_revision_presence(connection, manifest)
        rows = _rows_from_connection(connection)
        actual_count = len(rows)
        actual_min = rows[0].id if rows else None
        actual_max = rows[-1].id if rows else None
        if (
            manifest.count != actual_count
            or manifest.min_id != actual_min
            or manifest.max_id != actual_max
            or manifest.id_set_digest != id_set_digest(rows)
            or manifest.row_digest != row_digest(rows)
        ):
            raise VerificationError("history row count, range, ID set, or digest mismatch")
        try:
            sequence_row = connection.execute(
                "SELECT seq FROM sqlite_sequence WHERE name = 'cipher_operations'"
            ).fetchone()
        except sqlite3.Error as exc:
            raise VerificationError("SQLite sequence state is unavailable") from exc
        if sequence_row is None or type(sequence_row[0]) is not int:
            raise VerificationError("SQLite sequence state is missing")
        sequence = sequence_row[0]
        required_sequence = max(manifest.max_id or 0, manifest.identity_last_issued, 0)
        if sequence < required_sequence:
            raise VerificationError("SQLite sequence is below the required identity high-water")
        if (
            expected_schema_revision is not None
            and manifest.schema_revision != expected_schema_revision
        ):
            raise VerificationError("SQLite schema revision does not match expectation")
        if (
            expected_manifest is not None
            and manifest.canonical_bytes() != expected_manifest.canonical_bytes()
        ):
            raise VerificationError("SQLite manifest does not match expected evidence")
        if expected_manifest_digest is not None and manifest.digest != expected_manifest_digest:
            raise VerificationError("SQLite manifest digest does not match expectation")
        return VerificationReport(
            path=target,
            manifest=manifest,
            sequence=sequence,
            quick_check=quick_check,
            integrity_check=integrity_check,
        )
    except VerificationError:
        raise
    except (sqlite3.Error, OSError, ValueError, TypeError) as exc:
        raise VerificationError("SQLite staging verification failed") from exc
    finally:
        connection.close()


def import_staging(
    staging_path: PathInput,
    rows: Iterable[HistoryInput],
    identity: IdentityState | Mapping[str, Any],
    *,
    source_revision: str,
    schema_revision: str,
    snapshot_epoch_us: int | None = None,
) -> ImportResult:
    """Import abstract source rows into a new explicit-ID SQLite staging file."""

    target = _path(staging_path)
    _ensure_absent(target)
    normalized = normalize_history_rows(rows)
    state = (
        identity if isinstance(identity, IdentityState) else IdentityState.from_mapping(identity)
    )
    if snapshot_epoch_us is None:
        snapshot_epoch_us = datetime_to_epoch_microseconds(datetime.now(UTC))
    manifest = Manifest.from_rows(
        normalized,
        state,
        source_revision=source_revision,
        schema_revision=schema_revision,
        snapshot_epoch_us=snapshot_epoch_us,
    )
    _ensure_new_file(target)
    connection: sqlite3.Connection | None = None
    try:
        connection = _connect(target)
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA synchronous = FULL")
        _create_schema(
            connection,
            schema_revision=manifest.schema_revision,
            source_revision=manifest.source_revision,
        )
        connection.execute("BEGIN IMMEDIATE")
        connection.executemany(
            "INSERT INTO cipher_operations "
            "(id, created_at, cipher, operation, source, response_mode, input_length, "
            "output_length, http_status, succeeded, duration_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (row.as_sql_values() for row in normalized),
        )
        seed = max(manifest.max_id or 0, manifest.identity_last_issued, 0)
        updated = connection.execute(
            "UPDATE sqlite_sequence SET seq = ? WHERE name = 'cipher_operations'", (seed,)
        ).rowcount
        if updated != 1:
            connection.execute(
                "INSERT INTO sqlite_sequence(name, seq) VALUES ('cipher_operations', ?)", (seed,)
            )
        _set_metadata(
            connection,
            {
                "manifest_digest": manifest.digest,
                "manifest_json": manifest.canonical_bytes().decode("utf-8"),
            },
        )
        connection.commit()
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        if connection is not None:
            connection.close()
    verification = verify_staging(target, expected_manifest=manifest)
    return ImportResult(path=target, manifest=manifest, verification=verification)


def rows_from_sqlite(path: PathInput) -> tuple[HistoryRow, ...]:
    """Read only the eleven history fields from a SQLite file for delta review."""

    target = _path(path)
    _ensure_existing_file(target)
    connection = _connect(target, read_only=True)
    try:
        return _rows_from_connection(connection)
    finally:
        connection.close()


def publish_first(
    staging_path: PathInput,
    runtime_path: PathInput,
    *,
    expected_manifest_digest: str,
    app_stopped: bool,
) -> PublicationResult:
    """Publish a verified staging file without overwriting an existing runtime.

    POSIX has no portable Python ``rename-no-replace`` primitive.  A hard-link
    creation is an atomic directory-entry operation that fails if the destination
    exists; removing the old staging name after that succeeds leaves a safe,
    recoverable result even if the process stops between the two operations.
    """

    staging = _path(staging_path)
    runtime = _path(runtime_path)
    if app_stopped is not True:
        raise PublicationError("application-stopped evidence is required")
    expected_manifest_digest = _validate_digest(expected_manifest_digest)
    if staging.resolve() == runtime.resolve():
        raise PublicationError("staging and runtime must be different files")
    _ensure_existing_file(staging)
    _ensure_parent(runtime)
    if runtime.exists() or runtime.is_symlink():
        raise FileExistsError("runtime database already exists")
    if not _same_filesystem(staging, runtime.parent):
        raise PublicationError("staging and runtime must share a filesystem")
    verified = verify_staging(staging, expected_manifest_digest=expected_manifest_digest)
    try:
        os.link(staging, runtime)
    except FileExistsError:
        raise FileExistsError("runtime database appeared before publication") from None
    except OSError as exc:
        raise PublicationError("atomic no-overwrite publication failed") from exc
    try:
        _fsync_directory(runtime.parent)
        staging.unlink()
        _fsync_directory(runtime.parent)
    except OSError as exc:
        raise PublicationError("publication completed but staging cleanup was not durable") from exc
    return PublicationResult(path=runtime, manifest_digest=verified.manifest.digest)


def replace_runtime(
    staging_path: PathInput,
    runtime_path: PathInput,
    backup_path: PathInput,
    *,
    expected_old_digest: str,
    expected_new_digest: str,
    expected_backup_digest: str | None = None,
    app_stopped: bool,
    confirmation: str,
    backup_verified: bool,
) -> ReplacementResult:
    """Replace a pre-write runtime only after explicit evidence and confirmation.

    The persisted cutover manifest is deliberately immutable.  Any runtime write
    makes its digest diverge, so replacement fails before mutation and the
    operator must use the rollback-delta/manual-remediation path instead.
    """

    staging = _path(staging_path)
    runtime = _path(runtime_path)
    backup = _path(backup_path)
    if app_stopped is not True:
        raise PublicationError("application-stopped evidence is required")
    if confirmation != REPLACEMENT_CONFIRMATION:
        raise PublicationError("explicit replacement confirmation is required")
    if backup_verified is not True:
        raise PublicationError("verified backup evidence is required")
    expected_old_digest = _validate_digest(expected_old_digest, "expected_old_digest")
    expected_new_digest = _validate_digest(expected_new_digest, "expected_new_digest")
    expected_backup_digest = _validate_digest(
        expected_old_digest if expected_backup_digest is None else expected_backup_digest,
        "expected_backup_digest",
    )
    _ensure_existing_file(runtime)
    _ensure_existing_file(staging)
    _ensure_existing_file(backup)
    _ensure_parent(runtime)
    if runtime.resolve() in {staging.resolve(), backup.resolve()}:
        raise PublicationError("replacement paths must be distinct")
    if not _same_filesystem(staging, runtime.parent):
        raise PublicationError("staging and runtime must share a filesystem")
    current = verify_staging(runtime, expected_manifest_digest=expected_old_digest)
    cutover_sequence = max(
        current.manifest.max_id or 0,
        current.manifest.identity_last_issued,
        0,
    )
    if current.sequence != cutover_sequence:
        raise PublicationError(
            "runtime identity advanced after cutover; use rollback delta remediation"
        )
    staged = verify_staging(staging, expected_manifest_digest=expected_new_digest)
    backed_up = verify_staging(backup, expected_manifest_digest=expected_backup_digest)
    try:
        os.replace(staging, runtime)
    except OSError as exc:
        raise PublicationError("atomic runtime replacement failed") from exc
    try:
        _fsync_directory(runtime.parent)
    except OSError as exc:
        raise PublicationError(
            "runtime was replaced but directory durability is uncertain; "
            "do not retry before re-verification"
        ) from exc
    return ReplacementResult(
        path=runtime,
        old_digest=current.manifest.digest,
        new_digest=staged.manifest.digest,
        backup_digest=backed_up.manifest.digest,
    )


def backup_sqlite_live(
    source_path: PathInput,
    destination_path: PathInput,
    *,
    expected_manifest: Manifest | None = None,
    expected_manifest_digest: str | None = None,
    source_revision: str | None = None,
    schema_revision: str | None = None,
    timeout: float = BUSY_TIMEOUT_SECONDS,
) -> BackupEvidence:
    """Create and verify a new SQLite snapshot with ``Connection.backup()``.

    ``expected_manifest_digest`` is an optional optimistic pre-backup guard.  It
    is checked against a freshly read source snapshot when the source has enough
    persisted provenance to make that comparison meaningful; it is not required
    for a live database whose row set has advanced since cutover.  The returned
    ``backup_digest`` always belongs to a newly generated destination manifest.
    """

    if timeout <= 0:
        raise ValueError("backup timeout must be positive")
    source = _path(source_path)
    destination = _path(destination_path)
    _ensure_existing_file(source)
    _ensure_absent(destination)
    if expected_manifest_digest is not None:
        expected_manifest_digest = _validate_digest(expected_manifest_digest)
    source_connection: sqlite3.Connection | None = None
    destination_connection: sqlite3.Connection | None = None
    destination_created = False
    destination_manifest: Manifest | None = None
    try:
        source_connection = _connect(source, read_only=True, timeout=timeout)
        _check_pragma(source_connection, "quick_check")
        _check_pragma(source_connection, "integrity_check")
        _check_schema(source_connection)
        source_provenance, schema_provenance, persisted_manifest = _snapshot_provenance(
            source_connection,
            fallback_manifest=expected_manifest,
            source_revision=source_revision,
            schema_revision=schema_revision,
        )
        source_rows = _rows_from_connection(source_connection)
        source_sequence = _read_sqlite_sequence(source_connection)
        if expected_manifest_digest is not None:
            guard_manifest = persisted_manifest or expected_manifest
            if guard_manifest is None:
                raise VerificationError("pre-backup guard provenance is unavailable")
            guard_identity_source = guard_manifest.identity_source
            if guard_identity_source == "postgresql" and source_sequence == 0:
                guard_identity_source = "sqlite"
            guard = Manifest.from_sqlite_snapshot(
                source_rows,
                source_sequence,
                source_revision=source_provenance,
                schema_revision=schema_provenance,
                snapshot_epoch_us=guard_manifest.snapshot_epoch_us,
                identity_source=guard_identity_source,
            )
            if guard.digest != expected_manifest_digest:
                raise VerificationError("optional pre-backup manifest guard failed")
        _ensure_new_file(destination)
        destination_created = True
        destination_connection = _connect(destination, timeout=timeout)
        source_connection.backup(destination_connection, pages=64, sleep=min(0.05, timeout / 2))
        destination_connection.commit()
        _check_pragma(destination_connection, "quick_check")
        _check_pragma(destination_connection, "integrity_check")
        _check_schema(destination_connection)
        destination_rows = _rows_from_connection(destination_connection)
        destination_sequence = _read_sqlite_sequence(destination_connection)
        destination_source, destination_schema, _ = _snapshot_provenance(
            destination_connection,
            fallback_manifest=expected_manifest,
            source_revision=source_provenance,
            schema_revision=schema_provenance,
        )
        destination_manifest = Manifest.from_sqlite_snapshot(
            destination_rows,
            destination_sequence,
            source_revision=destination_source,
            schema_revision=destination_schema,
            snapshot_epoch_us=datetime_to_epoch_microseconds(datetime.now(UTC)),
        )
        _set_sqlite_sequence(destination_connection, destination_sequence)
        _write_manifest_metadata(destination_connection, destination_manifest)
        destination_connection.commit()
    except Exception:
        if destination_connection is not None:
            destination_connection.rollback()
        if destination_created:
            with suppress(OSError):
                destination.unlink()
        raise
    finally:
        if destination_connection is not None:
            destination_connection.close()
        if source_connection is not None:
            source_connection.close()
    if destination_manifest is None:
        raise VerificationError("backup manifest was not generated")
    try:
        verified = verify_staging(
            destination,
            expected_manifest=destination_manifest,
            expected_manifest_digest=destination_manifest.digest,
        )
    except Exception:
        if destination_created:
            with suppress(OSError):
                destination.unlink()
        raise
    return BackupEvidence(
        source_digest=expected_manifest_digest,
        backup_digest=verified.manifest.digest,
        path=destination,
        verified=True,
    )


def restore_sqlite_backup(
    backup_path: PathInput,
    target_path: PathInput,
    *,
    expected_manifest_digest: str,
    expected_manifest: Manifest | None = None,
    expected_schema_revision: str | None = None,
    runtime_path: PathInput | None = None,
) -> RestoreEvidence:
    """Restore a backup into a new file and verify it without touching runtime."""

    backup = _path(backup_path)
    target = _path(target_path)
    _ensure_existing_file(backup)
    _ensure_absent(target)
    if runtime_path is not None and target.resolve() == _path(runtime_path).resolve():
        raise PublicationError("restore target must be separate from runtime")
    source_report = verify_staging(
        backup,
        expected_manifest=expected_manifest,
        expected_manifest_digest=expected_manifest_digest,
        expected_schema_revision=expected_schema_revision,
    )
    _ensure_new_file(target)
    source_connection: sqlite3.Connection | None = None
    target_connection: sqlite3.Connection | None = None
    try:
        source_connection = _connect(backup, read_only=True)
        target_connection = _connect(target)
        source_connection.backup(target_connection, pages=64, sleep=0.025)
        target_connection.commit()
    except Exception:
        if target_connection is not None:
            target_connection.rollback()
        with suppress(OSError):
            target.unlink()
        raise
    finally:
        if target_connection is not None:
            target_connection.close()
        if source_connection is not None:
            source_connection.close()
    try:
        restored = verify_staging(
            target,
            expected_manifest=source_report.manifest,
            expected_schema_revision=expected_schema_revision,
        )
        # A small read smoke is intentionally separate from digest calculation:
        # it demonstrates that the restored database can serve a normal history read.
        connection = _connect(target, read_only=True)
        try:
            connection.execute(
                "SELECT id, created_at, cipher, operation, source, response_mode, "
                "input_length, output_length, http_status, succeeded, duration_ms "
                "FROM cipher_operations ORDER BY created_at DESC, id DESC LIMIT 1"
            ).fetchone()
        finally:
            connection.close()
    except Exception:
        with suppress(OSError):
            target.unlink()
        raise
    return RestoreEvidence(
        backup_digest=source_report.manifest.digest,
        restored_digest=restored.manifest.digest,
        path=target,
        verified=True,
    )


def _snapshot_input(
    value: PathInput | Iterable[HistoryInput],
) -> tuple[tuple[HistoryRow, ...], int | None]:
    if isinstance(value, (str, os.PathLike)):
        target = _path(value)
        _ensure_existing_file(target)
        connection = _connect(target, read_only=True)
        try:
            return _rows_from_connection(connection), _read_sqlite_sequence(connection)
        finally:
            connection.close()
    return normalize_history_rows(value), None


def rollback_delta_report(
    before: PathInput | Iterable[HistoryInput],
    after: PathInput | Iterable[HistoryInput],
) -> RollbackDeltaReport:
    """Compare snapshots without writing either side or attempting a merge."""

    before_rows, before_sequence = _snapshot_input(before)
    after_rows, after_sequence = _snapshot_input(after)
    before_by_id = {row.id: row for row in before_rows}
    after_by_id = {row.id: row for row in after_rows}
    before_ids = set(before_by_id)
    after_ids = set(after_by_id)
    changed = tuple(
        sorted(
            row_id
            for row_id in before_ids & after_ids
            if before_by_id[row_id] != after_by_id[row_id]
        )
    )
    return RollbackDeltaReport(
        before_count=len(before_rows),
        after_count=len(after_rows),
        added_ids=tuple(sorted(after_ids - before_ids)),
        removed_ids=tuple(sorted(before_ids - after_ids)),
        changed_ids=changed,
        before_id_digest=id_set_digest(before_rows),
        after_id_digest=id_set_digest(after_rows),
        before_row_digest=row_digest(before_rows),
        after_row_digest=row_digest(after_rows),
        before_sequence=before_sequence,
        after_sequence=after_sequence,
    )


def _cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safe history SQLite continuity checks")
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--database", required=True)
    verify.add_argument("--expected-manifest-digest", required=True)
    verify.add_argument("--schema-revision")

    publish = subparsers.add_parser("publish")
    publish.add_argument("--staging", required=True)
    publish.add_argument("--runtime", required=True)
    publish.add_argument("--expected-manifest-digest", required=True)
    publish.add_argument("--app-stopped", action="store_true", required=True)

    replace = subparsers.add_parser("replace")
    replace.add_argument("--staging", required=True)
    replace.add_argument("--runtime", required=True)
    replace.add_argument("--backup", required=True)
    replace.add_argument("--expected-old-digest", required=True)
    replace.add_argument("--expected-new-digest", required=True)
    replace.add_argument(
        "--expected-backup-digest",
        help="digest of the verified backup snapshot; defaults to the old runtime digest",
    )
    replace.add_argument("--app-stopped", action="store_true", required=True)
    replace.add_argument("--backup-verified", action="store_true", required=True)
    replace.add_argument("--confirm", choices=(REPLACEMENT_CONFIRMATION,), required=True)

    backup = subparsers.add_parser("backup")
    backup.add_argument("--source", required=True)
    backup.add_argument("--destination", required=True)
    backup.add_argument(
        "--expected-manifest-digest",
        help="optional optimistic pre-backup guard; not required after the live DB advances",
    )

    restore = subparsers.add_parser("restore")
    restore.add_argument("--backup", required=True)
    restore.add_argument("--target", required=True)
    restore.add_argument("--expected-manifest-digest", required=True)
    restore.add_argument("--schema-revision")

    delta = subparsers.add_parser("delta")
    delta.add_argument("--before", required=True)
    delta.add_argument("--after", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the safe continuity CLI; no retirement/destructive command exists."""

    args = _cli_parser().parse_args(argv)
    try:
        if args.command == "verify":
            report = verify_staging(
                args.database,
                expected_manifest_digest=args.expected_manifest_digest,
                expected_schema_revision=args.schema_revision,
            )
            print(json.dumps({"ok": True, "manifestDigest": report.manifest.digest}))
        elif args.command == "publish":
            result = publish_first(
                args.staging,
                args.runtime,
                expected_manifest_digest=args.expected_manifest_digest,
                app_stopped=args.app_stopped,
            )
            print(json.dumps({"ok": True, "manifestDigest": result.manifest_digest}))
        elif args.command == "replace":
            result = replace_runtime(
                args.staging,
                args.runtime,
                args.backup,
                expected_old_digest=args.expected_old_digest,
                expected_new_digest=args.expected_new_digest,
                expected_backup_digest=args.expected_backup_digest,
                app_stopped=args.app_stopped,
                confirmation=args.confirm,
                backup_verified=args.backup_verified,
            )
            print(json.dumps({"ok": True, "manifestDigest": result.new_digest}))
        elif args.command == "backup":
            result = backup_sqlite_live(
                args.source,
                args.destination,
                expected_manifest_digest=args.expected_manifest_digest,
            )
            print(json.dumps({"ok": result.verified, "manifestDigest": result.backup_digest}))
        elif args.command == "restore":
            result = restore_sqlite_backup(
                args.backup,
                args.target,
                expected_manifest_digest=args.expected_manifest_digest,
                expected_schema_revision=args.schema_revision,
            )
            print(json.dumps({"ok": result.verified, "manifestDigest": result.restored_digest}))
        else:
            report = rollback_delta_report(args.before, args.after)
            print(report.to_json())
        return 0
    except (ContinuityError, OSError, sqlite3.Error, ValueError, TypeError):
        # Exception text can contain filesystem paths or SQLite details.  Keep
        # the operator-facing failure deliberately generic and redacted.
        print("history continuity command failed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BUSY_TIMEOUT_SECONDS",
    "CIPHERS",
    "FORMAT_VERSION",
    "HISTORY_COLUMNS",
    "IDS_STREAM_HEADER",
    "MAX_ROW_ID",
    "OPERATIONS",
    "REPLACEMENT_CONFIRMATION",
    "ROWS_STREAM_HEADER",
    "SOURCES",
    "STAGING_SCHEMA_SQL",
    "ContinuityError",
    "HistoryRow",
    "IdentityState",
    "ImportResult",
    "InvalidHistoryRow",
    "Manifest",
    "PathInput",
    "PublicationError",
    "ReplacementResult",
    "RestoreEvidence",
    "RollbackDeltaReport",
    "UnsupportedSequenceState",
    "VerificationError",
    "VerificationReport",
    "backup_sqlite_live",
    "canonical_id_set_bytes",
    "canonical_row_bytes",
    "canonical_rows_bytes",
    "datetime_to_epoch_microseconds",
    "derive_last_issued_high_water",
    "epoch_microseconds_to_datetime",
    "id_set_digest",
    "import_staging",
    "main",
    "normalize_history_row",
    "normalize_history_rows",
    "publish_first",
    "replace_runtime",
    "restore_sqlite_backup",
    "rollback_delta_report",
    "row_digest",
    "rows_from_sqlite",
    "verify_staging",
]
