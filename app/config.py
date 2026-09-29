"""Application-wide configuration constants."""

import os

MAX_FILE_BYTES = 5242880  # 5242880 byte = 5 MiB
MAX_REQUEST_BYTES = 64 * 1024 * 1024
ALLOWED_EXTENSION = ".txt"
CHUNK_SIZE = 64 * 1024
PORT = 8000


def parse_bounded_int(raw: str, low: int, high: int) -> int | None:
    """Return ``raw`` as an int when it is ASCII digits within ``low..high``, else ``None``."""

    if not (raw.isascii() and raw.isdigit()):
        return None
    value = int(raw)
    return value if low <= value <= high else None


def database_url() -> str | None:
    """Return the PostgreSQL URL from ``DATABASE_URL``; ``None`` disables the database."""

    return os.environ.get("DATABASE_URL", "").strip() or None


_TRUE_VALUES = {"true", "1", "yes", "on"}
DEFAULT_HISTORY_RETENTION_DAYS = 30
MAX_HISTORY_RETENTION_DAYS = 3650


def history_api_enabled() -> bool:
    """Return whether ``GET /api/history`` is served; off unless explicitly enabled."""

    return os.environ.get("HISTORY_API_ENABLED", "").strip().lower() in _TRUE_VALUES


def history_retention_days() -> int:
    """Return ``HISTORY_RETENTION_DAYS`` (1 to 3650, default 30); invalid values raise."""

    raw = os.environ.get("HISTORY_RETENTION_DAYS", "").strip()
    if not raw:
        return DEFAULT_HISTORY_RETENTION_DAYS
    days = parse_bounded_int(raw, 1, MAX_HISTORY_RETENTION_DAYS)
    if days is None:
        raise ValueError(
            f"HISTORY_RETENTION_DAYS must be an integer from 1 to {MAX_HISTORY_RETENTION_DAYS}"
        )
    return days
