"""Contract tests for the four Hill endpoints."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.hill_schemas import MAX_TEXT_BYTES
from app.main import app

T01 = [[3, 3], [2, 5]]


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def assert_hill_error(response, status: int, code: str) -> dict[str, object]:
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"success", "message", "code", "details"}
    assert body["success"] is False
    assert body["code"] == code
    assert isinstance(body["message"], str)
    assert isinstance(body["details"], dict)
    return body


def test_encrypt_decrypt_T01_exact_response(client: TestClient) -> None:
    encrypted = client.post("/api/hill/encrypt", json={"text": "HELP", "key": T01})
    assert encrypted.status_code == 200
    assert encrypted.json() == {
        "success": True,
        "result": "DPLE",
        "blocks": [
            {"input": [7, 4], "output": [3, 15]},
            {"input": [11, 15], "output": [11, 4]},
        ],
        "key": {
            "matrix": T01,
            "m": 2,
            "det": 9,
            "gcd": 1,
            "detInverse": 3,
            "adjugate": [[5, 23], [24, 3]],
            "inverse": [[15, 17], [20, 9]],
        },
        "warnings": [],
    }
    decrypted = client.post("/api/hill/decrypt", json={"text": "DPLE", "key": T01})
    assert decrypted.status_code == 200
    assert decrypted.json()["result"] == "HELP"
    assert decrypted.json()["padding"] == {"count": 0, "positions": [], "filtered": "HELP"}


def test_decrypt_returns_six_fields_with_padding(client: TestClient) -> None:
    response = client.post("/api/hill/decrypt", json={"text": "DPDKKB", "key": T01})

    assert response.status_code == 200
    body = response.json()
    assert list(body) == ["success", "result", "blocks", "key", "warnings", "padding"]
    assert body["result"] == "HELLOX"
    assert len(body["blocks"]) == 3
    assert body["padding"] == {"count": 1, "positions": [5], "filtered": "HELLO"}
    encrypted = client.post("/api/hill/encrypt", json={"text": "HELLO", "key": T01}).json()
    assert list(encrypted) == ["success", "result", "blocks", "key", "warnings"]


@pytest.mark.parametrize(
    ("body", "result", "padding"),
    [
        (
            {"text": "HQKRJYDPDONU", "key": [[6, 1, 3], [17, 5, 7], [3, 2, 3]]},
            "THUDOHANOIXX",
            {"count": 2, "positions": [10, 11], "filtered": "THUDOHANOI"},
        ),
        (
            {"text": "DPDKK!B", "key": T01},
            "HELLO!X",
            {"count": 1, "positions": [5], "filtered": "HELLO!"},
        ),
        (
            {"text": "DPDKWS", "key": T01, "options": {"padChar": "Q"}},
            "HELLOQ",
            {"count": 1, "positions": [5], "filtered": "HELLO"},
        ),
        (
            {"text": "DPDKWS", "key": T01},
            "HELLOQ",
            {"count": 0, "positions": [], "filtered": "HELLOQ"},
        ),
    ],
)
def test_decrypt_padding_follows_pad_char_and_keeps_result_raw(
    client: TestClient, body: dict[str, object], result: str, padding: dict[str, object]
) -> None:
    response = client.post("/api/hill/decrypt", json=body).json()

    assert response["result"] == result
    assert response["padding"] == padding


def test_keyword_padding_case_and_punctuation(client: TestClient) -> None:
    keyword = client.post(
        "/api/hill/encrypt", json={"text": "HILLCIPHER", "keyword": "HILL", "m": 2}
    )
    assert keyword.json()["result"] == "HOQBYAAPHL"

    padded = client.post("/api/hill/encrypt", json={"text": "HELLO!", "key": T01}).json()
    assert padded["result"] == "DPDKK!B"
    assert padded["warnings"][0] == {
        "code": "W01",
        "message": "Đã thêm 1 ký tự X vào cuối để đủ khối 2 chữ.",
        "details": {"count": 1, "char": "X", "m": 2},
    }
    preserved = client.post("/api/hill/encrypt", json={"text": "Help, me!", "key": T01})
    assert preserved.json()["result"] == "Dple, se!"


def test_analyze_and_random_contract(client: TestClient) -> None:
    analyzed = client.post("/api/hill/key/analyze", json={"key": T01})
    body = analyzed.json()
    assert analyzed.status_code == 200
    assert set(body) == {"success", "result", "warnings"}
    assert body["result"]["det"] == 9
    assert body["warnings"] == []

    for m in (2, 3, 4):
        random = client.get(f"/api/hill/key/random?m={m}")
        result = random.json()["result"]
        assert random.status_code == 200
        assert result["m"] == m
        assert result["gcd"] == 1
        assert result["matrix"] != [[int(row == column) for column in range(m)] for row in range(m)]


@pytest.mark.parametrize(
    "body,code",
    [
        ({"text": "", "key": T01}, "E01"),
        ({"text": "123 !!", "key": T01}, "E02"),
        ({"text": "HELP", "key": [[3, 3], [2, "x"]]}, "E03"),
        ({"text": "HELP", "key": [[2, 4], [1, 3]]}, "E04"),
        ({"text": "DPL", "key": T01}, "E05"),
        ({"text": "HELP", "key": [[1]]}, "E08"),
        ({"text": "HELP", "keyword": "HI L", "m": 2}, "E09"),
        ({"text": "HELP", "key": T01, "options": {"padChar": "x"}}, "E10"),
        ({"text": 3, "key": T01}, "E11"),
    ],
)
def test_transform_error_codes(client: TestClient, body: dict[str, object], code: str) -> None:
    path = "/api/hill/decrypt" if code == "E05" else "/api/hill/encrypt"
    response = client.post(path, json=body)
    error = assert_hill_error(response, 422, code)
    if code == "E02":
        assert error["message"] == (
            "Văn bản không có chữ cái nào để mã hóa. Hill chỉ xử lý A\u2013Z."
        )
    if code == "E04":
        assert error["details"] == {"det": 2, "gcd": 2, "divisor": 2}
        assert error["message"] == (
            "Khóa không khả nghịch: det K mod 26 = 2, chia hết cho 2. Hãy đổi khóa."
        )


def test_E06_byte_limit_and_exact_boundary(client: TestClient) -> None:
    over = client.post(
        "/api/hill/encrypt",
        json={
            "text": "é" * (MAX_TEXT_BYTES // 2) + "A",
            "key": "bad",
            "options": {"stripDiacritics": True},
        },
    )
    body = assert_hill_error(over, 413, "E06")
    assert body["message"] == "Văn bản vượt quá giới hạn 5 MiB."
    assert body["details"] == {"actualBytes": MAX_TEXT_BYTES + 1, "maxBytes": MAX_TEXT_BYTES}

    exact = client.post(
        "/api/hill/encrypt",
        json={"text": "é" * (MAX_TEXT_BYTES // 2 - 1) + "AA", "key": [[1, 0], [0, 1]]},
    )
    assert exact.status_code == 200
    assert exact.json()["result"].endswith("AA")
    assert len(exact.json()["blocks"]) == 1


@pytest.mark.parametrize(
    "method,path,kwargs,code",
    [
        ("post", "/api/hill/encrypt", {"content": b"{"}, "E11"),
        ("post", "/api/hill/encrypt", {"content": b'{"text":"A","text":"B"}'}, "E11"),
        ("post", "/api/hill/key/analyze", {"json": {"key": T01, "text": "secret"}}, "E11"),
        ("get", "/api/hill/key/random", {}, "E08"),
        ("get", "/api/hill/key/random?m=2&m=3", {}, "E08"),
        ("get", "/api/hill/key/random?m=%EF%BC%92", {}, "E08"),
    ],
)
def test_decoder_and_random_query_errors(
    client: TestClient, method: str, path: str, kwargs: dict[str, object], code: str
) -> None:
    if "content" in kwargs:
        kwargs["headers"] = {"content-type": "application/json"}
    response = getattr(client, method)(path, **kwargs)
    assert_hill_error(response, 422, code)


def test_warning_order_and_unicode_NFC_NFD(client: TestClient) -> None:
    response = client.post(
        "/api/hill/encrypt",
        json={"text": "Aếế", "key": [[1, 0], [0, 1]]},
    )
    body = response.json()
    assert body["result"] == "AếếX"
    assert [warning["code"] for warning in body["warnings"]] == ["W01", "W02", "W03"]
    assert body["warnings"][1]["details"] == {"count": 2}

    stripped = client.post(
        "/api/hill/encrypt",
        json={
            "text": "AếếĐđ",
            "key": [[1, 0], [0, 1]],
            "options": {"stripDiacritics": True},
        },
    )
    assert stripped.json()["result"] == "AeeDdX"


def test_old_cipher_envelopes_and_missing_hill_file_are_unchanged(client: TestClient) -> None:
    old_error = client.post("/api/caesar/encrypt", json={"text": "", "key": "bad"})
    assert set(old_error.json()) == {"success", "message"}
    assert client.post("/api/hill/file").status_code == 404


def test_openapi_documents_hill_contract(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    for path in ("/api/hill/encrypt", "/api/hill/decrypt"):
        operation = schema["paths"][path]["post"]
        assert {tag.lower() for tag in operation["tags"]} == {"hill"}
        assert {"200", "413", "422", "500"} <= operation["responses"].keys()
        request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
        assert "oneOf" in request_schema
        assert all(
            variant["properties"]["text"]["description"]
            == "Tối đa 5 MiB (5.242.880 byte) khi mã hóa UTF-8."
            for variant in request_schema["oneOf"]
        )
        assert operation["responses"]["413"]["description"] == ("Text Hill vượt giới hạn 5 MiB.")
    assert "/api/hill/file" not in schema["paths"]
    components = schema["components"]["schemas"]
    assert "padding" not in components["HillEncryptResponse"]["properties"]
    assert "padding" in components["HillDecryptResponse"]["required"]
    assert set(components["PaddingInfo"]["required"]) == {"count", "positions", "filtered"}
    for path, model in (
        ("/api/hill/encrypt", "HillEncryptResponse"),
        ("/api/hill/decrypt", "HillDecryptResponse"),
    ):
        response_schema = schema["paths"][path]["post"]["responses"]["200"]["content"]
        assert response_schema["application/json"]["schema"]["$ref"].endswith(f"/{model}")
    random_operation = schema["paths"]["/api/hill/key/random"]["get"]
    assert random_operation["parameters"] == [
        {
            "name": "m",
            "in": "query",
            "required": True,
            "description": "Cấp ma trận Hill, xuất hiện đúng một lần.",
            "schema": {"type": "integer", "minimum": 2, "maximum": 4},
        }
    ]
