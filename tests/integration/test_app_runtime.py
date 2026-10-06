"""Runtime-serving tests for the single-process Caesar Cipher application.

These tests exercise the app the way the DOCX §7 acceptance criteria observe
it: a single process that serves interactive API docs and the JSON API on one
origin, with stateless request handling. The web UI belongs to the FE project.
They run against the real FastAPI app via TestClient (no Docker required).
"""

from fastapi.testclient import TestClient

from app.main import app


def test_root_and_static_paths_serve_no_web_ui() -> None:
    with TestClient(app) as client:
        root = client.get("/")
        script = client.get("/static/app.js")
    assert root.status_code == 404
    assert script.status_code == 404


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


def test_cipher_route_inventory_includes_hill_without_a_file_route() -> None:
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()

    cipher_paths = {
        path: operations
        for path, operations in schema["paths"].items()
        if path.startswith("/api/")
        and path.split("/")[2] != "history"
        and path not in {"/api/health"}
    }
    post_count = sum("post" in operations for operations in cipher_paths.values())
    get_count = sum("get" in operations for operations in cipher_paths.values())
    assert post_count == 26
    assert get_count == 1
    assert "/api/hill/file" not in cipher_paths
    assert {
        "/api/hill/encrypt",
        "/api/hill/decrypt",
        "/api/hill/key/analyze",
        "/api/hill/key/random",
    } <= cipher_paths.keys()
    assert {
        "/api/rsa/keys",
        "/api/rsa/keys/random",
        "/api/rsa/encrypt",
        "/api/rsa/decrypt",
    } <= cipher_paths.keys()


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
        docs = client.get("/docs")
        response = client.post("/api/caesar/encrypt", json={"text": "Hi", "key": 1})
    for headers in (docs.headers, response.headers):
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
