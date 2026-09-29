"""Unit acceptance tests for the transport-independent Hill cipher core."""

from __future__ import annotations

import random

import pytest

from app.core.hill import (
    HillError,
    adjugate,
    analyze_key,
    decrypt,
    decrypt_text,
    determinant,
    encrypt,
    encrypt_text,
    gcd,
    matrix_multiply,
    minor,
    mod,
    modular_inverse,
    normalize_key,
    normalize_matrix,
    random_key,
    random_key_result,
    row_times_matrix,
    transform_text,
    validate_text_size,
)

T01_KEY = [[3, 3], [2, 5]]
T01_INVERSE = [[15, 17], [20, 9]]
T01_ANALYSIS = {
    "matrix": T01_KEY,
    "m": 2,
    "det": 9,
    "gcd": 1,
    "detInverse": 3,
    "adjugate": [[5, 23], [24, 3]],
    "inverse": T01_INVERSE,
}


def _identity(size: int) -> list[list[int]]:
    return [[int(row == column) for column in range(size)] for row in range(size)]


def test_mod_gcd_and_all_invertible_residues() -> None:
    inverse_pairs = {
        1: 1,
        3: 9,
        5: 21,
        7: 15,
        9: 3,
        11: 19,
        15: 7,
        17: 23,
        19: 11,
        21: 5,
        23: 17,
        25: 25,
    }

    assert mod(-1) == 25
    assert gcd(-26, 52) == 26
    for value, expected in inverse_pairs.items():
        assert modular_inverse(value) == expected
        assert value * expected % 26 == 1


@pytest.mark.parametrize("value", [0, 2, 4, 6, 13, 26])
def test_noninvertible_values_raise_hill_error(value: int) -> None:
    with pytest.raises(HillError) as exc_info:
        modular_inverse(value)

    assert exc_info.value.code == "E04"


def test_matrix_arithmetic_uses_row_vectors_and_modulo_26() -> None:
    assert minor(T01_KEY, 0, 0) == [[5]]
    assert determinant(T01_KEY) == 9
    assert adjugate(T01_KEY) == [[5, 23], [24, 3]]
    assert row_times_matrix([7, 4], T01_KEY) == [3, 15]
    assert matrix_multiply(T01_KEY, T01_INVERSE) == _identity(2)
    assert normalize_matrix([[-1, 26], [52, 27]]) == [[25, 0], [0, 1]]


def test_t01_analysis_has_the_complete_normalized_contract() -> None:
    assert analyze_key(T01_KEY) == T01_ANALYSIS


@pytest.mark.parametrize(
    ("key", "plaintext", "ciphertext"),
    [
        ([[3, 3], [2, 5]], "HELP", "DPLE"),
        ([[11, 8], [3, 7]], "JULY", "DELW"),
        ([[6, 24, 1], [13, 16, 10], [20, 17, 15]], "ACT", "QRT"),
        ([[6, 13, 20], [24, 16, 17], [1, 10, 15]], "ACT", "POH"),
    ],
)
def test_t01_to_t04_row_vector_vectors(
    key: list[list[int]], plaintext: str, ciphertext: str
) -> None:
    result = encrypt(plaintext, key)

    assert result["result"] == ciphertext
    assert decrypt(ciphertext, key)["result"] == plaintext


def test_four_by_four_vector_and_inverse() -> None:
    key = [[3, 1, 2, 0], [0, 5, 1, 4], [0, 0, 7, 2], [0, 0, 0, 9]]
    analysis = analyze_key(key)

    assert analysis["det"] == 9
    assert encrypt("TEST", key)["result"] == "FNMP"
    assert decrypt("FNMP", key)["result"] == "TEST"
    assert matrix_multiply(key, analysis["inverse"]) == _identity(4)


def test_keyword_hill_is_row_major_and_matches_matrix_key() -> None:
    from_keyword = encrypt("HILLCIPHER", keyword="HILL", m=2)
    from_matrix = encrypt("HILLCIPHER", [[7, 8], [11, 11]])

    assert normalize_key(keyword="HILL", m=2) == [[7, 8], [11, 11]]
    assert from_keyword["result"] == "HOQBYAAPHL"
    assert from_keyword == from_matrix


def test_padding_blocks_case_punctuation_and_custom_pad() -> None:
    result = encrypt("HELLO!", T01_KEY)

    assert result["result"] == "DPDKK!B"
    assert result["blocks"] == [
        {"input": [7, 4], "output": [3, 15]},
        {"input": [11, 11], "output": [3, 10]},
        {"input": [14, 23], "output": [10, 1]},
    ]
    assert result["warnings"][0] == {
        "code": "W01",
        "message": "Đã thêm 1 ký tự X vào cuối để đủ khối 2 chữ.",
        "details": {"count": 1, "char": "X", "m": 2},
    }
    assert encrypt("HELLO", T01_KEY, pad_char="Q")["result"] == "DPDKWS"
    assert encrypt("Help, me!", T01_KEY)["result"] == "Dple, se!"
    assert decrypt("DPDKKB", T01_KEY)["result"] == "HELLOX"


def test_identity_and_self_inverse_warnings_have_the_expected_reason() -> None:
    identity_result = encrypt("HELP", _identity(2))
    self_inverse_result = encrypt("HELP", [[1, 0], [0, 25]])

    assert identity_result["result"] == "HELP"
    assert identity_result["warnings"][-1]["details"] == {"reason": "identity"}
    assert self_inverse_result["warnings"][-1]["details"] == {"reason": "self_inverse"}


def test_vietnamese_nfc_nfd_strip_and_preservation_rules() -> None:
    nfc = "ế"
    nfd = "e\u0302\u0301"
    kept_nfc = encrypt(f"A{nfc}Z", T01_KEY)
    kept_nfd = encrypt(f"A{nfd}Z", T01_KEY)
    stripped_nfc = encrypt(nfc + "X", T01_KEY, strip_diacritics=True)
    stripped_nfd = encrypt(nfd + "X", T01_KEY, strip_diacritics=True)

    assert kept_nfc["result"] == f"Y{nfc}V"
    assert kept_nfd["result"] == f"Y{nfd}V"
    assert kept_nfc["warnings"][-1]["details"] == {"count": 1}
    assert kept_nfd["warnings"][-1]["details"] == {"count": 1}
    assert stripped_nfc["result"] == stripped_nfd["result"] == "gX"
    assert [warning["code"] for warning in stripped_nfc["warnings"]] == []
    assert encrypt("Đđ", _identity(2), strip_diacritics=True)["result"] == "Dd"


def test_non_vietnamese_unicode_is_kept_without_w02() -> None:
    result = encrypt("öΩ🙂A", _identity(2))

    assert result["result"] == "öΩ🙂AX"
    assert [warning["code"] for warning in result["warnings"]] == ["W01", "W03"]
    assert encrypt("o\u0308A", _identity(2))["result"] == "o\u0308AX"


def test_warning_order_includes_padding_vietnamese_and_weak_key() -> None:
    warnings = encrypt("Aế", _identity(2))["warnings"]

    assert [warning["code"] for warning in warnings] == ["W01", "W02", "W03"]
    assert warnings[0]["details"] == {"count": 1, "char": "X", "m": 2}
    assert warnings[1]["details"] == {"count": 1}
    assert warnings[2]["details"] == {"reason": "identity"}


def test_t08_to_t11_errors_follow_core_contract() -> None:
    with pytest.raises(HillError) as noninvertible:
        encrypt("HELP", [[2, 4], [1, 3]])
    assert noninvertible.value.code == "E04"
    assert noninvertible.value.details == {"det": 2, "gcd": 2, "divisor": 2}

    with pytest.raises(HillError) as det_thirteen:
        encrypt("HELP", [[13, 0], [0, 1]])
    assert det_thirteen.value.code == "E04"
    assert det_thirteen.value.details == {"det": 13, "gcd": 13, "divisor": 13}

    with pytest.raises(HillError) as short_ciphertext:
        decrypt("DPL", T01_KEY)
    assert short_ciphertext.value.code == "E05"
    assert short_ciphertext.value.details == {"n": 3, "m": 2}

    with pytest.raises(HillError) as no_ascii:
        encrypt("123 !!", T01_KEY)
    assert no_ascii.value.code == "E02"

    with pytest.raises(HillError) as blank:
        encrypt(" \t\n", T01_KEY)
    assert blank.value.code == "E01"


def test_key_keyword_matrix_and_option_validation() -> None:
    invalid_matrices = [
        [[1, 2, 3], [4, 5, 6]],
        [[1, True], [3, 4]],
        [[1, 2], [3, "4"]],
    ]
    for key in invalid_matrices:
        with pytest.raises(HillError) as exc_info:
            normalize_matrix(key)
        assert exc_info.value.code in {"E03", "E08"}

    with pytest.raises(HillError) as bad_keyword:
        normalize_key(keyword="HI!L", m=2)
    assert bad_keyword.value.code == "E09"
    assert bad_keyword.value.details == {"m": 2, "expected": 4, "actual": 3}

    with pytest.raises(HillError) as missing_m:
        normalize_key(keyword="HILL")
    assert missing_m.value.code == "E08"

    with pytest.raises(HillError) as invalid_options:
        encrypt("HELP", T01_KEY, options={"padChar": "x"})
    assert invalid_options.value.code == "E10"
    assert invalid_options.value.details == {"field": "padChar"}


def test_random_keys_are_invertible_nonidentity_and_round_trip() -> None:
    rng = random.Random(20260929)
    for size in (2, 3, 4):
        for _ in range(1000):
            key = random_key(size, rng=rng)
            analysis = analyze_key(key)
            assert key != _identity(size)
            assert analysis["gcd"] == 1
            assert matrix_multiply(key, analysis["inverse"]) == _identity(size)

        text = "AbCz" * 3 + "!"
        result = encrypt(text, key)
        assert decrypt(result["result"], key)["result"] == text


def test_random_key_result_and_string_only_adapters() -> None:
    result = random_key_result(2, rng=random.Random(4))

    assert set(result) == {"result", "warnings"}
    assert result["result"]["gcd"] == 1
    assert encrypt_text("HELP", T01_KEY) == "DPLE"
    assert decrypt_text("DPLE", T01_KEY) == "HELP"
    assert transform_text("HELP", T01_KEY, "encrypt") == "DPLE"


def test_utf8_size_boundary_and_lone_surrogate() -> None:
    assert validate_text_size("A" * 1_048_576) == 1_048_576
    assert validate_text_size("ế" * 349_525 + "A") == 1_048_576

    with pytest.raises(HillError) as too_large:
        validate_text_size("A" * (1_048_576 + 1))
    assert too_large.value.code == "E06"
    assert too_large.value.details == {
        "actualBytes": 1_048_577,
        "maxBytes": 1_048_576,
    }

    with pytest.raises(HillError) as surrogate:
        validate_text_size("\ud800")
    assert surrogate.value.code == "E11"
