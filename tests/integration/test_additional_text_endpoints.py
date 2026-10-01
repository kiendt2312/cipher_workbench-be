"""Integration contract for the Vigenere and Playfair JSON endpoints."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.errors import messages
from app.main import app

VIGENERE_ENCRYPT = "/api/vigenere/encrypt"
VIGENERE_DECRYPT = "/api/vigenere/decrypt"
PLAYFAIR_ENCRYPT = "/api/playfair/encrypt"
PLAYFAIR_DECRYPT = "/api/playfair/decrypt"
ALL_PATHS = (VIGENERE_ENCRYPT, VIGENERE_DECRYPT, PLAYFAIR_ENCRYPT, PLAYFAIR_DECRYPT)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _assert_success(response, result: str) -> None:
    assert response.status_code == 200
    assert response.json() == {"success": True, "result": result}
    assert set(response.json()) == {"success", "result"}


def _assert_error(response, status: int, message: str) -> None:
    assert response.status_code == status
    assert response.json() == {"success": False, "message": message}
    assert set(response.json()) == {"success", "message"}
    assert "detail" not in response.json()


@pytest.mark.parametrize(
    ("path", "payload", "expected"),
    [
        (VIGENERE_ENCRYPT, {"text": "Attack at dawn!", "key": "LEMON"}, "Lxfopv ef rnhr!"),
        (VIGENERE_DECRYPT, {"text": "Lxfopv ef rnhr!", "key": "LEMON"}, "Attack at dawn!"),
        (
            PLAYFAIR_ENCRYPT,
            {"text": "HIDE THE GOLD IN THE TREE STUMP", "key": "PLAYFAIR EXAMPLE"},
            "BMODZBXDNABEKUDMUIXMMOUVIF",
        ),
        (PLAYFAIR_ENCRYPT, {"text": "XX", "key": "PLAYFAIR EXAMPLE"}, "GWGW"),
        (PLAYFAIR_ENCRYPT, {"text": "ABX", "key": "PLAYFAIR EXAMPLE"}, "PDGW"),
    ],
)
def test_text_happy_paths(
    client: TestClient, path: str, payload: dict[str, str], expected: str
) -> None:
    _assert_success(client.post(path, json=payload), expected)


@pytest.mark.parametrize(
    ("ciphertext", "result", "positions", "filtered"),
    [
        (
            "BMODZBXDNABEKUDMUIXMMOUVIF",
            "HIDETHEGOLDINTHETREXESTUMP",
            [19],
            "HIDETHEGOLDINTHETREESTUMP",
        ),
        ("PDGW", "ABXQ", [3], "ABX"),
        ("GWGW", "XQXQ", [1, 3], "XX"),
        ("BMODZBXDNAGE", "HIDETHEGOLDX", [11], "HIDETHEGOLD"),
        ("DPYRANQO", "BALXLOON", [3], "BALLOON"),
        ("VPMRDLGI", "TAXICABX", [7], "TAXICAB"),
        ("DKQNOIIAXE", "BOOKKEEPER", [], "BOOKKEEPER"),
    ],
)
def test_playfair_decrypt_returns_raw_result_and_padding(
    client: TestClient, ciphertext: str, result: str, positions: list[int], filtered: str
) -> None:
    response = client.post(PLAYFAIR_DECRYPT, json={"text": ciphertext, "key": "PLAYFAIR EXAMPLE"})

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "result": result,
        "padding": {"count": len(positions), "positions": positions, "filtered": filtered},
    }
    assert list(response.json()) == ["success", "result", "padding"]
    assert "normalizedInput" not in response.json()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("A-A", "B-C"),
        ("AéA", "BéC"),
        ("A\r\nA", "B\r\nC"),
        ("   \t\n", "   \t\n"),
    ],
)
def test_vigenere_preserves_nonletters_without_advancing_key(
    client: TestClient, text: str, expected: str
) -> None:
    _assert_success(client.post(VIGENERE_ENCRYPT, json={"text": text, "key": "BC"}), expected)


def test_vigenere_key_is_case_insensitive(client: TestClient) -> None:
    lower = client.post(VIGENERE_ENCRYPT, json={"text": "Attack", "key": "lemon"})
    upper = client.post(VIGENERE_ENCRYPT, json={"text": "Attack", "key": "LEMON"})

    assert lower.json() == upper.json() == {"success": True, "result": "Lxfopv"}


@pytest.mark.parametrize("path", ALL_PATHS)
@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {"content": b"not-json", "headers": {"content-type": "application/json"}},
            messages.INVALID_REQUEST_BODY,
        ),
        ({"json": []}, messages.INVALID_REQUEST_BODY),
        ({"json": {}}, messages.TEXT_EMPTY),
        ({"json": {"text": "", "key": 123}}, messages.TEXT_EMPTY),
        ({"json": {"text": "abc"}}, messages.MISSING_KEY),
        ({"json": {"text": "abc", "key": None}}, messages.MISSING_KEY),
        ({"json": {"text": "abc", "key": ""}}, messages.MISSING_KEY),
        ({"json": {"text": "abc", "key": 123}}, messages.INVALID_STRING_KEY),
    ],
)
def test_shared_text_validation_contract(
    client: TestClient, path: str, kwargs: dict[str, object], message: str
) -> None:
    _assert_error(client.post(path, **kwargs), 422, message)


@pytest.mark.parametrize("key", ["LE MON", "KEY1", "KHÓA", " "])
def test_vigenere_invalid_key_contract(client: TestClient, key: str) -> None:
    _assert_error(
        client.post(VIGENERE_ENCRYPT, json={"text": "abc", "key": key}),
        422,
        messages.INVALID_VIGENERE_KEY,
    )


def test_playfair_key_error_precedes_content_error(client: TestClient) -> None:
    _assert_error(
        client.post(PLAYFAIR_ENCRYPT, json={"text": "123", "key": "---"}),
        422,
        messages.INVALID_PLAYFAIR_KEY,
    )


@pytest.mark.parametrize(
    ("path", "text", "message"),
    [
        (PLAYFAIR_ENCRYPT, "123 — ộ", messages.PLAYFAIR_TEXT_EMPTY),
        (PLAYFAIR_DECRYPT, "ABC", messages.PLAYFAIR_CIPHERTEXT_ODD),
        (PLAYFAIR_DECRYPT, "AABC", messages.PLAYFAIR_DUPLICATE_DIGRAPH),
    ],
)
def test_playfair_specific_validation(
    client: TestClient, path: str, text: str, message: str
) -> None:
    _assert_error(client.post(path, json={"text": text, "key": "MONARCHY"}), 422, message)


def test_openapi_documents_four_string_key_routes(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    for path in ALL_PATHS:
        operation = schema["paths"][path]["post"]
        request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
        assert request_schema["properties"]["text"]["type"] == "string"
        assert request_schema["properties"]["key"]["type"] == "string"
        assert operation["responses"]["200"]
        for status in ("413", "422", "500"):
            error_schema = operation["responses"][status]["content"]["application/json"]["schema"]
            assert set(error_schema["required"]) == {"success", "message"}
            assert set(error_schema["properties"]) == {"success", "message"}

    def success_model(path: str) -> str:
        content = schema["paths"][path]["post"]["responses"]["200"]["content"]
        return content["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]

    assert success_model(PLAYFAIR_ENCRYPT) == success_model(VIGENERE_DECRYPT)
    decrypt_model = schema["components"]["schemas"][success_model(PLAYFAIR_DECRYPT)]
    assert set(decrypt_model["required"]) == {"success", "result", "padding"}


def test_caesar_integer_contract_remains_unchanged(client: TestClient) -> None:
    _assert_success(
        client.post("/api/caesar/encrypt", json={"text": "Hello World", "key": 3}),
        "Khoor Zruog",
    )
    _assert_error(
        client.post("/api/caesar/encrypt", json={"text": "Hello", "key": "3"}),
        422,
        messages.INVALID_KEY,
    )


def test_unexpected_text_failure_is_sanitized_and_does_not_log_payload(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def fail(*args: object) -> str:
        raise RuntimeError("secret-text SECRETKEY")

    monkeypatch.setattr("app.api.routes_additional_text.transform_vigenere", fail)
    caplog.set_level("ERROR", logger="app.errors.handlers")

    response = client.post(
        VIGENERE_ENCRYPT,
        json={"text": "secret-text", "key": "SECRETKEY"},
    )

    _assert_error(response, 500, messages.UNEXPECTED_FAILURE)
    assert "RuntimeError" in caplog.text
    assert "secret-text" not in caplog.text
    assert "SECRETKEY" not in caplog.text
