# Spec Delta

## MODIFIED Requirements

### Requirement: Bảng cipher_operations chỉ chứa metadata

SQLite SHALL lưu lịch sử trong bảng `cipher_operations` với đúng 11 cột logic và không thêm cột payload: `id` (SQLite `INTEGER PRIMARY KEY AUTOINCREMENT`, dương, không tái sử dụng, tối đa `2^63-1`), `created_at` (số nguyên 64-bit biểu diễn epoch microsecond UTC), `cipher` (text, CHECK thuộc `caesar`, `vigenere`, `playfair`, `affine`, `columnar`, `hill`, `des`, `rsa`), `operation` (text nullable, CHECK thuộc `encrypt`, `decrypt`), `source` (text, CHECK thuộc `text`, `file`), `response_mode` (text nullable, CHECK thuộc `content`, `file`), `input_length` (integer nullable, ≥ 0), `output_length` (integer nullable, ≥ 0), `http_status` (integer), `succeeded` (integer CHECK thuộc `0`, `1`) và `duration_ms` (integer, ≥ 0). SQLite sequence SHALL bắt đầu sau cả max row ID và PostgreSQL identity high-water đã từng cấp. Bảng SHALL có index `(created_at, id)` và `(cipher, created_at, id)`. Adapter SHALL giữ UTC/precision/order của API và cursor. (Truy vết: quyết định chủ sở hữu 2026-10-07; main spec `operation-history`; active `add-rsa-cipher` Q16; ngoại lệ hạ tầng được chủ sở hữu phê duyệt)

#### Scenario: Schema SQLite sau migration

- **WHEN** chạy migration SQLite tới head trên file mới
- **THEN** bảng `cipher_operations` có đúng 11 cột logic, các CHECK constraint và hai index trên
- **AND** CHECK `cipher` cho phép đủ tám cipher gồm `rsa`

#### Scenario: Schema sau migration

- **WHEN** chạy migration SQLite tới head
- **THEN** bảng `cipher_operations` có đúng 11 cột logic, các CHECK constraint và index đã định nghĩa
- **AND** schema cho phép đủ `caesar`, `vigenere`, `playfair`, `affine`, `columnar`, `hill`, `des`, `rsa`

#### Scenario: Migration giữ dữ liệu cũ

- **WHEN** source PostgreSQL có row Caesar/Hill/DES/RSA và quy trình migration dữ liệu hoàn tất đối soát
- **THEN** mọi row cũ còn nguyên ID, timestamp và metadata trên SQLite

#### Scenario: Migration DES

- **WHEN** source có row Caesar, Hill và DES rồi được import vào SQLite
- **THEN** mọi row còn nguyên và CHECK đích vẫn cho phép `des` nhưng chặn cipher lạ

#### Scenario: ID không tái sử dụng

- **WHEN** row có ID lớn nhất bị xóa rồi một row mới được thêm
- **THEN** ID mới lớn hơn mọi ID đã từng được cấp và vẫn nằm trong `1..2^63-1`

#### Scenario: High-water lớn hơn max row còn lại

- **WHEN** PostgreSQL identity đã cấp ID cao hơn max ID còn tồn tại do retention/delete
- **THEN** row SQLite mới đầu tiên có ID lớn hơn identity high-water nguồn, không chỉ lớn hơn max row được import

#### Scenario: UTC và thứ tự không đổi

- **WHEN** hai row có timestamp UTC khác nhau hoặc cùng timestamp nhưng khác ID được đọc qua `GET /api/history`
- **THEN** API trả `createdAt` ISO 8601 UTC và sắp giảm dần theo timestamp rồi ID

#### Scenario: Cursor cũ vẫn dùng được sau cutover

- **WHEN** client dùng cursor hợp lệ đã được cấp từ dữ liệu PostgreSQL trước cutover và các row đó đã được migrate giữ nguyên ID/thời điểm
- **THEN** trang SQLite bắt đầu đúng sau tuple của cursor, không lặp hoặc bỏ row do đổi precision/timezone

### Requirement: Ghi lịch sử là best-effort

Việc ghi lịch sử MUST NOT thay đổi status, body hay header của response cipher. Khi SQLite lỗi, read-only, đầy đĩa, bị khóa, quá hạn 500 ms, `DATABASE_URL` không được đặt, hoặc schema chưa sẵn sàng, hệ thống SHALL bỏ qua row đó và chỉ log một cảnh báo không chứa dữ liệu người dùng, chuỗi kết nối hay đường dẫn file. Việc ghi SHALL diễn ra sau khi response đã gửi xong. Semantics này áp dụng cho toàn bộ route đang có hiệu lực, gồm hai RSA transform; RSA keygen tiếp tục không ghi history và không lỗi storage nào được làm thay đổi safe best-effort transform response. (Truy vết: quyết định chủ sở hữu 2026-10-07; quyết định chủ sở hữu 2026-09-28; active `add-rsa-cipher` Q16 ngày 2026-10-06)

#### Scenario: DB tắt khi đang encrypt

- **WHEN** SQLite đã cấu hình nhưng không mở/ghi được và client gọi `POST /api/caesar/encrypt` hợp lệ
- **THEN** response giống hệt khi không có DB
- **AND** log có một cảnh báo không chứa input, key, chuỗi kết nối hay đường dẫn

#### Scenario: SQLite bị khóa khi đang encrypt

- **WHEN** SQLite được cấu hình nhưng lock cạnh tranh kéo dài quá giới hạn và client gọi `POST /api/caesar/encrypt` hợp lệ
- **THEN** response giống hệt khi không có DB
- **AND** log chỉ có cảnh báo generic không chứa input, key, URL hay đường dẫn

#### Scenario: Hết dung lượng khi ghi RSA

- **WHEN** hai RSA transform tạo response nhưng SQLite không thể commit vì hết dung lượng
- **THEN** response transform giữ nguyên status, body và header
- **AND** row history có thể bị bỏ lỡ, không có content/key/trace/error message được persist hoặc log

#### Scenario: Keygen vẫn bị loại

- **WHEN** client gọi hai RSA keygen route trong khi SQLite hoạt động
- **THEN** không có row history mới
