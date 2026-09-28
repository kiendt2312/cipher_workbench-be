"""Contract tests for the project's canonical Playfair profile."""

from __future__ import annotations

import pytest

from app.core.playfair import (
    build_matrix,
    normalize_keyword,
    normalize_text,
    prepare_plaintext,
    strip_trailing_filler,
    transform_pair,
    transform_text,
    validate_ciphertext,
)

KEY = "PLAYFAIR EXAMPLE"
EXPECTED_MATRIX = (
    ("P", "L", "A", "Y", "F"),
    ("I", "R", "E", "X", "M"),
    ("B", "C", "D", "G", "H"),
    ("K", "N", "O", "Q", "S"),
    ("T", "U", "V", "W", "Z"),
)


def test_keyword_normalization_and_canonical_matrix() -> None:
    assert normalize_keyword(KEY) == "PLAYFIREXM"
    assert normalize_keyword("JIG") == "IG"
    assert build_matrix(KEY) == EXPECTED_MATRIX


@pytest.mark.parametrize("keyword", ["đỏ", "ß", "123 !", ""])
def test_keyword_without_ascii_letters_is_rejected(keyword: str) -> None:
    with pytest.raises(ValueError, match="keyword"):
        normalize_keyword(keyword)


def test_matrix_contains_exactly_twenty_five_unique_letters_without_j() -> None:
    flattened = "".join(char for row in build_matrix(KEY) for char in row)

    assert len(flattened) == len(set(flattened)) == 25
    assert set(flattened) == set("ABCDEFGHIKLMNOPQRSTUVWXYZ")


def test_plaintext_normalization_is_ascii_only_and_maps_j_to_i() -> None:
    assert normalize_text("Jolly, café! 123") == "IOLLYCAF"
    assert normalize_text("123 — tiếng Việt: ộ") == "TINGVIT"
    assert normalize_text("123 — ộ 🙂") == ""


@pytest.mark.parametrize(
    "plaintext, expected",
    [
        pytest.param("BALLOON", "BALXLOON", id="repeated-letter"),
        pytest.param("XX", "XQXQ", id="repeated-x"),
        pytest.param("ABX", "ABXQ", id="odd-x"),
        pytest.param("ABC", "ABCX", id="odd-non-x"),
    ],
)
def test_digraph_preparation_is_deterministic(plaintext: str, expected: str) -> None:
    prepared = prepare_plaintext(plaintext)

    assert prepared == expected
    assert len(prepared) % 2 == 0
    assert all(prepared[index] != prepared[index + 1] for index in range(0, len(prepared), 2))


def test_pair_rules_cover_row_column_rectangle_and_wraparound() -> None:
    matrix = build_matrix(KEY)

    assert transform_pair("FP", matrix, "encrypt") == "PL"
    assert transform_pair("PB", matrix, "decrypt") == "TI"
    assert transform_pair("HI", matrix, "encrypt") == "BM"


def test_canonical_encrypt_and_decrypt_vectors() -> None:
    plaintext = "HIDE THE GOLD IN THE TREE STUMP"
    ciphertext = "BMODZBXDNABEKUDMUIXMMOUVIF"

    assert prepare_plaintext(plaintext) == "HIDETHEGOLDINTHETREXESTUMP"
    assert transform_text(plaintext, KEY, "encrypt") == ciphertext
    assert transform_text(ciphertext, KEY, "decrypt") == "HIDETHEGOLDINTHETREXESTUMP"


@pytest.mark.parametrize(
    "plaintext, prepared, ciphertext",
    [
        pytest.param("XX", "XQXQ", "GWGW", id="repeated-x"),
        pytest.param("ABX", "ABXQ", "PDGW", id="odd-x"),
        pytest.param("HIDE THE GOLD", "HIDETHEGOLDX", "BMODZBXDNAGE", id="text-file"),
    ],
)
def test_collision_and_text_file_vectors(plaintext: str, prepared: str, ciphertext: str) -> None:
    assert prepare_plaintext(plaintext) == prepared
    assert transform_text(plaintext, KEY, "encrypt") == ciphertext


def test_decrypt_drops_only_trailing_filler_and_does_not_restore_format() -> None:
    assert transform_text("GWGW", KEY, "decrypt") == "XQX"

    encrypted = transform_text("Jig saw!", KEY, "encrypt")
    assert transform_text(encrypted, KEY, "decrypt") == "IXIGSAW"


@pytest.mark.parametrize(
    "plaintext, expected",
    [
        pytest.param("ABX", "ABX", id="trailing-q-after-x"),
        pytest.param("ABC", "ABC", id="trailing-x"),
        pytest.param("HIDE THE GOLD", "HIDETHEGOLD", id="odd-tail"),
        pytest.param("BALLOON", "BALXLOON", id="middle-filler-kept"),
        pytest.param("HELLOS", "HELXLOS", id="middle-kept-tail-dropped"),
        pytest.param("AB", "AB", id="no-filler"),
    ],
)
def test_decrypt_round_trip_drops_trailing_filler(plaintext: str, expected: str) -> None:
    assert transform_text(transform_text(plaintext, KEY, "encrypt"), KEY, "decrypt") == expected


@pytest.mark.parametrize(
    "text, expected",
    [("ABXQ", "ABX"), ("ABCX", "ABC"), ("XQXQ", "XQX"), ("ABQX", "ABQ"), ("ABCD", "ABCD")],
)
def test_strip_trailing_filler_removes_one_filler(text: str, expected: str) -> None:
    assert strip_trailing_filler(text) == expected


def test_even_plaintext_ending_in_x_is_known_ambiguity() -> None:
    assert transform_text(transform_text("AX", KEY, "encrypt"), KEY, "decrypt") == "A"


@pytest.mark.parametrize(
    "ciphertext, message",
    [
        pytest.param("123 — ộ", "letters", id="empty-after-normalization"),
        pytest.param("ABC", "even", id="odd"),
        pytest.param("AABC", "identical", id="duplicate-pair"),
    ],
)
def test_ciphertext_validation_rejects_unrepairable_input(ciphertext: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_ciphertext(ciphertext)
    with pytest.raises(ValueError, match=message):
        transform_text(ciphertext, KEY, "decrypt")


def test_empty_normalized_plaintext_is_rejected() -> None:
    with pytest.raises(ValueError, match="letters"):
        prepare_plaintext("123 — ộ")
    with pytest.raises(ValueError, match="letters"):
        transform_text("123 — ộ", KEY, "encrypt")


@pytest.mark.parametrize("operation", ["ENCRYPT", "decrypt ", "", None])
def test_invalid_operation_is_rejected(operation: object) -> None:
    with pytest.raises(ValueError, match="operation"):
        transform_text("AB", KEY, operation)  # type: ignore[arg-type]


def test_core_is_deterministic_and_transport_independent() -> None:
    expected = "BMODZBXDNAGE"
    for _ in range(5):
        assert transform_text("HIDE THE GOLD", KEY, "encrypt") == expected

    json_text = "HIDE THE GOLD"
    decoded_file_text = "HIDE THE GOLD"
    assert transform_text(json_text, KEY, "encrypt") == transform_text(
        decoded_file_text, KEY, "encrypt"
    )
