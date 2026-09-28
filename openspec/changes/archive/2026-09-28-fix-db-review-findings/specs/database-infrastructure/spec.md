## MODIFIED Requirements

### Requirement: docker-compose cho môi trường local

Repository SHALL có `docker-compose.yml` gồm service `db` (image `postgres:17`, volume có tên, healthcheck bằng `pg_isready`), service `migrate` chạy `alembic upgrade head` sau khi `db` healthy, và service `app` chạy sau khi `migrate` hoàn tất thành công. Thông tin đăng nhập SHALL lấy từ file `.env` (có `.env.example` mẫu, `.env` bị gitignore). Service `app` SHALL publish cổng container `8000` ra máy host ở `${APP_HOST_PORT:-8080}`; service `db` SHALL chỉ publish ở `127.0.0.1:${DB_HOST_PORT:-5433}` để chạy app bằng uv trên máy host. (Truy vết: quyết định chủ sở hữu 2026-09-28)

#### Scenario: Chạy toàn bộ stack
- **WHEN** chạy `docker compose up` với `.env` sao chép từ `.env.example`
- **THEN** `GET http://localhost:8080/api/health` trả HTTP 200 với DB ở trạng thái sẵn sàng
