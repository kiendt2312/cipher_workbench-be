"""Framework-independent file byte processing helpers."""

from __future__ import annotations

from typing import Protocol
from unicodedata import normalize
from urllib.parse import quote

from app import config
from app.errors.exceptions import FileReadError, FileTooLargeError, UnsupportedEncodingError

UTF8_BOM = b"\xef\xbb\xbf"


class AsyncByteReader(Protocol):
    """The small async reader interface required by :func:`read_limited_bytes`."""

    async def read(self, size: int) -> bytes:
        """Read at most ``size`` bytes, returning ``b""`` at EOF."""


async def read_limited_bytes(
    reader: AsyncByteReader,
    max_bytes: int = config.MAX_FILE_BYTES,
) -> bytes:
    """Read bytes in fixed-size chunks and stop at the first byte over the limit.

    Only the reader's async ``read`` method is required.  The buffer is capped at
    ``max_bytes + 1`` so the caller can distinguish an exact-limit file from an
    oversized one without retaining any further input.
    """

    buffered = bytearray()
    while True:
        try:
            chunk = await reader.read(config.CHUNK_SIZE)
            if not isinstance(chunk, bytes):
                raise TypeError("file reader must return bytes")
        except Exception as exc:
            raise FileReadError() from exc

        if chunk == b"":
            return bytes(buffered)

        room = max_bytes + 1 - len(buffered)
        if len(chunk) >= room:
            buffered.extend(chunk[:room])
            raise FileTooLargeError()
        buffered.extend(chunk)


def decode_file_bytes(raw: bytes) -> tuple[str, bool]:
    """Decode complete file bytes once and return text plus leading-BOM state."""

    had_bom = raw.startswith(UTF8_BOM)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UnsupportedEncodingError() from exc
    return text, had_bom


def build_attachment_body(result: str, had_bom: bool) -> bytes:
    """Encode a transformed result, restoring a BOM only when the input had one."""

    encoded = result.encode("utf-8")
    return UTF8_BOM + encoded if had_bom else encoded


def result_byte_length(result: str, had_bom: bool) -> int:
    """Byte size of the result file, including the BOM restored for the attachment."""

    return len(result.encode("utf-8")) + (len(UTF8_BOM) if had_bom else 0)


def has_allowed_extension(filename: str | None) -> bool:
    """Return whether ``filename`` ends in the allowed extension, ignoring case."""

    return isinstance(filename, str) and filename.lower().endswith(config.ALLOWED_EXTENSION)


def _basename(filename: str) -> str:
    return filename.replace("\\", "/").rsplit("/", 1)[-1]


def build_result_filename(original_filename: str, action: str) -> str:
    """Build the result name by removing only the final case-insensitive ``.txt``."""

    if action not in ("encrypt", "decrypt"):
        raise ValueError("action must be 'encrypt' or 'decrypt'")

    filename = _basename(original_filename)
    stem = (
        filename[: -len(config.ALLOWED_EXTENSION)] if has_allowed_extension(filename) else filename
    )
    suffix = "encrypted" if action == "encrypt" else "decrypted"
    return f"{stem}.{suffix}{config.ALLOWED_EXTENSION}"


def _safe_header_filename(filename: str) -> str:
    basename = _basename(filename)
    safe = "".join(
        "_" if ord(char) < 0x20 or 0x7F <= ord(char) <= 0x9F else char for char in basename
    )
    return safe or "result.txt"


def build_content_disposition(filename: str) -> str:
    """Return a safe RFC 6266 attachment header for a result filename."""

    safe_name = _safe_header_filename(filename)
    ascii_name = normalize("NFKD", safe_name).encode("ascii", "ignore").decode() or "result.txt"
    quoted_name = ascii_name.replace("\\", "\\\\").replace('"', '\\"')
    header = f'attachment; filename="{quoted_name}"'
    if ascii_name != safe_name:
        encoded_name = quote(safe_name, safe="!#$&+-.^_`|~")
        header += f"; filename*=UTF-8''{encoded_name}"
    return header
