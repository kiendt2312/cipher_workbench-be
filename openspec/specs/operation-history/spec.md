# operation-history Specification

## Purpose

Định nghĩa việc ghi lịch sử thao tác cipher dưới dạng metadata, ranh giới dữ liệu tuyệt đối không được lưu, và hành vi khi DB lỗi.

## Requirements

### Requirement: Bảng cipher_operations chỉ chứa metadata

Hệ thống SHALL lưu lịch sử trong bảng `cipher_operations` với đúng các cột: `id` (bigint identity, khóa chính), `created_at` (timestamptz, mặc định thời điểm hiện tại), `cipher` (text, CHECK thuộc `caesar`, `vigenere`, `playfair`, `affine`, `columnar`), `operation` (text nullable, CHECK thuộc `encrypt`, `decrypt`), `source` (text, CHECK thuộc `text`, `file`), `response_mode` (text nullable, CHECK thuộc `content`, `file`), `input_length` (integer nullable, ≥ 0), `output_length` (integer nullable, ≥ 0), `http_status` (smallint), `succeeded` (boolean), `duration_ms` (integer, ≥ 0). Bảng SHALL có index B-tree trên `(created_at, id)` và trên `(cipher, created_at)`; PostgreSQL quét ngược các index này cho truy vấn mới nhất trước. (Truy vết: quyết định chủ sở hữu 2026-09-28; ngoại lệ hạ tầng được chủ sở hữu phê duyệt)

#### Scenario: Schema sau migration
- **WHEN** chạy `alembic upgrade head`
- **THEN** bảng `cipher_operations` có đúng 11 cột trên, các CHECK constraint và hai index

### Requirement: Không bao giờ lưu nội dung hay dữ liệu định danh

Hệ thống MUST NOT lưu plaintext, ciphertext, key (kể cả `a`, `b`), tên file, nội dung file, header request, IP, user agent hay message lỗi. Độ dài SHALL là số Unicode code point cho nguồn text và số byte cho nguồn file. (Truy vết: quyết định chủ sở hữu 2026-09-28; ràng buộc stateless trong `openspec/config.yaml`)

#### Scenario: Không lưu nội dung
- **WHEN** client encrypt `"Attack at dawn!"` với key `"LEMON"` qua `POST /api/vigenere/encrypt`
- **THEN** bản ghi mới có `cipher = "vigenere"`, `operation = "encrypt"`, `source = "text"`, `input_length = 15`, `output_length = 15`, `http_status = 200`, `succeeded = true`
- **AND** không cột nào trong DB chứa `Attack`, `LEMON` hay `Lxfopv`

### Requirement: Ghi một bản ghi cho mỗi request cipher

Hệ thống SHALL ghi đúng một bản ghi cho mỗi request tới 15 route `POST /api/{caesar|vigenere|playfair|affine|columnar}/...`, kể cả request lỗi 413/415/422/500. `cipher` và `source` SHALL suy ra từ path. `operation` SHALL lấy từ path với route text, và từ trường `action` đã validate với route file; nếu request lỗi trước khi biết operation thì `operation` là NULL. `input_length`/`output_length` là NULL khi chưa xác định được. Request tới route khác (UI, static, OpenAPI, health, history) MUST NOT được ghi. (Truy vết: quyết định chủ sở hữu 2026-09-28)

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

### Requirement: Ghi lịch sử là best-effort

Việc ghi lịch sử MUST NOT thay đổi status, body hay header của response cipher. Khi DB lỗi, quá hạn 500 ms, hoặc `DATABASE_URL` không được đặt, hệ thống SHALL bỏ qua bản ghi đó, chỉ log một cảnh báo không chứa dữ liệu người dùng hay chuỗi kết nối. Việc ghi SHALL diễn ra sau khi response đã gửi xong. (Truy vết: quyết định chủ sở hữu 2026-09-28)

#### Scenario: DB tắt khi đang encrypt
- **WHEN** DB đã cấu hình nhưng không kết nối được và client gọi `POST /api/caesar/encrypt` hợp lệ
- **THEN** response giống hệt khi không có DB
- **AND** log có một cảnh báo không chứa input, key hay chuỗi kết nối
