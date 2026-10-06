"""Accepted JSON RSA API vectors, exact schemas and isolation guarantees."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.history.routes import match_cipher_route
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_manual_key_tc01_exact_response(client: TestClient) -> None:
    response = client.post("/api/rsa/keys", json={"p": "17", "q": "11", "e": "7"})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "success",
        "n",
        "phi",
        "e",
        "d",
        "publicKey",
        "privateKey",
        "egcdSteps",
    }
    assert (body["n"], body["phi"], body["e"], body["d"]) == ("187", "160", "7", "23")
    assert body["publicKey"] == {"e": "7", "n": "187"}
    assert body["privateKey"] == {"d": "23", "n": "187"}
    assert body["egcdSteps"][0] == {"index": 0, "q": None, "r": "160", "t": "0"}
    assert body["egcdSteps"][-1]["r"] == "0"


@pytest.mark.parametrize(
    ("payload", "code", "field", "message"),
    [
        ({"p": "15", "q": "11", "e": "7"}, "NOT_PRIME", "p", "p = 15 không phải số nguyên tố."),
        ({"p": "11", "q": "11", "e": "7"}, "SAME_PRIME", "q", "p và q phải khác nhau."),
        (
            {"p": "17", "q": "11", "e": "10"},
            "E_NOT_COPRIME",
            "e",
            "gcd(10, 160) = 10, không tồn tại d. Gợi ý e = 3.",
        ),
        (
            {"p": "17", "q": "11", "e": "200"},
            "E_OUT_OF_RANGE",
            "e",
            "e phải thỏa 1 < e < phi(n) = 160.",
        ),
        (
            {"p": "1000000000001", "q": "11", "e": "7"},
            "PRIME_TOO_LARGE",
            "p",
            "Hãy dùng p, q ≤ 10^12 hoặc sinh khóa ngẫu nhiên.",
        ),
    ],
)
def test_manual_key_reference_errors(
    client: TestClient, payload: dict, code: str, field: str, message: str
) -> None:
    response = client.post("/api/rsa/keys", json=payload)
    assert response.status_code == 422
    assert response.json() == {"success": False, "code": code, "message": message, "field": field}


@pytest.mark.parametrize("bits", [16, 32, 64, 128])
def test_random_key_sizes_and_exact_response(client: TestClient, bits: int) -> None:
    response = client.post("/api/rsa/keys/random", json={"bits": bits})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "success",
        "p",
        "q",
        "n",
        "phi",
        "e",
        "d",
        "publicKey",
        "privateKey",
        "egcdSteps",
    }
    assert int(body["n"]).bit_length() == bits
    assert int(body["p"]) != int(body["q"])
    assert int(body["e"]) * int(body["d"]) % int(body["phi"]) == 1


def test_number_tc02_tc04_tc05_and_canonical_output(client: TestClient) -> None:
    encrypted = client.post(
        "/api/rsa/encrypt",
        json={"e": "17", "n": "3233", "inputType": "number", "data": "00065"},
    )
    assert encrypted.status_code == 200
    assert encrypted.json() == {
        "success": True,
        "inputType": "number",
        "blocks": ["65"],
        "cipher": ["2790"],
        "blockSize": None,
        "trace": None,
    }
    decrypted = client.post(
        "/api/rsa/decrypt",
        json={"d": "23", "n": "187", "inputType": "number", "cipher": ["11"]},
    )
    assert decrypted.json() == {
        "success": True,
        "inputType": "number",
        "blocks": ["88"],
        "plaintext": "88",
        "blockSize": None,
        "trace": None,
    }
    too_large = client.post(
        "/api/rsa/encrypt",
        json={"e": "7", "n": "187", "inputType": "number", "data": "200"},
    )
    assert too_large.json() == {
        "success": False,
        "code": "P_TOO_LARGE",
        "message": "P = 200 ≥ n = 187. Hãy chia khối hoặc dùng n lớn hơn.",
        "field": "data",
    }


def test_char_tc11_round_trip_bom_nul_and_composition(client: TestClient) -> None:
    key = client.post("/api/rsa/keys", json={"p": "101", "q": "113", "e": "3533"}).json()
    for text in ("Xin chào Việt Nam", "é", "e\u0301", " A\r\nB\n\x00"):
        encrypted = client.post(
            "/api/rsa/encrypt",
            json={"e": key["e"], "n": key["n"], "inputType": "text", "mode": "char", "data": text},
        )
        assert encrypted.status_code == 200
        package = encrypted.json()
        decrypted = client.post(
            "/api/rsa/decrypt",
            json={
                "d": key["d"],
                "n": key["n"],
                "inputType": "text",
                "mode": "char",
                "cipher": package["cipher"],
            },
        )
        assert decrypted.status_code == 200
        assert decrypted.json()["plaintext"] == text
        assert decrypted.json()["originalUtf8ByteLength"] == len(text.encode())

    bom = client.post(
        "/api/rsa/encrypt",
        json={"e": "3", "n": "67591", "inputType": "text", "mode": "char", "data": "\ufeffA"},
    ).json()
    restored = client.post(
        "/api/rsa/decrypt",
        json={
            "d": "44715",
            "n": "67591",
            "inputType": "text",
            "mode": "char",
            "cipher": bom["cipher"],
        },
    )
    assert restored.json()["plaintext"] == "\ufeffA"


def test_block_tc12_round_trip_and_metadata(client: TestClient) -> None:
    encrypted = client.post(
        "/api/rsa/encrypt",
        json={"e": "3", "n": "67591", "inputType": "text", "mode": "block", "data": "Hi!"},
    )
    assert encrypted.status_code == 200
    body = encrypted.json()
    assert (body["blockSize"], body["originalUtf8ByteLength"]) == (2, 3)
    assert body["blocks"] == ["18537", "8448"]
    assert body["cipher"] == ["37222", "6468"]
    decrypted = client.post(
        "/api/rsa/decrypt",
        json={
            "d": "44715",
            "n": "67591",
            "inputType": "text",
            "mode": "block",
            "cipher": body["cipher"],
            "originalUtf8ByteLength": 3,
        },
    )
    assert decrypted.status_code == 200
    assert decrypted.json()["plaintext"] == "Hi!"

    tampered_but_observably_valid = client.post(
        "/api/rsa/decrypt",
        json={
            "d": "44715",
            "n": "67591",
            "inputType": "text",
            "mode": "block",
            "cipher": body["cipher"],
            "originalUtf8ByteLength": 4,
        },
    )
    assert tampered_but_observably_valid.status_code == 200
    assert tampered_but_observably_valid.json()["plaintext"] == "Hi!\x00"


def test_selected_trace_is_complete_and_non_trace_fields_do_not_change(client: TestClient) -> None:
    payload = {"e": "7", "n": "187", "inputType": "number", "data": "88"}
    plain = client.post("/api/rsa/encrypt", json=payload).json()
    traced = client.post("/api/rsa/encrypt", json={**payload, "traceBlockIndex": 0}).json()
    assert {key: value for key, value in traced.items() if key != "trace"} == {
        key: value for key, value in plain.items() if key != "trace"
    }
    assert plain["trace"] is None
    assert traced["trace"] == {
        "operation": "encrypt",
        "blockIndex": 0,
        "input": "88",
        "exponent": "7",
        "modulus": "187",
        "result": "11",
        "steps": [
            {"i": 0, "bit": 1, "base": "88", "before": "1", "result": "88"},
            {"i": 1, "bit": 1, "base": "77", "before": "88", "result": "44"},
            {"i": 2, "bit": 1, "base": "132", "before": "44", "result": "11"},
        ],
    }


def test_strict_raw_json_and_exact_error_envelope(client: TestClient) -> None:
    cases = [
        (b'{"p":"17","p":"19","q":"11","e":"7"}', "INVALID_REQUEST", "p"),
        (b'{"p":"17","q":"11","e":"7","encoding":"hex"}', "INVALID_REQUEST", "encoding"),
        (b'{"p":17,"q":"11","e":"7"}', "NOT_INTEGER", "p"),
        (
            ('{"p":"' + "0" * 129 + '","q":"11","e":"7"}').encode(),
            "NUMBER_TOO_LARGE",
            "p",
        ),
    ]
    for raw, code, field in cases:
        response = client.post(
            "/api/rsa/keys", content=raw, headers={"content-type": "application/json"}
        )
        assert response.status_code == 422
        assert set(response.json()) == {"success", "code", "message", "field"}
        assert (response.json()["code"], response.json()["field"]) == (code, field)


def test_owner_reconciled_missing_length_and_lone_surrogate_errors(client: TestClient) -> None:
    missing_length = client.post(
        "/api/rsa/decrypt",
        json={
            "d": "44715",
            "n": "67591",
            "inputType": "text",
            "mode": "block",
            "cipher": ["37222", "6468"],
        },
    )
    assert missing_length.status_code == 422
    assert missing_length.json() == {
        "success": False,
        "code": "INVALID_LENGTH_METADATA",
        "message": "Độ dài UTF-8 gốc không khớp với danh sách bản mã.",
        "field": "originalUtf8ByteLength",
    }

    lone_surrogate = client.post(
        "/api/rsa/encrypt",
        content=(b'{"e":"3","n":"67591","inputType":"text","mode":"char","data":"\\ud800"}'),
        headers={"content-type": "application/json"},
    )
    assert lone_surrogate.status_code == 422
    assert lone_surrogate.json() == {
        "success": False,
        "code": "DECODE_FAILED",
        "message": "Không khôi phục được văn bản hợp lệ từ dữ liệu đã giải mã.",
        "field": "data",
    }


def test_media_type_framework_and_unexpected_errors_use_rsa_envelope(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    unsupported = client.post("/api/rsa/decrypt", data="x", headers={"content-type": "text/plain"})
    assert unsupported.status_code == 415
    assert unsupported.json()["code"] == "UNSUPPORTED_MEDIA_TYPE"

    from app.api import routes_rsa

    def broken(_: int) -> object:
        raise RuntimeError("secret operand")

    monkeypatch.setattr(routes_rsa.rsa, "generate_random_key", broken)
    failed = client.post("/api/rsa/keys/random", json={"bits": 16})
    assert failed.status_code == 500
    assert failed.json() == {
        "success": False,
        "code": "INTERNAL_ERROR",
        "message": "Đã xảy ra lỗi hệ thống.",
        "field": None,
    }
    assert "secret operand" not in failed.text


def test_openapi_has_exact_four_rsa_posts_and_contract_shapes(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    rsa_paths = {
        path: value for path, value in schema["paths"].items() if path.startswith("/api/rsa")
    }
    assert set(rsa_paths) == {
        "/api/rsa/keys",
        "/api/rsa/keys/random",
        "/api/rsa/encrypt",
        "/api/rsa/decrypt",
    }
    assert all(set(operations) == {"post"} for operations in rsa_paths.values())
    encrypt_content = rsa_paths["/api/rsa/encrypt"]["post"]["requestBody"]["content"]
    assert set(encrypt_content) == {"application/json", "multipart/form-data"}
    assert "Textbook RSA" in rsa_paths["/api/rsa/keys"]["post"]["description"]
    error_schema = schema["components"]["schemas"]["RsaErrorResponse"]
    assert error_schema["additionalProperties"] is False
    assert set(error_schema["required"]) == {"success", "code", "message", "field"}


def test_only_rsa_transforms_are_in_history_whitelist_and_crypto_stays_stateless(
    client: TestClient,
) -> None:
    for path in ("/api/rsa/keys", "/api/rsa/keys/random"):
        assert match_cipher_route("POST", path) is None
    assert match_cipher_route("POST", "/api/rsa/encrypt") is not None
    assert match_cipher_route("POST", "/api/rsa/decrypt") is not None
    payload = {"e": "17", "n": "3233", "inputType": "number", "data": "65"}
    assert (
        client.post("/api/rsa/encrypt", json=payload).json()
        == client.post("/api/rsa/encrypt", json=payload).json()
    )


def test_traceability_matrix_tc01_through_tc13() -> None:
    matrix = {
        "TC-01": "test_manual_key_tc01_exact_response",
        "TC-02": "test_number_tc02_tc04_tc05_and_canonical_output",
        "TC-03": "test_gcd_egcd_inverse_and_key_vectors",
        "TC-04": "test_number_tc02_tc04_tc05_and_canonical_output",
        "TC-05": "test_number_tc02_tc04_tc05_and_canonical_output",
        "TC-06": "test_manual_key_reference_errors",
        "TC-07": "test_manual_key_reference_errors",
        "TC-08": "test_manual_key_reference_errors",
        "TC-09": "test_manual_key_reference_errors",
        "TC-10": "test_char_rejects_surrogate_and_codepoint_over_modulus",
        "TC-11": "test_char_tc11_round_trip_bom_nul_and_composition",
        "TC-12": "test_block_tc12_round_trip_and_metadata",
        "TC-13": "test_block_boundaries_and_package_validation",
    }
    assert set(matrix) == {f"TC-{number:02d}" for number in range(1, 14)}
    assert all(name.startswith("test_") for name in matrix.values())
