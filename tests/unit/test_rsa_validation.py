"""Strict raw JSON and ordered RSA validation tests."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.api import rsa_schemas as schemas
from app.core import rsa
from app.errors.exceptions import RsaError


def _decode(raw: str) -> dict:
    return schemas.decode_json(raw.encode(), "application/json; charset=utf-8")


@pytest.mark.parametrize("raw", ["", "[]", "null", "{", "NaN", '"text"'])
def test_decode_requires_one_standard_json_object(raw: str) -> None:
    with pytest.raises(RsaError) as caught:
        _decode(raw)
    assert (caught.value.code, caught.value.field) == ("INVALID_REQUEST", None)


def test_decode_rejects_duplicate_at_any_object_depth() -> None:
    for raw, field in [('{"p":"17","p":"19"}', "p"), ('{"x":{"n":"1","n":"2"}}', "n")]:
        with pytest.raises(RsaError) as caught:
            _decode(raw)
        assert (caught.value.code, caught.value.field) == ("INVALID_REQUEST", field)


def test_decode_preserves_raw_integer_and_float_lexemes() -> None:
    payload = _decode('{"bits":128,"float":1e3}')
    assert type(payload["bits"]) is schemas.JsonIntegerToken
    assert payload["bits"] == "128"
    assert type(payload["float"]) is schemas.JsonFloatToken
    assert payload["float"] == "1e3"


def test_decode_requires_utf8_but_preserves_accepted_utf8_bom_behavior() -> None:
    payload = schemas.decode_json(b'\xef\xbb\xbf{"bits":128}', "application/json")
    assert type(payload["bits"]) is schemas.JsonIntegerToken
    assert payload["bits"] == "128"

    with pytest.raises(RsaError) as duplicate:
        schemas.decode_json(
            b'\xef\xbb\xbf{"bits":128,"bits":64}',
            "application/json",
        )
    assert (duplicate.value.code, duplicate.value.field) == ("INVALID_REQUEST", "bits")

    for encoding in ("utf-16", "utf-32"):
        raw = '{"bits":128}'.encode(encoding)
        with pytest.raises(RsaError) as caught:
            schemas.decode_json(raw, "application/json")
        assert (caught.value.code, caught.value.field) == ("INVALID_REQUEST", None)


@pytest.mark.parametrize("content_type", [None, "text/plain", "application/problem+json"])
def test_decode_rejects_non_contract_media_types(content_type: str | None) -> None:
    with pytest.raises(RsaError) as caught:
        schemas.decode_json(b"{}", content_type)
    assert (caught.value.status_code, caught.value.code) == (415, "UNSUPPORTED_MEDIA_TYPE")


@pytest.mark.parametrize(
    "raw",
    ["-1", "+1", " 1", "1 ", "1.0", "1e3", "1_0", "\uff11\uff12\uff13", "", 7, True, None],
)
def test_decimal_parser_is_ascii_string_only(raw: object) -> None:
    with pytest.raises(RsaError) as caught:
        schemas.parse_decimal(raw, "n")
    assert (caught.value.code, caught.value.field) == ("NOT_INTEGER", "n")


def test_decimal_parser_raw_and_value_ceiling_with_canonical_acceptance() -> None:
    assert schemas.parse_decimal("00065", "data") == 65
    assert schemas.parse_decimal(str(rsa.MAX_OPERAND), "n") == rsa.MAX_OPERAND
    for raw in ("0" * 129, str(rsa.MAX_OPERAND + 1)):
        with pytest.raises(RsaError) as caught:
            schemas.parse_decimal(raw, "n")
        assert caught.value.code == "NUMBER_TOO_LARGE"


def test_manual_field_order_and_unknown_raw_appearance() -> None:
    with pytest.raises(RsaError) as caught:
        schemas.validate_manual_key(_decode('{"e":"x","p":"x","q":"x"}'))
    assert caught.value.field == "p"
    with pytest.raises(RsaError) as caught:
        schemas.validate_manual_key(_decode('{"z":1,"a":2}'))
    assert caught.value.field == "z"


@pytest.mark.parametrize(
    "raw", ['{"bits":"128"}', '{"bits":true}', '{"bits":24}', '{"bits":12345678901}']
)
def test_bits_is_strict_bounded_json_integer(raw: str) -> None:
    with pytest.raises(RsaError) as caught:
        schemas.validate_random_key(_decode(raw))
    assert (caught.value.code, caught.value.field) == ("INVALID_BITS", "bits")


def test_discriminator_and_inapplicable_fields_are_strict() -> None:
    cases = [
        ('{"e":"7","n":"187","data":"1"}', "inputType"),
        ('{"e":"7","n":"187","inputType":"other","data":"1"}', "inputType"),
        (
            '{"e":"7","n":"187","inputType":"number","data":"1","mode":"char"}',
            "mode",
        ),
        ('{"e":"7","n":"187","inputType":"text","data":"A"}', "mode"),
    ]
    for raw, field in cases:
        with pytest.raises(RsaError) as caught:
            schemas.validate_encrypt(_decode(raw))
        assert (caught.value.code, caught.value.field) == ("INVALID_REQUEST", field)


def test_collection_cap_precedes_item_parsing() -> None:
    payload = {
        "d": "3",
        "n": "257",
        "inputType": "text",
        "mode": "char",
        "cipher": ["bad"] + ["0"] * 10_000,
    }
    raw = json.dumps(payload, separators=(",", ":"))
    with pytest.raises(RsaError) as caught:
        schemas.validate_decrypt(_decode(raw))
    assert (caught.value.code, caught.value.field) == ("INPUT_TOO_LARGE", "cipher")


def test_block_collection_accepts_exact_40000_item_limit() -> None:
    payload = {
        "d": "3",
        "n": "257",
        "inputType": "text",
        "mode": "block",
        "cipher": ["0"] * 40_000,
        "originalUtf8ByteLength": schemas.JsonIntegerToken("40000"),
    }
    validated = schemas.validate_decrypt(payload)
    assert isinstance(validated, schemas.TextDecryptRequest)
    assert len(validated.cipher) == 40_000


def test_numeric_schema_order_beats_json_member_order() -> None:
    raw = '{"inputType":"number","data":"1","n":"y","e":"x"}'
    with pytest.raises(RsaError) as caught:
        schemas.validate_encrypt(_decode(raw))
    assert (caught.value.code, caught.value.field) == ("NOT_INTEGER", "e")


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ('{"d":"23","n":"187","inputType":"number","cipher":[]}', "INVALID_REQUEST"),
        (
            '{"d":"23","n":"187","inputType":"number","cipher":["1","2"]}',
            "INVALID_REQUEST",
        ),
        (
            '{"d":"3","n":"67591","inputType":"text","mode":"block","cipher":["1"]}',
            "INVALID_REQUEST",
        ),
        (
            '{"d":"3","n":"67591","inputType":"text","mode":"block",'
            '"cipher":["1"],"originalUtf8ByteLength":"1"}',
            "INVALID_LENGTH_METADATA",
        ),
    ],
)
def test_decrypt_shape_and_length_metadata(raw: str, code: str) -> None:
    with pytest.raises(RsaError) as caught:
        schemas.validate_decrypt(_decode(raw))
    assert caught.value.code == code


def test_trace_control_is_strict_and_checked_after_domain() -> None:
    raw = '{"e":"1","n":"187","inputType":"number","data":"1","traceBlockIndex":true}'
    with pytest.raises(RsaError) as caught:
        schemas.validate_encrypt(_decode(raw))
    assert caught.value.code == "E_OUT_OF_RANGE"

    raw = '{"e":"7","n":"187","inputType":"number","data":"1","traceBlockIndex":true}'
    with pytest.raises(RsaError) as caught:
        schemas.validate_encrypt(_decode(raw))
    assert caught.value.code == "TRACE_INDEX_OUT_OF_RANGE"


def test_exact_models_forbid_extra_and_emit_aliases() -> None:
    model = schemas.NumberEncryptResponse(
        success=True,
        inputType="number",
        blocks=["65"],
        cipher=["2790"],
        blockSize=None,
        trace=None,
    )
    assert model.model_dump(by_alias=True) == {
        "success": True,
        "inputType": "number",
        "blocks": ["65"],
        "cipher": ["2790"],
        "blockSize": None,
        "trace": None,
    }
    assert model.model_json_schema()["additionalProperties"] is False
    with pytest.raises(ValidationError):
        schemas.NumberEncryptResponse(
            success=True,
            inputType="number",
            blocks=["65"],
            cipher=["2790"],
            blockSize=None,
            trace=None,
            extra="forbidden",
        )
