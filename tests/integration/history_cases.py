"""One valid request for each of the 15 recorded cipher routes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MARKER_TEXT = "SECRETMARKERWORDS"
PLAYFAIR_CIPHERTEXT = "BMODZBXDNAGE"

TEXT_KEYS: dict[str, dict[str, Any]] = {
    "caesar": {"key": 3},
    "vigenere": {"key": "ZEBRAKEY"},
    "playfair": {"key": "ZEBRA KEYWORD"},
    "affine": {"a": 5, "b": 8},
    "columnar": {"key": "ZEBRAKEY"},
}
FILE_KEYS: dict[str, dict[str, str]] = {
    "caesar": {"key": "3"},
    "vigenere": {"key": "ZEBRAKEY"},
    "playfair": {"key": "ZEBRA KEYWORD"},
    "affine": {"a": "5", "b": "8"},
    "columnar": {"key": "ZEBRAKEY"},
}
SENSITIVE_VALUES = (MARKER_TEXT, "ZEBRA", "marker-name")


@dataclass(frozen=True)
class CipherRequest:
    cipher: str
    source: str
    operation: str
    path: str
    kwargs: dict[str, Any] = field(default_factory=dict)


def cipher_requests() -> list[CipherRequest]:
    requests: list[CipherRequest] = []
    for cipher, key in TEXT_KEYS.items():
        for operation in ("encrypt", "decrypt"):
            text = (
                PLAYFAIR_CIPHERTEXT
                if cipher == "playfair" and operation == "decrypt"
                else MARKER_TEXT
            )
            requests.append(
                CipherRequest(
                    cipher,
                    "text",
                    operation,
                    f"/api/{cipher}/{operation}",
                    {"json": {"text": text, **key}},
                )
            )
        requests.append(
            CipherRequest(
                cipher,
                "file",
                "encrypt",
                f"/api/{cipher}/file",
                {
                    "data": {**FILE_KEYS[cipher], "action": "encrypt", "response_mode": "file"},
                    "files": {"file": ("marker-name.txt", MARKER_TEXT.encode(), "text/plain")},
                },
            )
        )
    return requests
