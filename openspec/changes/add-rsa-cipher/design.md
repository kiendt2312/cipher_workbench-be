# Design

## Context

Xem `proposal.md` cho động cơ và phạm vi. Backend hiện là Python `>=3.12,<3.13`, FastAPI/Pydantic v2, chia `app/core` cho thuật toán thuần và `app/api` cho schema/router. Router DES là tiền lệ gần nhất cho model strict, OpenAPI explicit và `run_in_threadpool`; request-size/multipart guards chạy trước router; history chỉ ghi các route có trong whitelist hiện hữu.

RSA cắt ngang core, hai media type trên cùng route encrypt, middleware guard và error handling, nhưng không thay đổi database. Hai tài liệu RSA ở source checkout là reference; Q1–Q15 trong proposal là authority cho ambiguity/deviation.

## Goals / Non-Goals

**Goals:**

- Tạo một seam rõ giữa số học/encoding thuần và transport FastAPI để test vector, lỗi, OpenAPI và lossless round-trip độc lập.
- Bảo đảm mọi input không tin cậy bị giới hạn trước bước tốn CPU/bộ nhớ, mọi response RSA theo exact schema và route cũ không đổi.
- Giữ đúng bốn endpoint bằng cách đặt selected-block trace trong request transform và dùng cùng route encrypt cho JSON/multipart.

**Non-Goals:**

- Không tạo framework cipher chung, repository abstraction, persistence, migration hoặc dependency runtime mới.
- Không tối ưu textbook RSA thành thư viện mật mã production, không thêm padding/signature/key serialization.
- Không đổi middleware/error/schema/history của route cũ ngoài nhánh nhận diện exact RSA path ở tầng guard.

## Decisions

### 1. Module boundaries theo kiến trúc hiện hữu

Implementation tương lai SHALL thêm:

- `app/core/rsa.py`: kiểu dữ liệu/exception nội bộ, gcd/egcd/mod inverse/modPow, primality, keygen, char/block packing và unpacking; không import FastAPI/Pydantic/database.
- `app/api/rsa_schemas.py`: strict JSON decoder, duplicate detection, discriminated request validation, decimal parser/raw guards, exact response models, RSA API exception và mapping core error.
- `app/api/routes_rsa.py`: bốn routes, content-type dispatch của `/encrypt`, bounded file read, threadpool boundary và OpenAPI request/response declarations.
- `app/errors/messages.py`: chỉ thêm constant message RSA; không sửa giá trị cũ.
- `app/api/request_size_guard.py`: nhận diện `/api/rsa/` để trả envelope RSA ở 64 MiB guard và coi multipart `/api/rsa/encrypt` là đối tượng của completion guard.
- `app/main.py`: include một RSA router.

Tests đặt ở `tests/unit/test_rsa.py`, `tests/unit/test_rsa_validation.py`, `tests/integration/test_rsa_endpoints.py`, `tests/integration/test_rsa_file_encrypt.py` và mở rộng test guard/history layering hiện hữu.

Lý do: giữ core sâu và thuần, còn toàn bộ lựa chọn public contract nằm ở API edge. Alternative gộp validation vào route bị loại vì duplicate JSON, union strict và error precedence cần một decoder có thể test riêng. Alternative thêm service/repository bị loại vì RSA stateless.

### 2. Exact request decoding trước Pydantic

Router không gọi `await request.json()` rồi giao thẳng dict cho model, vì cách đó đã làm mất bằng chứng duplicate key và raw numeric token. `rsa_schemas.py` SHALL đọc bounded body một lần, decode UTF-8 strict, dùng JSON decoder có `object_pairs_hook` để phát hiện member trùng ở mọi object, đồng thời dùng `parse_int`/`parse_float` hook để giữ raw numeric lexeme chưa chuyển thành Python number. Sau đó decoder xác nhận root object, dispatch theo endpoint/`inputType`/`mode`, áp raw token cap rồi mới chuyển control integer. Lỗi được chuyển trực tiếp thành RSA API exception thay vì để framework sinh envelope 422 chung.

Thứ tự field trong schema là dữ liệu tĩnh, không phụ thuộc thứ tự object do client gửi. Duplicate/unknown field giữ raw appearance để chọn field lỗi deterministic như spec. Pydantic response models dùng `extra="forbid"`, alias đúng camelCase và exact union; request models có thể dùng sau strict decoder nhưng không được thay thế decoder.

Alternative dựa hoàn toàn vào Pydantic bị loại vì không bảo đảm phát hiện duplicate member sau JSON parse và error shape/path mặc định không khớp Q15.

### 3. Decimal parser dùng hai tầng guard

Một helper duy nhất nhận `(raw, field)` và thực hiện:

1. type phải là string;
2. full-match ASCII `[0-9]+`;
3. chiều dài raw tối đa 128 digit trước mọi normalization;
4. chuyển thành Python integer;
5. giá trị tối đa `2^128-1`;
6. output dùng `str(value)` để canonical hóa.

Manual `p/q` tiếp tục có domain cap `10^12` sau parser. Transform yêu cầu `n>1`; encrypt yêu cầu `1<e<n`; decrypt yêu cầu `1<d<n`; number/plaintext và cipher item cho phép zero nhưng phải `<n`. Block mode kiểm `n>256` trước tính `k`.

Small controls trong JSON chỉ nhận raw lexeme thuộc grammar JSON integer (không dấu chấm/exponent), dài tối đa 10 digit không tính dấu trừ; sau raw guard mới chuyển thành integer và kiểm không âm/range. Bool/string/float vẫn bị loại theo code của control. Multipart `traceBlockIndex` dùng regex `0|[1-9][0-9]*`, raw cap 10 digit, sau đó cùng validator range/index.

Alternative chỉ kiểm giá trị sau `int()` bị loại vì chuỗi zero cực dài né operand cap và gây chi phí không cần thiết. Alternative cấm leading zero bị loại vì Q14 chỉ yêu cầu output canonical; input lexical `[0-9]+` đã được chốt.

### 4. Số học và primality thuần, có thể tái lập trong test

`egcd(phi,e)` trả cả hai dòng khởi tạo `(q=null,r=phi,t=0)`, `(q=null,r=e,t=1)` và mọi dòng quotient/remainder/coefficient tiếp theo đến remainder 0. `mod_pow` dùng right-to-left square-and-multiply và chỉ materialize rows khi selected trace được yêu cầu; transform các block còn lại tính result không cấp phát rows.

Manual primality dùng trial division có loại 2 và chỉ thử ước lẻ tới căn bậc hai cho `p,q<=10^12`, đúng reference. Random candidates lớn hơn `10^12` nhưng dưới `2^64` dùng Miller–Rabin deterministic cho miền 64 bit với witness set cố định; bước chia các prime nhỏ chạy trước. Random generation dùng CSPRNG của standard library, đặt highest/lowest bit để candidate có đúng độ dài/lẻ, sinh `p!=q`, rồi retry tới khi `n.bit_length()==bits`. Chọn kích thước prime quanh một nửa target bits; output chỉ được trả khi mọi invariant được kiểm lại.

`e=65537` được chọn khi nằm trong range và coprime; fallback quét số lẻ từ 3. Dependency injection cho nguồn random chỉ tồn tại ở hàm nội bộ/test, không thành public API.

Alternative dùng package `cryptography` bị loại: textbook raw RSA/trace và prime/key educational sizes cần dữ liệu trung gian mà API high-level không cung cấp, đồng thời runtime hiện không cần dependency mới. Alternative Miller–Rabin ngẫu nhiên bị loại để test deterministic và tránh xác suất false-positive trong miền candidate tối đa 64 bit.

### 5. Encoding lossless và canonical block package

Char mode duyệt Python string theo Unicode code point; trước transform, thử encode UTF-8 strict để loại lone surrogate. Mỗi `ord(character)` là một block. BOM là `ord(U+FEFF)=65279`, không có nhánh metadata riêng.

Block mode:

1. encode plaintext bằng UTF-8 strict, không normalize;
2. tính `k` bằng vòng lặp integer sao cho `256^k <= n-1 < 256^(k+1)`;
3. chia byte theo `k`, pad block cuối bên phải bằng `0x00`, parse big-endian;
4. lưu số byte trước padding trong `originalUtf8ByteLength`;
5. decrypt từng item, yêu cầu plaintext integer `<256^k`, serialize chính xác `k` byte;
6. yêu cầu `ceil(length/k)==cipher_count`; tách đúng `cipher_count*k-length` byte cuối và xác nhận tất cả bằng zero;
7. decode phần có nghĩa bằng UTF-8 strict và kiểm tối đa 10.000 code point.

Không dùng `rstrip(b"\0")`, `utf-8-sig`, universal newline hoặc normalization. Vì metadata không authenticated, server chỉ kiểm consistency có thể quan sát; metadata/key sai nhưng tạo package hợp lệ vẫn có thể trả plaintext khác.

Alternative đặt BOM vào metadata bị loại vì Q12 xác nhận BOM là nội dung. Alternative lưu padding count server-side bị loại vì Q13 yêu cầu stateless package.

### 6. Một route encrypt với hai body contracts

`routes_rsa.py` kiểm base media type, không so literal header có parameters:

- `application/json`: strict decoder ở Decision 2;
- `multipart/form-data`: parser hiện hành, `getlist` cho duplicate, exact field set và multipart completion flag; chỉ text encrypt;
- loại khác: `UNSUPPORTED_MEDIA_TYPE`.

Multipart đọc file theo helper bounded riêng ở ngưỡng `1_000_000 + 1` byte, tính raw BOM vào cap, decode bằng `bytes.decode("utf-8", errors="strict")`; không dùng helper hiện hành nếu helper đó strip BOM hoặc gắn cap 5 MiB. Filename extension so sánh case-insensitive; MIME chỉ phục vụ transport.

OpenAPI của `/encrypt` khai báo cả hai `requestBody.content` schema và exact response schema cho 200/413/415/422/500. `/decrypt` và key endpoints khai báo JSON schema. Alternative tạo `/api/rsa/file` bị loại vì phá bốn endpoint tham chiếu/Q7.

### 7. Exact success schemas và selected trace inline

Response model là discriminated union theo operation/inputType/mode và không echo secret ngoài keygen response đã yêu cầu. Các list luôn đầy đủ. `trace` luôn hiện diện: `null` mặc định hoặc một object:

```json
{
  "operation": "encrypt",
  "blockIndex": 0,
  "input": "88",
  "exponent": "7",
  "modulus": "187",
  "result": "11",
  "steps": [
    {"i": 0, "bit": 1, "base": "88", "before": "1", "result": "88"}
  ]
}
```

Route validate index sau collection/domain/package validation nhưng trước chạy transform; core chỉ thu rows cho block được chọn. Trần exponent 128 bit tạo ceiling tự nhiên 128 rows, nên không cần product truncation policy.

Key response dùng `egcdSteps` rows exact `{"index":0,"q":null,"r":"160","t":"0"}`; `q` từ dòng thứ ba và `r/t` là decimal string canonical có dấu trừ chỉ với signed coefficient `t`. Full table kết thúc ở remainder `0`.

Alternative nhét steps vào từng block bị loại vì Q11; alternative `/trace` route bị loại vì mục tiêu bốn endpoint.

### 8. Error isolation và deterministic precedence

Định nghĩa một `RsaApiError(status_code, code, message, field)` và handler theo exception type đó. Core error mang code/parameters không chứa HTTP. Router bắt/mapping lỗi dự kiến. Các global handler hiện hữu cho framework validation và exception ngoài dự kiến SHALL thêm một nhánh chỉ khi path thuộc exact set bốn RSA endpoint để trả envelope RSA; mọi path khác chạy nguyên logic baseline. Nhờ vậy lỗi trước/sau endpoint function, kể cả response validation, vẫn không rơi về envelope hai trường. Exception ngoài dự kiến tiếp tục được log theo cơ chế safe hiện hữu và map `INTERNAL_ERROR` không lộ traceback.

Validation được viết thành các phase đúng `rsa-error-handling`; phase trước hoàn tất trước phase sau. Multipart có phase riêng vì parse/stream khác JSON. Mọi lỗi trả một body, không aggregate. 64 MiB guard tạo cùng envelope trước router bằng path prefix exact `/api/rsa/`; các path gần giống như `/api/rsax` không được phân loại RSA.

Alternative thay toàn bộ global 422/500 contract bị loại vì Q2/Q15 cấm đổi old APIs; chỉ nhánh RSA path được phép cộng thêm. Alternative chỉ catch trong endpoint bị loại vì không bao phủ lỗi framework/response serialization. Alternative tái dùng two-field exception hiện hành bị loại vì thiếu `code/field`.

### 9. CPU-bound work rời event loop, không persistence

Primality, random key generation và transform list được gọi qua threadpool như tiền lệ DES. Request parsing, bounded file read và response serialization ở async route. Collection/operand caps chạy trước threadpool. Không gọi `note_history`, không thêm RSA vào `history.routes`, `CIPHERS`, model hoặc migration; whitelist hiện hữu khiến middleware bỏ qua RSA.

Alternative chạy vòng modular exponentiation 40.000 block trực tiếp trong event loop bị loại vì có thể làm nghẽn request khác. Alternative queue/background job bị loại vì mở rộng contract và state.

### 10. Warning giáo dục là tài liệu, không đổi success envelope

OpenAPI descriptions, README/consumer guide SHALL nói rõ textbook RSA 16–128 bit không an toàn cho dữ liệu thật, không có confidentiality production/authenticity và không phát hiện đáng tin cậy wrong key. Không thêm field `warnings` vào response vì không có trong contract đã chốt; warning nằm ở documentation/tag/operation descriptions.

## Risks / Trade-offs

- **[Textbook RSA và key rất nhỏ có thể bị lạm dụng]** → Gắn cảnh báo rõ trong OpenAPI/README; không mô tả là secure; không hỗ trợ OAEP/signature/key export.
- **[Wrong key hoặc metadata tamper có thể tạo plaintext hợp lệ]** → Chỉ trả `DECODE_FAILED` cho inconsistency quan sát được; ghi rõ không authenticated và không claim phát hiện wrong key.
- **[40.000 block tạo response/CPU đáng kể]** → Cap trước parse item/transform, operand tối đa 128 bit, trace tối đa một block, chạy CPU ở threadpool; không tăng cap trong implementation.
- **[Request body JSON dưới 64 MiB nhưng lớn hơn business cap vẫn phải được đọc]** → Strict decoder áp raw token/collection/text limits ngay sau parse; guard 64 MiB vẫn là hard ceiling. Đây là giới hạn kiến trúc hiện hành, không thay đổi transport streaming trong change này.
- **[Duplicate JSON detection cần custom decode và có thể lệch OpenAPI/Pydantic]** → Một decoder + table-driven tests cho mọi endpoint; response vẫn qua Pydantic exact models; OpenAPI schema viết explicit.
- **[Miller–Rabin witness implementation sai làm lọt hợp số]** → Unit test prime/composite boundary và pseudoprime corpus trong miền 64 bit; recheck invariant sau generation.
- **[Hai media type cùng route dễ có validation precedence khác nhau]** → Tách phase JSON/multipart nhưng dùng chung decimal/domain validators và cùng error factory; integration test cặp tương đương.
- **[RSA-specific 64 MiB envelope là nhánh cross-cutting]** → Match chính xác `/api/rsa/`, thêm regression tests cho mọi old file/non-file guard body.

## Migration Plan

1. Thêm core và unit tests, chưa đăng router.
2. Thêm strict schemas/error mapping, response models và OpenAPI fragments.
3. Thêm router RSA, middleware path handling và include router; không có database migration.
4. Chạy unit/integration/OpenAPI/history regression, Ruff và coverage gate theo repo trước merge implementation tương lai.
5. Cập nhật README/consumer docs với warning và examples.

Rollback là bỏ router include và các file RSA, rồi hoàn nguyên riêng nhánh RSA trong guards/messages. Vì không có persistence/schema change hoặc server state, không cần data migration/cleanup; old APIs phải giữ nguyên xuyên suốt deploy/rollback.
