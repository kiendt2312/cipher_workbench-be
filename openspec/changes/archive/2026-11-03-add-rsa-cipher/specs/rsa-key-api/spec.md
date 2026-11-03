# Spec Delta

## Purpose

Định nghĩa hai API sinh khóa RSA thủ công và ngẫu nhiên, response key material dạng decimal string, bảng Euclid đầy đủ và validation theo các vector TC-01, TC-03, TC-06–TC-09.

## ADDED Requirements

### Requirement: Endpoint sinh khóa thủ công strict

Hệ thống SHALL cung cấp `POST /api/rsa/keys` nhận `application/json` object có đúng ba field bắt buộc `p`, `q`, `e`, đều là decimal string. Response thành công HTTP 200 SHALL có đúng `success:true`, `n`, `phi`, `e`, `d`, `publicKey`, `privateKey`, `egcdSteps`; `publicKey` đúng `{e,n}`, `privateKey` đúng `{d,n}`. Mọi cryptographic value và mọi giá trị `q/r/t` trong Euclid SHALL là decimal string canonical; `t` có thể có dấu trừ, `q` là `null` ở hai dòng khởi tạo. (Truy vết: PDF RSA trang 3 endpoint `/keys`; HTML RSA §2; quyết định chủ sở hữu Q1, Q6, Q10, Q11, Q14)

#### Scenario: Response TC-01
- **WHEN** POST `{"p":"17","q":"11","e":"7"}`
- **THEN** HTTP 200 với `n="187"`, `phi="160"`, `e="7"`, `d="23"`
- **AND** `publicKey={"e":"7","n":"187"}` và `privateKey={"d":"23","n":"187"}`
- **AND** `egcdSteps` chứa toàn bộ các dòng tới remainder 0

#### Scenario: Không echo p và q ở manual response
- **WHEN** manual keygen thành công
- **THEN** response không có field `p` hoặc `q`

### Requirement: Endpoint sinh khóa ngẫu nhiên strict

Hệ thống SHALL cung cấp `POST /api/rsa/keys/random` nhận JSON object chỉ có `bits`, bắt buộc là JSON integer thuộc `16|32|64|128`. Response thành công HTTP 200 SHALL có cùng field như manual keygen và thêm `p`,`q`; `n` MUST có đúng bit length được yêu cầu. Endpoint MUST không nhận decimal string cho `bits` và MUST không ghi history. (Truy vết: PDF RSA trang 2 BE-03, trang 3 `/keys/random`; quyết định chủ sở hữu Q1, Q4, Q14)

#### Scenario: Random 128 bit
- **WHEN** POST `{"bits":128}`
- **THEN** HTTP 200 có `p`, `q`, `n`, `phi`, `e`, `d`, key objects và full `egcdSteps`
- **AND** `n` nằm trong `[2^127,2^128-1]`

#### Scenario: Bits dạng chuỗi bị từ chối
- **WHEN** POST `{"bits":"128"}`
- **THEN** HTTP 422 với RSA error code `INVALID_BITS` và `field="bits"`

### Requirement: Validation keygen theo bảng tham chiếu

Manual keygen SHALL kiểm tra theo thứ tự: lexical/raw/128-bit value của `p`, `q`, `e`; manual cap của `p` rồi `q`; primality của `p` rồi `q`; `p!=q`; range của `e`; cuối cùng coprime. `p`/`q` lớn hơn `10^12` SHALL không được đưa vào phép thử prime manual. Khi validation thất bại, endpoint MUST không trả partial key hoặc Euclid table. (Truy vết: PDF RSA trang 2 BE-02/BE-06, trang 3–5 bảng lỗi và TC-06…TC-09; quyết định chủ sở hữu Q5, Q14, Q15)

#### Scenario: TC-06 p không nguyên tố
- **WHEN** POST `{"p":"15","q":"11","e":"7"}`
- **THEN** HTTP 422 với `code="NOT_PRIME"`, message `p = 15 không phải số nguyên tố.` và `field="p"`

#### Scenario: TC-07 p bằng q
- **WHEN** POST `{"p":"11","q":"11","e":"7"}`
- **THEN** HTTP 422 với `code="SAME_PRIME"`, message `p và q phải khác nhau.` và `field="q"`

#### Scenario: TC-08 e không coprime
- **WHEN** POST `{"p":"17","q":"11","e":"10"}`
- **THEN** HTTP 422 với `code="E_NOT_COPRIME"`, message `gcd(10, 160) = 10, không tồn tại d. Gợi ý e = 3.` và `field="e"`

#### Scenario: TC-09 e ngoài range
- **WHEN** POST `{"p":"17","q":"11","e":"200"}`
- **THEN** HTTP 422 với `code="E_OUT_OF_RANGE"`, message `e phải thỏa 1 < e < phi(n) = 160.` và `field="e"`

#### Scenario: Prime manual vượt trần
- **WHEN** `p="1000000000001"`
- **THEN** HTTP 422 với `code="PRIME_TOO_LARGE"`, message `Hãy dùng p, q ≤ 10^12 hoặc sinh khóa ngẫu nhiên.` và `field="p"`

### Requirement: Keygen không lưu state hoặc secret

Hai endpoint keygen SHALL xử lý độc lập, không persist `p`, `q`, `phi`, `d`, key object hoặc Euclid steps; chúng MUST không tạo bản ghi `cipher_operations`. OpenAPI và tài liệu consumer SHALL cảnh báo key 16–128 bit và textbook RSA chỉ để học, không bảo vệ dữ liệu thật. (Truy vết: PDF RSA trang 1 Ngoài phạm vi; HTML RSA §6; quyết định chủ sở hữu Q2, Q4)

#### Scenario: Database đang bật
- **WHEN** `DATABASE_URL` được cấu hình và client gọi hai endpoint keygen
- **THEN** không có bản ghi history mới
- **AND** response không phụ thuộc request keygen trước đó
