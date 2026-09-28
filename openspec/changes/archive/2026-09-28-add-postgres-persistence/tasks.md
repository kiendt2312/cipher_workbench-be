## 1. Dependency và cấu hình (Giai đoạn 1)

- [x] 1.1 Thêm `sqlalchemy[asyncio]`, `asyncpg`, `alembic` vào `pyproject.toml`, cập nhật `uv.lock`. **Xong khi:** `uv sync --frozen` thành công và `uv run pytest` hiện tại vẫn xanh.
- [x] 1.2 Cho `app/config.py` đọc `DATABASE_URL` (rỗng = tắt) và thêm unit test cho cả hai trường hợp. **Xong khi:** test xác nhận không đặt biến thì giá trị là `None`, và giá trị không bao giờ bị in ra repr/log.
- [x] 1.3 Thêm `.env.example` (POSTGRES_USER/PASSWORD/DB, DATABASE_URL) và đưa `.env` vào `.gitignore`. **Xong khi:** `git status` không hiện `.env` sau khi sao chép từ mẫu.

## 2. Kết nối DB và lifespan (Giai đoạn 1)

- [x] 2.1 Tạo `app/db/engine.py`: tạo async engine và `async_sessionmaker` từ URL, cấu hình pool theo design. **Xong khi:** unit test tạo được engine với URL giả mà không mở kết nối.
- [x] 2.2 Thêm lifespan vào `app/main.py`: có URL thì tạo engine gắn `app.state.db`, shutdown thì dispose; không có URL thì `app.state.db = None`. **Xong khi:** toàn bộ test cũ xanh khi không có DB và test mới xác nhận dispose được gọi.
- [x] 2.3 Thêm `GET /api/health` (`app/api/routes_health.py`) với trạng thái `ok`/`unavailable`/`disabled`, timeout 1 giây, không lộ chuỗi kết nối. **Xong khi:** test cho `disabled` chạy không cần DB; test `ok`/`unavailable` đánh dấu `db`.

## 3. Alembic và docker-compose (Giai đoạn 1)

- [x] 3.1 Khởi tạo `alembic/` với `env.py` async đọc `DATABASE_URL`, `alembic.ini` không chứa thông tin đăng nhập. **Xong khi:** `alembic upgrade head` chạy được trên DB trống (chưa có migration).
- [x] 3.2 Viết `docker-compose.yml` với `db` (postgres:17, volume, healthcheck), `migrate`, `app` theo spec. **Xong khi:** `docker compose up` rồi `curl localhost:8000/api/health` trả `database: "ok"`.
- [x] 3.3 Cập nhật `Dockerfile` để copy `alembic/` và `alembic.ini`. **Xong khi:** service `migrate` chạy được bằng chính image của app.

## 4. Schema lịch sử (Giai đoạn 2a)

- [x] 4.1 Tạo model `CipherOperation` trong `app/db/models.py` với 11 cột, CHECK constraint và 2 index theo spec. **Xong khi:** model import được và không có cột nào kiểu tự do đủ chứa nội dung người dùng ngoài các enum text.
- [x] 4.2 Viết migration `0001_create_cipher_operations` (upgrade + downgrade). **Xong khi:** test `db` chạy upgrade → kiểm tra cột/constraint/index → downgrade base sạch.

## 5. Ghi lịch sử (Giai đoạn 2a)

- [x] 5.1 Tạo `app/history/store.py` với `record_operation`. **Xong khi:** test `db` ghi một bản ghi và đọc lại đủ trường.
- [x] 5.2 Tạo bảng ánh xạ path → (cipher, source) cho đúng 15 route và unit test đủ 15 path cùng các path không phải cipher. **Xong khi:** test chứng minh `/`, `/static/*`, `/docs`, `/api/health`, `/api/history` không khớp.
- [x] 5.3 Tạo middleware ASGI `OperationHistoryRecorder`: bắt status, đo thời gian, đọc `request.state`, ghi sau khi response gửi xong, timeout 500 ms, nuốt lỗi và log cảnh báo cố định. **Xong khi:** unit test với store giả xác nhận response không đổi khi store raise lỗi hoặc treo quá 500 ms.
- [x] 5.4 Gắn `history_operation`, `history_response_mode`, `history_input_length`, `history_output_length` vào `request.state` ở các route text và file của 5 cipher. **Xong khi:** test với store giả xác nhận metadata đúng cho mỗi cipher ở cả text và file, và `operation` là NULL khi file lỗi trước lúc validate `action`.
- [x] 5.5 Đăng ký middleware ở ngoài cùng trong `app/main.py`. **Xong khi:** request 413 từ `RequestSizeGuard` cũng sinh bản ghi với `http_status = 413`.

## 6. API đọc lịch sử (Giai đoạn 2b)

- [x] 6.1 Thêm message tiếng Việt và 4 exception mới theo spec `history-api`. **Xong khi:** test error contract xác nhận envelope hai trường và đúng message.
- [x] 6.2 Cài encode/decode cursor base64url `(created_at, id)`. **Xong khi:** unit test round-trip và các cursor hỏng (sai base64, sai JSON, thiếu trường) đều ra `InvalidHistoryCursorError`.
- [x] 6.3 Cài `list_operations` bằng keyset pagination và bộ lọc. **Xong khi:** test `db` với 25 bản ghi cho trang 20 + 5, không lặp, lọc đúng.
- [x] 6.4 Thêm `GET /api/history` (`app/api/routes_history.py`) với validation query, 503 khi không có DB, OpenAPI đầy đủ. **Xong khi:** test không cần DB phủ mọi lỗi 422/503; test `db` phủ đường thành công.

## 7. Test tích hợp và bảo mật dữ liệu

- [x] 7.1 Thêm fixture `db` trong `tests/conftest.py`: bỏ qua khi không có `TEST_DATABASE_URL`, chạy migration một lần, truncate giữa các test. **Xong khi:** `uv run pytest` không có DB vẫn xanh và bỏ qua đúng test `db`.
- [x] 7.2 Viết test quét dữ liệu: encrypt/decrypt chuỗi đánh dấu qua cả 15 route rồi quét mọi cột của mọi bản ghi. **Xong khi:** không cột nào chứa chuỗi đánh dấu, key hay tên file.
- [x] 7.3 Chạy lại toàn bộ test cipher hiện có khi có DB và khi DB tắt. **Xong khi:** mọi response cipher giống hệt baseline trong cả hai chế độ.

## 8. Tài liệu và Docker

- [x] 8.1 Cập nhật README: cách chạy bằng docker-compose, biến môi trường, migration, bỏ "database/history" khỏi ngoài phạm vi, ghi chú dữ liệu nào được lưu. **Xong khi:** làm theo README từ máy sạch chạy được stack và gọi được `/api/history`.
- [x] 8.2 Cập nhật `repo_docs/frontend-integration.md`: contract `GET /api/health` và `GET /api/history` (query, response, lỗi, ví dụ fetch/curl). **Xong khi:** mọi ví dụ trong tài liệu khớp response thật.
- [x] 8.3 Cập nhật `openspec/config.yaml` phần context cho tech stack mới (PostgreSQL, SQLAlchemy, Alembic). **Xong khi:** mô tả "stateless" được chỉnh thành "không lưu nội dung người dùng; chỉ lưu metadata thao tác".

## 9. Quality gates

- [x] 9.1 Chạy `uv run ruff check .`, `uv run ruff format --check .` và `uv run pytest` có `TEST_DATABASE_URL`. **Xong khi:** mọi lệnh exit 0 và coverage ≥ 90%.
- [x] 9.2 Chạy `docker compose up --build` từ đầu (xóa volume) và thử encrypt, health, history. **Xong khi:** cả ba hoạt động và `docker compose down -v` dọn sạch.
