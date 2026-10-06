# Spec Delta

## Purpose

Định nghĩa biến thể multipart duy nhất để mã hóa plaintext `.txt` trên endpoint RSA encrypt, với giới hạn byte decimal, decode UTF-8 lossless, BOM-as-content và response JSON đồng nhất.

## ADDED Requirements

### Requirement: Multipart encrypt có exact field set

`POST /api/rsa/encrypt` với `multipart/form-data` SHALL nhận đúng các part bắt buộc `file`, `e`, `n`, `mode` và part tùy chọn `traceBlockIndex`; `inputType` ngầm định là `text`. `file` SHALL là upload part có filename; các scalar SHALL xuất hiện đúng một lần. Các field `data`, `inputType`, `originalUtf8ByteLength`, `action`, `response_mode` hoặc field khác MUST bị từ chối. `e` và `n` SHALL dùng cùng decimal lexical/range contract như JSON; `mode` SHALL là `char|block`; trace index form SHALL là ASCII digits canonical cho JSON integer không âm. (Truy vết: PDF RSA trang 3 cho file field; quyết định chủ sở hữu Q7, Q10, Q11, Q14, Q15; quyết định kỹ thuật giữ đúng bốn endpoint)

#### Scenario: Multipart plaintext encrypt thành công

- **WHEN** client upload một `.txt` hợp lệ cùng `e`, `n`, `mode`
- **THEN** endpoint trả cùng exact text encrypt JSON schema như request `data`
- **AND** `Content-Type` response là `application/json`

#### Scenario: Ciphertext upload không tồn tại

- **WHEN** client gửi multipart tới `/api/rsa/decrypt` hoặc dùng `cipher` part tại `/api/rsa/encrypt`
- **THEN** request bị từ chối, không có đường upload ciphertext

#### Scenario: Scalar form bị lặp

- **WHEN** multipart có hai part cùng tên `e`
- **THEN** HTTP 422 `INVALID_REQUEST` với `field="e"`

### Requirement: Filename `.txt` và MIME

File SHALL có filename kết thúc bằng `.txt` không phân biệt hoa thường. Filename rỗng, không có extension, extension khác hoặc đuôi kép kết thúc bằng phần khác SHALL trả HTTP 415 `FILE_INVALID` với message `Chỉ nhận file .txt.` và `field="file"`. MIME upload MUST không được dùng làm authority; filename và raw bytes quyết định validity. (Truy vết: PDF RSA BE-04/BE-06 và bảng lỗi; quyết định chủ sở hữu Q7, Q8; baseline file API convention)

#### Scenario: Uppercase extension hợp lệ

- **WHEN** upload filename `plain.TXT` có bytes hợp lệ
- **THEN** file không bị từ chối vì extension

#### Scenario: Tên file sai extension

- **WHEN** upload filename `plain.txt.bin`
- **THEN** HTTP 415 với `{"success":false,"code":"FILE_INVALID","message":"Chỉ nhận file .txt.","field":"file"}`

### Requirement: Raw file tối đa 1.000.000 byte decimal

Handler SHALL đếm raw upload bytes, gồm UTF-8 BOM nếu có, với giới hạn đúng `1.000.000` byte decimal. Đúng 1.000.000 byte SHALL qua bước size; 1.000.001 byte trở lên SHALL trả HTTP 413 `FILE_INVALID`, message `File vượt quá dung lượng tối đa 1 MB.` và `field="file"`. Việc đọc SHALL có bounded read để không nạp quá giới hạn nghiệp vụ một cách không giới hạn; trần 64 MiB tầng 0 vẫn áp dụng trước đó theo `app-runtime`. (Truy vết: PDF RSA BE-06 ghi 1 MB; quyết định chủ sở hữu Q8 xác nhận decimal MB; baseline bounded file-read pattern)

#### Scenario: File đúng giới hạn byte

- **WHEN** file có đúng 1.000.000 raw byte, chưa xét các validation sau bước size
- **THEN** không bị từ chối bởi file byte limit

#### Scenario: File vượt một byte

- **WHEN** file có 1.000.001 raw byte
- **THEN** HTTP 413 với `code="FILE_INVALID"`, message `File vượt quá dung lượng tối đa 1 MB.` và `field="file"`

### Requirement: UTF-8 strict và BOM là plaintext content

Sau size check, bytes SHALL được decode bằng UTF-8 strict mà không dùng `utf-8-sig`, không universal-newline conversion, không trim và không Unicode normalization. Một leading UTF-8 BOM (`EF BB BF`) SHALL trở thành `U+FEFF` đầu plaintext và tham gia RSA như nội dung; không BOM nào được thêm nếu vắng. Invalid UTF-8 SHALL trả HTTP 415 `FILE_INVALID`, message `File phải sử dụng UTF-8.` và `field="file"`. Raw file 0 byte hoặc decoded text 0 code point SHALL trả HTTP 422 `EMPTY_INPUT`, message `Dữ liệu đầu vào đang rỗng.` và `field="file"`. (Truy vết: PDF RSA BE-04/BE-06; quyết định chủ sở hữu Q8, Q9, Q12)

#### Scenario: BOM được mã hóa như nội dung

- **WHEN** file bắt đầu bằng UTF-8 BOM rồi ký tự `A`
- **THEN** plaintext logic bắt đầu bằng `U+FEFF`
- **AND** response có `originalUtf8ByteLength=4`

#### Scenario: Không đổi CRLF

- **WHEN** file chứa byte sequence cho `A\r\nB\n`
- **THEN** chuỗi đi vào transform giữ nguyên `CR`, `LF`, `CRLF` theo đúng thứ tự

#### Scenario: Invalid UTF-8

- **WHEN** raw bytes không decode được bằng UTF-8 strict
- **THEN** HTTP 415 với `{"success":false,"code":"FILE_INVALID","message":"File phải sử dụng UTF-8.","field":"file"}`

### Requirement: Decoded file tối đa 10.000 code point

Sau decode strict và trước transform, handler SHALL đếm Unicode code point của toàn bộ plaintext, gồm `U+FEFF`, whitespace, newline và NUL. Đúng 10.000 SHALL được nhận; 10.001 SHALL trả HTTP 422 `INPUT_TOO_LARGE`, message `Dữ liệu văn bản không được vượt quá 10.000 ký tự Unicode.` và `field="file"`. (Truy vết: PDF RSA BE-06; quyết định chủ sở hữu Q8, Q9, Q12)

#### Scenario: BOM tham gia code-point limit

- **WHEN** file gồm BOM và 10.000 code point khác
- **THEN** decoded length là 10.001 và request bị từ chối

### Requirement: Thứ tự validation multipart xác định

Với request không bị guard 64 MiB từ chối, hệ thống SHALL dừng ở lỗi đầu theo thứ tự: parse multipart và exact/duplicate field set; sự hiện diện/type của `file`; sự hiện diện của `e`, `n`, `mode`; lexical/raw/value của `e`, rồi `n`; giá trị `mode`; filename extension; raw 1.000.000-byte cap; raw empty; UTF-8 decode; 10.000-code-point cap; block/domain constraints; `traceBlockIndex`. Lỗi đọc file ngoài dự kiến SHALL là HTTP 500 `FILE_READ_FAILED`; lỗi hệ thống khác là HTTP 500 `INTERNAL_ERROR`; cả hai không lộ traceback. (Truy vết: quyết định chủ sở hữu Q5, Q8, Q14, Q15; baseline deterministic validation/error convention)

#### Scenario: Sai e và sai extension đồng thời

- **WHEN** multipart có `e="x"` và filename `plain.bin`
- **THEN** response là HTTP 422 `NOT_INTEGER` với `field="e"`
- **AND** lỗi extension chưa được trả

#### Scenario: Lỗi đọc file

- **WHEN** upload hợp lệ về schema nhưng stream phát sinh lỗi đọc ngoài dự kiến
- **THEN** HTTP 500 với `code="FILE_READ_FAILED"`, message `Không thể đọc file.` và `field="file"`
