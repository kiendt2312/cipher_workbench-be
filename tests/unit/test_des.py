"""Unit acceptance tests for the transport-independent DES core."""

from __future__ import annotations

import random

import pytest
from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
from cryptography.hazmat.primitives.ciphers import Cipher, modes

from app.core.des import (
    IP,
    IP_INV,
    LS,
    PC1,
    PC2,
    SBOXES,
    DesError,
    E,
    P,
    decode_utf8,
    decrypt_bytes,
    encrypt_bytes,
    f_function,
    key_schedule,
    key_strength,
    parse_hex,
    parse_iv,
    parse_key,
    permute,
    pkcs7_pad,
    pkcs7_unpad,
    repeated_blocks,
    rotate_left,
    trace_block,
)

SLIDE_KEY = "133457799BBCDFF1"
SLIDE_BLOCK = "0123456789ABCDEF"
SLIDE_CIPHER = "85E813540F0AB405"

T01_SUBKEYS = (
    "1B02EFFC7072",
    "79AED9DBC9E5",
    "55FC8A42CF99",
    "72ADD6DB351D",
    "7CEC07EB53A8",
    "63A53E507B2F",
    "EC84B7F618BC",
    "F78A3AC13BFB",
    "E0DBEBEDE781",
    "B1F347BA464F",
    "215FD3DED386",
    "7571F59467E9",
    "97C5D1FABA41",
    "5F43B7F2E73A",
    "BF918D3D3F0A",
    "CB3D8B0E17F5",
)
T01_ROUNDS = (
    ("F0AAF0AA", "EF4A6544"),
    ("EF4A6544", "CC017709"),
    ("CC017709", "A25C0BF4"),
    ("A25C0BF4", "77220045"),
    ("77220045", "8A4FA637"),
    ("8A4FA637", "E967CD69"),
    ("E967CD69", "064ABA10"),
    ("064ABA10", "D5694B90"),
    ("D5694B90", "247CC67A"),
    ("247CC67A", "B7D5D7B2"),
    ("B7D5D7B2", "C5783C78"),
    ("C5783C78", "75BD1858"),
    ("75BD1858", "18C3155A"),
    ("18C3155A", "C28C960D"),
    ("C28C960D", "43423234"),
    ("43423234", "0A4CD995"),
)
SLIDE21_SUBKEYS_FIRST_LAST = ("6830E4476326", "603289BB03E2")
SLIDE21_F = (
    "7A310767",
    "C00018C0",
    "87817212",
    "B70FC6BF",
    "B6675E9C",
    "F4AEF11B",
    "C92CBFEF",
    "17A5D519",
    "03C25758",
    "F6CB822C",
    "A28D857C",
    "3E939F34",
    "57062525",
    "91752C68",
    "5F14938B",
    "AF008339",
)


def _hex(text: str) -> bytes:
    return bytes.fromhex(text)


def _key(text: str) -> int:
    return parse_key(text)


def _reference(data: bytes, key: bytes, mode: str, iv: bytes | None, operation: str) -> bytes:
    """Encrypt or decrypt with the cryptography library, used only as an oracle."""

    algorithm = TripleDES(key * 3)
    cipher_mode = modes.ECB() if mode == "ECB" else modes.CBC(iv)
    cipher = Cipher(algorithm, cipher_mode)
    context = cipher.encryptor() if operation == "encrypt" else cipher.decryptor()
    return context.update(data) + context.finalize()


# --- tables -----------------------------------------------------------------


def test_table_sizes() -> None:
    assert (len(PC1), len(PC2), len(IP), len(IP_INV), len(E), len(P)) == (56, 48, 64, 64, 48, 32)
    assert len(LS) == 16 and sum(LS) == 28
    assert all(position % 8 for position in PC1)
    assert sorted(IP) == list(range(1, 65)) == sorted(IP_INV)


def test_each_sbox_row_is_a_permutation() -> None:
    assert len(SBOXES) == 8
    for box in SBOXES:
        assert len(box) == 4
        for row in box:
            assert sorted(row) == list(range(16))


def test_ip_inverse_undoes_ip() -> None:
    generator = random.Random(46)
    for _ in range(200):
        value = generator.getrandbits(64)
        assert permute(permute(value, IP, 64), IP_INV, 64) == value


def test_permute_reads_one_based_positions_from_the_left() -> None:
    assert permute(0b1000, (1,), 4) == 1
    assert permute(0b1000, (4, 1), 4) == 0b01
    assert permute(0b0001, (4, 1), 4) == 0b10


def test_rotate_left_wraps_28_bits() -> None:
    assert rotate_left(0x8000000, 1) == 1
    assert rotate_left(0xC000000, 2) == 3


# --- key schedule and rounds ------------------------------------------------


def test_slide_key_schedule_matches_reference_table() -> None:
    subkeys = key_schedule(_key(SLIDE_KEY))
    assert tuple(f"{subkey:012X}" for subkey in subkeys) == T01_SUBKEYS


def test_slide21_key_schedule_first_and_last() -> None:
    subkeys = key_schedule(_key("10012334455EFA67"))
    assert (f"{subkeys[0]:012X}", f"{subkeys[15]:012X}") == SLIDE21_SUBKEYS_FIRST_LAST


def test_round_one_f_function() -> None:
    k1 = key_schedule(_key(SLIDE_KEY))[0]
    assert f"{f_function(0xF0AAF0AA, k1):08X}" == "234AA9BB"


def test_trace_matches_every_round_of_t01() -> None:
    trace = trace_block(_key(SLIDE_KEY), int(SLIDE_BLOCK, 16), "encrypt")
    assert trace["result"] == SLIDE_CIPHER
    assert trace["pc1"] == "F0CCAAF556678F"
    assert trace["ip"] == "CC00CCFFF0AAF0AA"
    assert (trace["l0"], trace["r0"]) == ("CC00CCFF", "F0AAF0AA")
    assert trace["subkeys"][0] == {
        "n": 1,
        "shift": 1,
        "c": "E19955F",
        "d": "AACCF1E",
        "k": "1B02EFFC7072",
    }
    assert tuple(step["k"] for step in trace["subkeys"]) == T01_SUBKEYS
    assert [step["shift"] for step in trace["subkeys"]] == list(LS)
    last = trace["subkeys"][15]
    assert last["c"] + last["d"] == trace["pc1"]  # C16D16 = C0D0
    assert tuple((round_["l"], round_["r"]) for round_ in trace["rounds"]) == T01_ROUNDS
    assert trace["preOutput"] == "0A4CD99543423234"


def test_trace_round_one_details() -> None:
    round_one = trace_block(_key(SLIDE_KEY), int(SLIDE_BLOCK, 16), "encrypt")["rounds"][0]
    assert round_one["n"] == 1 and round_one["subkey"] == 1
    assert round_one["expansion"] == "7A15557A1555"
    assert round_one["xorKey"] == "6117BA866527"
    assert round_one["sbox"] == [
        {"row": 0, "col": 12, "value": 5},
        {"row": 1, "col": 8, "value": 12},
        {"row": 0, "col": 15, "value": 8},
        {"row": 2, "col": 13, "value": 2},
        {"row": 3, "col": 0, "value": 11},
        {"row": 2, "col": 3, "value": 5},
        {"row": 0, "col": 10, "value": 9},
        {"row": 3, "col": 3, "value": 7},
    ]
    assert round_one["sboxOutput"] == "5C82B597"
    assert round_one["f"] == "234AA9BB"


def test_trace_slide21_f_values() -> None:
    trace = trace_block(_key("10012334455EFA67"), int("A1B2C3D4E5F60978", 16), "encrypt")
    assert tuple(round_["f"] for round_ in trace["rounds"]) == SLIDE21_F
    assert (trace["l0"], trace["r0"]) == ("BCAA3855", "3FB3C026")
    assert trace["result"] == "C291E07ED3004A9E"


def test_trace_decrypt_uses_reversed_subkeys() -> None:
    trace = trace_block(_key(SLIDE_KEY), int(SLIDE_CIPHER, 16), "decrypt")
    assert trace["result"] == SLIDE_BLOCK
    assert [round_["subkey"] for round_ in trace["rounds"]] == list(range(16, 0, -1))
    assert tuple(step["k"] for step in trace["subkeys"]) == T01_SUBKEYS


def test_trace_agrees_with_fast_path_on_random_blocks() -> None:
    generator = random.Random(1977)
    for _ in range(1000):
        key = generator.getrandbits(64)
        block = generator.getrandbits(64)
        fast = encrypt_bytes(block.to_bytes(8, "big"), key, "ECB", None)
        assert trace_block(key, block, "encrypt")["result"] == fast.hex().upper()
        assert trace_block(key, int.from_bytes(fast, "big"), "decrypt")["result"] == f"{block:016X}"


# --- vectors ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("plain", "key", "cipher"),
    [
        ("0123456789ABCDEF", "133457799BBCDFF1", "85E813540F0AB405"),  # T01
        ("A1B2C3D4E5F60978", "10012334455EFA67", "C291E07ED3004A9E"),  # T02
        ("0123456789ABCDEF", "123456789ABCDEF0", "85E813540F0AB405"),  # T03 parity only
        ("8787878787878787", "0E329232EA6D0D73", "0000000000000000"),  # T04
        ("0000000000000000", "0000000000000000", "8CA64DE9C1B123A7"),  # T05
        (
            "0123456789ABCDEF0123456789ABCDEF",
            "133457799BBCDFF1",
            "85E813540F0AB40585E813540F0AB405",
        ),  # T06
        ("0123456789ABCDEF", "0101010101010101", "617B3A0CE8F07100"),  # T12
        ("0123456789ABCDEF", "011F011F010E010E", "6F2C1F78866CCF13"),  # T13
    ],
)
def test_hex_vectors_both_directions(plain: str, key: str, cipher: str) -> None:
    assert encrypt_bytes(_hex(plain), _key(key), "ECB", None).hex().upper() == cipher
    assert decrypt_bytes(_hex(cipher), _key(key), "ECB", None).hex().upper() == plain


@pytest.mark.parametrize(
    ("text", "cipher"),
    [
        ("Hello World", "B1CA74BB3514268701A9ACC3E4E69FAA"),  # T07
        ("Xin chào DES!", "06602CF53D9AD6AAC800F8D8643F636C"),  # T08
        ("12345678", "8B96B79529CCA218FDF2E174492922F8"),  # T09
    ],
)
def test_text_vectors_with_pkcs7(text: str, cipher: str) -> None:
    key = _key(SLIDE_KEY)
    data = pkcs7_pad(text.encode("utf-8"))
    assert encrypt_bytes(data, key, "ECB", None).hex().upper() == cipher
    assert decode_utf8(pkcs7_unpad(decrypt_bytes(_hex(cipher), key, "ECB", None))) == text


def test_cbc_vectors() -> None:
    key = _key(SLIDE_KEY)
    hello = encrypt_bytes(pkcs7_pad(b"Hello World"), key, "CBC", 0)
    assert hello.hex().upper() == "B1CA74BB351426875F9A5BCA734D9EF4"  # T10
    iv = parse_iv("1234567890ABCDEF")
    repeated = encrypt_bytes(_hex("0123456789ABCDEF" * 2), key, "CBC", iv)
    assert repeated.hex().upper() == "F02B595EB219AB97E6DB189E19AF7792"  # T11
    assert decrypt_bytes(repeated, key, "CBC", iv) == _hex("0123456789ABCDEF" * 2)
    assert repeated_blocks(repeated) == 0


def test_weak_key_encrypts_back_to_plaintext() -> None:
    key = _key("0101010101010101")
    once = encrypt_bytes(_hex(SLIDE_BLOCK), key, "ECB", None)
    assert encrypt_bytes(once, key, "ECB", None).hex().upper() == SLIDE_BLOCK


def test_empty_data_round_trips() -> None:
    assert encrypt_bytes(b"", _key(SLIDE_KEY), "ECB", None) == b""
    assert decrypt_bytes(b"", _key(SLIDE_KEY), "CBC", 0) == b""


# --- padding and UTF-8 -------------------------------------------------------


def test_pkcs7_pad_always_adds_padding() -> None:
    assert pkcs7_pad(b"") == b"\x08" * 8
    assert pkcs7_pad(b"12345678") == b"12345678" + b"\x08" * 8
    assert pkcs7_pad(b"Hello World") == b"Hello World" + b"\x05" * 5


@pytest.mark.parametrize(
    "data",
    [b"", b"1234567\x00", b"1234567\x09", b"123456\x01\x02", b"\x02" * 7 + b"\x03"],
)
def test_pkcs7_unpad_rejects_invalid_padding(data: bytes) -> None:
    with pytest.raises(DesError) as caught:
        pkcs7_unpad(data)
    assert caught.value.code == "E07"


def test_t17_wrong_padding_and_t18_hex_output() -> None:
    plain = decrypt_bytes(_hex(SLIDE_CIPHER), _key(SLIDE_KEY), "ECB", None)
    assert plain.hex().upper() == SLIDE_BLOCK  # T18
    with pytest.raises(DesError) as caught:
        pkcs7_unpad(plain)  # T17
    assert caught.value.code == "E07"


def test_t19_invalid_utf8() -> None:
    plain = pkcs7_unpad(decrypt_bytes(_hex("09A9EB2F8878EBF8"), _key(SLIDE_KEY), "ECB", None))
    assert plain == b"\xff\xfe"
    with pytest.raises(DesError) as caught:
        decode_utf8(plain)
    assert caught.value.code == "E08"


# --- parsing -----------------------------------------------------------------


def test_parse_key_normalizes_case_and_whitespace() -> None:
    assert parse_key("1334 5779\t9bbc\ndff1") == 0x133457799BBCDFF1


@pytest.mark.parametrize(
    ("value", "code", "count"),
    [
        ("", "E02", None),
        (" \t\n", "E02", None),
        ("133457799BBCDFFG", "E03", None),
        ("0x33457799BBCDFF1", "E03", None),
        ("133457799BBCDFF\u0661", "E03", None),
        ("13345779", "E04", 8),
        ("133457799BBCDFF1A", "E04", 17),
    ],
)
def test_parse_key_errors(value: str, code: str, count: int | None) -> None:
    with pytest.raises(DesError) as caught:
        parse_key(value)
    assert (caught.value.code, caught.value.count) == (code, count)


def test_parse_hex_accepts_whitespace_and_lowercase() -> None:
    assert parse_hex("01234567 89abcdef\r\nFEDCBA98\t76543210") == _hex(
        "0123456789ABCDEFFEDCBA9876543210"
    )


@pytest.mark.parametrize(
    ("value", "code", "count"),
    [
        ("", "E01", None),
        (" \n ", "E01", None),
        ("0123456789ABCDEZ", "E05", None),
        ("XYZ", "E05", None),
        ("0123456789ABCD\u0661F", "E05", None),
        ("85E813540F0AB40", "E06", 15),
        ("0123456789ABCDEF01", "E06", 18),
    ],
)
def test_parse_hex_errors(value: str, code: str, count: int | None) -> None:
    with pytest.raises(DesError) as caught:
        parse_hex(value)
    assert (caught.value.code, caught.value.count) == (code, count)


@pytest.mark.parametrize("value", ["", "123", "1234567890ABCDEG", "1234567890ABCDEF00"])
def test_parse_iv_errors(value: str) -> None:
    with pytest.raises(DesError) as caught:
        parse_iv(value)
    assert caught.value.code == "E09"


def test_parse_iv_normalizes() -> None:
    assert parse_iv("1234 5678 90ab cdef") == 0x1234567890ABCDEF


# --- weak keys and repeated blocks --------------------------------------------


@pytest.mark.parametrize(
    "key",
    [
        "0101010101010101",
        "FEFEFEFEFEFEFEFE",
        "E0E0E0E0F1F1F1F1",
        "1F1F1F1F0E0E0E0E",
        "0000000000000000",
        "FFFFFFFFFFFFFFFF",
    ],
)
def test_weak_keys_ignore_parity(key: str) -> None:
    assert key_strength(_key(key)) == "weak"


@pytest.mark.parametrize(
    "key",
    [
        "011F011F010E010E",
        "1F011F010E010E01",
        "01E001E001F101F1",
        "E001E001F101F101",
        "01FE01FE01FE01FE",
        "FE01FE01FE01FE01",
        "1FE01FE00EF10EF1",
        "E01FE01FF10EF10E",
        "1FFE1FFE0EFE0EFE",
        "FE1FFE1FFE0EFE0E",
        "E0FEE0FEF1FEF1FE",
        "FEE0FEE0FEF1FEF1",
        "001E001E000E000E",
    ],
)
def test_semi_weak_keys_ignore_parity(key: str) -> None:
    assert key_strength(_key(key)) == "semi_weak"


def test_ordinary_key_has_no_strength_flag() -> None:
    assert key_strength(_key(SLIDE_KEY)) is None


def test_repeated_blocks_counts_duplicates_of_earlier_blocks() -> None:
    a, b = b"A" * 8, b"B" * 8
    assert repeated_blocks(a + b) == 0
    assert repeated_blocks(a + a) == 1
    assert repeated_blocks(a + b + a + a) == 2


# --- oracle --------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["ECB", "CBC"])
def test_random_round_trips_match_reference_library(mode: str) -> None:
    generator = random.Random(4630 if mode == "ECB" else 4631)
    alphabet = "abcXYZ 019 àảãạăắđêếơưữ€😀\n"
    for _ in range(1000):
        key_bytes = generator.randbytes(8)
        key = int.from_bytes(key_bytes, "big")
        iv_bytes = generator.randbytes(8) if mode == "CBC" else None
        iv = int.from_bytes(iv_bytes, "big") if iv_bytes is not None else None
        text = "".join(generator.choice(alphabet) for _ in range(generator.randrange(0, 40)))
        data = pkcs7_pad(text.encode("utf-8"))

        cipher = encrypt_bytes(data, key, mode, iv)
        assert cipher == _reference(data, key_bytes, mode, iv_bytes, "encrypt")
        assert decode_utf8(pkcs7_unpad(decrypt_bytes(cipher, key, mode, iv))) == text
