"""Six stateless educational Diffie-Hellman endpoints."""

from __future__ import annotations

from threading import BoundedSemaphore
from typing import Any

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from app.api.dh_schemas import (
    DhCaesarResponse,
    DhErrorResponse,
    ExchangeRequest,
    ExchangeResponse,
    KeyPairRequest,
    KeyPairResponse,
    ParamsRequest,
    ParamsResponse,
    RandomParamsRequest,
    RandomParamsResponse,
    SharedSecretRequest,
    SharedSecretResponse,
    action,
    bits,
    caesar_request_schema,
    decimal,
    decode_json,
    error,
    fields,
    json_request_schema,
)
from app.api.history_recorder import note_history
from app.api.request_size_guard import MultipartCompletionGuard
from app.core import dh
from app.core.caesar import transform_text
from app.errors import messages
from app.errors.exceptions import FileReadError, FileTooLargeError, UnsupportedEncodingError
from app.services.file_processing import (
    decode_file_bytes,
    has_allowed_extension,
    read_limited_bytes,
)

router = APIRouter(prefix="/api/dh", tags=["Diffie-Hellman (giáo dục)"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    status: {"model": DhErrorResponse} for status in (413, 415, 422, 500)
}
DH_CAPACITY_LIMIT = 4
_DH_LIMITER = BoundedSemaphore(DH_CAPACITY_LIMIT)


def _core_message(exc: dh.DhCoreError) -> str:
    details = exc.details
    if exc.code == "Q_OUT_OF_RANGE":
        return (
            messages.DH_Q_OUT_OF_RANGE_MANUAL
            if details.get("manual")
            else messages.DH_Q_OUT_OF_RANGE_128
        )
    if exc.code == "NOT_PRIME":
        return f"q = {details.get('value', details.get('q'))} không phải số nguyên tố."
    if exc.code == "ALPHA_OUT_OF_RANGE":
        return f"α phải thỏa 1 < α < q = {details['q']}."  # noqa: RUF001
    if exc.code == "NOT_PRIMITIVE_ROOT":
        return (
            f"α = {details['alpha']} không phải nguyên căn của {details['q']}. "  # noqa: RUF001
            f"Gợi ý α = {details['suggestion']}."  # noqa: RUF001
        )
    if exc.code == "PRIVATE_KEY_OUT_OF_RANGE":
        return f"Khóa riêng phải thỏa 2 ≤ X ≤ q − 2 = {details['q'] - 2}."  # noqa: RUF001
    return {
        "NOT_INTEGER": messages.DH_NOT_INTEGER,
        "NUMBER_TOO_LARGE": messages.DH_Q_OUT_OF_RANGE_128,
        "PRIVATE_KEY_WEAK": messages.DH_PRIVATE_KEY_WEAK,
        "PUBLIC_KEY_INVALID": messages.DH_PUBLIC_KEY_INVALID,
        "BITS_INVALID": messages.DH_BITS_INVALID,
    }.get(exc.code, messages.DH_INVALID_REQUEST)


def _core_call(function: Any, *args: Any, **kwargs: Any) -> Any:
    with _DH_LIMITER:
        try:
            return function(*args, **kwargs)
        except dh.DhCoreError as exc:
            raise error(422, exc.code, _core_message(exc), exc.field) from None


async def _run_dh(function: Any, *args: Any, **kwargs: Any) -> Any:
    """Run bounded DH CPU work outside the event loop."""

    return await run_in_threadpool(_core_call, function, *args, **kwargs)


async def _json(request: Request) -> dict[str, Any]:
    return decode_json(await request.body(), request.headers.get("content-type"))


@router.post(
    "/params",
    response_model=ParamsResponse,
    responses=_ERRORS,
    openapi_extra=json_request_schema(ParamsRequest),
    description=(
        "Kiểm tra q thủ công đến 10^12. Nếu bỏ alpha, chỉ trả suggestedAlpha; "
        "server không tự chọn alpha."
    ),
)
async def params(request: Request) -> dict[str, Any]:
    payload = await _json(request)
    fields(payload, allowed=("q", "alpha"), required=("q",))
    q = decimal(payload["q"], "q", manual_q=True)
    await _run_dh(dh.validate_q, q, manual=True)
    alpha = decimal(payload["alpha"], "alpha") if "alpha" in payload else None
    result = await _run_dh(dh.validate_parameters, q, alpha, manual=True)
    return {"success": True, **result.as_dict()}


@router.post(
    "/params/random",
    response_model=RandomParamsResponse,
    responses=_ERRORS,
    openapi_extra=json_request_schema(RandomParamsRequest),
    description="Sinh safe-prime group giáo dục 16/32/64/128 bit bằng CSPRNG.",
)
async def random_params(request: Request) -> dict[str, Any]:
    payload = await _json(request)
    fields(payload, allowed=("bits",), required=("bits",))
    result = await _run_dh(dh.generate_safe_prime, bits(payload["bits"]))
    return {"success": True, **result.as_dict()}


@router.post(
    "/keypair",
    response_model=KeyPairResponse,
    responses=_ERRORS,
    openapi_extra=json_request_schema(KeyPairRequest),
    description=(
        "Tạo cặp khóa DH giáo dục. q đến 128 bit được kiểm bằng probable-prime policy; "
        "khóa riêng bị thiếu được sinh ngẫu nhiên."
    ),
)
async def keypair(request: Request) -> dict[str, Any]:
    payload = await _json(request)
    fields(payload, allowed=("q", "alpha", "privateKey"), required=("q", "alpha"))
    q = decimal(payload["q"], "q")
    await _run_dh(dh.validate_q, q)
    alpha = decimal(payload["alpha"], "alpha")
    assert alpha is not None
    private = decimal(payload["privateKey"], "privateKey") if "privateKey" in payload else None
    result = await _run_dh(dh.generate_key_pair, q, alpha, private_key=private)
    return {"success": True, **result.as_dict()}


@router.post(
    "/shared-secret",
    response_model=SharedSecretResponse,
    responses=_ERRORS,
    openapi_extra=json_request_schema(SharedSecretRequest),
    description="Tính shared secret và trace lũy thừa modulo trái sang phải.",
)
async def shared_secret_route(request: Request) -> dict[str, Any]:
    payload = await _json(request)
    fields(
        payload,
        allowed=("q", "privateKey", "otherPublicKey"),
        required=("q", "privateKey", "otherPublicKey"),
    )
    q = decimal(payload["q"], "q")
    await _run_dh(dh.validate_q, q)
    private = decimal(payload["privateKey"], "privateKey")
    public = decimal(payload["otherPublicKey"], "otherPublicKey")
    result = await _run_dh(dh.shared_secret, q, private, public)
    return {"success": True, **result.as_dict()}


@router.post(
    "/exchange",
    response_model=ExchangeResponse,
    responses=_ERRORS,
    openapi_extra=json_request_schema(ExchangeRequest),
    description=(
        "Tính exchange DH hai phía và trả private/public/shared keys cùng trace số học. "
        "Response có warning vì private keys chỉ được công khai để minh họa/đối chiếu; "
        "hệ thống thực tế phải giữ private key tại bên sở hữu và xác thực public key."
    ),
)
async def exchange_route(request: Request) -> dict[str, Any]:
    payload = await _json(request)
    fields(
        payload,
        allowed=("q", "alpha", "privateKeyA", "privateKeyB"),
        required=("q", "alpha"),
    )
    q = decimal(payload["q"], "q")
    await _run_dh(dh.validate_q, q)
    alpha = decimal(payload["alpha"], "alpha")
    assert alpha is not None
    private_a = decimal(payload["privateKeyA"], "privateKeyA") if "privateKeyA" in payload else None
    private_b = decimal(payload["privateKeyB"], "privateKeyB") if "privateKeyB" in payload else None
    result = await _run_dh(
        dh.exchange,
        q,
        alpha,
        private_key_a=private_a,
        private_key_b=private_b,
    )
    body = result.as_dict()
    return {"success": True, **body}


def _caesar_body(result: dh.SharedSecretResult, operation: str, data: str) -> dict[str, Any]:
    shift = result.shared_key % 26
    body: dict[str, Any] = {
        "success": True,
        "sharedKey": str(result.shared_key),
        "shift": str(shift),
        "result": transform_text(data, shift, operation),
    }
    if shift == 0:
        body["warning"] = {
            "code": "SHIFT_ZERO",
            "message": (
                f"K = {result.shared_key} cho độ dịch 0, văn bản không đổi. "
                "Hãy chọn khóa riêng khác."
            ),
        }
    return body


async def _caesar_json(request: Request) -> dict[str, Any]:
    payload = await _json(request)
    fields(
        payload,
        allowed=("q", "privateKey", "otherPublicKey", "action", "data"),
        required=("q", "privateKey", "otherPublicKey", "data"),
    )
    q = decimal(payload["q"], "q")
    await _run_dh(dh.validate_q, q)
    private = decimal(payload["privateKey"], "privateKey")
    public = decimal(payload["otherPublicKey"], "otherPublicKey")
    result = await _run_dh(dh.shared_secret, q, private, public)
    operation = action(payload.get("action"))
    note_history(request, operation=operation)
    data = payload["data"]
    if type(data) is not str:
        raise error(422, "INVALID_REQUEST", messages.DH_INVALID_REQUEST, "data")
    if data == "":
        raise error(422, "EMPTY_INPUT", messages.DH_EMPTY_INPUT, "data")
    note_history(request, input_length=len(data))
    body = await run_in_threadpool(_caesar_body, result, operation, data)
    note_history(request, output_length=len(body["result"]))
    return body


async def _caesar_multipart(request: Request) -> dict[str, Any]:
    form = await request.form(max_files=1, max_fields=5, max_part_size=5_242_881)
    if request.scope.get(MultipartCompletionGuard.SCOPE_KEY) is False:
        raise error(422, "INVALID_REQUEST", messages.DH_INVALID_REQUEST)
    allowed = {"file", "q", "privateKey", "otherPublicKey", "action"}
    for name, _value in form.multi_items():
        if name not in allowed or len(form.getlist(name)) != 1:
            raise error(422, "INVALID_REQUEST", messages.DH_INVALID_REQUEST, name)
    upload = form.get("file")
    if not isinstance(upload, UploadFile):
        raise error(422, "MISSING_FILE", messages.DH_MISSING_FILE, "file")
    for name in ("q", "privateKey", "otherPublicKey"):
        if name not in form:
            raise error(422, "INVALID_REQUEST", messages.DH_INVALID_REQUEST, name)
    q = decimal(form["q"], "q")
    await _run_dh(dh.validate_q, q)
    private = decimal(form["privateKey"], "privateKey")
    public = decimal(form["otherPublicKey"], "otherPublicKey")
    result = await _run_dh(dh.shared_secret, q, private, public)
    operation = action(form.get("action"))
    note_history(request, operation=operation)
    if not has_allowed_extension(upload.filename):
        raise error(415, "FILE_INVALID", messages.DH_FILE_INVALID, "file")
    try:
        raw = await read_limited_bytes(upload)
    except FileTooLargeError:
        raise error(413, "FILE_INVALID", messages.DH_FILE_TOO_LARGE, "file") from None
    except FileReadError:
        raise error(500, "FILE_READ_FAILED", messages.DH_FILE_READ_FAILED, "file") from None
    if raw == b"":
        raise error(422, "EMPTY_INPUT", messages.DH_EMPTY_INPUT, "file")
    try:
        data, had_bom = decode_file_bytes(raw)
    except UnsupportedEncodingError:
        raise error(415, "UNSUPPORTED_ENCODING", messages.DH_UNSUPPORTED_ENCODING, "file") from None
    note_history(request, input_length=len(raw))
    body = await run_in_threadpool(_caesar_body, result, operation, data)
    output_bytes = len(body["result"].encode("utf-8")) + (3 if had_bom else 0)
    note_history(request, output_length=output_bytes)
    return body


@router.post(
    "/caesar",
    response_model=DhCaesarResponse,
    response_model_exclude_none=True,
    responses=_ERRORS,
    openapi_extra=caesar_request_schema(),
)
async def caesar_route(request: Request) -> dict[str, Any]:
    media_type = request.headers.get("content-type", "").partition(";")[0].strip().lower()
    if media_type == "application/json":
        return await _caesar_json(request)
    if media_type == "multipart/form-data":
        return await _caesar_multipart(request)
    raise error(415, "UNSUPPORTED_MEDIA_TYPE", messages.DH_UNSUPPORTED_MEDIA_TYPE)
