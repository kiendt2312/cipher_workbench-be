"""Strict transport validation and response models for RSA signatures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import Field

from app import config
from app.api.rsa_schemas import ExactModel, RsaErrorResponse, error, parse_decimal

MAX_PEM_BYTES = 64 * 1024
MAX_PASSPHRASE_BYTES = 4 * 1024
MAX_SIGNATURE_TEXT_BYTES = 64 * 1024


class HistoryStatus(ExactModel):
    saved: bool
    id: int | None
    reason: Literal["saved", "disabled", "unavailable", "capacity"]


class SignatureAlgorithm(ExactModel):
    scheme: Literal["RSASSA-PSS"] = "RSASSA-PSS"
    hash: Literal["SHA-256"] = "SHA-256"
    mgf: Literal["MGF1-SHA-256"] = "MGF1-SHA-256"
    salt_length: int = Field(default=32, alias="saltLength")
    signature_encoding: Literal["base64"] = Field(default="base64", alias="signatureEncoding")


class RawTraceStep(ExactModel):
    i: int
    bit: Literal[0, 1]
    base: str
    before: str
    result: str


class RawTrace(ExactModel):
    operation: Literal["sign", "verify"]
    input: str
    exponent: str
    modulus: str
    result: str
    steps: list[RawTraceStep]


class RawSignResult(ExactModel):
    mode: Literal["raw-integer"] = Field(alias="mode")
    warning: str
    m: str
    signature: str
    public_key: dict[str, str] = Field(alias="publicKey")
    trace: RawTrace


class RawVerifyResult(ExactModel):
    mode: Literal["raw-integer"] = Field(alias="mode")
    warning: str
    valid: bool
    m: str
    recovered_message: str = Field(alias="recoveredMessage")
    signature: str
    public_key: dict[str, str] = Field(alias="publicKey")
    trace: RawTrace


class RawSignResponse(ExactModel):
    success: Literal[True]
    result: RawSignResult
    history: HistoryStatus


class RawVerifyResponse(ExactModel):
    success: Literal[True]
    result: RawVerifyResult
    history: HistoryStatus


class StandardSignResult(ExactModel):
    mode: Literal["standard"]
    source: Literal["text", "file"]
    signature: str
    public_key_pem: str = Field(alias="publicKeyPem")
    content_bytes: int = Field(alias="contentBytes")
    sha256: str
    algorithm: SignatureAlgorithm


class StandardVerifyResult(ExactModel):
    mode: Literal["standard"]
    source: Literal["text", "file"]
    valid: bool
    content_bytes: int = Field(alias="contentBytes")
    sha256: str
    algorithm: SignatureAlgorithm


class StandardSignResponse(ExactModel):
    success: Literal[True]
    result: StandardSignResult
    history: HistoryStatus


class StandardVerifyResponse(ExactModel):
    success: Literal[True]
    result: StandardVerifyResult
    history: HistoryStatus


class SignatureErrorResponse(RsaErrorResponse):
    pass


@dataclass(frozen=True)
class RawSignInput:
    m: int
    d: int
    e: int
    n: int


@dataclass(frozen=True)
class RawVerifyInput:
    m: int
    signature: int
    e: int
    n: int


@dataclass(frozen=True)
class StandardSignInput:
    source: Literal["text", "file"]
    content: bytes
    private_key_pem: bytes
    passphrase: bytes | None
    filename: str | None = None


@dataclass(frozen=True)
class StandardVerifyInput:
    source: Literal["text", "file"]
    content: bytes
    signature: str
    public_key_pem: bytes
    filename: str | None = None


def _fields(
    payload: dict[str, Any], *, allowed: tuple[str, ...], required: tuple[str, ...]
) -> None:
    for name in payload:
        if name not in allowed:
            raise error(422, "INVALID_REQUEST", "Dữ liệu chữ ký RSA không hợp lệ.", name)
    for name in required:
        if name not in payload:
            raise error(422, "INVALID_REQUEST", "Dữ liệu chữ ký RSA không hợp lệ.", name)


def _bounded_utf8(raw: Any, field: str, maximum: int, *, empty: bool = False) -> bytes:
    if type(raw) is not str:
        raise error(422, "INVALID_REQUEST", "Dữ liệu chữ ký RSA không hợp lệ.", field)
    try:
        encoded = raw.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise error(422, "INVALID_TEXT_ENCODING", "Văn bản phải là UTF-8 hợp lệ.", field) from exc
    if not empty and not encoded:
        raise error(422, "EMPTY_CONTENT", "Nội dung ký không được rỗng.", field)
    if len(encoded) > maximum:
        raise error(413, "CONTENT_TOO_LARGE", "Nội dung vượt quá 5 MiB.", field)
    return encoded


def parse_raw_sign(payload: dict[str, Any]) -> RawSignInput:
    _fields(payload, allowed=("m", "d", "e", "n"), required=("m", "d", "e", "n"))
    values = {name: parse_decimal(payload[name], name) for name in ("m", "d", "e", "n")}
    return RawSignInput(**values)


def parse_raw_verify(payload: dict[str, Any]) -> RawVerifyInput:
    _fields(
        payload,
        allowed=("m", "signature", "e", "n"),
        required=("m", "signature", "e", "n"),
    )
    return RawVerifyInput(
        m=parse_decimal(payload["m"], "m"),
        signature=parse_decimal(payload["signature"], "signature"),
        e=parse_decimal(payload["e"], "e"),
        n=parse_decimal(payload["n"], "n"),
    )


def parse_standard_sign_json(payload: dict[str, Any]) -> StandardSignInput:
    _fields(
        payload,
        allowed=("source", "text", "privateKeyPem", "passphrase"),
        required=("source", "text", "privateKeyPem"),
    )
    if payload["source"] != "text":
        raise error(422, "INVALID_REQUEST", "JSON chỉ hỗ trợ source=text.", "source")
    content = _bounded_utf8(payload["text"], "text", config.MAX_FILE_BYTES)
    pem = _bounded_utf8(payload["privateKeyPem"], "privateKeyPem", MAX_PEM_BYTES)
    passphrase_raw = payload.get("passphrase")
    passphrase = (
        None
        if passphrase_raw is None
        else _bounded_utf8(passphrase_raw, "passphrase", MAX_PASSPHRASE_BYTES, empty=True)
    )
    return StandardSignInput("text", content, pem, passphrase)


def parse_standard_verify_json(payload: dict[str, Any]) -> StandardVerifyInput:
    _fields(
        payload,
        allowed=("source", "text", "signature", "publicKeyPem"),
        required=("source", "text", "signature", "publicKeyPem"),
    )
    if payload["source"] != "text":
        raise error(422, "INVALID_REQUEST", "JSON chỉ hỗ trợ source=text.", "source")
    content = _bounded_utf8(payload["text"], "text", config.MAX_FILE_BYTES)
    signature = payload["signature"]
    try:
        signature_size = len(signature.encode("utf-8")) if type(signature) is str else 0
    except UnicodeEncodeError as exc:
        raise error(
            422,
            "INVALID_SIGNATURE_ENCODING",
            "Chữ ký base64 không hợp lệ.",
            "signature",
        ) from exc
    if type(signature) is not str or not signature or signature_size > MAX_SIGNATURE_TEXT_BYTES:
        raise error(422, "INVALID_SIGNATURE_ENCODING", "Chữ ký base64 không hợp lệ.", "signature")
    pem = _bounded_utf8(payload["publicKeyPem"], "publicKeyPem", MAX_PEM_BYTES)
    return StandardVerifyInput("text", content, signature, pem)


def validate_txt_bytes(filename: str | None, content: bytes) -> None:
    if not filename or not filename.lower().endswith(".txt"):
        raise error(415, "UNSUPPORTED_FILE_TYPE", "Chỉ chấp nhận tệp .txt.", "file")
    if not content:
        raise error(422, "EMPTY_CONTENT", "Nội dung ký không được rỗng.", "file")
    if len(content) > config.MAX_FILE_BYTES:
        raise error(413, "CONTENT_TOO_LARGE", "Nội dung vượt quá 5 MiB.", "file")
    try:
        content.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise error(
            415, "INVALID_TEXT_ENCODING", "Tệp .txt phải dùng UTF-8 hợp lệ.", "file"
        ) from exc
