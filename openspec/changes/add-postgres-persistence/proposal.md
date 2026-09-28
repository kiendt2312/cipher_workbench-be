## Why

Backend hiện hoàn toàn stateless: không có database, không ghi lại bất kỳ thao tác nào. Chủ sở hữu muốn có nền tảng lưu trữ bền vững để theo dõi mức độ sử dụng từng cipher và làm nền cho các tính năng sau (user, thống kê). Change này thêm PostgreSQL theo lộ trình hai giai đoạn: dựng hạ tầng DB trước, sau đó ghi lịch sử thao tác **chỉ gồm metadata**, không bao giờ lưu plaintext, ciphertext, key hay nội dung file.

## What Changes

**Giai đoạn 1 — Hạ tầng PostgreSQL**

- Thêm dependency `sqlalchemy[asyncio]` 2.x, `asyncpg` và `alembic`.
- Thêm cấu hình `DATABASE_URL` qua biến môi trường. Khi không đặt biến này, app chạy đúng như hiện tại (không kết nối DB, lịch sử bị tắt).
- Thêm async engine/session quản lý qua FastAPI lifespan: tạo khi startup, dispose khi shutdown.
- Thêm Alembic với async `env.py` và migration đầu tiên tạo bảng `cipher_operations`.
- Thêm `docker-compose.yml` gồm service `db` (PostgreSQL 17, volume bền vững, healthcheck), service `migrate` chạy `alembic upgrade head` một lần, và service `app` chờ DB healthy.
- Thêm `GET /api/health` trả trạng thái app và DB.

**Giai đoạn 2 — Lịch sử thao tác (metadata-only)**

- Thêm ASGI middleware ghi một bản ghi cho mỗi request tới 15 route cipher hiện có: cipher, operation, nguồn (text/file), response mode, độ dài input/output, HTTP status, thành công hay lỗi, thời gian xử lý.
- Việc ghi là best-effort: DB lỗi hoặc chậm không được làm đổi status, body, header hay latency đáng kể của response cipher.
- Thêm `GET /api/history` trả danh sách phân trang theo cursor, mới nhất trước, lọc tùy chọn theo cipher/operation.
- Bổ sung test (unit, integration có Postgres thật), README, tài liệu FE và Docker.

## Capabilities

### New Capabilities

- `database-infrastructure`: Cấu hình kết nối, vòng đời engine, migration Alembic, docker-compose và endpoint health.
- `operation-history`: Ghi metadata thao tác cipher, ranh giới dữ liệu cấm lưu, hành vi best-effort khi DB lỗi.
- `history-api`: Endpoint đọc lịch sử, phân trang cursor, bộ lọc, envelope và lỗi tiếng Việt.

### Modified Capabilities

Không sửa requirement của change cũ. Ràng buộc "Ứng dụng stateless, không lưu input/file/kết quả sau request" vẫn giữ nguyên cho nội dung người dùng; change này chỉ lưu metadata và được gắn nhãn là ngoại lệ hạ tầng được chủ sở hữu phê duyệt.

## Impact

- Code mới: `app/db/` (engine, session, model), `app/history/` (middleware ghi, truy vấn đọc), `app/api/routes_history.py`, `app/api/routes_health.py`, thư mục `alembic/` và `alembic.ini`.
- Code sửa: `app/main.py` (lifespan, middleware, router), `app/config.py` (đọc biến môi trường), `app/errors/messages.py` (message mới), các route cipher chỉ để gắn operation/độ dài vào `request.state`.
- Hạ tầng: `pyproject.toml`/`uv.lock`, `Dockerfile` (copy `alembic/`), `docker-compose.yml` mới, `.env.example`.
- Contract của 15 route cipher không đổi. OpenAPI thêm 2 route GET.
- Test: suite hiện tại phải chạy xanh khi không có `DATABASE_URL`; test DB chạy với Postgres thật qua `TEST_DATABASE_URL`; coverage vẫn tối thiểu 90% khi chạy đầy đủ.

## Ngoài phạm vi

- Không lưu plaintext, ciphertext, key, tên file, nội dung file, IP, user agent hay bất kỳ dữ liệu định danh người dùng nào.
- Không có authentication, tài khoản người dùng hay lịch sử theo từng user; `GET /api/history` là lịch sử chung của instance.
- Không có UI xem lịch sử trong static UI hiện tại; FE tích hợp theo tài liệu.
- Không có retention/tự động xóa, thống kê tổng hợp, export, backup, replica, pooler (PgBouncer) hay deploy cloud/CI.
- Không đổi contract của 15 route cipher hiện có.

## Giải quyết khác biệt giữa nguồn

- Không có DOCX nào quy định database. Nguồn có thẩm quyền là quyết định chủ sở hữu ngày 2026-09-28: chọn PostgreSQL, phạm vi "hạ tầng + lịch sử thao tác metadata-only".
- `openspec/config.yaml` ghi "Ứng dụng stateless, không lưu input/file/kết quả sau request" và README/OpenSpec cũ xếp "database, persistence, history" vào ngoài phạm vi. Change này không lưu input/file/kết quả, chỉ lưu metadata, và được gắn nhãn "ngoại lệ hạ tầng được chủ sở hữu phê duyệt". Các ghi chú "ngoài phạm vi" trong README và tài liệu FE sẽ được cập nhật sau implementation.
- `openspec/config.yaml` cấm repository pattern ở Tuần 1. Change này chỉ thêm một module truy vấn nhỏ trong `app/history/`, không tạo abstract repository hay interface chung.
