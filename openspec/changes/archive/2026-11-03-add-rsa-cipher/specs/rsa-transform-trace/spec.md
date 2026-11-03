# Spec Delta

## Purpose

Định nghĩa cơ chế opt-in giải thích square-and-multiply cho đúng một block ngay trong hai endpoint transform, với schema deterministic và bảng đầy đủ nhưng bị chặn bởi trần operand 128 bit.

## ADDED Requirements

### Requirement: Trace là opt-in một selected block

Client MAY gửi `traceBlockIndex` để chọn đúng một block trong request encrypt/decrypt hiện tại; không có trace route thứ năm. Index là zero-based JSON integer không âm (hoặc ASCII integer form trong multipart). Với number input, giá trị duy nhất hợp lệ là `0`. Với text, index MUST nhỏ hơn số block/cipher item thực tế. Không có field nào cho phép nhiều index, all-block trace, offset, cursor hoặc truncation. (Truy vết: PDF RSA BE-05; quyết định chủ sở hữu Q6, Q11; quyết định kỹ thuật giữ bốn endpoint)

#### Scenario: Chọn block text thứ hai

- **WHEN** request có ít nhất hai block và `traceBlockIndex=1`
- **THEN** response có đúng một trace object cho block index 1
- **AND** các block khác vẫn có result đầy đủ nhưng không có per-bit rows

#### Scenario: Index ngoài collection

- **WHEN** request có hai block và `traceBlockIndex=2`
- **THEN** HTTP 422 với `code="TRACE_INDEX_OUT_OF_RANGE"`, message `Chỉ số khối cần xem không hợp lệ.` và `field="traceBlockIndex"`

### Requirement: Exact trace schema

Khi opt-in hợp lệ, `trace` SHALL có đúng `operation`, `blockIndex`, `input`, `exponent`, `modulus`, `result`, `steps`. `operation` là `encrypt|decrypt`; `blockIndex` là JSON integer; bốn cryptographic value `input`, `exponent`, `modulus`, `result` dùng decimal string canonical. `steps` SHALL là array đầy đủ, mỗi row có đúng `i`, `bit`, `base`, `before`, `result`; `i` là JSON integer từ 0 tăng một, `bit` là JSON integer `0|1`, ba giá trị số là canonical decimal string. (Truy vết: HTML RSA §3 và implementation tham chiếu `modPow`; quyết định chủ sở hữu Q10, Q11, Q14; quyết định kỹ thuật exact schema)

#### Scenario: Row đầu của TC-02 encrypt

- **WHEN** trace encrypt block `88` với exponent `7`, modulus `187`
- **THEN** row đầu là `{"i":0,"bit":1,"base":"88","before":"1","result":"88"}`
- **AND** trace result cuối là `"11"`

#### Scenario: Trace decrypt dùng private exponent

- **WHEN** selected trace thuộc request decrypt
- **THEN** `operation="decrypt"`, `input` là cipher item được chọn và `exponent` là `d`

### Requirement: Bảng modPow đầy đủ không silent truncation

Trace SHALL chứa đúng một row cho mỗi bit từ least-significant bit tới most-significant bit của exponent, theo thuật toán right-to-left square-and-multiply: row ghi base và result trước phép nhân có điều kiện, rồi result sau phép nhân; sau row mới bình phương base. Exponent transform phải lớn hơn 1 nên trace luôn có row. Do exponent bị giới hạn `2^128-1`, trace có nhiều nhất 128 row; server MUST NOT cắt, paginate hoặc ghi marker thay thế. (Truy vết: PDF RSA BE-01/BE-05; HTML RSA §3; quyết định chủ sở hữu Q11, Q14)

#### Scenario: Exponent 128 bit

- **WHEN** exponent có bit length 128 và request trace hợp lệ
- **THEN** `steps` có đúng 128 row
- **AND** row cuối có `i=127`

### Requirement: Trace không làm thay đổi transform

Bật trace SHALL không thay đổi `blocks`, `cipher`, `plaintext`, `blockSize` hoặc `originalUtf8ByteLength`; chỉ field `trace` đổi từ `null` sang object. Validation của toàn request và selected index SHALL hoàn tất trước khi trả result; endpoint MUST không trả partial transform nếu trace request không hợp lệ. (Truy vết: quyết định chủ sở hữu Q6, Q11; convention response atomic của backend)

#### Scenario: So sánh bật và tắt trace

- **WHEN** gửi hai request giống nhau, một request không trace và một request chọn index hợp lệ
- **THEN** mọi field ngoài `trace` bằng nhau
