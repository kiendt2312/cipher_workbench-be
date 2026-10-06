## Why

Backend hiện chưa có RSA trong khi hai tài liệu tham chiếu ngày 2026-10-06 mô tả đầy đủ một workflow textbook RSA phục vụ học tập: sinh khóa, mã hóa/giải mã số và văn bản, chia khối UTF-8 và giải thích từng bước. Change này bổ sung RSA vào backend hiện tại bằng một contract implementation-ready, giữ nguyên toàn bộ thuật toán, route và response của bảy cipher đang có.

## What Changes

- Thêm lõi textbook RSA dùng số nguyên Python: `gcd`, Euclid mở rộng, nghịch đảo modulo, bình phương-và-nhân, kiểm tra nguyên tố, sinh khóa thủ công và sinh khóa ngẫu nhiên đúng 16/32/64/128 bit.
- Thêm đúng bốn endpoint tham chiếu: `POST /api/rsa/keys`, `/api/rsa/keys/random`, `/api/rsa/encrypt`, `/api/rsa/decrypt`. `/encrypt` nhận JSON hoặc multipart plaintext `.txt`; mọi phản hồi thành công và lỗi đều là JSON. Không có route upload/download ciphertext.
- Hỗ trợ `inputType=number|text`; text có `mode=char|block`. `char` biến từng Unicode code point thành một block; `block` ghép UTF-8 big-endian theo `k` lớn nhất thỏa `256^k <= n - 1` và đệm `0x00` bên phải ở block cuối.
- Bảo toàn lossless plaintext: không trim, không chuẩn hóa Unicode, không đổi CR/LF/CRLF, giữ BOM như ký tự `U+FEFF` nếu có và không tự thêm BOM. Text encrypt trả `originalUtf8ByteLength`; block decrypt bắt buộc nhận lại metadata này để chỉ bỏ đúng zero-padding, không xóa NUL thật ở cuối.
- Mọi cryptographic value dùng chuỗi thập phân canonical; không hỗ trợ hex/base64. Operand bị giới hạn ở `2^128-1`; manual `p,q <= 10^12`; text tối đa 10.000 Unicode code point; file tối đa 1.000.000 byte; cipher list tối đa 1/10.000/40.000 item theo number/char/block.
- Transform mặc định trả toàn bộ block/result nhưng không trả bảng từng bit. Client có thể chọn đúng một `traceBlockIndex` mỗi request để nhận bảng modPow đầy đủ, không cắt ngầm; keygen luôn trả toàn bộ bảng Euclid mở rộng.
- Lỗi RSA dùng status hiện hành (413/415/422/500) nhưng có envelope bổ sung riêng `{success:false,code,message,field}`. Request strict: field lạ, trùng hoặc không áp dụng bị từ chối; lỗi lexical của số dùng `NOT_INTEGER`. Không thay đổi error contract của API cũ.
- RSA hoàn toàn stateless và không tham gia database/history. Đây là textbook RSA không OAEP, không dùng cho dữ liệu thật và không thể xác định đáng tin cậy một kết quả giải mã trông hợp lệ có dùng sai khóa hay không.

## Capabilities

### New Capabilities

- `rsa-core`: số học RSA, kiểm tra/sinh số nguyên tố, sinh khóa, biến đổi một block, mã hóa text char/block, phục hồi UTF-8 lossless và các giới hạn số học.
- `rsa-key-api`: request/response của `/api/rsa/keys` và `/api/rsa/keys/random`, bảng Euclid đầy đủ và validation khóa.
- `rsa-transform-api`: contract JSON của `/api/rsa/encrypt` và `/api/rsa/decrypt` cho number/text, cipher package, metadata byte length và response đầy đủ.
- `rsa-file-encrypt-api`: biến thể multipart plaintext `.txt` duy nhất của `/api/rsa/encrypt`, giới hạn 1.000.000 byte, UTF-8/BOM và JSON response.
- `rsa-transform-trace`: opt-in trace đúng một block trong hai endpoint transform, schema bảng square-and-multiply đầy đủ và giới hạn index.
- `rsa-error-handling`: envelope bốn trường, bảng code/message/status/field, strict body, raw guards và thứ tự lỗi RSA.

### Modified Capabilities

- `app-runtime`: giữ trần hạ tầng 64 MiB nhưng các request RSA bị guard từ chối phải dùng exact RSA error envelope bốn trường; hành vi của mọi route cũ không đổi.

## Impact

- Code tương lai: thêm core/schema/router RSA, đăng ký router ở `app/main.py`, mở rộng request-size guard chỉ để nhận diện envelope RSA, thêm message/exception RSA mà không sửa contract cũ.
- API: thêm bốn POST endpoint dưới `/api/rsa`; `/api/rsa/encrypt` quảng bá cả `application/json` và `multipart/form-data`; không thêm route generalized hoặc versioned.
- Persistence: không migration, không thêm `rsa` vào `CIPHERS`, history filter hoặc bảng route ghi lịch sử.
- Dependency: không cần dependency runtime mới; random generation dùng nguồn ngẫu nhiên an toàn của thư viện chuẩn.
- Tài liệu tương lai: README, consumer guide và helper FE cần mô tả RSA, warning giáo dục, metadata lossless và selected-block trace.

## Ngoài phạm vi

- UI/FE implementation; authentication, authorization hoặc session.
- OAEP, PKCS#1 v1.5 encryption padding, chữ ký số, PEM/DER/JWK, certificate, key import/export và hybrid encryption.
- Khóa production 2048 bit trở lên, bảo vệ side-channel, CRT optimization hoặc cam kết bảo mật dữ liệu thật.
- Ciphertext file upload/download, hex/base64, lưu server-side hoặc lịch sử database.
- Tự động phát hiện sai private key khi output vẫn là Unicode/UTF-8 hợp lệ.
- Thay đổi route, thuật toán, response, error envelope, history hoặc deployment của bảy cipher hiện hữu.

## Nguồn và quyết định ưu tiên

1. Quyết định chủ sở hữu Q1-Q15 ngày 2026-10-06 giải quyết mọi ambiguity và deviation được liệt kê bên dưới.
2. `scope_rsa_BE.pdf` là tham chiếu cho phạm vi BE-01…BE-07, bốn endpoint, thuật toán chia block, bảng lỗi và TC-01…TC-13.
3. `rsa-giai-thich.html` là tham chiếu cho workflow, công thức, vector, bảng Euclid và bảng square-and-multiply.
4. Main specs/runtime hiện tại là nguồn cho tính tương thích của API cũ, status HTTP, strict request precedent, guard 64 MiB, OpenAPI, statelessness và ranh giới history.

Hai tài liệu RSA là tài liệu tham chiếu phải được bám theo, không phải nguồn bất biến có quyền ghi đè quyết định chủ sở hữu. Mọi khác biệt có chủ đích phải truy vết về Q tương ứng.

### Quyết định chủ sở hữu ngày 2026-10-06

| # | Quyết định |
|---|---|
| Q1 | PDF và HTML là tài liệu tham chiếu phải bám theo; ambiguity và thay đổi vật chất phải được owner xác nhận, không âm thầm suy diễn. |
| Q2 | Thêm RSA vào backend hiện tại và không thay đổi algorithm/API hiện hữu nếu không có ủy quyền riêng. |
| Q3 | Deliverable là OpenSpec implementation-ready; change này không triển khai code. |
| Q4 | Không có requirement/handoff bên ngoài ngoài hai tài liệu tham chiếu. |
| Q5 | Dùng status convention hiện hành; giữ RSA `code`, message tiếng Việt và `field`; ghi rõ deviation khỏi HTTP 400-only. |
| Q6 | Transform luôn trả kết quả/block đầy đủ; giải thích modPow cho phép chọn block; keygen trả bảng Euclid đầy đủ. |
| Q7 | Chỉ upload plaintext `.txt` để encrypt; decrypt chỉ nhận cipher JSON; mọi result là JSON; không upload/download ciphertext file. |
| Q8 | Text và nội dung file đã decode tối đa 10.000 Unicode code point; file upload tối đa 1.000.000 byte decimal. |
| Q9 | Round-trip lossless cho whitespace, newline, trailing NUL và Unicode composition; không trim/normalize; metadata kỹ thuật cần thiết phải công khai để owner duyệt. |
| Q10 | Ciphertext canonical chỉ dùng chuỗi số thập phân; không hex/base64. |
| Q11 | Mặc định không có bảng per-bit; opt-in đúng một selected block/request với steps đầy đủ, không truncation; keygen luôn trả full Euclid. |
| Q12 | BOM nếu hiện diện là plaintext content được giữ nguyên cùng newline style; không thêm BOM khi vắng. |
| Q13 | Text encrypt trả `originalUtf8ByteLength` tính cả BOM; block decrypt bắt buộc nhận metadata này để bỏ đúng zero-padding, không dùng server state/history. |
| Q14 | Operand tối đa `2^128-1`; manual `p,q <= 10^12`; collection cap number=1, char=10.000, block=40.000; crypto value là decimal string, control value nhỏ là JSON integer; raw guard phải chặn normalization bypass. |
| Q15 | RSA error luôn đúng `{success:false,code,message,field}`; `field` luôn có mặt; strict unknown/duplicate/inapplicable; lexical number dùng `NOT_INTEGER`; không đổi API cũ. |

### Khác biệt đã được chấp nhận

| Tài liệu tham chiếu nói | Contract change này | Căn cứ |
|---|---|---|
| Mọi lỗi HTTP 400 với `{code,message,field}` | 422 validation, 413 size, 415 file type/UTF-8, 500 system; thêm `success:false` và luôn có `field` | Q5, Q15 |
| Transform trả steps của từng block | Mặc định trả toàn bộ result/block không steps; opt-in một selected block với full steps | Q6, Q11 |
| Block decrypt bỏ mọi `0x00` cuối | Bỏ đúng padding theo `originalUtf8ByteLength`, giữ NUL thật | Q9, Q13 |
| File `.txt` tối đa 1 MB nhưng chưa rõ transport/output | Chỉ multipart plaintext encrypt trên `/api/rsa/encrypt`, raw tối đa 1.000.000 byte; response JSON | Q7, Q8 |
| File/HTML demo có thể coi BOM là metadata | BOM được decode thành `U+FEFF` và mã hóa như plaintext; byte length tính cả BOM | Q9, Q12, Q13 |
| Output format còn mở decimal/hex/base64 | Chỉ decimal string canonical | Q10 |
| Random key size là câu hỏi mở | Chỉ exact modulus 16/32/64/128 bit | Q1, Q14; PDF BE-03 |
| Không nêu operand/list ceiling tổng quát | Operand 128 bit và collection cap cố định | Q14 |

