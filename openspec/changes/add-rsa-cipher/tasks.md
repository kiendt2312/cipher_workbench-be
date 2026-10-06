# Tasks

## 1. RSA Core Arithmetic

- [x] 1.1 Tạo `app/core/rsa.py` với error/value types nội bộ, `gcd`, Euclid mở rộng và modular inverse; thêm unit tests khóa full `q/r/t` rows (hai dòng đầu `q=null`, dòng cuối remainder 0) cùng TC-01/TC-03. **Xong khi:** `uv run --frozen pytest tests/unit/test_rsa.py -k 'gcd or egcd or inverse or key_vector'` xanh.
- [x] 1.2 Implement square-and-multiply không trace và biến thể thu full rows theo exact `i/bit/base/before/result`; thêm TC-02/TC-04, exponent 128-bit và đối chiếu với `pow(..., ..., ...)`. **Xong khi:** targeted modPow tests xanh, số row bằng bit length và không có truncation.
- [x] 1.3 Implement manual primality (`<=10^12` trial division) và deterministic Miller–Rabin cho candidate `<2^64`; thêm prime/composite boundary, Carmichael/pseudoprime corpus và test không chạy primality sau manual cap. **Xong khi:** targeted primality tests xanh và mọi composite corpus bị loại.
- [x] 1.4 Implement manual keygen validation/invariants cùng e suggestion; thêm tests TC-01/TC-03/TC-06–TC-09 và manual p/q cap. **Xong khi:** output n/phi/d và lỗi/gợi ý e khớp vector, không có partial key khi lỗi.
- [x] 1.5 Implement random exact-modulus-bit keygen 16/32/64/128 bằng CSPRNG và e preference/fallback; thêm deterministic injected-random tests. **Xong khi:** test xác nhận `n.bit_length()==bits`, `p!=q`, primality, `gcd(e,phi)=1`, `e*d%phi==1` và ưu tiên/fallback e.

## 2. Unicode và Block Encoding

- [x] 2.1 Implement char encode/decode theo Unicode code point, UTF-8 strict precheck và không normalize/trim; thêm tests TC-10/TC-11, composed/decomposed Unicode, CR/LF/CRLF, whitespace, BOM, NUL và lone surrogate. **Xong khi:** mọi round-trip giữ đúng chuỗi đầu vào và TC-11 cipher list khớp reference.
- [x] 2.2 Implement tính `k`, pack UTF-8 big-endian, right-zero-pad và unpack đúng `k` byte; thêm TC-12/TC-13 cùng boundary `n=256/257` và plaintext đa byte. **Xong khi:** blocks/cipher vector `Hi!` khớp PDF và `n<=256` bị từ chối.
- [x] 2.3 Implement block decrypt theo `originalUtf8ByteLength`, canonical block count, block-width/padding/strict UTF-8 checks và post-decode 10.000-code-point cap; thêm tests trailing NUL thật, BOM-as-content, zero padding, metadata tamper hợp lệ/không hợp lệ và decoded-text overflow. **Xong khi:** chỉ padding xác định bị bỏ, NUL/BOM thật được giữ và mọi package bất nhất map đúng core error.
- [x] 2.4 Implement collection/domain caps ở core boundary (number 1, char 10.000, block 40.000, operand 128 bit, `P/C<n`) và tests tại limit/limit+1. **Xong khi:** cap lỗi xảy ra trước modular loop và TC-05 trả domain error đúng.

## 3. Strict Schema và Error Contract

- [x] 3.1 Tạo RSA error constants/factory và exact `{success,code,message,field}` responses cho toàn bộ bảng `rsa-error-handling`; thêm nhánh RSA-only vào framework/unexpected handlers, giữ logic route cũ nguyên trạng. **Xong khi:** mỗi code/status/message/field có assertion, lỗi response/framework RSA vẫn bốn trường và regression old handler bodies không đổi.
- [x] 3.2 Implement strict JSON decoder phát hiện malformed/non-object/duplicate ở mọi object, giữ raw integer/float lexeme không eager-convert, rồi exact unknown/missing/inapplicable field-set dispatch cho bốn operation variants. **Xong khi:** unit tests phủ duplicate raw member, unknown field, discriminator/mode, number/text inapplicable fields và oversized JSON integer token với precedence đã spec.
- [x] 3.3 Implement decimal parser ASCII `[0-9]+`, raw 128-digit guard trước normalization, 128-bit value cap và canonical output; implement strict JSON small-integer validators. **Xong khi:** tests phủ signs/space/exponent/underscore/Unicode digit/JSON number/bool/null, leading zero, 129 zero và exact `2^128-1` boundary.
- [x] 3.4 Tạo exact request/response/trace/Euclid Pydantic models với `extra="forbid"` và aliases camelCase. **Xong khi:** model/schema tests xác nhận required/optional fields, decimal string output, `trace:null|object` và không có response field ngoài spec.
- [x] 3.5 Tạo OpenAPI fragments cho JSON/multipart bodies và RSA responses 200/413/415/422/500 với `additionalProperties:false`. **Xong khi:** OpenAPI schema snapshot phản ánh đúng union/media type và exact RSA error envelope.
- [x] 3.6 Implement table-driven JSON validation phases theo precedence trong spec, gồm collection cap trước item parse và indexed path `cipher[i]`; thêm multi-error tests. **Xong khi:** các cặp lỗi đồng thời luôn trả đúng lỗi đầu, không phụ thuộc JSON member order ngoài duplicate/unknown.

## 4. Key API

- [x] 4.1 Implement `POST /api/rsa/keys` trong `app/api/routes_rsa.py`, chuyển core errors sang RSA envelope và chạy CPU work qua threadpool. **Xong khi:** integration tests TC-01, TC-06–TC-09, prime cap, strict body và exact manual success schema đều xanh.
- [x] 4.2 Implement `POST /api/rsa/keys/random` cho integer bits 16/32/64/128, exact modulus length, p/q response và full Euclid rows. **Xong khi:** integration tests cho bốn bit sizes, invalid type/value, e preference/fallback và exact random response schema đều xanh.
- [x] 4.3 Thêm OpenAPI descriptions cho hai key endpoints, cảnh báo textbook/small-key và examples từ TC-01/TC-03 mà không mô tả an toàn production. **Xong khi:** OpenAPI contract test thấy đúng hai key operations, request bodies, response schemas và warning text.
- [x] 4.4 Thêm integration assertion hai key routes không gọi history khi `DATABASE_URL` bật và không phụ thuộc request trước. **Xong khi:** history row count không đổi sau success/error key requests.

## 5. JSON Transform API và Selected Trace

- [x] 5.1 Implement JSON number encrypt/decrypt trên hai transform routes với exact list-one request, canonical blocks/result và full response. **Xong khi:** integration tests TC-02/TC-04/TC-05, empty/two-item cipher, operand/range errors và exact number schemas xanh.
- [x] 5.2 Implement JSON char encrypt/decrypt với full block lists, Unicode scalar checks và computed `originalUtf8ByteLength`. **Xong khi:** tests TC-10/TC-11, BOM, whitespace/newlines, composed/decomposed Unicode, NUL, 10.000/10.001 code point và invalid scalar xanh.
- [x] 5.3 Implement JSON block encrypt/decrypt với `k`, required length metadata và lossless package response. **Xong khi:** tests TC-12/TC-13, BOM, trailing NUL, block count/width/padding/UTF-8 mismatch và 40.000/40.001 collection boundary xanh.
- [x] 5.4 Implement `traceBlockIndex` inline cho encrypt/decrypt, materialize full rows chỉ cho selected block và trả `trace:null` mặc định. **Xong khi:** tests number index 0, text index đầu/cuối/out-of-range, 128-row ceiling, encrypt/decrypt schema và equality của mọi non-trace field xanh.
- [x] 5.5 Implement wrong-key/decode behavior chỉ báo `DECODE_FAILED` cho scalar/block-width/padding/UTF-8 inconsistency quan sát được; thêm valid-looking wrong-key/metadata cases. **Xong khi:** invalid packages lỗi theo spec, còn output hợp lệ quan sát được trả 200 và test không kỳ vọng wrong-key detection.
- [x] 5.6 Thêm transform OpenAPI request/response examples và educational warning, không tạo `/trace` hoặc ciphertext route. **Xong khi:** OpenAPI route inventory có đúng bốn RSA POST operation và transform examples/schema khớp integration responses.
- [x] 5.7 Thêm integration assertion mọi RSA transform success/error không ghi `cipher_operations`. **Xong khi:** history row count không đổi và cipher enum/filter/schema không có `rsa`.

## 6. Multipart Encrypt và Guards

- [x] 6.1 Thêm content-type dispatch trên `/api/rsa/encrypt` và multipart exact/duplicate field validation (`file,e,n,mode,traceBlockIndex?`); nối multipart completion guard cho đúng route/media type. **Xong khi:** integration tests JSON parity, duplicate/missing/scalar file, unknown/inapplicable field, malformed boundary và unsupported media type xanh.
- [x] 6.2 Implement bounded file read ở 1.000.000 byte decimal, case-insensitive `.txt`, MIME-agnostic validation và UTF-8 strict không strip BOM/đổi newline. **Xong khi:** tests 1.000.000/1.000.001 byte, 0 byte, `.TXT`, sai extension, invalid UTF-8, BOM và CR/LF/CRLF trả đúng status/envelope.
- [x] 6.3 Dùng chung text transform/response cho decoded file, kiểm 10.000 code point gồm BOM và selected trace. **Xong khi:** file-vs-JSON parity tests cho char/block, BOM byte length, 10.000/10.001 boundary và trace selected block xanh; response luôn JSON, không attachment header.
- [x] 6.4 Mở rộng request-size guard nhận diện exact `/api/rsa/` và trả RSA `REQUEST_TOO_LARGE` bốn trường, giữ toàn bộ old route bodies nguyên vẹn. **Xong khi:** guard tests phủ bốn RSA routes, JSON/multipart encrypt, path gần giống và regression old file/non-file envelopes.
- [x] 6.5 Thêm tests deterministic multipart precedence (`e` trước extension, extension trước byte size, size trước empty/decode, decode trước code-point cap, trace sau domain). **Xong khi:** mọi multi-error fixture trả đúng một error đầu theo `rsa-file-encrypt-api`.

## 7. Assembly, Documentation và Integration Gates

- [x] 7.1 Include RSA router trong `app/main.py`, giữ layering rule và không thêm dependency/database migration/history wiring. **Xong khi:** import/layering tests xanh, `uv.lock` và migration inventory không đổi, app route inventory chỉ tăng bốn.
- [x] 7.2 Cập nhật `README.md` và `repo_docs/frontend-integration.md` với bốn endpoint, exact JSON/multipart examples, decimal-only contract, `originalUtf8ByteLength`, selected trace, limits, status/error table, BOM/lossless behavior và warning textbook/wrong-key. **Xong khi:** docs review đối chiếu đủ Q1–Q15 và không hứa upload/download/history/OAEP/security production.
- [x] 7.3 Thêm một TC-01…TC-13 traceability matrix test/document assertion để mỗi vector PDF có ít nhất một automated test, kèm accepted policy edges (duplicate/unknown fields, raw guard, caps, metadata tamper, BOM/NUL, one-block trace). **Xong khi:** không TC hoặc accepted edge nào thiếu test reference.
- [x] 7.4 Chạy targeted RSA unit/integration suites và OpenAPI/history/guard regressions. **Xong khi:** tất cả targeted tests xanh, exact error/response snapshots không drift và không cần database migration.
- [x] 7.5 Chạy full `uv run --frozen pytest`, `uv run --frozen ruff check .`, `uv run --frozen ruff format --check .` và `openspec validate add-rsa-cipher --strict` bằng CLI tương thích. **Xong khi:** mọi gate exit 0, branch coverage backend vẫn tối thiểu 90%, không thêm exclusion che code RSA và kết quả được ghi nhận trên cùng final state.

> Ghi chú quyết định Q16: task 5.7 và phần “không history/migration” của 7.1–7.5 là bằng chứng đã hoàn thành theo scope được chấp nhận trước đó; chúng không bị viết lại thành chưa từng tồn tại. Q16 supersede riêng kết luận no-history cho hai transform và được thực hiện bằng các task 8.x bên dưới. Task 4.4 về keygen vẫn giữ nguyên hiệu lực.

## 8. RSA Operation History Scope Extension (Q16)

- [x] 8.1 Cập nhật proposal/design/spec delta để ghi rõ Q16 supersede quyết định transform no-history, nhưng giữ keygen no-history và ranh giới không lưu content/key/trace. **Xong khi:** artifact nêu exact route/source/length semantics, hành vi DB chưa migrate và rollback; OpenSpec validate strict xanh.
- [x] 8.2 Đăng ký `rsa` trong model/filter và chỉ hai route transform trong history matcher, phân biệt JSON `source=text` với multipart encrypt `source=file`; keygen không được đăng ký. **Xong khi:** unit tests phủ route/media matching, `cipher=rsa` hợp lệ và keygen/non-RSA behavior không đổi.
- [x] 8.3 Gắn `note_history` an toàn vào transform: JSON text encrypt chỉ input code point, JSON text decrypt chỉ output code point, multipart chỉ input raw byte; number/cipher-array side và `response_mode` là NULL. **Xong khi:** fake-recorder tests phủ success/error/413/415/422/500, `.txt` encrypt, best-effort failure và chứng minh không có payload/key/trace/filename/IP/user-agent.
- [x] 8.4 Thêm Alembic `0004` chỉ nới `ck_cipher_operations_cipher` để nhận `rsa`, giữ schema/data/index; downgrade không âm thầm xóa row RSA. **Xong khi:** upgrade/downgrade/preserve/constraint tests xanh trên PostgreSQL disposable và code với schema `0003` vẫn trả nguyên response RSA dù recorder bỏ lỡ row.
- [x] 8.5 Cập nhật README/frontend guide và delta OpenSpec history specs về `cipher=rsa`, metadata/null length semantics, migrate-first, pre-upgrade data-gap và rollback cần xử lý row RSA; không đổi bốn RSA contracts. **Xong khi:** docs không hứa lưu content/key và không còn statement transform RSA no-history lỗi thời.
- [x] 8.6 Chạy targeted/full pytest, Ruff check/format, Alembic/OpenSpec strict checks và PostgreSQL disposable verification nếu khả thi. **Xong khi:** mọi gate thực thi xanh; nếu real DB không khả thi phải ghi exact blocker/skip, không trình bày skip-only là DB proof.
