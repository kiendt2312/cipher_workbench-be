"""The fixed set of cipher routes whose requests are recorded in history."""

from __future__ import annotations

from dataclasses import dataclass

from app.db.models import CIPHERS


@dataclass(frozen=True)
class CipherRoute:
    cipher: str
    source: str
    operation: str | None  # ``None`` for file routes, where ``action`` is in the form body.


def _routes_for(cipher: str) -> dict[str, CipherRoute]:
    prefix = f"/api/{cipher}"
    return {
        f"{prefix}/encrypt": CipherRoute(cipher, "text", "encrypt"),
        f"{prefix}/decrypt": CipherRoute(cipher, "text", "decrypt"),
        f"{prefix}/file": CipherRoute(cipher, "file", None),
    }


CIPHER_ROUTES: dict[str, CipherRoute] = {
    path: route
    for cipher in CIPHERS
    for path, route in _routes_for(cipher).items()
    if cipher != "hill" or route.source == "text"
}


def match_cipher_route(method: str, path: str) -> CipherRoute | None:
    """Return the recorded route for a cipher ``POST``, or ``None`` for anything else."""

    return CIPHER_ROUTES.get(path) if method == "POST" else None
