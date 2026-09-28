## Purpose

Định nghĩa endpoint multipart Affine dùng cùng core với text và kế thừa nguyên vẹn contract file, preview/attachment, UTF-8, BOM, kích thước và filename đã nghiệm thu.

## ADDED Requirements

### Requirement: Endpoint file Affine và exact multipart field set

Hệ thống SHALL cung cấp `POST /api/affine/file`, đưa tổng route cipher lên đúng 12. Multipart SHALL chỉ cho phép các field `file`, `a`, `b`, `action`, `response_mode`; field lạ hoặc duplicate field MUST trả HTTP 422 `Dữ liệu gửi lên không hợp lệ.` trước field/content validation. `file`, `a`, `b`, `action` bắt buộc; `response_mode` tùy chọn và mặc định `content`. Không có default cho `a` hoặc `b`. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed `additional-file-cipher-api`)

#### Scenario: File content mode canonical
- **WHEN** client gửi `hello.txt` chứa `HELLO`, `a=5`, `b=8`, `action=encrypt`, `response_mode=content`
- **THEN** hệ thống trả HTTP 200 với `{"success":true,"result":"RCLLA"}`

#### Scenario: Multipart field lạ bị từ chối
- **WHEN** request hợp lệ khác nhưng có thêm field `key=5`
- **THEN** hệ thống trả HTTP 422 với message `Dữ liệu gửi lên không hợp lệ.`

#### Scenario: Bỏ response mode mặc định content
- **WHEN** request có `file`, `a`, `b`, `action` hợp lệ và không gửi `response_mode`
- **THEN** endpoint xử lý như `response_mode=content`

### Requirement: a và b multipart là signed-decimal tối đa 32 ký tự

Giá trị `a` và `b` SHALL được đọc như string form. Mỗi giá trị SHALL được trim whitespace ngoài theo convention hiện hành, sau đó phải khác rỗng, dài tối đa 32 ký tự và khớp toàn bộ `[+-]?[0-9]+`. Độ dài được tính sau trim và gồm dấu nếu có. Thiếu/rỗng SHALL dùng message thiếu field; sai grammar hoặc quá 32 ký tự SHALL dùng message integer tương ứng. Hệ thống SHALL normalize modulo 26 sau parse; `a'` còn phải khả nghịch. (Truy vết: quyết định chủ sở hữu cho change này; baseline Caesar multipart `parse_multipart_key`)

#### Scenario: Signed decimal âm được chấp nhận
- **WHEN** client gửi `a=-21`, `b=-18`
- **THEN** endpoint dùng normalized pair `(5,8)`

#### Scenario: Whitespace ngoài được trim theo convention hiện tại
- **WHEN** client gửi `a="  +5  "` và `b=" 8 "`
- **THEN** hai field qua grammar và endpoint dùng `(5,8)`

#### Scenario: Key multipart dài 33 ký tự bị từ chối
- **WHEN** `a` hoặc `b` sau trim dài 33 ký tự
- **THEN** hệ thống trả HTTP 422 với message integer của field đó

#### Scenario: Key multipart đúng 32 ký tự được chấp nhận
- **WHEN** client gửi `a=+0000000000000000000000000000005` và `b=+0000000000000000000000000000008`, mỗi giá trị dài đúng 32 ký tự
- **THEN** hai field qua bước length/grammar và endpoint dùng normalized pair `(5,8)`

### Requirement: Action và response mode phân biệt hoa thường

`action` SHALL là chính xác `encrypt` hoặc `decrypt`. `response_mode` SHALL là chính xác `content` hoặc `file` nếu được gửi. Giá trị thiếu/sai của action trả `Action phải là encrypt hoặc decrypt.`; response mode sai trả `Response mode phải là content hoặc file.`. Hai field phân biệt hoa thường. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed `additional-file-cipher-api`)

#### Scenario: Action viết hoa bị từ chối
- **WHEN** `action=ENCRYPT` với các field trước đó hợp lệ
- **THEN** hệ thống trả HTTP 422 với message `Action phải là encrypt hoặc decrypt.`

#### Scenario: Response mode viết hoa bị từ chối
- **WHEN** `response_mode=FILE` với các field trước đó hợp lệ
- **THEN** hệ thống trả HTTP 422 với message `Response mode phải là content hoặc file.`

### Requirement: Content mode trả exact JSON success

Khi `response_mode=content`, request hợp lệ SHALL trả HTTP 200, `Content-Type: application/json` và đúng body `{"success":true,"result":"<result>"}`. Nếu input có UTF-8 BOM, BOM MUST không xuất hiện trong result. Response MUST không có `Content-Disposition`, normalized keys, inverse, analysis hoặc metadata khác. (Truy vết: quyết định chủ sở hữu cho change này; baseline file content mode)

#### Scenario: Content mode bỏ BOM logic
- **WHEN** input bắt đầu bằng UTF-8 BOM rồi chứa `HELLO`
- **THEN** result là `RCLLA` và không bắt đầu bằng `U+FEFF`

### Requirement: File mode trả attachment do server sở hữu

Khi `response_mode=file`, request hợp lệ SHALL trả HTTP 200, `Content-Type: text/plain; charset=utf-8`, `Content-Disposition: attachment` và bytes UTF-8 result không bọc JSON. Attachment SHALL giữ UTF-8 BOM nếu và chỉ nếu input có BOM. Server SHALL quyết định bytes và filename; client MUST gửi request download riêng thay vì đóng gói preview. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed file specs và guide FE)

#### Scenario: Attachment encrypt giữ BOM
- **WHEN** input `note.txt` có BOM, chứa `HELLO`, action `encrypt`, mode `file`
- **THEN** attachment bắt đầu bằng bytes `EF BB BF` rồi `RCLLA`
- **AND** filename là `note.encrypted.txt`

#### Scenario: Input không BOM không được thêm BOM
- **WHEN** input không có BOM và mode là `file`
- **THEN** attachment không bắt đầu bằng bytes `EF BB BF`

### Requirement: Filename attachment kế thừa baseline

Filename SHALL là `<basename>.encrypted.txt` hoặc `<basename>.decrypted.txt`. Hệ thống SHALL loại path component, chỉ bỏ suffix `.txt` cuối cùng không phân biệt hoa thường, giữ các dấu chấm trước đó và luôn dùng `.txt` viết thường. Tên MUST không thêm `affine` và không dùng underscore suffix. (Truy vết: quyết định chủ sở hữu cho change này; baseline Caesar Week 1 `file-cipher-api`)

#### Scenario: Tên nhiều dấu chấm và đuôi viết hoa
- **WHEN** file `bao.cao.TXT` được encrypt
- **THEN** attachment filename là `bao.cao.encrypted.txt`

#### Scenario: Decrypt dùng suffix đúng
- **WHEN** file `secret.txt` được decrypt
- **THEN** attachment filename là `secret.decrypted.txt`

### Requirement: Chỉ chấp nhận txt UTF-8 khác 0 byte

Endpoint SHALL chỉ nhận upload file có filename kết thúc `.txt` không phân biệt hoa thường; sai extension, kể cả upload part có `filename=""`, trả HTTP 415 `Chỉ chấp nhận file .txt.`. Thiếu field `file` trả HTTP 422 `Thiếu file.`; form part tên `file` nhưng không có tham số `filename` nên được parse thành scalar thay vì upload file trả HTTP 422 `Dữ liệu gửi lên không hợp lệ.` ở body framing. File upload 0 byte trả HTTP 422 `File không được để trống.`; bytes không decode được UTF-8 trả HTTP 415 `File phải sử dụng UTF-8.`. UTF-8 thường và UTF-8 có BOM SHALL hợp lệ. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed file/error specs và current Starlette multipart/runtime behavior)

#### Scenario: TXT viết hoa hợp lệ
- **WHEN** filename là `DATA.TXT` và các field/nội dung khác hợp lệ
- **THEN** file qua bước extension

#### Scenario: Double extension bị từ chối
- **WHEN** filename là `data.txt.exe`
- **THEN** hệ thống trả HTTP 415 với message `Chỉ chấp nhận file .txt.`

#### Scenario: Upload filename rỗng bị từ chối như extension không hợp lệ
- **WHEN** upload part tên `file` có tham số `filename=""`
- **THEN** hệ thống trả HTTP 415 với message `Chỉ chấp nhận file .txt.` theo baseline runtime

#### Scenario: Part file không có filename parameter không phải upload file
- **WHEN** multipart có form part tên `file` nhưng part không có tham số `filename`
- **THEN** hệ thống trả HTTP 422 với message `Dữ liệu gửi lên không hợp lệ.` ở body framing

#### Scenario: Filename không có extension bị từ chối
- **WHEN** upload có filename `readme`
- **THEN** hệ thống trả HTTP 415 với message `Chỉ chấp nhận file .txt.`

#### Scenario: Invalid UTF-8 bị từ chối
- **WHEN** file `.txt` chứa bytes không decode được bằng UTF-8
- **THEN** hệ thống trả HTTP 415 với message `File phải sử dụng UTF-8.`

### Requirement: Giới hạn file chính xác 5 MiB

Endpoint SHALL giới hạn raw upload content ở `5*1024*1024=5242880` bytes, tính cả ba byte BOM nếu có. File đúng `5242880` bytes SHALL qua bước size; file `5242881` bytes trở lên MUST trả HTTP 413 với `File vượt quá dung lượng tối đa 5 MB.`. Message cố ý ghi MB dù phép đo là MiB. (Truy vết: quyết định chủ sở hữu cho change này; baseline Caesar Week 1 file contract và runtime `read_limited_bytes` trước `decode_file_bytes`)

#### Scenario: Boundary 5 MiB được chấp nhận
- **WHEN** nội dung file có đúng 5.242.880 bytes
- **THEN** endpoint không từ chối vì size và tiếp tục validation sau

#### Scenario: Một byte trên boundary bị từ chối
- **WHEN** nội dung file có 5.242.881 bytes
- **THEN** hệ thống trả HTTP 413 với message `File vượt quá dung lượng tối đa 5 MB.`

### Requirement: Nội dung Affine file được bảo toàn ngoài ASCII

Sau decode UTF-8/BOM, endpoint SHALL đưa chuỗi logic nguyên vẹn vào Affine core. Whitespace-only SHALL hợp lệ; LF/CRLF, tab, số, dấu câu, Unicode và emoji SHALL được giữ chính xác trong preview và attachment, chỉ ASCII letter thay đổi và giữ case. (Truy vết: quyết định chủ sở hữu cho change này; `affine-core`; baseline file flow)

#### Scenario: CRLF Unicode và emoji giữ nguyên
- **WHEN** file chứa `Hé🙂z!\r\n` được encrypt bằng `(5,8)`
- **THEN** result là `Ré🙂d!\r\n`

#### Scenario: Whitespace-only file hợp lệ
- **WHEN** file khác 0 byte chỉ chứa ` \t\r\n`
- **THEN** request thành công và result giữ nguyên nội dung

### Requirement: OpenAPI mô tả endpoint file Affine

OpenAPI SHALL mô tả request multipart với required `file`, `a`, `b`, `action`, optional `response_mode=content`, `additionalProperties=false`, `a`/`b` string signed-decimal tối đa 32 ký tự, cùng response 200 JSON/text và error 413/415/422/500 JSON. (Truy vết: quyết định chủ sở hữu cho change này; baseline runtime `/openapi.json`)

#### Scenario: OpenAPI có hai success media type
- **WHEN** client đọc operation `/api/affine/file`
- **THEN** response 200 công bố `application/json` và `text/plain`
- **AND** request không công bố default cho `a` hoặc `b`

### Requirement: Ba endpoint file hiện hữu không thay đổi

Việc thêm Affine MUST NOT thay đổi request/response, field acceptance, key policy, precedence, 5 MiB, UTF-8, BOM, filename, guard hoặc result của `/api/caesar/file`, `/api/vigenere/file`, `/api/playfair/file`. (Truy vết: quyết định chủ sở hữu cho change này; completed file specs)

#### Scenario: Regression ba file endpoint hiện hữu
- **WHEN** toàn bộ file acceptance hiện tại được chạy sau change
- **THEN** mọi response quan sát được của ba route cũ giống baseline
