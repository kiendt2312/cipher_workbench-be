# Spec Delta

## Purpose

Định nghĩa lỗi DH ổn định bằng mã máy, thông báo tiếng Việt, field và HTTP status tương thích với các API giáo dục mới nhất trong repository.

## ADDED Requirements

### Requirement: Envelope lỗi DH chính xác
Mọi lỗi DH SHALL trả đúng `{success:false,code,message,field}`; `field` luôn có mặt và là null cho lỗi toàn request/hệ thống. Response MUST không chứa traceback, exception string, operand bí mật hoặc partial result. (Truy vết: Scope DH §Bắt lỗi; `rsa-error-handling`; quyết định chủ sở hữu DH Q6)

#### Scenario: Lỗi field cụ thể
- **WHEN** q sai miền
- **THEN** response có đúng bốn field, `success=false`, `field="q"`, không có trace hay result

### Requirement: Phân loại HTTP status
Validation/domain DH SHALL dùng 422; request/file quá lớn dùng 413; media type, extension hoặc encoding không hỗ trợ dùng 415; chỉ lỗi hệ thống thật dùng 500. Đây là deviation được chủ sở hữu phê duyệt khỏi HTTP 400 trong Scope DH BE-07. (Truy vết: Scope DH BE-07, §API; `rsa-error-handling`; quyết định chủ sở hữu DH Q6)

#### Scenario: Domain error không dùng 400
- **WHEN** `q="21"`
- **THEN** trả HTTP 422, không phải 400

#### Scenario: Internal failure được che giấu
- **WHEN** xảy ra lỗi hệ thống ngoài lỗi domain đã biết
- **THEN** HTTP 500 trả `INTERNAL_ERROR`, message `Đã xảy ra lỗi hệ thống.`, field null và không lộ chi tiết

### Requirement: Lỗi số học và tham số
DH SHALL dùng đúng codes/messages động dưới đây và HTTP 422: `NOT_INTEGER`, `Q_OUT_OF_RANGE`, `NOT_PRIME`, `ALPHA_OUT_OF_RANGE`, `NOT_PRIMITIVE_ROOT`, `BITS_INVALID`. (Truy vết: Scope DH §Bắt lỗi, TC-05–TC-08, TC-13; quyết định chủ sở hữu DH Q2/Q4/Q6)

#### Scenario: Không phải decimal string dương
- **WHEN** q, alpha, X hoặc Y không phải canonical decimal string số nguyên dương
- **THEN** trả `NOT_INTEGER`, message `Giá trị phải là số nguyên dương.`, field đúng tên input

#### Scenario: q manual ngoài miền
- **WHEN** `/params` nhận q ngoài `5..10^12`
- **THEN** trả `Q_OUT_OF_RANGE`, message `q phải từ 5 đến 10¹², hoặc dùng sinh tham số ngẫu nhiên.`, field `q`

#### Scenario: q downstream vượt 128 bit
- **WHEN** keypair, shared-secret, exchange hoặc caesar nhận q lớn hơn `2^128-1`
- **THEN** trả HTTP 422 `Q_OUT_OF_RANGE`, message `q không được vượt quá 128 bit.`, field `q`

#### Scenario: q composite
- **WHEN** q bằng `"21"`
- **THEN** trả `NOT_PRIME`, message `q = 21 không phải số nguyên tố.`, field `q`

#### Scenario: Alpha ngoài miền
- **WHEN** q bằng `"23"` và alpha bằng `"25"`
- **THEN** trả `ALPHA_OUT_OF_RANGE`, message `α phải thỏa 1 < α < q = 23.`, field `alpha`

#### Scenario: Alpha không nguyên căn có suggestion
- **WHEN** q bằng `"23"` và alpha bằng `"4"`
- **THEN** trả `NOT_PRIMITIVE_ROOT`, message `α = 4 không phải nguyên căn của 23. Gợi ý α = 5.`, field `alpha`
- **AND** server không thay alpha bằng 5

#### Scenario: Bits sai
- **WHEN** bits sai type hoặc không thuộc `16,32,64,128`
- **THEN** trả `BITS_INVALID`, message `Chỉ hỗ trợ 16, 32, 64 hoặc 128 bit.`, field `bits`

### Requirement: Lỗi khóa DH
Private key ngoài `2..q-2` SHALL dùng `PRIVATE_KEY_OUT_OF_RANGE`; private key tạo public key suy biến dùng `PRIVATE_KEY_WEAK`; peer public key ngoài `2..q-2` dùng `PUBLIC_KEY_INVALID`, đều HTTP 422. (Truy vết: Tài liệu thuật toán DH §§4,10; Scope DH §Bắt lỗi, TC-09–TC-10; `rsa-error-handling`; quyết định kỹ thuật Lead)

#### Scenario: Private key sai
- **WHEN** q bằng `"23"` và private key bằng `"22"`
- **THEN** trả `PRIVATE_KEY_OUT_OF_RANGE`, message `Khóa riêng phải thỏa 2 ≤ X ≤ q − 2 = 21.`, field của private key tương ứng

#### Scenario: Public key sai
- **WHEN** other public key bằng `"22"` với q `"23"`
- **THEN** trả `PUBLIC_KEY_INVALID`, message `Khóa công khai của bên kia không hợp lệ.`, field `otherPublicKey`

#### Scenario: Private key tạo public key suy biến
- **WHEN** keypair manual nhận X trong range nhưng tạo Y bằng `1` hoặc `q-1`
- **THEN** trả HTTP 422 `PRIVATE_KEY_WEAK`, message `Khóa riêng tạo khóa công khai không hợp lệ. Hãy chọn khóa riêng khác.`, field `privateKey`

### Requirement: Lỗi input Caesar DH
Data/file rỗng SHALL dùng `EMPTY_INPUT` 422. Sai extension dùng `FILE_INVALID` 415; vượt 5 MiB dùng `FILE_INVALID` 413; UTF-8 sai dùng `UNSUPPORTED_ENCODING` 415. (Truy vết: Scope DH §Bắt lỗi; `file-cipher-api`; quyết định chủ sở hữu DH Q5/Q6)

#### Scenario: Data rỗng
- **WHEN** JSON `/caesar` có `data=""`
- **THEN** trả HTTP 422 `EMPTY_INPUT`, message `Dữ liệu đầu vào đang rỗng.`, field `data`

#### Scenario: Thiếu file
- **WHEN** multipart `/caesar` không có part `file`
- **THEN** trả HTTP 422 `MISSING_FILE`, message `Thiếu file.`, field `file`

#### Scenario: Extension file sai
- **WHEN** multipart upload không có đuôi `.txt` không phân biệt hoa thường
- **THEN** trả HTTP 415 `FILE_INVALID`, message `Chỉ chấp nhận file .txt.`, field `file`

#### Scenario: File vượt đúng một byte
- **WHEN** `.txt` có 5,242,881 byte
- **THEN** trả HTTP 413 `FILE_INVALID`, message `File vượt quá dung lượng tối đa 5 MB.`, field `file`

#### Scenario: File không phải UTF-8
- **WHEN** `.txt` trong giới hạn có byte sequence UTF-8 sai
- **THEN** trả HTTP 415 `UNSUPPORTED_ENCODING`, message `File phải sử dụng UTF-8.`, field `file`

#### Scenario: Lỗi đọc file
- **WHEN** server không thể đọc upload sau khi metadata/extension hợp lệ
- **THEN** trả HTTP 500 `FILE_READ_FAILED`, message `Không thể đọc file.`, field `file`

### Requirement: Media và request lỗi
DH JSON routes SHALL chỉ nhận `application/json`; `/caesar` nhận JSON hoặc multipart. Media sai dùng 415 `UNSUPPORTED_MEDIA_TYPE`; malformed/missing/unknown/duplicate/inapplicable field dùng 422 `INVALID_REQUEST`. (Truy vết: `rsa-error-handling`; quyết định chủ sở hữu DH Q6; quyết định kỹ thuật strict contract)

#### Scenario: Media không hỗ trợ
- **WHEN** `/params` nhận `text/plain`
- **THEN** trả HTTP 415 `UNSUPPORTED_MEDIA_TYPE`, message `Kiểu nội dung không được hỗ trợ.`, field null

#### Scenario: Unknown field
- **WHEN** một DH request chứa field ngoài schema variant
- **THEN** trả HTTP 422 `INVALID_REQUEST`, message `Dữ liệu gửi lên không hợp lệ.`, field là tên field đầu tiên đó

#### Scenario: Action thiếu hoặc sai
- **WHEN** `/caesar` thiếu action hoặc action không phải `encrypt|decrypt`
- **THEN** trả HTTP 422 `INVALID_ACTION`, message `Action phải là encrypt hoặc decrypt.`, field `action`

#### Scenario: Data bị thiếu
- **WHEN** JSON `/caesar` thiếu field `data`
- **THEN** trả HTTP 422 `INVALID_REQUEST`, message `Dữ liệu gửi lên không hợp lệ.`, field `data`

#### Scenario: Multipart bị cắt hoặc framing sai
- **WHEN** multipart `/caesar` thiếu closing boundary hoặc malformed
- **THEN** trả HTTP 422 `INVALID_REQUEST`, message `Dữ liệu gửi lên không hợp lệ.`, field null

#### Scenario: Request DH vượt trần hạ tầng
- **WHEN** bất kỳ `/api/dh/*` có `Content-Length` lớn hơn 64 MiB
- **THEN** trả HTTP 413 `REQUEST_TOO_LARGE`, message `Yêu cầu vượt quá dung lượng cho phép.`, field null trước khi đọc body

### Requirement: Validation precedence xác định
Sau guard 64 MiB, DH SHALL dừng ở lỗi đầu theo thứ tự: media/parse/duplicate; exact field set; control type; q lexical/range/primality; alpha; private key; public key; action/data; trace computation. Multipart SHALL validate scalar fields trước extension, size, empty và encoding. (Truy vết: `rsa-error-handling` precedence; quyết định kỹ thuật của change)

#### Scenario: q lỗi thắng file lỗi
- **WHEN** multipart `/caesar` vừa có q sai vừa có extension file sai
- **THEN** trả lỗi q tương ứng và không đọc nội dung file

#### Scenario: Extension thắng file size
- **WHEN** multipart có scalar hợp lệ nhưng file vừa sai extension vừa quá 5 MiB
- **THEN** trả HTTP 415 `FILE_INVALID` cho extension
