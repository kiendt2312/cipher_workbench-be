"""Strict transport-unit coverage for DH schemas."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api import dh_schemas
from app.errors.exceptions import DhError


def _error(callable_, *args, **kwargs) -> DhError:
    with pytest.raises(DhError) as caught:
        callable_(*args, **kwargs)
    return caught.value


def test_json_decoder_preserves_controls_and_rejects_bad_documents() -> None:
    decoded = dh_schemas.decode_json(b'{"bits":32,"q":"23"}', "application/json; charset=utf-8")
    assert type(decoded["bits"]) is dh_schemas.JsonIntegerToken
    assert decoded["q"] == "23"

    assert _error(dh_schemas.decode_json, b"{}", "text/plain").status_code == 415
    for raw in (b"[]", b"{", b'{"q":"23","q":"29"}', b'{"q":NaN}'):
        assert _error(dh_schemas.decode_json, raw, "application/json").code == "INVALID_REQUEST"


def test_exact_fields_decimal_bits_and_action_validation() -> None:
    dh_schemas.fields({"q": "23"}, allowed=("q",), required=("q",))
    assert (
        _error(dh_schemas.fields, {"q": "23", "x": 1}, allowed=("q",), required=("q",)).field == "x"
    )
    assert _error(dh_schemas.fields, {}, allowed=("q",), required=("q",)).field == "q"

    assert dh_schemas.decimal("23", "q") == 23
    for raw in (23, "", "01", "-1", "١"):  # noqa: RUF001
        assert _error(dh_schemas.decimal, raw, "q").code == "NOT_INTEGER"
    assert _error(dh_schemas.decimal, str(2**128), "q").code == "Q_OUT_OF_RANGE"

    assert dh_schemas.bits(dh_schemas.JsonIntegerToken("32")) == 32
    for raw in ("32", dh_schemas.JsonIntegerToken("24")):
        assert _error(dh_schemas.bits, raw).code == "BITS_INVALID"
    assert dh_schemas.action("encrypt") == "encrypt"
    assert _error(dh_schemas.action, "sign").code == "INVALID_ACTION"


def test_trace_check_and_openapi_serializers() -> None:
    step = SimpleNamespace(index=0, bit=1, exponent_prefix=1, squared=1, multiplied=None, result=5)
    assert dh_schemas.serialize_steps([step]) == [
        {
            "index": 0,
            "bit": 1,
            "exponentPrefix": "1",
            "squared": "1",
            "multiplied": None,
            "result": "5",
        }
    ]
    check = SimpleNamespace(factor=2, exponent=11, result=22, passes=True)
    assert dh_schemas.serialize_checks([check]) == [
        {"factor": "2", "exponent": "11", "result": "22", "passes": True}
    ]
    json_schema = dh_schemas.json_request_schema(dh_schemas.ParamsRequest)
    assert set(json_schema["requestBody"]["content"]) == {"application/json"}
    caesar_schema = dh_schemas.caesar_request_schema()
    assert set(caesar_schema["requestBody"]["content"]) == {
        "application/json",
        "multipart/form-data",
    }
