"""Application-wide configuration constants."""

import os

MAX_FILE_BYTES = 5242880  # 5242880 byte = 5 MiB
MAX_REQUEST_BYTES = 64 * 1024 * 1024
ALLOWED_EXTENSION = ".txt"
CHUNK_SIZE = 64 * 1024
PORT = 8000


def database_url() -> str | None:
    """Return the PostgreSQL URL from ``DATABASE_URL``; ``None`` disables the database."""

    return os.environ.get("DATABASE_URL", "").strip() or None
