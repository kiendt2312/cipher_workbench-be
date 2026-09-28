## Purpose

Định nghĩa cách backend kết nối PostgreSQL, quản lý vòng đời kết nối, áp dụng migration và báo trạng thái DB, trong khi vẫn chạy được như hiện tại khi không cấu hình DB.

## ADDED Requirements

### Requirement: Cấu hình DB qua biến môi trường và tùy chọn

Hệ thống SHALL đọc chuỗi kết nối từ biến môi trường `DATABASE_URL` theo dạng `postgresql+asyncpg://…`. Khi biến này không được đặt hoặc rỗng, hệ thống SHALL khởi động bình thường, không mở kết nối DB, và mọi route cipher SHALL hoạt động đúng như trước change. Chuỗi kết nối, mật khẩu và host MUST NOT xuất hiện trong log, response lỗi hay OpenAPI. (Truy vết: quyết định chủ sở hữu 2026-09-28; ngoại lệ hạ tầng được chủ sở hữu phê duyệt)

#### Scenario: Không có DATABASE_URL
- **WHEN** app khởi động mà không đặt `DATABASE_URL`
- **THEN** app khởi động thành công
- **AND** `POST /api/caesar/encrypt` với input hợp lệ trả kết quả giống hệt trước change

#### Scenario: Chuỗi kết nối không lộ ra ngoài
- **WHEN** DB không kết nối được và client gọi `GET /api/health`
- **THEN** body response không chứa host, user, mật khẩu hay chuỗi `DATABASE_URL`

### Requirement: Vòng đời engine qua lifespan

Khi `DATABASE_URL` được đặt, hệ thống SHALL tạo đúng một async engine SQLAlchemy trong lifespan startup và SHALL dispose engine khi shutdown. App SHALL khởi động được kể cả khi DB tạm thời chưa sẵn sàng; lỗi kết nối chỉ được phản ánh qua health và history. (Truy vết: quyết định chủ sở hữu 2026-09-28)

#### Scenario: DB chưa sẵn sàng lúc khởi động
- **WHEN** `DATABASE_URL` trỏ tới DB chưa chạy và app khởi động
- **THEN** app vẫn khởi động và phục vụ route cipher
- **AND** `GET /api/health` báo DB không sẵn sàng

### Requirement: Migration bằng Alembic, tách khỏi startup

Schema DB SHALL được quản lý hoàn toàn bằng Alembic. App MUST NOT tự tạo hay sửa bảng khi khởi động. Migration SHALL chạy bằng lệnh riêng `alembic upgrade head` (service `migrate` trong docker-compose hoặc chạy tay), và `alembic downgrade base` SHALL xóa sạch mọi đối tượng do change này tạo. (Truy vết: quyết định chủ sở hữu 2026-09-28)

#### Scenario: Upgrade rồi downgrade
- **WHEN** chạy `alembic upgrade head` rồi `alembic downgrade base` trên DB trống
- **THEN** cả hai lệnh thành công
- **AND** sau downgrade DB không còn bảng `cipher_operations`

### Requirement: docker-compose cho môi trường local

Repository SHALL có `docker-compose.yml` gồm service `db` (image `postgres:17`, volume có tên, healthcheck bằng `pg_isready`), service `migrate` chạy `alembic upgrade head` sau khi `db` healthy, và service `app` chạy sau khi `migrate` hoàn tất thành công. Thông tin đăng nhập SHALL lấy từ file `.env` (có `.env.example` mẫu, `.env` bị gitignore). (Truy vết: quyết định chủ sở hữu 2026-09-28)

#### Scenario: Chạy toàn bộ stack
- **WHEN** chạy `docker compose up` với `.env` sao chép từ `.env.example`
- **THEN** `GET http://localhost:8000/api/health` trả HTTP 200 với DB ở trạng thái sẵn sàng

### Requirement: Endpoint health

Hệ thống SHALL cung cấp `GET /api/health`. Response SHALL là JSON `{"success": true, "result": {"app": "ok", "database": <trạng thái>}}`, trong đó trạng thái là `"ok"` khi `SELECT 1` thành công trong tối đa 1 giây, `"unavailable"` khi thất bại hoặc quá hạn, và `"disabled"` khi không có `DATABASE_URL`. Status SHALL là 200 khi DB `ok` hoặc `disabled`, và 503 khi DB `unavailable`. (Truy vết: quyết định chủ sở hữu 2026-09-28)

#### Scenario: DB sẵn sàng
- **WHEN** DB chạy bình thường và client gọi `GET /api/health`
- **THEN** hệ thống trả HTTP 200 với `result.database` bằng `"ok"`

#### Scenario: DB tắt
- **WHEN** DB đã được cấu hình nhưng không kết nối được
- **THEN** hệ thống trả HTTP 503 với `result.database` bằng `"unavailable"`

#### Scenario: DB không được cấu hình
- **WHEN** không đặt `DATABASE_URL`
- **THEN** hệ thống trả HTTP 200 với `result.database` bằng `"disabled"`
