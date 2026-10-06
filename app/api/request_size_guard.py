"""Pure-ASGI guards for request size and multipart framing."""

from collections.abc import Iterable
from email.message import Message

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.types import Message as ASGIMessage

from app import config
from app.errors import messages

FILE_ROUTE_PATHS = frozenset(
    {
        "/api/caesar/file",
        "/api/vigenere/file",
        "/api/playfair/file",
        "/api/affine/file",
        "/api/columnar/file",
        "/api/des/file",
    }
)
RSA_ROUTE_PATHS = frozenset(
    {
        "/api/rsa/keys",
        "/api/rsa/keys/random",
        "/api/rsa/encrypt",
        "/api/rsa/decrypt",
    }
)
MULTIPART_ROUTE_PATHS = FILE_ROUTE_PATHS | {"/api/rsa/encrypt"}


def _content_length(scope: Scope) -> bytes | None:
    """Return the sole Content-Length value, or None when it is unusable."""

    values = [value for name, value in _headers(scope) if name.lower() == b"content-length"]
    if len(values) != 1:
        return None
    return values[0]


def _headers(scope: Scope) -> Iterable[tuple[bytes, bytes]]:
    headers = scope.get("headers", [])
    return headers if isinstance(headers, list) else []


def _header(scope: Scope, target: bytes) -> bytes | None:
    values = [value for name, value in _headers(scope) if name.lower() == target]
    return values[0] if len(values) == 1 else None


def _multipart_boundary(scope: Scope) -> bytes | None:
    """Return the declared multipart boundary for the file endpoint, if any."""

    if scope.get("method") != "POST" or scope.get("path") not in MULTIPART_ROUTE_PATHS:
        return None

    content_type = _header(scope, b"content-type")
    if content_type is None:
        return None

    parsed = Message()
    parsed["content-type"] = content_type.decode("latin-1")
    if parsed.get_content_type() != "multipart/form-data":
        return None

    boundary = parsed.get_param("boundary")
    if not isinstance(boundary, str) or boundary == "":
        return None
    try:
        return boundary.encode("ascii")
    except UnicodeEncodeError:
        return None


def _exceeds_limit(value: bytes | None, max_bytes: int) -> bool:
    """Return whether an ASCII nonnegative decimal value exceeds ``max_bytes``."""

    if value is None:
        return False

    decimal = value.strip(b" \t")
    if not decimal or any(byte < 48 or byte > 57 for byte in decimal):
        return False

    significant = decimal.lstrip(b"0") or b"0"
    limit = str(max_bytes).encode("ascii")
    return len(significant) > len(limit) or (len(significant) == len(limit) and significant > limit)


def _request_too_large_message(scope: Scope) -> str:
    """Select the public 413 message from the route, never from Content-Type."""

    if scope.get("path") in FILE_ROUTE_PATHS:
        return messages.FILE_TOO_LARGE
    return messages.REQUEST_TOO_LARGE


class RequestSizeGuard:
    """Reject over-ceiling Content-Length values before downstream body access."""

    def __init__(self, app: ASGIApp, max_bytes: int = config.MAX_REQUEST_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not _exceeds_limit(_content_length(scope), self.max_bytes):
            await self.app(scope, receive, send)
            return

        if scope.get("path") in RSA_ROUTE_PATHS:
            content = {
                "success": False,
                "code": "REQUEST_TOO_LARGE",
                "message": messages.RSA_REQUEST_TOO_LARGE,
                "field": None,
            }
        else:
            content = {"success": False, "message": _request_too_large_message(scope)}
        response = JSONResponse(status_code=413, content=content)
        await response(scope, receive, send)


class MultipartCompletionGuard:
    """Record whether a file request ends with its declared closing boundary.

    ``python-multipart`` intentionally tolerates some truncated bodies.  The
    public API contract does not: an unreadable multipart body must fail before
    field validation.  This guard inspects only a bounded tail while forwarding
    every body chunk unchanged to Starlette's streaming parser.
    """

    SCOPE_KEY = "request.multipart_complete"

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        boundary = _multipart_boundary(scope) if scope["type"] == "http" else None
        if boundary is None:
            await self.app(scope, receive, send)
            return

        closing = b"--" + boundary + b"--"
        tail = b""
        scope[self.SCOPE_KEY] = False

        async def receive_with_completion_check() -> ASGIMessage:
            nonlocal tail
            message = await receive()
            if message["type"] != "http.request":
                return message

            # Keep enough context for the CRLF before the delimiter and the
            # optional CRLF after it.  Matching the token alone would let a
            # field value ending in ``--<boundary>--`` impersonate framing.
            tail = (tail + message.get("body", b""))[-(len(closing) + 4) :]
            if not message.get("more_body", False):
                scope[self.SCOPE_KEY] = (
                    tail in (closing, closing + b"\r\n")
                    or tail.endswith(b"\r\n" + closing)
                    or tail.endswith(b"\r\n" + closing + b"\r\n")
                )
            return message

        await self.app(scope, receive_with_completion_check, send)
