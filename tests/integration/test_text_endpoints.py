"""Integration coverage for all 45 text-cipher-api scenarios.

The inventory below follows the scenario order in
``openspec/specs/text-cipher-api/spec.md``.
The numbered comments on the tests map the inventory to executable coverage;
the same request cases are exercised against both endpoint paths where the
spec requires shared validation.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.errors import messages
from app.main import app

ENCRYPT_PATH = "/api/caesar/encrypt"
DECRYPT_PATH = "/api/caesar/decrypt"

# Explicit 45-scenario inventory from text-cipher-api.
TEXT_CIPHER_API_SCENARIOS = (
    "01 standard encryption acceptance",
    "02 encryption preserves case digits and punctuation",
    "03 repeated encryption is stable",
    "04 standard decryption acceptance",
    "05 encryption then decryption round-trip",
    "06 application/json request is accepted",
    "07 both endpoints share validation rules",
    "08 success response shape",
    "09 boolean true key is rejected",
    "10 boolean false key is rejected",
    "11 integral float key is rejected",
    "12 fractional float key is rejected",
    "13 numeric string key is rejected",
    "14 nonnumeric string key is rejected",
    "15 null key is missing",
    "16 array and object keys are rejected",
    "17 negative key is accepted",
    "18 key above 25 is accepted",
    "19 zero key is accepted",
    "20 very large integer key is accepted",
    "21 missing text is rejected",
    "22 empty text is rejected",
    "23 null text is rejected",
    "24 non-string text is rejected",
    "25 spaces-only text is preserved",
    "26 tab-and-newline-only text is preserved",
    "27 surrounding whitespace is preserved",
    "28 missing key is rejected",
    "29 null key is rejected as missing",
    "30 empty-string key is rejected as missing",
    "31 missing key differs from invalid key",
    "32 empty text precedes missing key",
    "33 empty object precedes missing fields",
    "34 empty text precedes invalid key",
    "35 empty text precedes null key",
    "36 malformed body precedes field errors",
    "37 accented Vietnamese text is preserved",
    "38 line endings are preserved",
    "39 emoji and special characters are preserved",
    "40 Unicode decryption restores original text",
    "41 non-JSON body is canonical",
    "42 malformed JSON syntax is canonical",
    "43 non-object JSON is canonical",
    "44 empty body is canonical",
    "45 technical details are not exposed",
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _assert_success(response, result: str) -> None:
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"success", "result"}
    assert body == {"success": True, "result": result}
    assert response.headers["content-type"].startswith("application/json")
    assert "message" not in body


def _assert_error(response, status_code: int, message: str) -> None:
    assert response.status_code == status_code
    body = response.json()
    assert set(body) == {"success", "message"}
    assert body == {"success": False, "message": message}
    assert "detail" not in body


def test_text_api_scenario_inventory_is_complete() -> None:
    assert len(TEXT_CIPHER_API_SCENARIOS) == 45
    assert [scenario[:2] for scenario in TEXT_CIPHER_API_SCENARIOS] == [
        f"{number:02d}" for number in range(1, 46)
    ]


# Scenarios 01, 02, 04, 06, 08, 17, 18, 19, and 20: valid JSON requests.
@pytest.mark.parametrize(
    ("path", "payload", "expected"),
    [
        pytest.param(ENCRYPT_PATH, {"text": "Hello World", "key": 3}, "Khoor Zruog", id="01"),
        pytest.param(
            ENCRYPT_PATH,
            {"text": "aBc-123!xyZ", "key": 3},
            "dEf-123!abC",
            id="02",
        ),
        pytest.param(DECRYPT_PATH, {"text": "Khoor Zruog", "key": 3}, "Hello World", id="04"),
        pytest.param(ENCRYPT_PATH, {"text": "abc", "key": 1}, "bcd", id="06"),
        pytest.param(ENCRYPT_PATH, {"text": "Hello World", "key": -23}, "Khoor Zruog", id="17"),
        pytest.param(ENCRYPT_PATH, {"text": "Hello World", "key": 29}, "Khoor Zruog", id="18"),
        pytest.param(ENCRYPT_PATH, {"text": "Hello World", "key": 0}, "Hello World", id="19"),
        pytest.param(DECRYPT_PATH, {"text": "Khoor Zruog", "key": 26003}, "Hello World", id="20"),
    ],
)
def test_valid_text_requests(
    client: TestClient, path: str, payload: dict[str, object], expected: str
) -> None:
    response = client.post(path, json=payload)

    _assert_success(response, expected)


@pytest.mark.parametrize("sign", ["", "-"])
def test_text_api_accepts_json_integer_beyond_python_conversion_ceiling(
    client: TestClient, sign: str
) -> None:
    digits = "1" + "0" * 4300
    normalized = pow(10, 4300, 26)
    if sign:
        normalized = -normalized
    expected = chr(ord("A") + normalized % 26)
    raw = f'{{"text":"A","key":{sign}{digits}}}'

    response = client.post(
        ENCRYPT_PATH,
        content=raw,
        headers={"content-type": "application/json"},
    )

    _assert_success(response, expected)


# Scenario 03: repeated identical requests do not share mutable state.
def test_repeated_encryption_is_stable(client: TestClient) -> None:
    payload = {"text": "Hello World", "key": 3}

    first = client.post(ENCRYPT_PATH, json=payload)
    second = client.post(ENCRYPT_PATH, json=payload)

    _assert_success(first, "Khoor Zruog")
    _assert_success(second, "Khoor Zruog")


# Scenario 05: the decrypt endpoint consumes the result of the encrypt endpoint.
def test_encrypt_then_decrypt_round_trip(client: TestClient) -> None:
    original = "Chào Thế Giới 2026!"
    encrypted = client.post(ENCRYPT_PATH, json={"text": original, "key": 7})
    _assert_success(encrypted, "Joàv Aoế Npớp 2026!")

    decrypted = client.post(
        DECRYPT_PATH,
        json={"text": encrypted.json()["result"], "key": 7},
    )
    _assert_success(decrypted, original)


# Scenario 07: both endpoints use the same missing-key validation.
def test_both_endpoints_share_validation_rules(client: TestClient) -> None:
    payload = {"text": "abc"}

    for path in (ENCRYPT_PATH, DECRYPT_PATH):
        _assert_error(client.post(path, json=payload), 422, messages.MISSING_KEY)


# Scenarios 09-16: exact JSON key typing and missing/null/empty precedence.
@pytest.mark.parametrize(
    ("path", "key", "expected_message"),
    [
        pytest.param(ENCRYPT_PATH, True, messages.INVALID_KEY, id="09-true"),
        pytest.param(ENCRYPT_PATH, False, messages.INVALID_KEY, id="10-false"),
        pytest.param(ENCRYPT_PATH, 3.0, messages.INVALID_KEY, id="11-3.0"),
        pytest.param(DECRYPT_PATH, 3.5, messages.INVALID_KEY, id="12-3.5"),
        pytest.param(ENCRYPT_PATH, "3", messages.INVALID_KEY, id="13-numeric-string"),
        pytest.param(ENCRYPT_PATH, "ba", messages.INVALID_KEY, id="14-text-string"),
        pytest.param(ENCRYPT_PATH, None, messages.MISSING_KEY, id="15-null"),
        pytest.param(ENCRYPT_PATH, "", messages.MISSING_KEY, id="30-empty-string"),
    ],
)
def test_key_validation_precedence(
    client: TestClient, path: str, key: object, expected_message: str
) -> None:
    response = client.post(path, json={"text": "Hello", "key": key})

    _assert_error(response, 422, expected_message)


@pytest.mark.parametrize(
    ("key", "case_id"),
    [pytest.param([3], "16-array"), pytest.param({"value": 3}, "16-object")],
)
def test_array_and_object_keys_are_rejected(client: TestClient, key: object, case_id: str) -> None:
    response = client.post(ENCRYPT_PATH, json={"text": "Hello", "key": key})

    _assert_error(response, 422, messages.INVALID_KEY)


# Scenarios 21-24: text presence/type/nonempty validation.
@pytest.mark.parametrize(
    ("payload", "case_id"),
    [
        pytest.param({"key": 3}, "21-missing"),
        pytest.param({"text": "", "key": 3}, "22-empty"),
        pytest.param({"text": None, "key": 3}, "23-null"),
        pytest.param({"text": 123, "key": 3}, "24-non-string"),
    ],
)
def test_text_validation(client: TestClient, payload: dict[str, object], case_id: str) -> None:
    response = client.post(ENCRYPT_PATH, json=payload)

    _assert_error(response, 422, messages.TEXT_EMPTY)


# Scenarios 25-27 and the API's whitespace-preservation edge cases.
@pytest.mark.parametrize(
    ("path", "text", "key", "expected"),
    [
        pytest.param(ENCRYPT_PATH, "   ", 3, "   ", id="25-spaces"),
        pytest.param(DECRYPT_PATH, "\t\n\n", 5, "\t\n\n", id="26-tabs-and-lf"),
        pytest.param(ENCRYPT_PATH, "  abc  ", 1, "  bcd  ", id="27-surrounding"),
    ],
)
def test_whitespace_text_is_valid_and_verbatim(
    client: TestClient, path: str, text: str, key: int, expected: str
) -> None:
    _assert_success(client.post(path, json={"text": text, "key": key}), expected)


# Scenarios 28-30: missing, null, and empty-string keys are all "missing".
@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"text": "Hello"}, id="28-missing"),
        pytest.param({"text": "Hello", "key": None}, id="29-null"),
        pytest.param({"text": "Hello", "key": ""}, id="30-empty-string"),
    ],
)
def test_missing_key_variants_use_missing_message(
    client: TestClient, payload: dict[str, object]
) -> None:
    _assert_error(client.post(ENCRYPT_PATH, json=payload), 422, messages.MISSING_KEY)


# Scenario 31: missing key and present-but-invalid key remain distinct.
def test_missing_key_differs_from_invalid_key(client: TestClient) -> None:
    missing = client.post(ENCRYPT_PATH, json={"text": "Hello"})
    invalid = client.post(ENCRYPT_PATH, json={"text": "Hello", "key": "3"})

    _assert_error(missing, 422, messages.MISSING_KEY)
    _assert_error(invalid, 422, messages.INVALID_KEY)


# Scenarios 32-35: text validation precedes every key presence/type check.
@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"text": ""}, id="32-missing-key"),
        pytest.param({}, id="33-empty-object"),
        pytest.param({"text": "", "key": "3"}, id="34-invalid-key"),
        pytest.param({"text": "", "key": None}, id="35-null-key"),
    ],
)
def test_text_validation_precedes_key_validation(
    client: TestClient, payload: dict[str, object]
) -> None:
    _assert_error(client.post(DECRYPT_PATH, json=payload), 422, messages.TEXT_EMPTY)


# Scenario 36 and scenarios 41-44: body readability/object validation precedes fields.
@pytest.mark.parametrize(
    ("path", "kwargs", "case_id"),
    [
        pytest.param(
            ENCRYPT_PATH,
            {"json": ["Hello World", 3]},
            "36-array-precedes-fields",
        ),
        pytest.param(
            ENCRYPT_PATH,
            {"content": b"not json at all", "headers": {"content-type": "application/json"}},
            "41-non-json",
        ),
        pytest.param(
            DECRYPT_PATH,
            {
                "content": b'{"text": "abc", "key":',
                "headers": {"content-type": "application/json"},
            },
            "42-malformed-json",
        ),
        pytest.param(ENCRYPT_PATH, {"json": 42}, "43-number"),
        pytest.param(DECRYPT_PATH, {"json": None}, "43-null"),
        pytest.param(ENCRYPT_PATH, {"json": "Hello"}, "43-string"),
        pytest.param(ENCRYPT_PATH, {}, "44-empty-body"),
    ],
)
def test_unreadable_or_non_object_bodies_are_canonical(
    client: TestClient, path: str, kwargs: dict[str, object], case_id: str
) -> None:
    _assert_error(client.post(path, **kwargs), 422, messages.INVALID_REQUEST_BODY)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
@pytest.mark.parametrize("path", [ENCRYPT_PATH, DECRYPT_PATH])
def test_nonstandard_numeric_constants_are_malformed_json(
    client: TestClient, path: str, constant: str
) -> None:
    raw = f'{{"text":"abc","key":{constant}}}'

    response = client.post(
        path,
        content=raw,
        headers={"content-type": "application/json"},
    )

    _assert_error(response, 422, messages.INVALID_REQUEST_BODY)


# Scenarios 37-40: Unicode, emoji, LF, CRLF, and special characters pass through the API.
def test_accented_vietnamese_text_is_preserved(client: TestClient) -> None:
    response = client.post(ENCRYPT_PATH, json={"text": "Xin chào", "key": 3})

    _assert_success(response, "Alq fkàr")
    assert "\\u" not in response.text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param("abc\ndef", "bcd\nefg", id="38-lf"),
        pytest.param("abc\r\ndef", "bcd\r\nefg", id="38-crlf"),
    ],
)
def test_line_endings_are_preserved(client: TestClient, text: str, expected: str) -> None:
    response = client.post(ENCRYPT_PATH, json={"text": text, "key": 1})

    _assert_success(response, expected)
    assert response.json()["result"].count("\r\n") == text.count("\r\n")


def test_emoji_and_special_characters_are_preserved(client: TestClient) -> None:
    response = client.post(ENCRYPT_PATH, json={"text": "hi 🙂 @#$ 42", "key": 2})

    _assert_success(response, "jk 🙂 @#$ 42")


def test_unicode_decryption_restores_original(client: TestClient) -> None:
    response = client.post(DECRYPT_PATH, json={"text": "Alq fkàr", "key": 3})

    _assert_success(response, "Xin chào")


# Scenario 45: malformed and invalid requests expose only the canonical envelope.
def test_invalid_responses_expose_no_technical_details(client: TestClient) -> None:
    responses = [
        client.post(ENCRYPT_PATH, json={"text": "Hello", "key": True}),
        client.post(DECRYPT_PATH, json={"text": "Hello", "key": 3.5}),
        client.post(
            ENCRYPT_PATH,
            content=b"not json",
            headers={"content-type": "application/json"},
        ),
    ]

    for response in responses:
        body = response.json()
        assert set(body) == {"success", "message"}
        assert "detail" not in body
        assert all(
            term not in response.text
            for term in ("Traceback", "ValidationError", "app.", "site-packages", "/home/")
        )


def test_openapi_documents_both_text_routes(client: TestClient) -> None:
    docs = client.get("/docs")
    openapi = client.get("/openapi.json")

    assert docs.status_code == 200
    assert openapi.status_code == 200
    paths = openapi.json()["paths"]
    assert ENCRYPT_PATH in paths
    assert DECRYPT_PATH in paths
    for path in (ENCRYPT_PATH, DECRYPT_PATH):
        operation = paths[path]["post"]
        assert operation["requestBody"]["content"]["application/json"]
        assert operation["responses"]["200"]
