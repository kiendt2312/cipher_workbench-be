"""HTTP middleware for server-issued anonymous private-history credentials."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from http.cookies import SimpleCookie

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app import config
from app.history.routes import CIPHER_ROUTES

OWNER_STATE_KEY = "history_owner_id"
_TOKEN = re.compile(r"([A-Za-z0-9_-]{43})\.([A-Za-z0-9_-]{43})", re.ASCII)


def owner_id_for_token(token: str) -> str:
    """Return the non-secret database identifier for a 256-bit bearer token."""

    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _signature(nonce: str) -> str:
    import base64

    digest = hmac.digest(config.history_profile_signing_key(), nonce.encode("ascii"), "sha256")
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def profile_token_for_nonce(nonce: str) -> str:
    """Sign one canonical 256-bit profile nonce."""

    if re.fullmatch(r"[A-Za-z0-9_-]{43}", nonce, re.ASCII) is None:
        raise ValueError("profile nonce must be canonical URL-safe base64")
    return f"{nonce}.{_signature(nonce)}"


def issue_profile_token() -> str:
    """Issue a self-authenticating, unguessable anonymous profile credential."""

    return profile_token_for_nonce(secrets.token_urlsafe(32))


def _valid_token(token: str | None) -> bool:
    if token is None:
        return False
    match = _TOKEN.fullmatch(token)
    return bool(match and hmac.compare_digest(match.group(2), _signature(match.group(1))))


def _request_cookie(scope: Scope) -> str | None:
    values = [
        value.decode("latin-1")
        for name, value in scope.get("headers", [])
        if name.lower() == b"cookie"
    ]
    if len(values) != 1:
        return None
    parsed = SimpleCookie()
    try:
        parsed.load(values[0])
    except Exception:
        return None
    morsel = parsed.get(config.HISTORY_COOKIE_NAME)
    token = morsel.value if morsel is not None else None
    return token if _valid_token(token) else None


def _set_cookie_header(token: str) -> bytes:
    cookie = SimpleCookie()
    cookie[config.HISTORY_COOKIE_NAME] = token
    morsel = cookie[config.HISTORY_COOKIE_NAME]
    morsel["path"] = "/"
    morsel["max-age"] = str(config.HISTORY_COOKIE_MAX_AGE_SECONDS)
    morsel["httponly"] = True
    morsel["samesite"] = "Lax"
    if config.history_cookie_secure():
        morsel["secure"] = True
    return morsel.OutputString().encode("latin-1")


def _in_scope(scope: Scope) -> bool:
    if scope.get("type") != "http":
        return False
    path = scope.get("path", "")
    return (
        path in CIPHER_ROUTES
        or path.startswith("/api/history")
        or path
        in {
            "/api/rsa/sign/raw",
            "/api/rsa/verify/raw",
            "/api/rsa/sign",
            "/api/rsa/verify",
        }
    )


class HistoryProfileMiddleware:
    """Resolve only server-issued profile tokens and expose their hash to handlers."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not _in_scope(scope):
            await self.app(scope, receive, send)
            return

        token = _request_cookie(scope)
        recognized = token is not None
        if token is None:
            token = issue_profile_token()
        owner_id = owner_id_for_token(token)
        assert token is not None and owner_id is not None
        scope.setdefault("state", {})[OWNER_STATE_KEY] = owner_id

        async def send_with_cookie(message: Message) -> None:
            if message["type"] == "http.response.start" and not recognized:
                headers = list(message.get("headers", []))
                headers.append((b"set-cookie", _set_cookie_header(token)))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_cookie)
