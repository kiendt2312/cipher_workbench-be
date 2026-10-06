# Spec Delta

## Purpose

Định nghĩa contract JSON chính xác cho hai endpoint biến đổi RSA số/văn bản, gồm request union strict, cipher package lossless, response canonical và giới hạn collection đã được chủ sở hữu chấp nhận.

## ADDED Requirements

### Requirement: Hai endpoint transform và media type

Hệ thống SHALL cung cấp đúng `POST /api/rsa/encrypt` và `POST /api/rsa/decrypt` cho transform RSA. `/encrypt` SHALL nhận `application/json`; riêng plaintext text còn có thể dùng `multipart/form-data` theo capability `rsa-file-encrypt-api`. `/decrypt` SHALL chỉ nhận `application/json`. Mọi response, kể cả encrypt từ file, MUST là `application/json`; hệ thống MUST NOT cung cấp endpoint ciphertext upload/download khác. (Truy vết: PDF RSA trang 3; quyết định chủ sở hữu Q2, Q7; proposal `add-rsa-cipher`)

#### Scenario: Bốn endpoint tham chiếu được giữ nguyên

- **WHEN** OpenAPI được sinh
- **THEN** RSA chỉ thêm bốn operation `POST /api/rsa/keys`, `/api/rsa/keys/random`, `/api/rsa/encrypt`, `/api/rsa/decrypt`
- **AND** không có route `/api/rsa/file`, `/trace`, download hoặc history

#### Scenario: Decrypt multipart bị từ chối

- **WHEN** client gửi multipart tới `POST /api/rsa/decrypt`
- **THEN** HTTP 415 với RSA error envelope và `code="UNSUPPORTED_MEDIA_TYPE"`

### Requirement: Request encrypt JSON là discriminated union strict

JSON number encrypt SHALL có đúng các field bắt buộc `e`, `n`, `inputType:"number"`, `data` và field tùy chọn `traceBlockIndex`; `mode` và `originalUtf8ByteLength` không áp dụng. JSON text encrypt SHALL có đúng `e`, `n`, `inputType:"text"`, `mode:"char"|"block"`, `data` và tùy chọn `traceBlockIndex`; `originalUtf8ByteLength` không áp dụng. `e`, `n` và number `data` SHALL là decimal string; text `data` SHALL là JSON string. `traceBlockIndex`, nếu có, SHALL là JSON integer không âm. (Truy vết: PDF RSA trang 3 `/encrypt`; quyết định chủ sở hữu Q10, Q11, Q14, Q15)

#### Scenario: Number encrypt TC-04

- **WHEN** POST `/api/rsa/encrypt` với `{"e":"17","n":"3233","inputType":"number","data":"65"}`
- **THEN** HTTP 200 với `blocks=["65"]` và `cipher=["2790"]`

#### Scenario: TC-05 P vượt modulus

- **WHEN** POST number encrypt với `e="7"`, `n="187"`, `data="200"`
- **THEN** HTTP 422 với `code="P_TOO_LARGE"`, message `P = 200 ≥ n = 187. Hãy chia khối hoặc dùng n lớn hơn.` và `field="data"`

#### Scenario: Field mode không áp dụng cho number

- **WHEN** number encrypt có thêm `mode="char"`
- **THEN** HTTP 422 `INVALID_REQUEST` với `field="mode"`

### Requirement: Request decrypt JSON là discriminated union strict

JSON number decrypt SHALL có đúng các field bắt buộc `d`, `n`, `inputType:"number"`, `cipher` và field tùy chọn `traceBlockIndex`; `cipher` SHALL là array đúng một decimal string, còn `mode` và `originalUtf8ByteLength` không áp dụng. JSON char decrypt SHALL có đúng `d`, `n`, `inputType:"text"`, `mode:"char"`, `cipher` và tùy chọn `traceBlockIndex`; `originalUtf8ByteLength` không áp dụng. JSON block decrypt SHALL có đúng các field trên với `mode:"block"` và thêm `originalUtf8ByteLength` bắt buộc. `d`, `n` và mỗi cipher item SHALL là decimal string; metadata length và trace index SHALL là JSON integer, không phải string. (Truy vết: PDF RSA trang 3 `/decrypt`; quyết định chủ sở hữu Q7, Q10, Q13–Q15)

#### Scenario: Number decrypt TC-02

- **WHEN** POST `/api/rsa/decrypt` với `{"d":"23","n":"187","inputType":"number","cipher":["11"]}`
- **THEN** HTTP 200 với `blocks=["88"]` và `plaintext="88"`

#### Scenario: Number cipher phải đúng một item

- **WHEN** number decrypt nhận zero item hoặc hai item
- **THEN** HTTP 422 với `code="INVALID_REQUEST"` và `field="cipher"`

#### Scenario: Block decrypt thiếu length metadata

- **WHEN** text block decrypt không có `originalUtf8ByteLength`
- **THEN** HTTP 422 với `code="INVALID_LENGTH_METADATA"` và `field="originalUtf8ByteLength"`

### Requirement: Response transform exact và canonical

Number encrypt response HTTP 200 SHALL có đúng `success:true`, `inputType:"number"`, `blocks`, `cipher`, `blockSize:null`, `trace`. Text encrypt response SHALL có đúng các field đó cộng `mode` và `originalUtf8ByteLength`; `blockSize=1` cho char và bằng `k` byte cho block. Number decrypt response SHALL có đúng `success:true`, `inputType:"number"`, `blocks`, `plaintext`, `blockSize:null`, `trace`. Text decrypt response SHALL có đúng các field đó cộng `mode` và `originalUtf8ByteLength`; `blockSize=1` cho char và bằng `k` cho block. `blocks`, `cipher` và number `plaintext` SHALL dùng decimal string canonical không zero thừa; text `plaintext` SHALL là JSON string nguyên trạng. `trace` SHALL là `null` khi không opt-in và object theo `rsa-transform-trace` khi opt-in. (Truy vết: PDF RSA trang 3; quyết định chủ sở hữu Q6, Q9–Q13; quyết định kỹ thuật của change này về exact schema)

#### Scenario: Leading zero chỉ được canonical hóa ở output

- **WHEN** number encrypt nhận `data="00065"` cùng key TC-04
- **THEN** request hợp lệ
- **AND** response dùng `blocks=["65"]`, `cipher=["2790"]`

#### Scenario: Text response mang byte length

- **WHEN** encrypt text thành công ở char hoặc block mode
- **THEN** response có `originalUtf8ByteLength` là JSON integer tính từ chính chuỗi UTF-8 đầu vào

#### Scenario: Default không có per-bit rows

- **WHEN** request không có `traceBlockIndex`
- **THEN** response vẫn chứa toàn bộ `blocks` và toàn bộ `cipher` hoặc `plaintext`
- **AND** `trace` bằng `null`, không có `steps` ở cấp response hoặc từng block

### Requirement: Text char round-trip và vector TC-11

Char encrypt SHALL trả một plaintext block và một cipher item cho mỗi Unicode code point; char decrypt SHALL trả lại đúng chuỗi code point, không trim hoặc normalize. Sau decrypt, `originalUtf8ByteLength` SHALL được tính từ plaintext đã phục hồi. (Truy vết: PDF RSA TC-10/TC-11; HTML RSA §4; quyết định chủ sở hữu Q8, Q9, Q12)

#### Scenario: TC-11 tiếng Việt

- **WHEN** char encrypt `"Xin chào Việt Nam"` với `p=101`, `q=113`, `e=3533` nên `n=11413`
- **THEN** cipher là `["1191","4861","8266","5410","9661","4909","11155","6070","5410","8077","4861","6970","7780","5410","4334","290","10050"]`
- **AND** decrypt với khóa riêng tương ứng trả đúng `"Xin chào Việt Nam"`

#### Scenario: Composition không bị normalize

- **WHEN** round-trip lần lượt `"é"` và `"e\u0301"`
- **THEN** mỗi output bằng chính input tương ứng
- **AND** hai request có block list và byte length phù hợp với hai representation khác nhau

### Requirement: Text block package lossless

Block encrypt SHALL trả `originalUtf8ByteLength` bằng số byte của UTF-8 strict, gồm ba byte BOM khi input bắt đầu bằng `U+FEFF`. Block decrypt SHALL yêu cầu metadata đó và chỉ trả HTTP 200 khi số block, block width, zero-padding và UTF-8 đều hợp lệ. Metadata không được xác thực mật mã; nếu metadata hoặc key sai nhưng vẫn tạo một package hợp lệ, endpoint SHALL trả kết quả hợp lệ quan sát được và MUST NOT tuyên bố đã phát hiện sai khóa. (Truy vết: PDF RSA trang 1 chia khối và TC-12; quyết định chủ sở hữu Q9, Q12, Q13; giới hạn factual về textbook RSA)

#### Scenario: TC-12 response package

- **WHEN** block encrypt `"Hi!"` với `e="3"`, `n="67591"`
- **THEN** `blockSize=2`, `originalUtf8ByteLength=3`, `blocks=["18537","8448"]`, `cipher=["37222","6468"]`

#### Scenario: Trailing NUL không bị bỏ nhầm

- **WHEN** block decrypt một cipher package hợp lệ của `"A\u0000"` với đúng `originalUtf8ByteLength=2`
- **THEN** plaintext kết thúc bằng `U+0000`

#### Scenario: Length metadata bị sửa nhưng output vẫn hợp lệ

- **WHEN** metadata bị thay đổi vẫn thỏa canonical block count, zero-padding và strict UTF-8
- **THEN** endpoint có thể trả HTTP 200 với plaintext khác
- **AND** tài liệu không mô tả kết quả đó là authenticated hoặc chứng minh key/metadata đúng

### Requirement: Giới hạn collection và plaintext ở API

Text `data` JSON và nội dung file đã decode SHALL có từ 1 đến 10.000 Unicode code point. Number cipher SHALL đúng một item; char cipher SHALL có 1–10.000 item; block cipher SHALL có 1–40.000 item. Hệ thống SHALL kiểm tra collection cap trước modular exponentiation. Sau block decrypt, plaintext vượt 10.000 code point SHALL bị từ chối dù số cipher item hợp lệ. Không request transform nào SHALL tạo history hoặc lưu cipher package server-side. (Truy vết: PDF RSA BE-06; quyết định chủ sở hữu Q2, Q7, Q8, Q13, Q14)

#### Scenario: Text data 10.001 code point

- **WHEN** encrypt JSON nhận text có 10.001 Unicode code point
- **THEN** HTTP 422 `INPUT_TOO_LARGE` với `field="data"` trước khi transform

#### Scenario: Block cipher 40.001 item

- **WHEN** decrypt block nhận 40.001 cipher item
- **THEN** HTTP 422 `INPUT_TOO_LARGE` với `field="cipher"` trước khi parse từng item

#### Scenario: Transform không ghi history

- **WHEN** database đang bật và bất kỳ transform RSA nào thành công hoặc thất bại
- **THEN** không có bản ghi `cipher_operations` mới

