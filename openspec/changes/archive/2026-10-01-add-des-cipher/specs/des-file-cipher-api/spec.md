# des-file-cipher-api Specification

## Purpose

Định nghĩa endpoint multipart `/api/des/file` dùng cùng lõi với text API và kế thừa nguyên vẹn contract file hiện hành về preview/attachment, UTF-8, BOM, dung lượng và tên file. Nguồn: `Scope Backend_ Hệ mã hóa DES.html` §§1, 7 BE-D08; main spec `file-cipher-api`, `affine-file-cipher-api`; quyết định chủ sở hữu Q4, Q5, Q8, Q11, Q19 ngày 2026-10-01.

## ADDED Requirements

### Requirement: Endpoint file DES và exact multipart field set

Hệ thống SHALL cung cấp `POST /api/des/file`. Multipart SHALL chỉ cho phép các field `file`, `key`, `action`, `mode`, `iv`, `response_mode`; field lạ hoặc field trùng MUST trả HTTP 422 `Dữ liệu gửi lên không hợp lệ.` trước field/content validation. `file`, `key`, `action` bắt buộc; `mode` tùy chọn mặc định `ECB`; `response_mode` tùy chọn mặc định `content`; `iv` chỉ dùng khi `mode=CBC` và bị bỏ qua khi `mode=ECB`. Khóa và IV theo cùng quy tắc chuẩn hóa như text API. (Truy vết: HTML DES scope §7; quyết định chủ sở hữu Q11, Q19; baseline `affine-file-cipher-api`)

#### Scenario: Field lạ bị từ chối
- **WHEN** request hợp lệ nhưng có thêm field `inputFormat=hex`
- **THEN** hệ thống trả HTTP 422 với message `Dữ liệu gửi lên không hợp lệ.`

#### Scenario: Mặc định content và ECB
- **WHEN** request có `file`, `key`, `action` hợp lệ và không gửi `mode`, `response_mode`
- **THEN** endpoint xử lý như `mode=ECB`, `response_mode=content`

### Requirement: Chiều xử lý nội dung file

Với `action=encrypt`, nội dung file (đã bỏ BOM UTF-8 nếu có) SHALL được xử lý như `inputFormat=text`: mã UTF-8, đệm PKCS#7, kết quả là một chuỗi hex in hoa. Với `action=decrypt`, nội dung file SHALL là bản mã hex, cho phép khoảng trắng và xuống dòng, và được xử lý như `outputFormat=text`. (Truy vết: HTML DES scope §7 "POST /api/des/file")

#### Scenario: Mã hóa file content mode
- **WHEN** client gửi `hello.txt` chứa `Hello World`, `key=133457799BBCDFF1`, `action=encrypt`
- **THEN** hệ thống trả HTTP 200 với `{"success":true,"result":"B1CA74BB3514268701A9ACC3E4E69FAA","warnings":[]}`

#### Scenario: Giải mã file hex nhiều dòng
- **WHEN** client gửi `cipher.txt` chứa `B1CA74BB35142687\r\n01A9ACC3E4E69FAA\r\n`, cùng khóa, `action=decrypt`
- **THEN** `result` là `Hello World`

#### Scenario: CBC qua file
- **WHEN** client gửi file chứa `Hello World`, `action=encrypt`, `mode=CBC`, `iv=0000000000000000`
- **THEN** `result` là `B1CA74BB351426875F9A5BCA734D9EF4`

### Requirement: Response mode content và file

`response_mode=content` SHALL trả JSON `{"success":true,"result":…,"warnings":[…]}` với warnings theo cùng quy tắc text API: W01/W02 cho cả hai action, W03 chỉ khi `action=encrypt` và `mode=ECB`. `response_mode=file` SHALL trả `text/plain; charset=utf-8` chứa kết quả, khôi phục BOM nếu file đầu vào có BOM, `Content-Disposition: attachment` theo quy tắc tên file hiện hành với hậu tố `.encrypted.txt` hoặc `.decrypted.txt`; response file không mang warnings. Lỗi ở `response_mode=file` vẫn là JSON và không có attachment. (Truy vết: HTML DES scope §7; quyết định chủ sở hữu Q8, Q11; main spec `file-cipher-api`)

#### Scenario: Tải file mã hóa
- **WHEN** client gửi `bai tap.txt` chứa `Hello World`, `action=encrypt`, `response_mode=file`
- **THEN** body là `B1CA74BB3514268701A9ACC3E4E69FAA` và `Content-Disposition` có `filename="bai tap.encrypted.txt"`

#### Scenario: Tải file giải mã giữ BOM
- **WHEN** file đầu vào có BOM và chứa bản mã hex hợp lệ, `action=decrypt`, `response_mode=file`
- **THEN** body bắt đầu bằng BOM, theo sau là văn bản giải mã, tên file kết thúc `.decrypted.txt`

#### Scenario: Warning ở content mode
- **WHEN** client gửi file chứa `AAAAAAAAAAAAAAAA` (16 byte ASCII), khóa `133457799BBCDFF1`, `action=encrypt`, `response_mode=content`
- **THEN** `warnings` có W03 với `details.repeatedBlocks=1`

### Requirement: Kiểm tra file kế thừa baseline

Route file DES SHALL trả HTTP 422 `Thiếu file.` khi thiếu file; HTTP 415 `Chỉ chấp nhận file .txt.` cho extension khác `.txt` (không phân biệt hoa thường); HTTP 413 `File vượt quá dung lượng tối đa 5 MB.` khi nội dung vượt 5.242.880 byte; HTTP 422 `File không được để trống.` cho file 0 byte; HTTP 415 `File phải sử dụng UTF-8.` khi không decode được UTF-8; HTTP 500 `Không thể đọc file.` khi lỗi đọc. `action` sai hoặc thiếu trả HTTP 422 `Action phải là encrypt hoặc decrypt.`; `response_mode` sai trả HTTP 422 `Response mode phải là content hoặc file.`. Đúng 5.242.880 byte được nhận. (Truy vết: quyết định chủ sở hữu Q11; main spec `file-cipher-api`, `affine-error-handling`)

#### Scenario: File quá 5 MiB
- **WHEN** file `.txt` có 5.242.881 byte
- **THEN** hệ thống trả HTTP 413 với message `File vượt quá dung lượng tối đa 5 MB.`

#### Scenario: Extension sai
- **WHEN** client gửi `data.md` với các field khác hợp lệ
- **THEN** hệ thống trả HTTP 415 với message `Chỉ chấp nhận file .txt.`

#### Scenario: File hex chỉ có khoảng trắng
- **WHEN** `action=decrypt` và file chỉ chứa khoảng trắng và xuống dòng
- **THEN** hệ thống trả HTTP 422 với message `Nhập văn bản hoặc tải file .txt để bắt đầu.`
