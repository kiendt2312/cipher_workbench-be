"""Focused tests for Hill's strict decoder and validation precedence."""

import json

import pytest

from app.api.hill_schemas import MAX_TEXT_BYTES, decode, validate_key, validate_transform
from app.errors.exceptions import HillError

TRANSFORM_FIELDS = {"text", "key", "keyword", "m", "options"}


def parsed(value: object, allowed: set[str] = TRANSFORM_FIELDS) -> dict[str, object]:
    return decode(json.dumps(value).encode(), "application/json; charset=utf-8", allowed)


@pytest.mark.parametrize(
    "raw,content_type",
    [
        (b"{}", "text/plain"),
        (b"[1]", "application/json"),
        (b"{", "application/json"),
        (b'{"text":"x","text":"y"}', "application/json"),
        (b'{"text":"\\ud800"}', "application/json"),
        (b'{"unknown":1}', "application/json"),
        (b'{"x":NaN}', "application/json"),
    ],
)
def test_decode_rejects_invalid_json_contract(raw: bytes, content_type: str) -> None:
    with pytest.raises(HillError) as caught:
        decode(raw, content_type, TRANSFORM_FIELDS)
    assert (caught.value.code, caught.value.status_code, caught.value.details) == ("E11", 422, {})


def test_decode_accepts_vendor_json_and_normalizes_huge_integer_cells() -> None:
    payload = decode(
        b'{"text":"HELP","key":[[100000000000000000000000003,3],[2,-1]]}',
        "application/vnd.cipher+json",
        TRANSFORM_FIELDS,
    )
    request = validate_transform(payload)
    assert request.matrix == [[25, 3], [2, 25]]


@pytest.mark.parametrize("text", [None, "", " \t\n"])
def test_E01_precedes_bad_key(text: object) -> None:
    with pytest.raises(HillError) as caught:
        validate_transform(parsed({"text": text, "key": "bad"}))
    assert caught.value.code == "E01"


def test_E06_precedes_key_validation_and_reports_utf8_bytes() -> None:
    text = "é" * (MAX_TEXT_BYTES // 2) + "A"
    with pytest.raises(HillError) as caught:
        validate_transform(parsed({"text": text, "key": "bad"}))
    assert caught.value.code == "E06"
    assert caught.value.status_code == 413
    assert caught.value.details == {"actualBytes": MAX_TEXT_BYTES + 1, "maxBytes": MAX_TEXT_BYTES}


def test_exact_text_limit_is_accepted() -> None:
    text = "é" * (MAX_TEXT_BYTES // 2 - 1) + "AA"
    request = validate_transform(parsed({"text": text, "key": [[3, 3], [2, 5]]}))
    assert len((request.text or "").encode("utf-8")) == MAX_TEXT_BYTES


@pytest.mark.parametrize("value", [False, 1.5, [], {}])
def test_text_wrong_type_is_E11(value: object) -> None:
    with pytest.raises(HillError) as caught:
        validate_transform(parsed({"text": value, "key": [[3, 3], [2, 5]]}))
    assert caught.value.code == "E11"


@pytest.mark.parametrize(
    "payload,code,details",
    [
        ({}, "E03", {"reason": "key_variant"}),
        ({"key": [[3, 3], [2, 5]], "keyword": "HILL", "m": 2}, "E03", {"reason": "key_variant"}),
        ({"key": [[1]], "m": 1}, "E11", {}),
        ({"key": [[1]]}, "E08", {"min": 2, "max": 4, "m": 1}),
        ({"key": [[1, 0], [0]]}, "E03", {"reason": "invalid_shape"}),
        ({"key": [[1, 0], [0, True]]}, "E03", {"reason": "invalid_cell", "row": 2, "column": 2}),
        ({"keyword": "HILL"}, "E08", {"min": 2, "max": 4}),
        ({"keyword": "HILL", "m": 5}, "E08", {"min": 2, "max": 4, "m": 5}),
        ({"keyword": "HI L", "m": 2}, "E09", {"m": 2, "expected": 4, "actual": 3}),
        ({"keyword": 12, "m": 2}, "E09", {"m": 2, "expected": 4, "actual": None}),
    ],
)
def test_key_error_table(payload: dict[str, object], code: str, details: dict[str, object]) -> None:
    with pytest.raises(HillError) as caught:
        validate_key(parsed(payload))
    assert caught.value.code == code
    assert caught.value.details == details


@pytest.mark.parametrize(
    "options,field",
    [
        ([], "options"),
        ({"unknown": True}, "options"),
        ({"stripDiacritics": 1}, "stripDiacritics"),
        ({"padChar": "x"}, "padChar"),
        ({"padChar": "XX"}, "padChar"),
    ],
)
def test_options_are_strict(options: object, field: str) -> None:
    with pytest.raises(HillError) as caught:
        validate_transform(parsed({"text": "HELP", "key": [[3, 3], [2, 5]], "options": options}))
    assert caught.value.code == "E10"
    assert caught.value.details == {"field": field}


def test_keyword_and_option_defaults() -> None:
    request = validate_transform(parsed({"text": "HELP", "keyword": "HILL", "m": 2}))
    assert request.matrix == [[7, 8], [11, 11]]
    assert request.options == {"stripDiacritics": False, "padChar": "X"}
