"""Direct ASGI tests for the early Content-Length abuse ceiling."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable

import pytest
from starlette.types import Message, Receive, Scope, Send

from app import config
from app.api.request_size_guard import FILE_ROUTE_PATHS, MultipartCompletionGuard, RequestSizeGuard
from app.errors import messages
from app.main import app

ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


def _scope(
    headers: list[tuple[bytes, bytes]],
    path: str = "/api/caesar/file",
) -> Scope:
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("testclient", 1234),
        "server": ("testserver", 80),
    }


def _run_asgi(
    asgi_app: ASGIApp,
    headers: list[tuple[bytes, bytes]],
    path: str = "/api/caesar/file",
) -> tuple[list[Message], int]:
    events: list[Message] = []
    receive_calls = 0

    async def receive() -> Message:
        nonlocal receive_calls
        receive_calls += 1
        return {"type": "http.request", "body": b"request body", "more_body": False}

    async def send(message: Message) -> None:
        events.append(message)

    asyncio.run(asgi_app(_scope(headers, path), receive, send))
    return events, receive_calls


def _downstream_with_body_observation(called: list[bool], received: list[Message]) -> ASGIApp:
    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        del scope
        called.append(True)
        received.append(await receive())
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"downstream"})

    return downstream


def _response_body(events: list[Message]) -> bytes:
    return next(event["body"] for event in events if event["type"] == "http.response.body")


def test_over_ceiling_is_rejected_before_downstream_or_body_receive() -> None:
    called: list[bool] = []
    received: list[Message] = []
    guard = RequestSizeGuard(
        _downstream_with_body_observation(called, received),
        max_bytes=config.MAX_REQUEST_BYTES,
    )

    events, receive_calls = _run_asgi(
        guard,
        [(b"content-length", str(config.MAX_REQUEST_BYTES + 1).encode("ascii"))],
    )

    assert called == []
    assert received == []
    assert receive_calls == 0
    assert events[0]["type"] == "http.response.start"
    assert events[0]["status"] == 413
    assert dict(events[0]["headers"])[b"content-type"] == b"application/json"
    assert _response_body(events) == json.dumps(
        {"success": False, "message": messages.FILE_TOO_LARGE},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


@pytest.mark.parametrize(
    ("path", "expected_message"),
    [
        ("/api/caesar/file", messages.FILE_TOO_LARGE),
        ("/api/vigenere/file", messages.FILE_TOO_LARGE),
        ("/api/playfair/file", messages.FILE_TOO_LARGE),
        ("/api/affine/file", messages.FILE_TOO_LARGE),
        ("/api/columnar/file", messages.FILE_TOO_LARGE),
        ("/api/des/file", messages.FILE_TOO_LARGE),
        ("/api/caesar/encrypt", messages.REQUEST_TOO_LARGE),
        ("/api/vigenere/encrypt", messages.REQUEST_TOO_LARGE),
        ("/api/vigenere/decrypt", messages.REQUEST_TOO_LARGE),
        ("/api/playfair/encrypt", messages.REQUEST_TOO_LARGE),
        ("/api/playfair/decrypt", messages.REQUEST_TOO_LARGE),
        ("/api/affine/encrypt", messages.REQUEST_TOO_LARGE),
        ("/api/affine/decrypt", messages.REQUEST_TOO_LARGE),
        ("/api/columnar/encrypt", messages.REQUEST_TOO_LARGE),
        ("/api/columnar/decrypt", messages.REQUEST_TOO_LARGE),
        ("/api/des/encrypt", messages.REQUEST_TOO_LARGE),
        ("/api/des/decrypt", messages.REQUEST_TOO_LARGE),
        ("/api/des/trace", messages.REQUEST_TOO_LARGE),
        ("/api/not-a-file-route", messages.REQUEST_TOO_LARGE),
        ("/docs", messages.REQUEST_TOO_LARGE),
    ],
)
def test_production_app_wires_route_aware_early_guard(
    path: str,
    expected_message: str,
) -> None:
    events, receive_calls = _run_asgi(
        app,
        [(b"content-length", str(config.MAX_REQUEST_BYTES + 1).encode("ascii"))],
        path,
    )

    assert receive_calls == 0
    assert events[0]["status"] == 413
    body = json.loads(_response_body(events))
    assert body == {
        "success": False,
        "message": expected_message,
    }
    assert set(body) == {"success", "message"}
    assert "64" not in body["message"]


def test_exact_ceiling_passes_through_and_downstream_reads_body() -> None:
    called: list[bool] = []
    received: list[Message] = []
    guard = RequestSizeGuard(_downstream_with_body_observation(called, received))

    events, receive_calls = _run_asgi(
        guard,
        [(b"content-length", str(config.MAX_REQUEST_BYTES).encode("ascii"))],
    )

    assert called == [True]
    assert receive_calls == 1
    assert received == [{"type": "http.request", "body": b"request body", "more_body": False}]
    assert events[0]["status"] == 200
    assert _response_body(events) == b"downstream"


@pytest.mark.parametrize(
    "content_length",
    [
        pytest.param(None, id="absent"),
        pytest.param(b"not-a-number", id="text"),
        pytest.param(b"-1", id="negative"),
        pytest.param(b"+1", id="signed"),
        pytest.param(b"1_000", id="underscore"),
    ],
)
def test_absent_or_malformed_content_length_passes_through(
    content_length: bytes | None,
) -> None:
    called: list[bool] = []
    received: list[Message] = []
    guard = RequestSizeGuard(_downstream_with_body_observation(called, received))
    headers = [] if content_length is None else [(b"content-length", content_length)]

    events, receive_calls = _run_asgi(guard, headers)

    assert called == [True]
    assert receive_calls == 1
    assert received[0]["type"] == "http.request"
    assert events[0]["status"] == 200


def test_oversized_decimal_with_leading_zeros_is_rejected_without_integer_conversion() -> None:
    called: list[bool] = []
    received: list[Message] = []
    guard = RequestSizeGuard(_downstream_with_body_observation(called, received))
    content_length = b"0" * 5000 + str(config.MAX_REQUEST_BYTES + 1).encode("ascii")

    events, receive_calls = _run_asgi(guard, [(b"content-length", content_length)])

    assert called == []
    assert received == []
    assert receive_calls == 0
    assert events[0]["status"] == 413


@pytest.mark.parametrize(
    ("ending", "expected"),
    [
        (b"field value--stream-boundary--", False),
        (b"field value\r\n--stream-boundary--", True),
        (b"field value\r\n--stream-boundary--\r\n", True),
    ],
)
@pytest.mark.parametrize(
    "path",
    [
        "/api/caesar/file",
        "/api/vigenere/file",
        "/api/playfair/file",
        "/api/affine/file",
        "/api/columnar/file",
    ],
)
def test_multipart_completion_requires_a_line_delimited_closing_boundary(
    ending: bytes,
    expected: bool,
    path: str,
) -> None:
    observed: list[bool] = []
    chunks = [b"x"] * 64 + [ending]

    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        while True:
            message = await receive()
            if not message.get("more_body", False):
                break
        observed.append(bool(scope[MultipartCompletionGuard.SCOPE_KEY]))
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def exercise() -> None:
        pending = list(chunks)

        async def receive() -> Message:
            body = pending.pop(0)
            return {"type": "http.request", "body": body, "more_body": bool(pending)}

        async def send(message: Message) -> None:
            del message

        scope = _scope(
            [(b"content-type", b"multipart/form-data; boundary=stream-boundary")],
            path,
        )
        await MultipartCompletionGuard(downstream)(scope, receive, send)

    asyncio.run(exercise())

    assert observed == [expected]


def test_file_route_guard_inventory_is_exactly_six() -> None:
    assert {
        "/api/caesar/file",
        "/api/vigenere/file",
        "/api/playfair/file",
        "/api/affine/file",
        "/api/columnar/file",
        "/api/des/file",
    } == FILE_ROUTE_PATHS


def test_multipart_completion_guard_ignores_routes_outside_exact_file_set() -> None:
    scope_keys: list[bool] = []

    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        scope_keys.append(MultipartCompletionGuard.SCOPE_KEY in scope)
        await receive()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    events, receive_calls = _run_asgi(
        MultipartCompletionGuard(downstream),
        [(b"content-type", b"multipart/form-data; boundary=stream-boundary")],
        "/api/vigenere/encrypt",
    )

    assert scope_keys == [False]
    assert receive_calls == 1
    assert events[0]["status"] == 200
