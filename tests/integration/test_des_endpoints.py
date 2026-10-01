"""Contract tests for the four DES endpoints (scope test vectors T01-T20 and DES-E01..E13)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.des_schemas import MAX_TEXT_BYTES
from app.errors import messages
from app.main import app

KEY = "133457799BBCDFF1"
ENCRYPT = "/api/des/encrypt"
DECRYPT = "/api/des/decrypt"
TRACE = "/api/des/trace"
FILE = "/api/des/file"
W01 = {"code": "W01", "message": messages.DES_WEAK_KEY, "details": {}}
W02 = {"code": "W02", "message": messages.DES_SEMI_WEAK_KEY, "details": {}}


def _w03(repeated: int) -> dict[str, Any]:
    return {
        "code": "W03",
        "message": messages.DES_ECB_REPEATED_BLOCKS,
        "details": {"repeatedBlocks": repeated},
    }


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _ok(response: Any, result: str, warnings: list[dict[str, Any]] | None = None) -> None:
    assert response.status_code == 200, response.text
    assert response.json() == {"success": True, "result": result, "warnings": warnings or []}


def _error(response: Any, status: int, message: str) -> None:
    assert response.status_code == status, response.text
    assert response.json() == {"success": False, "message": message}


def _file(
    client: TestClient,
    content: bytes,
    *,
    filename: str = "input.txt",
    **fields: str,
) -> Any:
    data = {"key": KEY, "action": "encrypt", **fields}
    return client.post(FILE, files={"file": (filename, content, "text/plain")}, data=data)


# --- vectors through the JSON API --------------------------------------------------


@pytest.mark.parametrize(
    ("plain", "key", "cipher", "warnings"),
    [
        ("0123456789ABCDEF", KEY, "85E813540F0AB405", []),  # T01
        ("A1B2C3D4E5F60978", "10012334455EFA67", "C291E07ED3004A9E", []),  # T02
        ("0123456789ABCDEF", "123456789ABCDEF0", "85E813540F0AB405", []),  # T03
        ("8787878787878787", "0E329232EA6D0D73", "0000000000000000", []),  # T04
        ("0000000000000000", "0000000000000000", "8CA64DE9C1B123A7", [W01]),  # T05
        ("0123456789ABCDEF0123456789ABCDEF", KEY, "85E813540F0AB405" * 2, [_w03(1)]),  # T06
        ("0123456789ABCDEF", "0101010101010101", "617B3A0CE8F07100", [W01]),  # T12
        ("0123456789ABCDEF", "011F011F010E010E", "6F2C1F78866CCF13", [W02]),  # T13
    ],
)
def test_hex_vectors(
    client: TestClient, plain: str, key: str, cipher: str, warnings: list[dict[str, Any]]
) -> None:
    _ok(
        client.post(ENCRYPT, json={"text": plain, "key": key, "inputFormat": "hex"}),
        cipher,
        warnings,
    )
    decrypted = client.post(DECRYPT, json={"text": cipher, "key": key, "outputFormat": "hex"})
    assert decrypted.status_code == 200
    assert decrypted.json()["result"] == plain


@pytest.mark.parametrize(
    ("text", "cipher"),
    [
        ("Hello World", "B1CA74BB3514268701A9ACC3E4E69FAA"),  # T07
        ("Xin chào DES!", "06602CF53D9AD6AAC800F8D8643F636C"),  # T08
        ("12345678", "8B96B79529CCA218FDF2E174492922F8"),  # T09
    ],
)
def test_text_vectors_round_trip(client: TestClient, text: str, cipher: str) -> None:
    _ok(client.post(ENCRYPT, json={"text": text, "key": KEY}), cipher)
    _ok(client.post(DECRYPT, json={"text": cipher, "key": KEY}), text)


def test_cbc_vectors(client: TestClient) -> None:
    hello = {"text": "Hello World", "key": KEY, "mode": "CBC", "iv": "0000000000000000"}
    _ok(client.post(ENCRYPT, json=hello), "B1CA74BB351426875F9A5BCA734D9EF4")  # T10
    repeated = {
        "text": "0123456789ABCDEF0123456789ABCDEF",
        "key": KEY,
        "inputFormat": "hex",
        "mode": "CBC",
        "iv": "1234567890ABCDEF",
    }
    _ok(client.post(ENCRYPT, json=repeated), "F02B595EB219AB97E6DB189E19AF7792")  # T11, no W03
    _ok(
        client.post(
            DECRYPT,
            json={
                "text": "F02B595EB219AB97E6DB189E19AF7792",
                "key": KEY,
                "outputFormat": "hex",
                "mode": "CBC",
                "iv": "1234 5678 90ab cdef",
            },
        ),
        "0123456789ABCDEF0123456789ABCDEF",
    )


def test_t18_decrypt_to_hex_keeps_padding(client: TestClient) -> None:
    _ok(
        client.post(DECRYPT, json={"text": "85E813540F0AB405", "key": KEY, "outputFormat": "hex"}),
        "0123456789ABCDEF",
    )


def test_iv_is_ignored_in_ecb(client: TestClient) -> None:
    _ok(
        client.post(ENCRYPT, json={"text": "Hello World", "key": KEY, "mode": "ECB", "iv": "xyz"}),
        "B1CA74BB3514268701A9ACC3E4E69FAA",
    )
    _ok(
        client.post(ENCRYPT, json={"text": "Hello World", "key": KEY, "iv": None}),
        "B1CA74BB3514268701A9ACC3E4E69FAA",
    )


def test_whitespace_lowercase_key_and_hex(client: TestClient) -> None:
    _ok(
        client.post(
            ENCRYPT,
            json={"text": "01234567 89abcdef", "key": "1334 5779 9bbc dff1", "inputFormat": "hex"},
        ),
        "85E813540F0AB405",
    )
    _ok(
        client.post(DECRYPT, json={"text": "b1ca74bb35142687\n01a9acc3e4e69faa", "key": KEY}),
        "Hello World",
    )


def test_whitespace_only_text_is_data_in_text_format(client: TestClient) -> None:
    response = client.post(ENCRYPT, json={"text": "   ", "key": KEY})
    assert response.status_code == 200
    _ok(client.post(DECRYPT, json={"text": response.json()["result"], "key": KEY}), "   ")


def test_weak_key_and_repeated_blocks_warn_in_order(client: TestClient) -> None:
    _ok(
        client.post(
            ENCRYPT,
            json={"text": "0" * 32, "key": "0000000000000000", "inputFormat": "hex"},
        ),
        "8CA64DE9C1B123A7" * 2,
        [W01, _w03(1)],
    )


def test_decrypt_with_weak_key_warns_w01(client: TestClient) -> None:
    _ok(
        client.post(
            DECRYPT,
            json={"text": "617B3A0CE8F07100", "key": "0101010101010101", "outputFormat": "hex"},
        ),
        "0123456789ABCDEF",
        [W01],
    )


def test_application_json_suffix_is_accepted(client: TestClient) -> None:
    response = client.post(
        ENCRYPT,
        content=b'{"text":"Hello World","key":"133457799BBCDFF1"}',
        headers={"content-type": "application/vnd.api+json; charset=utf-8"},
    )
    _ok(response, "B1CA74BB3514268701A9ACC3E4E69FAA")


# --- error table ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "body", "status", "message"),
    [
        (ENCRYPT, {"text": "abc", "key": "13345779"}, 422, messages.DES_KEY_LENGTH.format(n=8)),
        (ENCRYPT, {"text": "abc", "key": "133457799BBCDFFG"}, 422, messages.DES_KEY_NOT_HEX),
        (
            DECRYPT,
            {"text": "85E813540F0AB40", "key": KEY},
            422,
            messages.DES_DATA_LENGTH.format(n=15),
        ),
        (DECRYPT, {"text": "85E813540F0AB405", "key": KEY}, 422, messages.DES_INVALID_PADDING),
        (DECRYPT, {"text": "09A9EB2F8878EBF8", "key": KEY}, 422, messages.DES_INVALID_UTF8),
        (ENCRYPT, {"text": "", "key": KEY}, 422, messages.DES_TEXT_EMPTY),
        (ENCRYPT, {"key": KEY}, 422, messages.DES_TEXT_EMPTY),
        (ENCRYPT, {"text": None, "key": KEY}, 422, messages.DES_TEXT_EMPTY),
        (ENCRYPT, {"text": " \n", "key": KEY, "inputFormat": "hex"}, 422, messages.DES_TEXT_EMPTY),
        (DECRYPT, {"text": "", "key": KEY}, 422, messages.DES_TEXT_EMPTY),
        (ENCRYPT, {"text": "abc"}, 422, messages.DES_MISSING_KEY),
        (ENCRYPT, {"text": "abc", "key": None}, 422, messages.DES_MISSING_KEY),
        (ENCRYPT, {"text": "abc", "key": "   "}, 422, messages.DES_MISSING_KEY),
        (
            ENCRYPT,
            {"text": "0123456789ABCDEZ", "key": KEY, "inputFormat": "hex"},
            422,
            messages.DES_DATA_NOT_HEX,
        ),
        (DECRYPT, {"text": "XYZ", "key": KEY}, 422, messages.DES_DATA_NOT_HEX),
        (ENCRYPT, {"text": "abc", "key": KEY, "mode": "CBC"}, 422, messages.DES_INVALID_IV),
        (
            ENCRYPT,
            {"text": "abc", "key": KEY, "mode": "CBC", "iv": "123"},
            422,
            messages.DES_INVALID_IV,
        ),
        (
            DECRYPT,
            {"text": "85E813540F0AB405", "key": KEY, "mode": "CBC", "iv": None},
            422,
            messages.DES_INVALID_IV,
        ),
        (
            ENCRYPT,
            {"text": "abc", "key": KEY, "mode": "cbc"},
            422,
            messages.DES_INVALID_PARAMETER.format(name="mode"),
        ),
        (
            ENCRYPT,
            {"text": "abc", "key": KEY, "mode": None},
            422,
            messages.DES_INVALID_PARAMETER.format(name="mode"),
        ),
        (
            ENCRYPT,
            {"text": "abc", "key": KEY, "inputFormat": "base64"},
            422,
            messages.DES_INVALID_PARAMETER.format(name="inputFormat"),
        ),
        (
            DECRYPT,
            {"text": "abc", "key": KEY, "outputFormat": 1},
            422,
            messages.DES_INVALID_PARAMETER.format(name="outputFormat"),
        ),
        (
            TRACE,
            {"block": "0123456789ABCDEF", "key": KEY, "operation": "both"},
            422,
            messages.DES_INVALID_PARAMETER.format(name="operation"),
        ),
        (ENCRYPT, {"text": 123, "key": KEY}, 422, messages.INVALID_REQUEST_BODY),
        (ENCRYPT, {"text": "abc", "key": 133457799}, 422, messages.INVALID_REQUEST_BODY),
        (ENCRYPT, {"text": "abc", "key": KEY, "iv": 0}, 422, messages.INVALID_REQUEST_BODY),
        (
            ENCRYPT,
            {"text": "abc", "key": KEY, "outputFormat": "hex"},
            422,
            messages.INVALID_REQUEST_BODY,
        ),
        (
            DECRYPT,
            {"text": "abc", "key": KEY, "inputFormat": "hex"},
            422,
            messages.INVALID_REQUEST_BODY,
        ),
        (
            TRACE,
            {"block": "0123456789ABCDEF", "key": KEY, "mode": "ECB"},
            422,
            messages.INVALID_REQUEST_BODY,
        ),
    ],
)
def test_error_table(
    client: TestClient, path: str, body: dict[str, Any], status: int, message: str
) -> None:
    _error(client.post(path, json=body), status, message)


@pytest.mark.parametrize(
    ("content", "content_type"),
    [
        (b'{"text":"a","key":"133457799BBCDFF1"}', "text/plain"),
        (b"[]", "application/json"),
        (b"{not json", "application/json"),
        (b'{"text":"a","text":"b","key":"133457799BBCDFF1"}', "application/json"),
        (b'{"text":"\\ud800","key":"133457799BBCDFF1"}', "application/json"),
        (b'{"text":NaN,"key":"133457799BBCDFF1"}', "application/json"),
    ],
)
def test_malformed_bodies(client: TestClient, content: bytes, content_type: str) -> None:
    _error(
        client.post(ENCRYPT, content=content, headers={"content-type": content_type}),
        422,
        messages.INVALID_REQUEST_BODY,
    )


# --- precedence ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"text": "", "key": "bad", "extra": 1}, messages.INVALID_REQUEST_BODY),
        (
            {"text": "x", "key": "abc", "mode": "XYZ"},
            messages.DES_INVALID_PARAMETER.format(name="mode"),
        ),
        (
            {"text": "x", "key": "abc", "inputFormat": "b", "mode": "XYZ"},
            messages.DES_INVALID_PARAMETER.format(name="inputFormat"),
        ),
        ({"text": "", "key": "13345779", "mode": "CBC"}, messages.DES_KEY_LENGTH.format(n=8)),
        ({"text": "", "key": "G3345779", "mode": "CBC"}, messages.DES_KEY_NOT_HEX),
        ({"text": "", "key": KEY, "mode": "CBC"}, messages.DES_INVALID_IV),
        ({"text": "", "key": KEY}, messages.DES_TEXT_EMPTY),
    ],
)
def test_json_precedence(client: TestClient, body: dict[str, Any], message: str) -> None:
    _error(client.post(ENCRYPT, json=body), 422, message)


def test_size_precedes_parameter_errors(client: TestClient) -> None:
    oversized = "a" * (MAX_TEXT_BYTES + 1)
    _error(
        client.post(ENCRYPT, json={"text": oversized, "key": "bad", "mode": "X"}),
        413,
        messages.DES_TOO_LARGE,
    )


def test_exact_size_limit_is_accepted_and_one_more_byte_rejected(client: TestClient) -> None:
    exact = "z" * MAX_TEXT_BYTES
    response = client.post(DECRYPT, json={"text": exact, "key": KEY, "outputFormat": "hex"})
    _error(response, 422, messages.DES_DATA_NOT_HEX)  # passes the size check
    multibyte = "é" * (MAX_TEXT_BYTES // 2) + "a"  # 5,242,881 UTF-8 bytes
    _error(client.post(ENCRYPT, json={"text": multibyte, "key": KEY}), 413, messages.DES_TOO_LARGE)


# --- trace ------------------------------------------------------------------------------


def test_trace_t01_matches_scope_sample(client: TestClient) -> None:
    response = client.post(
        TRACE,
        json={"block": "01234567 89abcdef", "key": "133457799bbcdff1", "operation": "encrypt"},
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"success", "result", "trace", "warnings"}
    assert body["result"] == "85E813540F0AB405"
    assert body["warnings"] == []
    trace = body["trace"]
    assert set(trace) == {
        "operation", "input", "key", "pc1", "subkeys", "ip", "l0", "r0", "rounds", "preOutput",
    }  # fmt: skip
    assert (trace["operation"], trace["input"], trace["key"]) == (
        "encrypt",
        "0123456789ABCDEF",
        "133457799BBCDFF1",
    )
    assert trace["pc1"] == "F0CCAAF556678F"
    assert len(trace["subkeys"]) == 16
    assert trace["subkeys"][0] == {
        "n": 1,
        "shift": 1,
        "c": "E19955F",
        "d": "AACCF1E",
        "k": "1B02EFFC7072",
    }
    assert (trace["ip"], trace["l0"], trace["r0"]) == ("CC00CCFFF0AAF0AA", "CC00CCFF", "F0AAF0AA")
    first = trace["rounds"][0]
    assert first["expansion"] == "7A15557A1555"
    assert first["xorKey"] == "6117BA866527"
    assert first["sbox"][:2] == [
        {"row": 0, "col": 12, "value": 5},
        {"row": 1, "col": 8, "value": 12},
    ]
    assert len(first["sbox"]) == 8
    assert (first["sboxOutput"], first["f"], first["l"], first["r"]) == (
        "5C82B597",
        "234AA9BB",
        "F0AAF0AA",
        "EF4A6544",
    )
    assert trace["preOutput"] == "0A4CD99543423234"


def test_trace_decrypt_reverses_subkeys(client: TestClient) -> None:
    response = client.post(
        TRACE, json={"block": "85E813540F0AB405", "key": KEY, "operation": "decrypt"}
    )
    body = response.json()
    assert body["result"] == "0123456789ABCDEF"
    assert [round_["subkey"] for round_ in body["trace"]["rounds"]] == list(range(16, 0, -1))


def test_trace_defaults_to_encrypt_and_warns_weak_keys(client: TestClient) -> None:
    body = client.post(TRACE, json={"block": "0123456789ABCDEF", "key": "0101010101010101"}).json()
    assert body["trace"]["operation"] == "encrypt"
    assert body["result"] == "617B3A0CE8F07100"
    assert body["warnings"] == [W01]


@pytest.mark.parametrize(
    "block", ["0123456789ABCDEF0123456789ABCDEF", "0123456789ABCDEG", "", None, "0123"]
)
def test_trace_requires_exactly_one_block(client: TestClient, block: str | None) -> None:
    _error(client.post(TRACE, json={"block": block, "key": KEY}), 422, messages.DES_TRACE_BLOCK)


def test_trace_key_error_precedes_block_error(client: TestClient) -> None:
    _error(
        client.post(TRACE, json={"block": "XYZ", "key": "13345779"}),
        422,
        messages.DES_KEY_LENGTH.format(n=8),
    )


# --- file -----------------------------------------------------------------------------------


def test_file_encrypt_content_mode(client: TestClient) -> None:
    _ok(_file(client, b"Hello World"), "B1CA74BB3514268701A9ACC3E4E69FAA")


def test_file_decrypt_multiline_hex(client: TestClient) -> None:
    _ok(
        _file(client, b"B1CA74BB35142687\r\n01A9ACC3E4E69FAA\r\n", action="decrypt"),
        "Hello World",
    )


def test_file_cbc(client: TestClient) -> None:
    _ok(
        _file(client, b"Hello World", mode="CBC", iv="0000000000000000"),
        "B1CA74BB351426875F9A5BCA734D9EF4",
    )


def test_file_attachment_name_and_body(client: TestClient) -> None:
    response = _file(client, b"Hello World", filename="bai tap.txt", response_mode="file")
    assert response.status_code == 200
    assert response.content == b"B1CA74BB3514268701A9ACC3E4E69FAA"
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["content-disposition"] == (
        'attachment; filename="bai tap.encrypted.txt"'
    )


def test_file_decrypt_attachment_restores_bom(client: TestClient) -> None:
    response = _file(
        client,
        b"\xef\xbb\xbfB1CA74BB3514268701A9ACC3E4E69FAA",
        filename="cipher.TXT",
        action="decrypt",
        response_mode="file",
    )
    assert response.status_code == 200
    assert response.content == b"\xef\xbb\xbfHello World"
    assert response.headers["content-disposition"] == 'attachment; filename="cipher.decrypted.txt"'


def test_file_content_mode_reports_w03(client: TestClient) -> None:
    response = _file(client, b"AAAAAAAAAAAAAAAA")
    assert response.json()["warnings"] == [_w03(1)]


def test_file_decrypt_warns_weak_key(client: TestClient) -> None:
    encrypted = _file(client, b"abc", key="0101010101010101").json()
    assert encrypted["warnings"] == [W01]
    decrypted = _file(
        client, encrypted["result"].encode(), key="0101010101010101", action="decrypt"
    )
    _ok(decrypted, "abc", [W01])


def test_file_exact_limit_accepted(client: TestClient) -> None:
    response = _file(client, b"z" * MAX_TEXT_BYTES, action="decrypt")
    _error(response, 422, messages.DES_DATA_NOT_HEX)


@pytest.mark.parametrize(
    ("content", "filename", "fields", "status", "message"),
    [
        (b"a" * (MAX_TEXT_BYTES + 1), "big.txt", {}, 413, messages.FILE_TOO_LARGE),
        (b"Hello", "data.md", {}, 415, messages.UNSUPPORTED_FILE_TYPE),
        (b"", "empty.txt", {}, 422, messages.EMPTY_FILE),
        (b"\xff\xfe", "bad.txt", {}, 415, messages.UNSUPPORTED_ENCODING),
        (b" \r\n ", "blank.txt", {"action": "decrypt"}, 422, messages.DES_TEXT_EMPTY),
        (b"XYZ", "c.txt", {"action": "decrypt"}, 422, messages.DES_DATA_NOT_HEX),
        (b"ABC", "c.txt", {"action": "decrypt"}, 422, messages.DES_DATA_LENGTH.format(n=3)),
        (b"85E813540F0AB405", "c.txt", {"action": "decrypt"}, 422, messages.DES_INVALID_PADDING),
        (b"09A9EB2F8878EBF8", "c.txt", {"action": "decrypt"}, 422, messages.DES_INVALID_UTF8),
        (b"abc", "a.txt", {"key": ""}, 422, messages.DES_MISSING_KEY),
        (b"abc", "a.txt", {"key": "XYZ"}, 422, messages.DES_KEY_NOT_HEX),
        (b"abc", "a.txt", {"action": "both"}, 422, messages.INVALID_ACTION),
        (b"abc", "a.txt", {"response_mode": "x"}, 422, messages.INVALID_RESPONSE_MODE),
        (b"abc", "a.txt", {"mode": "OFB"}, 422, messages.DES_INVALID_PARAMETER.format(name="mode")),
        (b"abc", "a.txt", {"mode": "CBC"}, 422, messages.DES_INVALID_IV),
        (b"abc", "a.txt", {"inputFormat": "hex"}, 422, messages.INVALID_REQUEST_BODY),
    ],
)
def test_file_errors(
    client: TestClient,
    content: bytes,
    filename: str,
    fields: dict[str, str],
    status: int,
    message: str,
) -> None:
    _error(_file(client, content, filename=filename, **fields), status, message)


def test_file_missing_key_and_action(client: TestClient) -> None:
    response = client.post(FILE, files={"file": ("a.txt", b"abc", "text/plain")})
    _error(response, 422, messages.DES_MISSING_KEY)


@pytest.mark.parametrize(
    ("files", "data", "message"),
    [
        (None, {"action": "encrypt"}, messages.MISSING_FILE),
        (
            {"file": ("bad.md", b"x", "text/plain")},
            {"key": "ABC", "action": "foo"},
            messages.DES_KEY_LENGTH.format(n=3),
        ),
        (
            {"file": ("bad.md", b"x", "text/plain")},
            {"key": KEY, "action": "encrypt", "mode": "OFB"},
            messages.DES_INVALID_PARAMETER.format(name="mode"),
        ),
        (
            {"file": ("bad.md", b"x", "text/plain")},
            {"key": KEY, "action": "encrypt", "mode": "CBC"},
            messages.DES_INVALID_IV,
        ),
    ],
)
def test_file_precedence(
    client: TestClient,
    files: dict[str, Any] | None,
    data: dict[str, str],
    message: str,
) -> None:
    if files is None:
        response = client.post(
            FILE,
            content=(
                b'--cut\r\nContent-Disposition: form-data; name="action"\r\n\r\nencrypt\r\n'
                b"--cut--\r\n"
            ),
            headers={"content-type": "multipart/form-data; boundary=cut"},
        )
    else:
        response = client.post(FILE, files=files, data=data)
    _error(response, 422, message)


def test_file_duplicate_field_rejected(client: TestClient) -> None:
    response = client.post(
        FILE,
        content=(
            b'--cut\r\nContent-Disposition: form-data; name="file"; filename="a.txt"\r\n'
            b"Content-Type: text/plain\r\n\r\nabc\r\n"
            b'--cut\r\nContent-Disposition: form-data; name="key"\r\n\r\n133457799BBCDFF1\r\n'
            b'--cut\r\nContent-Disposition: form-data; name="key"\r\n\r\n133457799BBCDFF1\r\n'
            b'--cut\r\nContent-Disposition: form-data; name="action"\r\n\r\nencrypt\r\n'
            b"--cut--\r\n"
        ),
        headers={"content-type": "multipart/form-data; boundary=cut"},
    )
    _error(response, 422, messages.INVALID_REQUEST_BODY)


def test_file_key_as_upload_is_rejected(client: TestClient) -> None:
    response = client.post(
        FILE,
        files={"file": ("a.txt", b"abc", "text/plain"), "key": ("k.txt", b"x", "text/plain")},
        data={"action": "encrypt"},
    )
    _error(response, 422, messages.INVALID_REQUEST_BODY)


def test_file_error_in_file_mode_is_json(client: TestClient) -> None:
    response = _file(client, b"abc", key="xyz", response_mode="file")
    _error(response, 422, messages.DES_KEY_NOT_HEX)
    assert "content-disposition" not in response.headers


def test_truncated_multipart_rejected(client: TestClient) -> None:
    response = client.post(
        FILE,
        content=(
            b'--cut\r\nContent-Disposition: form-data; name="file"; filename="input.txt"\r\n'
            b"Content-Type: text/plain\r\n\r\nABCDE"
        ),
        headers={"content-type": "multipart/form-data; boundary=cut"},
    )
    _error(response, 422, messages.INVALID_REQUEST_BODY)


# --- contract ---------------------------------------------------------------------------------


def test_openapi_documents_des_routes(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for path in (ENCRYPT, DECRYPT, TRACE, FILE):
        operation = paths[path]["post"]
        assert operation["tags"] == ["DES"]
        assert {"413", "422", "500"} <= operation["responses"].keys()
    encrypt_schema = paths[ENCRYPT]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert set(encrypt_schema["properties"]) == {"text", "key", "inputFormat", "mode", "iv"}
    assert encrypt_schema["additionalProperties"] is False
    file_schema = paths[FILE]["post"]["requestBody"]["content"]["multipart/form-data"]["schema"]
    assert set(file_schema["properties"]) == {
        "file",
        "key",
        "action",
        "mode",
        "iv",
        "response_mode",
    }
    assert set(file_schema["required"]) == {"file", "key", "action"}


def test_other_ciphers_keep_their_envelopes(client: TestClient) -> None:
    caesar = client.post("/api/caesar/encrypt", json={"text": "", "key": 3})
    assert set(caesar.json()) == {"success", "message"}
    assert client.post("/api/caesar/encrypt", json={"text": "ABC", "key": 3}).json() == {
        "success": True,
        "result": "DEF",
    }
    hill = client.post("/api/hill/encrypt", json={"text": "", "key": [[3, 3], [2, 5]]})
    assert set(hill.json()) == {"success", "message", "code", "details"}


def test_file_field_as_text_is_rejected(client: TestClient) -> None:
    response = client.post(FILE, data={"file": "abc", "key": KEY, "action": "encrypt"})
    _error(response, 422, messages.INVALID_REQUEST_BODY)


def test_ciphertext_of_five_mib_text_exceeds_the_decrypt_limit(client: TestClient) -> None:
    ciphertext_hex = "0" * (2 * (MAX_TEXT_BYTES + 8))  # 5 MiB text + one PKCS#7 block, as hex
    _error(
        client.post(DECRYPT, json={"text": ciphertext_hex, "key": KEY}), 413, messages.DES_TOO_LARGE
    )


def test_unexpected_failure_is_masked_and_not_logged_with_secrets(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from app.core import des

    def explode(*args: object, **kwargs: object) -> bytes:
        raise RuntimeError("boom")

    monkeypatch.setattr(des, "encrypt_bytes", explode)
    caplog.set_level("ERROR", logger="app.errors.handlers")
    response = client.post(
        ENCRYPT,
        json={
            "text": "SECRETPLAINTEXT",
            "key": "0E329232EA6D0D73",
            "mode": "CBC",
            "iv": "FEDCBA9876543210",
        },
    )

    _error(response, 500, messages.UNEXPECTED_FAILURE)
    assert "RuntimeError" in caplog.text
    for secret in ("SECRETPLAINTEXT", "0E329232EA6D0D73", "FEDCBA9876543210"):
        assert secret not in caplog.text
