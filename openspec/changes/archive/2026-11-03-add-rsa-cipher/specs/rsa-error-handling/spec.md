# Spec Delta

## Purpose

Định nghĩa error contract cộng thêm riêng cho RSA: status tương thích backend, envelope bốn trường, strict parsing kể cả duplicate key, raw numeric guards, deterministic precedence và thông báo tiếng Việt.

## ADDED Requirements

### Requirement: Exact RSA error envelope và status

Mọi lỗi phát sinh trên bốn RSA endpoint SHALL trả JSON object có đúng bốn field `{success:false,code,message,field}`; `field` luôn có mặt và là `null` cho lỗi toàn request/hệ thống, tên field cho lỗi đơn, hoặc path như `cipher[3]` cho item. Validation/domain dùng HTTP 422, request/file quá lớn dùng 413, media type/extension/UTF-8 không hỗ trợ dùng 415, lỗi đọc/hệ thống dùng 500. Response MUST không có traceback, exception string, input text, key secret hoặc partial result. Error handler và schema của route cũ MUST không thay đổi. (Truy vết: PDF RSA trang 3–4 dùng HTTP 400; quyết định chủ sở hữu Q2, Q5, Q15 chấp nhận deviation)

#### Scenario: Lỗi lexical item có indexed field

- **WHEN** `cipher[3]="12x"`
- **THEN** HTTP 422 với exact body `{"success":false,"code":"NOT_INTEGER","message":"Giá trị phải là số nguyên không âm.","field":"cipher[3]"}`

#### Scenario: Lỗi hệ thống không lộ chi tiết

- **WHEN** RSA handler phát sinh exception ngoài dự kiến
- **THEN** HTTP 500 với `{"success":false,"code":"INTERNAL_ERROR","message":"Đã xảy ra lỗi hệ thống.","field":null}`
- **AND** response không chứa traceback hoặc operand

### Requirement: JSON object và field set strict

RSA JSON body SHALL là một object UTF-8 hợp lệ. Parser SHALL phát hiện duplicate member name trước khi model validation; unknown, duplicate và inapplicable field đều bị từ chối, không silently ignore. Malformed JSON, non-object body hoặc missing discriminator dùng `INVALID_REQUEST`; field là `null` khi không quy được cho một member, còn missing/unknown/duplicate/inapplicable member dùng đúng tên field. Ngoại lệ duy nhất cho missing required member là block decrypt thiếu `originalUtf8ByteLength`: trường hợp đó SHALL dùng `INVALID_LENGTH_METADATA` với field cùng tên theo `rsa-transform-api`. Nếu có nhiều duplicate/unknown field cùng cấp, field đầu tiên theo thứ tự raw JSON SHALL thắng. (Truy vết: quyết định chủ sở hữu Q15; strict request precedent trong repository; làm rõ corrective R1 được chủ sở hữu duyệt ngày 2026-10-06)

#### Scenario: Duplicate cryptographic field

- **WHEN** raw body chứa hai member `"n"`
- **THEN** HTTP 422 `INVALID_REQUEST` với `field="n"`

#### Scenario: Unknown field

- **WHEN** request có thêm `encoding="hex"`
- **THEN** HTTP 422 `INVALID_REQUEST` với `field="encoding"`

#### Scenario: Malformed JSON

- **WHEN** body không parse được thành JSON object
- **THEN** HTTP 422 với `{"success":false,"code":"INVALID_REQUEST","message":"Dữ liệu gửi lên không hợp lệ.","field":null}`

### Requirement: Decimal string lexical contract và raw guard

Mọi cryptographic input `p`, `q`, `e`, `d`, `n`, number `data` và mỗi cipher item SHALL là JSON string khớp chính xác ASCII regex `[0-9]+`. Dấu cộng/trừ, whitespace, dấu chấm, exponent, underscore, ký số Unicode, chuỗi rỗng và JSON number/bool/null đều SHALL trả `NOT_INTEGER`. Leading zero được chấp nhận cho input nhưng không ở output. Trước khi bỏ leading zero hoặc chuyển số, server SHALL từ chối token dài hơn 128 ASCII digit bằng `NUMBER_TOO_LARGE`; sau parse, giá trị lớn hơn `2^128-1` cũng SHALL dùng code đó. Guard raw này MUST ngăn chuỗi zero dài né practical limit. (Truy vết: PDF RSA trang 3 mọi số là string và `NOT_INTEGER`; quyết định chủ sở hữu Q10, Q14, Q15)

#### Scenario: Unicode digit bị từ chối

- **WHEN** `n="１２３"`
- **THEN** HTTP 422 `NOT_INTEGER` với `field="n"`

#### Scenario: JSON number bị từ chối

- **WHEN** `e` là JSON number `7`
- **THEN** HTTP 422 `NOT_INTEGER` với `field="e"`

#### Scenario: Chuỗi 129 zero bị raw guard chặn

- **WHEN** cryptographic field chứa 129 ký tự `0`
- **THEN** HTTP 422 `NUMBER_TOO_LARGE` cho field đó trước normalization

#### Scenario: Giá trị đúng trần 128 bit

- **WHEN** operand là `"340282366920938463463374607431768211455"`
- **THEN** không bị từ chối bởi operand ceiling

### Requirement: Bảng code status message và field

RSA SHALL dùng các mapping dưới đây; message có placeholder SHALL nội suy decimal canonical. Validation không được thay bằng error mặc định của framework.

| Code | HTTP | Message | Field |
|---|---:|---|---|
| `REQUEST_TOO_LARGE` | 413 | `Yêu cầu vượt quá dung lượng cho phép.` | `null` |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | `Kiểu nội dung không được hỗ trợ.` | `null` |
| `INVALID_REQUEST` | 422 | `Dữ liệu gửi lên không hợp lệ.` | `null` hoặc field liên quan |
| `NOT_INTEGER` | 422 | `Giá trị phải là số nguyên không âm.` | numeric field/path |
| `NUMBER_TOO_LARGE` | 422 | `Giá trị không được vượt quá 2^128 - 1.` | numeric field/path |
| `INVALID_BITS` | 422 | `Số bit phải là một trong 16, 32, 64 hoặc 128.` | `bits` |
| `NOT_PRIME` | 422 | `{field} = {value} không phải số nguyên tố.` | `p` hoặc `q` |
| `SAME_PRIME` | 422 | `p và q phải khác nhau.` | `q` |
| `E_OUT_OF_RANGE` | 422 | keygen: `e phải thỏa 1 < e < phi(n) = {phi}.`; transform: `e phải thỏa 1 < e < n.` | `e` |
| `D_OUT_OF_RANGE` | 422 | `d phải thỏa 1 < d < n.` | `d` |
| `E_NOT_COPRIME` | 422 | `gcd({e}, {phi}) = {g}, không tồn tại d. Gợi ý e = {suggestion}.` | `e` |
| `PRIME_TOO_LARGE` | 422 | `Hãy dùng p, q ≤ 10^12 hoặc sinh khóa ngẫu nhiên.` | `p` hoặc `q` |
| `P_TOO_LARGE` | 422 | `P = {P} ≥ n = {n}. Hãy chia khối hoặc dùng n lớn hơn.` | `data` |
| `N_TOO_SMALL` | 422 | block: `n phải lớn hơn 256 để chứa ít nhất 1 byte mỗi khối.`; general: `n phải lớn hơn 1.` | `n` |
| `CIPHER_TOO_LARGE` | 422 | `Bản mã không hợp lệ với khóa này.` | `cipher[{i}]` |
| `DECODE_FAILED` | 422 | `Không khôi phục được văn bản hợp lệ từ dữ liệu đã giải mã.` | `data`, `cipher` hoặc indexed path gần nhất |
| `EMPTY_INPUT` | 422 | `Dữ liệu đầu vào đang rỗng.` | `data`, `cipher` hoặc `file` |
| `INPUT_TOO_LARGE` | 422 | text: `Dữ liệu văn bản không được vượt quá 10.000 ký tự Unicode.`; collection: `Danh sách bản mã vượt quá giới hạn cho phép.` | `data`, `file` hoặc `cipher` |
| `FILE_INVALID` | 413/415 | size: `File vượt quá dung lượng tối đa 1 MB.`; extension: `Chỉ nhận file .txt.`; encoding: `File phải sử dụng UTF-8.` | `file` |
| `INVALID_LENGTH_METADATA` | 422 | `Độ dài UTF-8 gốc không khớp với danh sách bản mã.` | `originalUtf8ByteLength` |
| `TRACE_INDEX_OUT_OF_RANGE` | 422 | `Chỉ số khối cần xem không hợp lệ.` | `traceBlockIndex` |
| `FILE_READ_FAILED` | 500 | `Không thể đọc file.` | `file` |
| `INTERNAL_ERROR` | 500 | `Đã xảy ra lỗi hệ thống.` | `null` |

(Truy vết: PDF RSA trang 3–4; quyết định chủ sở hữu Q5, Q8, Q13–Q15; làm rõ corrective R2 được chủ sở hữu duyệt ngày 2026-10-06; wording hiện hành trong `app/errors/messages.py`; deviation `DECODE_FAILED` tránh khẳng định phát hiện sai khóa)

#### Scenario: TC-13 n quá nhỏ

- **WHEN** block transform dùng `n="187"`
- **THEN** HTTP 422 với `code="N_TOO_SMALL"`, message `n phải lớn hơn 256 để chứa ít nhất 1 byte mỗi khối.` và `field="n"`

#### Scenario: Cipher bằng n

- **WHEN** `cipher[0]` bằng `n`
- **THEN** HTTP 422 `CIPHER_TOO_LARGE` với `field="cipher[0]"`

#### Scenario: Wrong key tạo UTF-8 hợp lệ

- **WHEN** private key sai vẫn tạo block width, padding và UTF-8 hợp lệ
- **THEN** endpoint trả HTTP 200 với plaintext quan sát được
- **AND** không trả hoặc tuyên bố một lỗi wrong-key

#### Scenario: Plaintext JSON chứa lone surrogate

- **WHEN** text encrypt nhận `data` là JSON string chứa lone surrogate nên không encode được thành UTF-8 strict
- **THEN** HTTP 422 với exact body `{"success":false,"code":"DECODE_FAILED","message":"Không khôi phục được văn bản hợp lệ từ dữ liệu đã giải mã.","field":"data"}`

### Requirement: Control integer strict

`bits`, `traceBlockIndex` và `originalUtf8ByteLength` trong JSON SHALL là integer thực, không nhận bool, float hoặc string. JSON decoder SHALL giữ raw integer token và áp trần 10 ASCII digit trước khi chuyển sang Python integer để một token cực dài không né resource guard; quá trần dùng code riêng của control tương ứng. `bits` ngoài enum/type dùng `INVALID_BITS`; trace index âm/sai type/vượt index dùng `TRACE_INDEX_OUT_OF_RANGE`; length sai type, ngoài `1..40000`, không canonical với block count hoặc padding dùng `INVALID_LENGTH_METADATA`. Multipart trace index là ngoại lệ transport: part value SHALL là ASCII canonical `0|[1-9][0-9]*`, tối đa 10 digit trước parse. (Truy vết: quyết định chủ sở hữu Q11, Q13, Q14, Q15; quyết định kỹ thuật exact transport)

#### Scenario: Bool không phải integer

- **WHEN** `traceBlockIndex=true`
- **THEN** HTTP 422 `TRACE_INDEX_OUT_OF_RANGE` với `field="traceBlockIndex"`

#### Scenario: Length gửi dạng string

- **WHEN** block decrypt gửi `originalUtf8ByteLength="3"`
- **THEN** HTTP 422 `INVALID_LENGTH_METADATA` với `field="originalUtf8ByteLength"`

#### Scenario: Control integer token quá dài

- **WHEN** `traceBlockIndex` là một JSON integer token có 11 digit
- **THEN** HTTP 422 `TRACE_INDEX_OUT_OF_RANGE` với `field="traceBlockIndex"` trước khi chuyển token thành integer

### Requirement: Thứ tự lỗi JSON xác định

Sau guard 64 MiB, JSON RSA SHALL dừng ở lỗi đầu theo thứ tự: media type và parse object/duplicate; discriminator (`inputType`, rồi `mode` khi áp dụng) và exact required/unknown/inapplicable field set; collection/string business cap; type/enum/raw guard của `bits` hoặc `originalUtf8ByteLength` khi áp dụng; cryptographic field lexical/raw/value theo thứ tự schema (`p,q,e`; `e,n,data`; `d,n,cipher` từ index thấp lên); semantic key/domain range; plaintext/cipher item `<n`; block length-count/padding/UTF-8; type/raw/range của `traceBlockIndex`; transform. Với cùng tầng, schema order nêu trên thắng raw member order, ngoại trừ duplicate/unknown field dùng raw appearance. Hệ thống SHALL trả đúng một error và không partial result. (Truy vết: quyết định chủ sở hữu Q5, Q14, Q15; backend deterministic-error convention)

#### Scenario: Nhiều numeric field cùng sai

- **WHEN** encrypt JSON có `e="x"` và `n="y"`
- **THEN** HTTP 422 `NOT_INTEGER` với `field="e"`

#### Scenario: Collection quá lớn chứa item sai

- **WHEN** char cipher có 10.001 item và item đầu sai lexical
- **THEN** HTTP 422 `INPUT_TOO_LARGE` với `field="cipher"` trước item parsing
