"""Raw educational and interoperable RSA signature endpoints."""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Literal

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import FormData, UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import config
from app.api.history_profile import OWNER_STATE_KEY
from app.api.request_size_guard import MultipartCompletionGuard
from app.api.rsa_schemas import decode_json, error
from app.api.rsa_signature_schemas import (
    HistoryStatus,
    RawSignInput,
    RawSignResponse,
    RawVerifyInput,
    RawVerifyResponse,
    SignatureAlgorithm,
    StandardSignInput,
    StandardSignResponse,
    StandardVerifyInput,
    StandardVerifyResponse,
    parse_raw_sign,
    parse_raw_verify,
    parse_standard_sign_json,
    parse_standard_verify_json,
    validate_txt_bytes,
)
from app.core import rsa, rsa_signatures
from app.db.engine import app_database
from app.errors.exceptions import RsaError
from app.history.signatures import HistoryCapacityError, SignatureRecord, save_signature_history

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rsa", tags=["RSA signatures"])

RAW_WARNING = (
    "Raw RSA integer arithmetic is educational only; it has no hash, padding, document "
    "encoding, signer identity, or production security claim."
)
_RESPONSES: dict[int | str, dict[str, Any]] = {
    413: {"description": "The UTF-8 or file content exceeds exactly 5 MiB."},
    415: {"description": "Unsupported media, file extension, or file text encoding."},
    422: {"description": "Malformed request, key, signature encoding, or numeric domain."},
    500: {"description": "Unexpected service failure."},
}


def _media_type(request: Request) -> str:
    return request.headers.get("content-type", "").partition(";")[0].strip().lower()


def _raw_domain(value: RawSignInput | RawVerifyInput) -> None:
    if value.n < 2:
        raise error(422, "N_TOO_SMALL", "n phải lớn hơn hoặc bằng 2.", "n")
    if value.e < 1:
        raise error(422, "EXPONENT_OUT_OF_RANGE", "e phải lớn hơn hoặc bằng 1.", "e")
    if value.m >= value.n:
        raise error(422, "MESSAGE_OUT_OF_RANGE", "m phải nhỏ hơn n.", "m")
    if isinstance(value, RawSignInput):
        if value.d < 1:
            raise error(422, "EXPONENT_OUT_OF_RANGE", "d phải lớn hơn hoặc bằng 1.", "d")
    elif value.signature >= value.n:
        raise error(
            422,
            "SIGNATURE_OUT_OF_RANGE",
            "signature phải nhỏ hơn n.",
            "signature",
        )


def _trace(
    operation: Literal["sign", "verify"], value: int, exponent: int, modulus: int
) -> tuple[int, dict[str, Any]]:
    result, rows = rsa.mod_pow(value, exponent, modulus, collect_steps=True)
    return result, {
        "operation": operation,
        "input": str(value),
        "exponent": str(exponent),
        "modulus": str(modulus),
        "result": str(result),
        "steps": [
            {
                "i": row["i"],
                "bit": row["bit"],
                "base": str(row["base"]),
                "before": str(row["before"]),
                "result": str(row["result"]),
            }
            for row in rows
        ],
    }


def _core_error(exc: rsa_signatures.RsaSignatureError) -> None:
    field = {
        "privateKey": "privateKeyPem",
        "publicKey": "publicKeyPem",
        "password": "passphrase",
    }.get(exc.field or "", exc.field)
    if exc.code == "CRYPTOGRAPHY_UNAVAILABLE":
        raise error(500, "INTERNAL_ERROR", "Dịch vụ chữ ký RSA tạm thời không khả dụng.")
    messages = {
        "INVALID_PRIVATE_KEY": "Private key RSA hoặc passphrase không hợp lệ.",
        "INVALID_PUBLIC_KEY": "Public key RSA không hợp lệ.",
        "INVALID_PASSPHRASE": "Passphrase không hợp lệ.",
        "INVALID_SIGNATURE_ENCODING": "Chữ ký base64 không hợp lệ.",
        "SIGNING_FAILED": "Private key RSA không dùng được với cấu hình chữ ký này.",
        "VERIFICATION_FAILED": "Public key RSA không dùng được với cấu hình chữ ký này.",
    }
    raise error(422, exc.code, messages.get(exc.code, "Dữ liệu chữ ký RSA không hợp lệ."), field)


async def _history(request: Request, record: SignatureRecord) -> HistoryStatus:
    database = app_database(request.app)
    if database is None:
        return HistoryStatus(saved=False, id=None, reason="disabled")
    owner_id = getattr(request.state, OWNER_STATE_KEY, None)
    if not isinstance(owner_id, str):
        return HistoryStatus(saved=False, id=None, reason="unavailable")
    try:
        record_id = await save_signature_history(database, owner_id, record)
    except HistoryCapacityError:
        return HistoryStatus(saved=False, id=None, reason="capacity")
    except Exception:
        logger.warning("Could not save RSA signature history")
        return HistoryStatus(saved=False, id=None, reason="unavailable")
    return HistoryStatus(saved=True, id=record_id, reason="saved")


def _form_value(form: FormData, name: str, *, required: bool = True) -> str | None:
    values = form.getlist(name)
    if not values and not required:
        return None
    if len(values) != 1 or not isinstance(values[0], str):
        raise error(422, "INVALID_REQUEST", "Dữ liệu chữ ký RSA không hợp lệ.", name)
    return values[0]


async def _multipart(request: Request, operation: Literal["sign", "verify"]):
    try:
        form = await request.form(
            max_files=1,
            max_fields=4,
            # The application reads only MAX_FILE_BYTES + 1 below and emits
            # the public 413 contract. Keep Starlette's parser ceiling aligned
            # with the outer request guard so larger file parts are not
            # misclassified as malformed multipart requests.
            max_part_size=config.MAX_REQUEST_BYTES,
        )
    except RsaError:
        raise
    except Exception as exc:
        raise StarletteHTTPException(status_code=400, detail="Malformed multipart body") from exc
    if request.scope.get(MultipartCompletionGuard.SCOPE_KEY) is not True:
        raise StarletteHTTPException(status_code=400, detail="Malformed multipart body")
    allowed = (
        {"file", "privateKeyPem", "passphrase"}
        if operation == "sign"
        else {"file", "signature", "publicKeyPem"}
    )
    if any(name not in allowed for name, _value in form.multi_items()):
        raise error(422, "INVALID_REQUEST", "Dữ liệu chữ ký RSA không hợp lệ.")
    files = form.getlist("file")
    if len(files) != 1 or not isinstance(files[0], UploadFile):
        raise error(422, "INVALID_REQUEST", "Thiếu tệp .txt.", "file")
    upload = files[0]
    try:
        content = await upload.read(config.MAX_FILE_BYTES + 1)
    except Exception as exc:
        raise error(500, "FILE_READ_FAILED", "Không thể đọc tệp .txt.", "file") from exc
    validate_txt_bytes(upload.filename, content)
    if operation == "sign":
        private_key = _form_value(form, "privateKeyPem")
        passphrase = _form_value(form, "passphrase", required=False)
        assert private_key is not None
        parsed = parse_standard_sign_json(
            {
                "source": "text",
                "text": "x",
                "privateKeyPem": private_key,
                **({"passphrase": passphrase} if passphrase is not None else {}),
            }
        )
        return StandardSignInput(
            source="file",
            content=content,
            private_key_pem=parsed.private_key_pem,
            passphrase=parsed.passphrase,
            filename=upload.filename,
        )
    signature = _form_value(form, "signature")
    public_key = _form_value(form, "publicKeyPem")
    assert signature is not None and public_key is not None
    parsed_verify = parse_standard_verify_json(
        {
            "source": "text",
            "text": "x",
            "signature": signature,
            "publicKeyPem": public_key,
        }
    )
    return StandardVerifyInput(
        source="file",
        content=content,
        signature=parsed_verify.signature,
        public_key_pem=parsed_verify.public_key_pem,
        filename=upload.filename,
    )


@router.post("/sign/raw", response_model=RawSignResponse, responses=_RESPONSES)
async def sign_raw(request: Request) -> dict[str, Any]:
    value = parse_raw_sign(decode_json(await request.body(), request.headers.get("content-type")))
    _raw_domain(value)
    signature, trace = await run_in_threadpool(_trace, "sign", value.m, value.d, value.n)
    result = {
        "mode": "raw-integer",
        "warning": RAW_WARNING,
        "m": str(value.m),
        "signature": str(signature),
        "publicKey": {"e": str(value.e), "n": str(value.n)},
        "trace": trace,
    }
    history = await _history(
        request,
        SignatureRecord(
            operation="sign",
            mode="raw-integer",
            source="number",
            content=None,
            numeric_input={"m": str(value.m)},
            signature=str(signature),
            public_key={"e": str(value.e), "n": str(value.n)},
            result={"signature": str(signature)},
            valid=None,
        ),
    )
    return {"success": True, "result": result, "history": history}


@router.post("/verify/raw", response_model=RawVerifyResponse, responses=_RESPONSES)
async def verify_raw(request: Request) -> dict[str, Any]:
    value = parse_raw_verify(decode_json(await request.body(), request.headers.get("content-type")))
    _raw_domain(value)
    recovered, trace = await run_in_threadpool(_trace, "verify", value.signature, value.e, value.n)
    valid = recovered == value.m
    result = {
        "mode": "raw-integer",
        "warning": RAW_WARNING,
        "valid": valid,
        "m": str(value.m),
        "recoveredMessage": str(recovered),
        "signature": str(value.signature),
        "publicKey": {"e": str(value.e), "n": str(value.n)},
        "trace": trace,
    }
    history = await _history(
        request,
        SignatureRecord(
            operation="verify",
            mode="raw-integer",
            source="number",
            content=None,
            numeric_input={"m": str(value.m)},
            signature=str(value.signature),
            public_key={"e": str(value.e), "n": str(value.n)},
            result={"recoveredMessage": str(recovered)},
            valid=valid,
        ),
    )
    return {"success": True, "result": result, "history": history}


async def _sign_input(request: Request) -> StandardSignInput:
    if _media_type(request) == "multipart/form-data":
        return await _multipart(request, "sign")
    if _media_type(request) != "application/json":
        raise error(415, "UNSUPPORTED_MEDIA_TYPE", "Chỉ chấp nhận JSON hoặc multipart.")
    return parse_standard_sign_json(
        decode_json(await request.body(), request.headers.get("content-type"))
    )


async def _verify_input(request: Request) -> StandardVerifyInput:
    if _media_type(request) == "multipart/form-data":
        return await _multipart(request, "verify")
    if _media_type(request) != "application/json":
        raise error(415, "UNSUPPORTED_MEDIA_TYPE", "Chỉ chấp nhận JSON hoặc multipart.")
    return parse_standard_verify_json(
        decode_json(await request.body(), request.headers.get("content-type"))
    )


@router.post("/sign", response_model=StandardSignResponse, responses=_RESPONSES)
async def sign_standard(request: Request) -> dict[str, Any]:
    value = await _sign_input(request)
    try:
        signature, public_key_pem = await run_in_threadpool(
            rsa_signatures.sign_with_public_key,
            value.content,
            value.private_key_pem,
            value.passphrase,
        )
    except rsa_signatures.RsaSignatureError as exc:
        _core_error(exc)
    signature_text = rsa_signatures.encode_signature(signature)
    public_key_text = public_key_pem.decode("ascii")
    digest = hashlib.sha256(value.content).hexdigest()
    result = {
        "mode": "standard",
        "source": value.source,
        "signature": signature_text,
        "publicKeyPem": public_key_text,
        "contentBytes": len(value.content),
        "sha256": digest,
        "algorithm": SignatureAlgorithm(),
    }
    history = await _history(
        request,
        SignatureRecord(
            operation="sign",
            mode="standard",
            source=value.source,
            content=value.content,
            numeric_input=None,
            signature=signature_text,
            public_key=public_key_text,
            result={"sha256": digest},
            valid=None,
        ),
    )
    return {"success": True, "result": result, "history": history}


@router.post("/verify", response_model=StandardVerifyResponse, responses=_RESPONSES)
async def verify_standard(request: Request) -> dict[str, Any]:
    value = await _verify_input(request)
    try:
        valid = await run_in_threadpool(
            rsa_signatures.verify_bytes_base64,
            value.content,
            value.signature,
            value.public_key_pem,
        )
    except rsa_signatures.RsaSignatureError as exc:
        _core_error(exc)
    public_key_text = value.public_key_pem.decode("ascii")
    digest = hashlib.sha256(value.content).hexdigest()
    result = {
        "mode": "standard",
        "source": value.source,
        "valid": valid,
        "contentBytes": len(value.content),
        "sha256": digest,
        "algorithm": SignatureAlgorithm(),
    }
    history = await _history(
        request,
        SignatureRecord(
            operation="verify",
            mode="standard",
            source=value.source,
            content=value.content,
            numeric_input=None,
            signature=value.signature,
            public_key=public_key_text,
            result={"sha256": digest},
            valid=valid,
        ),
    )
    return {"success": True, "result": result, "history": history}
