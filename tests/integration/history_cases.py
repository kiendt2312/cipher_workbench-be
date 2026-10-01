"""One valid request for each of the 20 recorded cipher transform routes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MARKER_TEXT = "SECRETMARKERWORDS"
PLAYFAIR_CIPHERTEXT = "BMODZBXDNAGE"
DES_KEY = "133457799BBCDFF1"
DES_CIPHERTEXT = "864A9843D0DBB9DAE1B098BC5A766C603F6139AE5DDDE941"  # MARKER_TEXT, ECB

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
SENSITIVE_VALUES = (
    MARKER_TEXT,
    "HILLSENSITIVE",
    "DPLE",
    "HELP",
    "[[3,3],[2,5]]",
    "ZEBRA",
    "marker-name",
    DES_KEY,
    DES_CIPHERTEXT[:16],
)


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
    for operation, text in (("encrypt", "HILLSENSITIVE"), ("decrypt", "DPLE")):
        requests.append(
            CipherRequest(
                "hill",
                "text",
                operation,
                f"/api/hill/{operation}",
                {"json": {"text": text, "key": [[3, 3], [2, 5]]}},
            )
        )
    for operation, text in (("encrypt", MARKER_TEXT), ("decrypt", DES_CIPHERTEXT)):
        requests.append(
            CipherRequest(
                "des",
                "text",
                operation,
                f"/api/des/{operation}",
                {"json": {"text": text, "key": DES_KEY}},
            )
        )
    requests.append(
        CipherRequest(
            "des",
            "file",
            "encrypt",
            "/api/des/file",
            {
                "data": {"key": DES_KEY, "action": "encrypt", "response_mode": "file"},
                "files": {"file": ("marker-name.txt", MARKER_TEXT.encode(), "text/plain")},
            },
        )
    )
    return requests
