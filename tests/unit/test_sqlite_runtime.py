"""Focused tests for the SQLite runtime boundary and value codecs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import config
from app.db.types import (
    Boolean01,
    EpochMicrosecondUTC,
    datetime_to_epoch_microseconds,
    epoch_microseconds_to_datetime,
)


def _url(path: Path) -> str:
    return f"sqlite+aiosqlite:////{path.as_posix().lstrip('/')}"


def test_database_url_rejects_non_sqlite_and_memory_urls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for value in (
        "postgresql+asyncpg://user:secret@db/history",
        "sqlite+aiosqlite:///:memory:",
        "sqlite+aiosqlite:///relative.sqlite3",
    ):
        monkeypatch.setenv("DATABASE_URL", value)
        with pytest.raises(ValueError, match="absolute local SQLite file URL") as error:
            config.database_url()
        assert "secret" not in str(error.value)
        assert str(tmp_path) not in str(error.value)


def test_database_url_rejects_symlinked_database_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "target.sqlite3"
    link = tmp_path / "link.sqlite3"
    link.symlink_to(target)
    monkeypatch.setenv("DATABASE_URL", _url(link))
    with pytest.raises(ValueError, match="absolute local SQLite file URL"):
        config.database_url()


def test_linux_database_url_fails_closed_when_mount_is_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(config.sys, "platform", "linux")
    monkeypatch.setattr(config, "_filesystem_type", lambda _path: None)
    monkeypatch.setenv("DATABASE_URL", _url(tmp_path / "history.sqlite3"))

    with pytest.raises(ValueError, match="absolute local SQLite file URL"):
        config.database_url()


def test_linux_database_url_rejects_known_remote_mount(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(config.sys, "platform", "linux")
    monkeypatch.setattr(config, "_filesystem_type", lambda _path: "nfs4")
    monkeypatch.setenv("DATABASE_URL", _url(tmp_path / "history.sqlite3"))

    with pytest.raises(ValueError, match="absolute local SQLite file URL"):
        config.database_url()


@pytest.mark.parametrize("filesystem", ["ramfs", "tmpfs"])
def test_linux_database_url_rejects_ephemeral_mounts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, filesystem: str
) -> None:
    monkeypatch.setattr(config.sys, "platform", "linux")
    monkeypatch.setattr(config, "_filesystem_type", lambda _path: filesystem)
    monkeypatch.setenv("DATABASE_URL", _url(tmp_path / "history.sqlite3"))

    with pytest.raises(ValueError, match="absolute local SQLite file URL"):
        config.database_url()


def test_database_url_rejects_unwritable_parent_without_leaking_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    secret_path = tmp_path / "operator-private" / "history.sqlite3"
    secret_path.parent.mkdir()
    monkeypatch.setattr(config.os, "access", lambda _path, _mode: False)
    monkeypatch.setenv("DATABASE_URL", _url(secret_path))

    with pytest.raises(ValueError, match="absolute local SQLite file URL") as error:
        config.database_url()
    assert str(secret_path) not in str(error.value)


def test_non_linux_runtime_does_not_apply_linux_mountinfo_gate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(config.sys, "platform", "darwin")
    monkeypatch.setattr(config, "_filesystem_type", lambda _path: None)
    path = tmp_path / "history.sqlite3"
    monkeypatch.setenv("DATABASE_URL", _url(path))

    assert config.sqlite_database_path(config.database_url()) == path


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (datetime(1970, 1, 1, tzinfo=UTC), 0),
        (datetime(1969, 12, 31, 23, 59, 59, 999999, tzinfo=UTC), -1),
        (
            datetime(2026, 10, 7, 8, 0, 0, 123456, tzinfo=timezone(timedelta(hours=7))),
            1_791_334_800_123456,
        ),
    ],
)
def test_epoch_microsecond_codec_preserves_utc_precision(value: datetime, expected: int) -> None:
    encoded = datetime_to_epoch_microseconds(value)
    assert encoded == expected
    assert epoch_microseconds_to_datetime(encoded) == value.astimezone(UTC)


def test_epoch_microsecond_codec_rejects_naive_and_invalid_values() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        datetime_to_epoch_microseconds(datetime(2026, 10, 7))
    with pytest.raises(ValueError, match="supported range"):
        epoch_microseconds_to_datetime(2**63)


def test_sqlalchemy_sqlite_type_decorators_preserve_none_and_boolean_values() -> None:
    timestamp_type = EpochMicrosecondUTC()
    timestamp = datetime(2026, 10, 7, 1, 2, 3, 456789, tzinfo=UTC)
    encoded = timestamp_type.process_bind_param(timestamp, object())
    assert encoded == datetime_to_epoch_microseconds(timestamp)
    assert timestamp_type.process_result_value(encoded, object()) == timestamp
    assert timestamp_type.process_bind_param(None, object()) is None
    assert timestamp_type.process_result_value(None, object()) is None

    boolean_type = Boolean01()
    assert boolean_type.process_bind_param(True, object()) == 1
    assert boolean_type.process_bind_param(False, object()) == 0
    assert boolean_type.process_bind_param(None, object()) is None
    assert boolean_type.process_result_value(1, object()) is True
    assert boolean_type.process_result_value(0, object()) is False
    assert boolean_type.process_result_value(None, object()) is None
