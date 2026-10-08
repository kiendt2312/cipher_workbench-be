"""Accepted HTTP contracts for the educational Diffie-Hellman API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import routes_dh
from app.errors.exceptions import FileReadError
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_openapi_exposes_exactly_six_dh_operations(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    dh_paths = {path for path in paths if path.startswith("/api/dh/")}
    assert dh_paths == {
        "/api/dh/params",
        "/api/dh/params/random",
        "/api/dh/keypair",
        "/api/dh/shared-secret",
        "/api/dh/exchange",
        "/api/dh/caesar",
    }
    assert all(set(paths[path]) == {"post"} for path in dh_paths)
    assert all("requestBody" in paths[path]["post"] for path in dh_paths)
    assert set(paths["/api/dh/caesar"]["post"]["requestBody"]["content"]) == {
        "application/json",
        "multipart/form-data",
    }


def test_params_missing_alpha_is_suggestion_only(client: TestClient) -> None:
    response = client.post("/api/dh/params", json={"q": "23"})
    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "q": "23",
        "alpha": None,
        "factors": ["2", "11"],
        "primitiveRootChecks": [],
        "suggestedAlpha": "5",
    }


def test_params_oversized_q_keeps_manual_range_message(client: TestClient) -> None:
    response = client.post("/api/dh/params", json={"q": str(1 << 128)})
    assert response.status_code == 422
    assert response.json() == {
        "success": False,
        "code": "Q_OUT_OF_RANGE",
        "message": "q phải từ 5 đến 10¹², hoặc dùng sinh tham số ngẫu nhiên.",
        "field": "q",
    }


@pytest.mark.parametrize("bits", [16, 32, 64, 128])
def test_random_params_all_bit_sizes_are_composable(client: TestClient, bits: int) -> None:
    response = client.post("/api/dh/params/random", json={"bits": bits})
    assert response.status_code == 200
    body = response.json()
    assert int(body["q"]).bit_length() == bits
    assert int(body["q"]) == 2 * int(body["p"]) + 1
    assert (
        client.post("/api/dh/keypair", json={"q": body["q"], "alpha": body["alpha"]}).status_code
        == 200
    )


def test_keypair_and_left_to_right_trace(client: TestClient) -> None:
    response = client.post("/api/dh/keypair", json={"q": "353", "alpha": "3", "privateKey": "97"})
    assert response.status_code == 200
    body = response.json()
    assert (body["privateKey"], body["publicKey"]) == ("97", "40")
    assert [step["result"] for step in body["steps"]] == [
        "3",
        "27",
        "23",
        "176",
        "265",
        "331",
        "40",
    ]
    assert all(type(step["index"]) is int and type(step["bit"]) is int for step in body["steps"])


def test_shared_secret_stallings_vector(client: TestClient) -> None:
    response = client.post(
        "/api/dh/shared-secret",
        json={"q": "353", "privateKey": "97", "otherPublicKey": "248"},
    )
    assert response.status_code == 200
    assert response.json()["sharedKey"] == "160"
    assert response.json()["steps"][-1]["result"] == "160"


def test_exchange_exposes_educational_private_keys(client: TestClient) -> None:
    response = client.post(
        "/api/dh/exchange",
        json={"q": "353", "alpha": "3", "privateKeyA": "97", "privateKeyB": "233"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["match"] is True
    assert (body["privateKeyA"], body["privateKeyB"]) == ("97", "233")
    assert (body["sharedKeyA"], body["sharedKeyB"]) == ("160", "160")
    assert body["warning"] == {
        "code": "EDUCATIONAL_PRIVATE_KEYS",
        "message": (
            "Response trả khóa riêng để minh họa và đối chiếu phép tính. Trong hệ thống thực tế, "
            "khóa riêng không được gửi hoặc lưu ngoài bên sở hữu; khóa công khai phải được xác "
            "thực để chống tấn công người đứng giữa (MITM)."
        ),
    }
    # These values come from the request arithmetic, not a canned demonstration payload.
    assert (body["publicKeyA"], body["publicKeyB"]) == ("40", "248")
    for group, output in (
        ("publicKeyA", "publicKeyA"),
        ("publicKeyB", "publicKeyB"),
        ("sharedKeyA", "sharedKeyA"),
        ("sharedKeyB", "sharedKeyB"),
    ):
        assert body["steps"][group][-1]["result"] == body[output]


def test_caesar_json_tc11_and_shift_zero(client: TestClient) -> None:
    encrypted = client.post(
        "/api/dh/caesar",
        json={
            "q": "353",
            "privateKey": "97",
            "otherPublicKey": "248",
            "action": "encrypt",
            "data": "Hello World",
        },
    )
    assert encrypted.status_code == 200
    assert encrypted.json() == {
        "success": True,
        "sharedKey": "160",
        "shift": "4",
        "result": "Lipps Asvph",
    }

    zero = client.post(
        "/api/dh/caesar",
        json={
            "q": "47",
            "privateKey": "3",
            "otherPublicKey": "22",
            "action": "encrypt",
            "data": "Abc",
        },
    )
    assert zero.status_code == 200
    assert zero.json()["shift"] == "0"
    assert zero.json()["warning"]["code"] == "SHIFT_ZERO"


def test_caesar_json_decrypt_round_trip_preserves_non_ascii(client: TestClient) -> None:
    payload = {
        "q": "353",
        "privateKey": "97",
        "otherPublicKey": "248",
        "action": "encrypt",
        "data": "Xin chào, Việt Nam!",
    }
    encrypted = client.post("/api/dh/caesar", json=payload)
    assert encrypted.status_code == 200
    decrypted = client.post(
        "/api/dh/caesar",
        json={**payload, "action": "decrypt", "data": encrypted.json()["result"]},
    )
    assert decrypted.status_code == 200
    assert decrypted.json()["result"] == payload["data"]
    assert "à" in encrypted.json()["result"] and "ệ" in encrypted.json()["result"]


@pytest.mark.parametrize(
    ("path", "payload", "code", "field", "message"),
    [
        ("/api/dh/params", {"q": 23}, "NOT_INTEGER", "q", "Giá trị phải là số nguyên dương."),
        ("/api/dh/params", {"q": "21"}, "NOT_PRIME", "q", "q = 21 không phải số nguyên tố."),
        (
            "/api/dh/params",
            {"q": "1000000000039"},
            "Q_OUT_OF_RANGE",
            "q",
            "q phải từ 5 đến 10¹², hoặc dùng sinh tham số ngẫu nhiên.",
        ),
        (
            "/api/dh/params",
            {"q": "23", "alpha": "25"},
            "ALPHA_OUT_OF_RANGE",
            "alpha",
            "α phải thỏa 1 < α < q = 23.",  # noqa: RUF001
        ),
        (
            "/api/dh/params",
            {"q": "23", "alpha": "4"},
            "NOT_PRIMITIVE_ROOT",
            "alpha",
            "α = 4 không phải nguyên căn của 23. Gợi ý α = 5.",  # noqa: RUF001
        ),
        (
            "/api/dh/keypair",
            {"q": "23", "alpha": "5", "privateKey": "11"},
            "PRIVATE_KEY_WEAK",
            "privateKey",
            "Khóa riêng tạo khóa công khai không hợp lệ. Hãy chọn khóa riêng khác.",
        ),
        (
            "/api/dh/shared-secret",
            {"q": "23", "privateKey": "6", "otherPublicKey": "22"},
            "PUBLIC_KEY_INVALID",
            "otherPublicKey",
            "Khóa công khai của bên kia không hợp lệ.",
        ),
        (
            "/api/dh/shared-secret",
            {"q": "23", "privateKey": "22", "otherPublicKey": "8"},
            "PRIVATE_KEY_OUT_OF_RANGE",
            "privateKey",
            "Khóa riêng phải thỏa 2 ≤ X ≤ q − 2 = 21.",  # noqa: RUF001
        ),
    ],
)
def test_exact_domain_errors(
    client: TestClient,
    path: str,
    payload: dict[str, object],
    code: str,
    field: str,
    message: str,
) -> None:
    response = client.post(path, json=payload)
    assert response.status_code == 422
    assert response.json() == {
        "success": False,
        "code": code,
        "message": message,
        "field": field,
    }


def test_strict_media_fields_and_bits(client: TestClient) -> None:
    media = client.post("/api/dh/params", content=b"{}", headers={"content-type": "text/plain"})
    assert media.status_code == 415
    assert media.json()["code"] == "UNSUPPORTED_MEDIA_TYPE"

    unknown = client.post("/api/dh/params", json={"q": "23", "extra": True})
    assert unknown.status_code == 422
    assert unknown.json()["field"] == "extra"

    wrong_bits = client.post("/api/dh/params/random", json={"bits": "32"})
    assert wrong_bits.status_code == 422
    assert wrong_bits.json()["code"] == "BITS_INVALID"


def test_caesar_validation_precedence_and_missing_action(client: TestClient) -> None:
    base = {"privateKey": "6", "otherPublicKey": "8", "data": ""}
    q_first = client.post("/api/dh/caesar", json={**base, "q": "21", "action": "invalid"})
    assert q_first.status_code == 422
    assert q_first.json()["code"] == "NOT_PRIME"
    missing_action = client.post("/api/dh/caesar", json={**base, "q": "23", "data": "A"})
    assert missing_action.status_code == 422
    assert missing_action.json() == {
        "success": False,
        "code": "INVALID_ACTION",
        "message": "Action phải là encrypt hoặc decrypt.",
        "field": "action",
    }
    empty = client.post("/api/dh/caesar", json={**base, "q": "23", "action": "encrypt"})
    assert empty.status_code == 422
    assert empty.json()["code"] == "EMPTY_INPUT"
    unsupported = client.post(
        "/api/dh/caesar", content=b"x", headers={"content-type": "text/plain"}
    )
    assert unsupported.status_code == 415
    assert unsupported.json()["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_q_domain_precedes_later_scalar_errors_and_null_is_not_omission(
    client: TestClient,
) -> None:
    params = client.post("/api/dh/params", json={"q": "21", "alpha": "x"})
    assert params.json()["code"] == "NOT_PRIME"
    keypair = client.post("/api/dh/keypair", json={"q": "21", "alpha": "x", "privateKey": "x"})
    assert keypair.json()["code"] == "NOT_PRIME"
    shared = client.post(
        "/api/dh/shared-secret",
        json={"q": "21", "privateKey": "x", "otherPublicKey": "x"},
    )
    assert shared.json()["code"] == "NOT_PRIME"
    explicit_null = client.post("/api/dh/params", json={"q": "23", "alpha": None})
    assert explicit_null.json() == {
        "success": False,
        "code": "NOT_INTEGER",
        "message": "Giá trị phải là số nguyên dương.",
        "field": "alpha",
    }


def test_oversized_keys_use_key_specific_range_errors(client: TestClient) -> None:
    huge = str(2**128)
    private = client.post(
        "/api/dh/shared-secret",
        json={"q": "23", "privateKey": huge, "otherPublicKey": "8"},
    )
    assert private.json()["code"] == "PRIVATE_KEY_OUT_OF_RANGE"
    assert private.json()["field"] == "privateKey"
    public = client.post(
        "/api/dh/shared-secret",
        json={"q": "23", "privateKey": "6", "otherPublicKey": huge},
    )
    assert public.json()["code"] == "PUBLIC_KEY_INVALID"
    assert public.json()["field"] == "otherPublicKey"


def test_caesar_multipart_bom_and_file_errors(client: TestClient) -> None:
    data = {"q": "353", "privateKey": "97", "otherPublicKey": "248", "action": "encrypt"}
    response = client.post(
        "/api/dh/caesar", data=data, files={"file": ("input.txt", b"\xef\xbb\xbfHello World")}
    )
    assert response.status_code == 200
    assert response.json()["result"] == "Lipps Asvph"
    assert response.headers["content-type"].startswith("application/json")

    uppercase = client.post(
        "/api/dh/caesar",
        data=data,
        files={"file": ("input.TXT", b"A\r\nB\nC\rD")},
    )
    assert uppercase.status_code == 200
    assert uppercase.json()["result"] == "E\r\nF\nG\rH"

    extension = client.post("/api/dh/caesar", data=data, files={"file": ("input.bin", b"Hello")})
    assert extension.status_code == 415
    assert extension.json()["code"] == "FILE_INVALID"

    encoding = client.post("/api/dh/caesar", data=data, files={"file": ("input.txt", b"\xff")})
    assert encoding.status_code == 415
    assert encoding.json()["code"] == "UNSUPPORTED_ENCODING"

    missing = client.post(
        "/api/dh/caesar",
        files={name: (None, value) for name, value in data.items()},
    )
    assert missing.status_code == 422
    assert missing.json()["code"] == "MISSING_FILE"
    empty = client.post("/api/dh/caesar", data=data, files={"file": ("input.txt", b"")})
    assert empty.status_code == 422
    assert empty.json()["code"] == "EMPTY_INPUT"

    malformed = client.post(
        "/api/dh/caesar",
        content=b'--cut\r\nContent-Disposition: form-data; name="q"\r\n\r\n353',
        headers={"content-type": "multipart/form-data; boundary=cut"},
    )
    assert malformed.status_code == 422
    assert malformed.json() == {
        "success": False,
        "code": "INVALID_REQUEST",
        "message": "Dữ liệu gửi lên không hợp lệ.",
        "field": None,
    }


def test_file_size_boundaries(
    client: TestClient, exact_limit_bytes: bytes, over_limit_bytes: bytes
) -> None:
    data = {"q": "353", "privateKey": "97", "otherPublicKey": "248", "action": "encrypt"}
    accepted = client.post(
        "/api/dh/caesar", data=data, files={"file": ("input.txt", exact_limit_bytes)}
    )
    assert accepted.status_code == 200
    rejected = client.post(
        "/api/dh/caesar", data=data, files={"file": ("input.txt", over_limit_bytes)}
    )
    assert rejected.status_code == 413
    assert rejected.json() == {
        "success": False,
        "code": "FILE_INVALID",
        "message": "File vượt quá dung lượng tối đa 5 MB.",
        "field": "file",
    }


def test_internal_and_file_read_failures_are_redacted(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "private-secret-must-not-leak"

    def fail_core(*_args, **_kwargs):
        raise RuntimeError(secret)

    monkeypatch.setattr(routes_dh.dh, "shared_secret", fail_core)
    internal = client.post(
        "/api/dh/shared-secret",
        json={"q": "23", "privateKey": "6", "otherPublicKey": "8"},
    )
    assert internal.status_code == 500
    assert internal.json() == {
        "success": False,
        "code": "INTERNAL_ERROR",
        "message": "Đã xảy ra lỗi hệ thống.",
        "field": None,
    }
    assert secret not in caplog.text

    monkeypatch.undo()

    async def fail_read(_upload):
        raise FileReadError()

    monkeypatch.setattr(routes_dh, "read_limited_bytes", fail_read)
    file_error = client.post(
        "/api/dh/caesar",
        data={
            "q": "23",
            "privateKey": "6",
            "otherPublicKey": "8",
            "action": "encrypt",
        },
        files={"file": ("input.txt", b"A")},
    )
    assert file_error.status_code == 500
    assert file_error.json() == {
        "success": False,
        "code": "FILE_READ_FAILED",
        "message": "Không thể đọc file.",
        "field": "file",
    }
