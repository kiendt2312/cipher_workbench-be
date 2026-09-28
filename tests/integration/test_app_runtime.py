"""Runtime-serving tests for the single-process Caesar Cipher application.

These tests exercise the app the way the DOCX §7 acceptance criteria observe
it: a single process that serves the web UI, static assets, interactive API
docs and the JSON API all on one origin, with stateless request handling.
They run against the real FastAPI app via TestClient (no Docker required).
"""

import re

from fastapi.testclient import TestClient

from app.main import app


def test_root_serves_the_web_ui() -> None:
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_docs_serves_interactive_api_documentation() -> None:
    with TestClient(app) as client:
        response = client.get("/docs")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "swagger" in response.text.lower()


def test_openapi_schema_lists_all_caesar_endpoints() -> None:
    with TestClient(app) as client:
        schema = client.get("/openapi.json")
    assert schema.status_code == 200
    paths = set(schema.json()["paths"])
    assert {
        "/api/caesar/encrypt",
        "/api/caesar/decrypt",
        "/api/caesar/file",
        "/api/vigenere/encrypt",
        "/api/vigenere/decrypt",
        "/api/vigenere/file",
        "/api/playfair/encrypt",
        "/api/playfair/decrypt",
        "/api/playfair/file",
    } <= paths


def test_static_assets_are_served_by_the_same_application() -> None:
    with TestClient(app) as client:
        styles = client.get("/static/styles.css")
        script = client.get("/static/app.js")
    assert styles.status_code == 200
    assert styles.headers["content-type"].startswith("text/css")
    assert script.status_code == 200
    assert script.headers["content-type"].startswith("text/javascript")


def test_ui_makes_only_same_origin_api_calls() -> None:
    with TestClient(app) as client:
        page = client.get("/")
        script = client.get("/static/app.js")
    assert "localhost:" not in page.text
    assert "8080" not in page.text
    assert "localhost:" not in script.text
    assert "8080" not in script.text
    base = "http://testserver"
    for url in re.findall(r'(?:href|src)="([^"]+)"', page.text):
        assert url.startswith("/") or url.startswith(base), url


def test_api_responses_need_no_cors_headers() -> None:
    with TestClient(app) as client:
        response = client.post("/api/caesar/encrypt", json={"text": "Hi", "key": 1})
        vigenere = client.post("/api/vigenere/encrypt", json={"text": "Attack", "key": "LEMON"})
        docs = client.get("/docs")
    for headers in (response.headers, vigenere.headers, docs.headers):
        assert "access-control-allow-origin" not in headers


def test_identical_requests_produce_identical_results() -> None:
    payload = {"text": "Hello World", "key": 3}
    with TestClient(app) as client:
        first = client.post("/api/caesar/encrypt", json=payload)
        second = client.post("/api/caesar/encrypt", json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json() == {"success": True, "result": "Khoor Zruog"}


def test_result_does_not_depend_on_previous_requests() -> None:
    with TestClient(app) as client:
        client.post("/api/caesar/encrypt", json={"text": "AAAA", "key": 1})
        after = client.post("/api/caesar/encrypt", json={"text": "Hello", "key": 3})
        control = client.post("/api/caesar/encrypt", json={"text": "Hello", "key": 3})
    assert after.json() == control.json() == {"success": True, "result": "Khoor"}


def test_additional_cipher_results_are_stateless() -> None:
    vigenere_payload = {"text": "Attack at dawn!", "key": "LEMON"}
    playfair_payload = {"text": "HIDE THE GOLD", "key": "PLAYFAIR EXAMPLE"}
    with TestClient(app) as client:
        vigenere_first = client.post("/api/vigenere/encrypt", json=vigenere_payload)
        client.post("/api/playfair/encrypt", json={"text": "XX", "key": "MONARCHY"})
        vigenere_second = client.post("/api/vigenere/encrypt", json=vigenere_payload)
        playfair_first = client.post("/api/playfair/encrypt", json=playfair_payload)
        client.post("/api/vigenere/encrypt", json={"text": "AAAA", "key": "B"})
        playfair_second = client.post("/api/playfair/encrypt", json=playfair_payload)

    assert (
        vigenere_first.json()
        == vigenere_second.json()
        == {
            "success": True,
            "result": "Lxfopv ef rnhr!",
        }
    )
    assert (
        playfair_first.json()
        == playfair_second.json()
        == {
            "success": True,
            "result": "BMODZBXDNAGE",
        }
    )


def test_no_session_cookie_or_stored_state_is_created() -> None:
    with TestClient(app) as client:
        page = client.get("/")
        response = client.post("/api/caesar/encrypt", json={"text": "Hi", "key": 1})
    for headers in (page.headers, response.headers):
        assert "set-cookie" not in headers


def test_only_metadata_history_route_exists_and_no_previous_results() -> None:
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
        missing = client.get("/api/caesar/encrypt")
    stateful = {
        path
        for path in schema["paths"]
        if any(token in path.lower() for token in ("history", "record", "log", "session"))
    }
    assert stateful == {"/api/history"}
    item_fields = set(schema["components"]["schemas"]["HistoryItem"]["properties"])
    assert not item_fields & {"text", "result", "key", "a", "b", "filename", "content"}
    assert missing.status_code == 405


def test_single_process_serves_every_asset_the_ui_references() -> None:
    with TestClient(app) as client:
        page = client.get("/")
        for url in re.findall(r'(?:href|src)="([^"]+)"', page.text):
            path = url.removeprefix("http://testserver")
            assert client.get(path).status_code == 200, path
