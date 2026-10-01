# operation-history Delta

## MODIFIED Requirements

### Requirement: Bảng cipher_operations chỉ chứa metadata

Hệ thống SHALL lưu lịch sử trong bảng `cipher_operations` với đúng các cột: `id` (bigint identity, khóa chính), `created_at` (timestamptz, mặc định thời điểm hiện tại), `cipher` (text, CHECK thuộc `caesar`, `vigenere`, `playfair`, `affine`, `columnar`, `hill`, `des`), `operation` (text nullable, CHECK thuộc `encrypt`, `decrypt`), `source` (text, CHECK thuộc `text`, `file`), `response_mode` (text nullable, CHECK thuộc `content`, `file`), `input_length` (integer nullable, ≥ 0), `output_length` (integer nullable, ≥ 0), `http_status` (smallint), `succeeded` (boolean), `duration_ms` (integer, ≥ 0). Bảng SHALL có index B-tree trên `(created_at, id)` và trên `(cipher, created_at)`; PostgreSQL quét ngược các index này cho truy vấn mới nhất trước. Migration mới SHALL chỉ nới CHECK của `cipher`, giữ nguyên các bản ghi và cấu trúc khác; không sửa migration `0001`, `0002` đã áp dụng. (Truy vết: main spec `operation-history`, `alembic/versions/0001_create_cipher_operations.py`; quyết định chủ sở hữu Q3 ngày 2026-09-29; quyết định chủ sở hữu Q12 ngày 2026-10-01)

#### Scenario: Schema sau migration
- **WHEN** chạy `alembic upgrade head`
- **THEN** bảng `cipher_operations` có đúng 11 cột trên, các CHECK constraint và hai index
- **AND** CHECK `cipher` cho phép `hill` và `des` bên cạnh năm giá trị cũ

#### Scenario: Migration giữ dữ liệu cũ
- **WHEN** bảng đang có bản ghi Caesar và chạy migration Hill
- **THEN** bản ghi cũ còn nguyên và có thể thêm bản ghi `cipher="hill"`

#### Scenario: Migration DES
- **WHEN** bảng đang có bản ghi Caesar và Hill rồi chạy migration DES
- **THEN** bản ghi cũ còn nguyên, có thể thêm bản ghi `cipher="des"` và CHECK vẫn chặn tên cipher lạ

### Requirement: Ghi một bản ghi cho mỗi request cipher

Hệ thống SHALL ghi đúng một bản ghi cho mỗi request tới 20 route biến đổi `POST /api/{caesar|vigenere|playfair|affine|columnar|des}/{encrypt|decrypt|file}` và `POST /api/hill/{encrypt|decrypt}`, kể cả request lỗi 413/415/422/500. `cipher` và `source` SHALL suy ra từ path. `operation` SHALL lấy từ path với route text, và từ trường `action` đã validate với route file; nếu request lỗi trước khi biết operation thì `operation` là NULL. `input_length`/`output_length` là NULL khi chưa xác định được. Với Hill, `source="text"`, `response_mode=NULL`, độ dài là số Unicode code point của text nhận vào và result trả về, kể cả ký tự đệm; không ghi key, blocks, warnings hoặc nội dung. Với DES, route JSON có `source="text"`, `response_mode=NULL`, độ dài là số Unicode code point của `text` nhận vào và `result` trả về; route file theo quy tắc file hiện hành; không ghi khóa, IV, `mode`, `inputFormat`, `outputFormat`, warnings hoặc nội dung. Request tới route khác, gồm `/api/hill/key/analyze`, `/api/hill/key/random`, `/api/des/trace`, OpenAPI, health và history, MUST NOT được ghi. (Truy vết: main spec `operation-history`; quyết định chủ sở hữu Q3, Q9, Q16 ngày 2026-09-29; quyết định chủ sở hữu Q12 ngày 2026-10-01)

#### Scenario: Request lỗi vẫn được ghi
- **WHEN** client gửi `POST /api/vigenere/encrypt` với key `"LE MON"`
- **THEN** response vẫn là HTTP 422 với message hiện hành
- **AND** bản ghi mới có `http_status = 422`, `succeeded = false`, `output_length` là NULL

#### Scenario: File lỗi trước khi validate action
- **WHEN** client gửi `POST /api/caesar/file` có `action=encrypt` nhưng thiếu `key`
- **THEN** response vẫn là HTTP 422 với message hiện hành
- **AND** bản ghi mới có `source = "file"`, `http_status = 422` và `operation` là NULL

#### Scenario: Route không phải cipher
- **WHEN** client gọi `GET /api/health` hoặc `GET /`
- **THEN** không có bản ghi mới

#### Scenario: Hill chỉ ghi hai route biến đổi
- **WHEN** client gọi Hill encrypt thành công rồi gọi key/analyze và key/random
- **THEN** chỉ có một bản ghi mới với `cipher="hill"`, `source="text"`, `operation="encrypt"`
- **AND** history không lưu text, khóa, result, blocks hoặc warnings

#### Scenario: DES ghi route biến đổi, không ghi trace
- **WHEN** client gọi DES encrypt `Hello World` thành công rồi gọi `/api/des/trace`
- **THEN** chỉ có một bản ghi mới với `cipher="des"`, `source="text"`, `operation="encrypt"`, `input_length=11`, `output_length=32`
- **AND** history không lưu text, khóa, IV, result hoặc warnings
