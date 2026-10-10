import ast
from pathlib import Path

import pytest

from app import config

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_application_constants_match_approved_structure() -> None:
    assert config.MAX_FILE_BYTES == 5 * 1024 * 1024
    assert config.MAX_REQUEST_BYTES == 64 * 1024 * 1024
    assert config.ALLOWED_EXTENSION == ".txt"
    assert config.CHUNK_SIZE == 64 * 1024
    assert config.PORT == 8000


def test_file_size_threshold_literal_has_one_implementation_source() -> None:
    occurrences: list[Path] = []

    for source_root in (PROJECT_ROOT / "app", PROJECT_ROOT / "tests"):
        for path in source_root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            if any(
                isinstance(node, ast.Constant) and node.value == config.MAX_FILE_BYTES
                for node in ast.walk(tree)
            ):
                occurrences.append(path.relative_to(PROJECT_ROOT))

    assert occurrences == [Path("app/config.py")]


def test_file_limit_comment_states_the_exact_binary_size() -> None:
    source = (PROJECT_ROOT / "app/config.py").read_text(encoding="utf-8")
    assert "5242880 byte = 5 MiB" in source


def test_persistent_history_requires_a_valid_256_bit_profile_signing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(config.HISTORY_PROFILE_SIGNING_KEY_ENV, raising=False)
    with pytest.raises(ValueError, match="required"):
        config.history_profile_signing_key(database_enabled=True)
    assert len(config.history_profile_signing_key(database_enabled=False)) == 32

    monkeypatch.setenv(config.HISTORY_PROFILE_SIGNING_KEY_ENV, "not-hex")
    with pytest.raises(ValueError, match="64 hexadecimal"):
        config.history_profile_signing_key(database_enabled=True)

    monkeypatch.setenv(config.HISTORY_PROFILE_SIGNING_KEY_ENV, "ab" * 32)
    assert config.history_profile_signing_key(database_enabled=True) == bytes.fromhex("ab" * 32)
