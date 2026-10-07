"""Application-wide configuration constants."""

import os
import re
import sys
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

MAX_FILE_BYTES = 5242880  # 5242880 byte = 5 MiB
MAX_REQUEST_BYTES = 64 * 1024 * 1024
ALLOWED_EXTENSION = ".txt"
CHUNK_SIZE = 64 * 1024
PORT = 8000

DATABASE_CONFIGURATION_ERROR = "DATABASE_URL must be an absolute local SQLite file URL"
SQLITE_DRIVER = "sqlite+aiosqlite"
SQLITE_SCHEMA_REVISION = "sqlite_0001"

_REMOTE_FILESYSTEMS = {
    "9p",
    "afs",
    "cifs",
    "ceph",
    "davfs",
    "fuse.sshfs",
    "gfs2",
    "glusterfs",
    "lustre",
    "ncp",
    "nfs",
    "nfs4",
    "ocfs2",
    "smb3",
    "smbfs",
}
_LOCAL_FILESYSTEMS = {
    "apfs",
    "btrfs",
    "ext2",
    "ext3",
    "ext4",
    "f2fs",
    "hfs",
    "ntfs",
    "overlay",
    "squashfs",
    "vfat",
    "xfs",
    "zfs",
}


def parse_bounded_int(raw: str, low: int, high: int) -> int | None:
    """Return ``raw`` as an int when it is ASCII digits within ``low..high``, else ``None``."""

    if not (raw.isascii() and raw.isdigit()):
        return None
    value = int(raw)
    return value if low <= value <= high else None


def _mountinfo_unescape(value: str) -> str:
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), value)


def _filesystem_type(path: Path) -> str | None:
    """Return the Linux filesystem type for ``path`` when mountinfo can identify it."""

    if not sys.platform.startswith("linux"):
        return None
    try:
        lines = Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return None

    best_mount: Path | None = None
    best_type: str | None = None
    for line in lines:
        try:
            left, right = line.split(" - ", 1)
            fields = left.split()
            mount_point = Path(_mountinfo_unescape(fields[4]))
            filesystem = right.split()[0]
        except (IndexError, ValueError):
            continue
        if (path == mount_point or mount_point in path.parents) and (
            best_mount is None or len(mount_point.parts) > len(best_mount.parts)
        ):
            best_mount = mount_point
            best_type = filesystem
    return best_type


def _contains_symlink(path: Path) -> bool:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            return True
    return False


def _validated_sqlite_path(raw_url: str) -> Path:
    try:
        parsed = urlsplit(raw_url)
        database = unquote(parsed.path[1:]) if parsed.path.startswith("/") else ""
        if (
            parsed.scheme != SQLITE_DRIVER
            or parsed.netloc
            or parsed.query
            or parsed.fragment
            or not parsed.path.startswith("/")
        ):
            raise ValueError
        path = Path(database)
        if not database or database == ":memory:" or database.startswith("file:"):
            raise ValueError
        if not path.is_absolute() or "\x00" in database:
            raise ValueError
        if _contains_symlink(path):
            raise ValueError
        path = path.resolve(strict=False)
        if not path.parent.is_dir() or not os.access(path.parent, os.R_OK | os.W_OK | os.X_OK):
            raise ValueError
        filesystem = _filesystem_type(path.parent)
        if sys.platform.startswith("linux"):
            if filesystem is None or filesystem in _REMOTE_FILESYSTEMS:
                raise ValueError
            if filesystem not in _LOCAL_FILESYSTEMS:
                raise ValueError
        elif filesystem in _REMOTE_FILESYSTEMS:
            raise ValueError
        return path
    except (OSError, TypeError, ValueError):
        raise ValueError(DATABASE_CONFIGURATION_ERROR) from None


def sqlite_database_path(url: str) -> Path:
    """Return the canonical path for a validated SQLite runtime URL."""

    return _validated_sqlite_path(url)


def sqlite_runtime_url(path: Path) -> str:
    """Build a SQLite URI that opens an existing file without creating it."""

    encoded_path = quote(path.as_posix(), safe="/")
    return f"{SQLITE_DRIVER}:///file:{encoded_path}?mode=rw&uri=true"


def database_url() -> str | None:
    """Return the canonical SQLite URL; ``None`` disables history storage."""

    raw_url = os.environ.get("DATABASE_URL", "").strip()
    if not raw_url:
        return None
    path = _validated_sqlite_path(raw_url)
    return f"{SQLITE_DRIVER}:///{quote(path.as_posix(), safe='/')}"


_TRUE_VALUES = {"true", "1", "yes", "on"}
DEFAULT_HISTORY_RETENTION_DAYS = 30
MAX_HISTORY_RETENTION_DAYS = 3650


def history_api_enabled() -> bool:
    """Return whether ``GET /api/history`` is served; off unless explicitly enabled."""

    return os.environ.get("HISTORY_API_ENABLED", "").strip().lower() in _TRUE_VALUES


_ORIGIN_PATTERN = re.compile(r"https?://[^/\s*]+")


def cors_allow_origins() -> tuple[str, ...]:
    """Return the exact origins in ``CORS_ALLOW_ORIGINS`` (comma separated); empty disables CORS."""

    raw = os.environ.get("CORS_ALLOW_ORIGINS", "")
    origins = tuple(origin.strip() for origin in raw.split(",") if origin.strip())
    for origin in origins:
        if not _ORIGIN_PATTERN.fullmatch(origin):
            raise ValueError(
                "CORS_ALLOW_ORIGINS must list exact origins such as https://app.example.com"
            )
    return origins


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
