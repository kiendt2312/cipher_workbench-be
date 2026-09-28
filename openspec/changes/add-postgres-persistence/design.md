## Context

Backend là FastAPI 1 process, 15 route cipher, stateless hoàn toàn, chạy bằng uvicorn trong Docker multi-stage. Các route đều là `async def`. Middleware hiện có (`RequestSizeGuard`, `MultipartCompletionGuard`) là ASGI thuần. Test dùng `TestClient`, coverage tối thiểu 90%. Chủ sở hữu đã chọn PostgreSQL với phạm vi "hạ tầng + lịch sử thao tác metadata-only" (2026-09-28).

## Goals / Non-Goals

**Goals:**

- Thêm PostgreSQL mà không đổi contract, behavior hay latency đáng kể của 15 route cipher.
- App vẫn chạy và toàn bộ test hiện tại vẫn xanh khi không có DB.
- Lịch sử chỉ chứa metadata; dữ liệu nhạy cảm không bao giờ chạm DB.
- Có môi trường local một lệnh (`docker compose up`).

**Non-Goals:**

- Auth, user, lịch sử theo user, retention, thống kê, UI lịch sử, deploy cloud/CI, pooler.

## Decisions

### 1. SQLAlchemy 2.x async + asyncpg

Route đều là `async def`, nên dùng `create_async_engine` với driver `asyncpg` để không chặn event loop. Dùng SQLAlchemy Core/ORM 2.x style (`Mapped`, `mapped_column`) cho một model duy nhất `CipherOperation`.

Phương án không chọn: driver sync `psycopg` chạy trong threadpool (thêm độ phức tạp, không lợi gì), ORM khác như SQLModel/Tortoise (thêm lớp trừu tượng, ít phổ biến hơn với Alembic).

### 2. DB là tùy chọn, bật bằng `DATABASE_URL`

`app/config.py` đọc `DATABASE_URL` từ môi trường. Không có biến này thì lifespan không tạo engine, middleware ghi lịch sử trở thành no-op, health trả `disabled`, history trả 503. Nhờ vậy suite test hiện tại, chạy local bằng `uvicorn` và image Docker cũ vẫn hoạt động y như trước.

### 3. Engine trong lifespan, lưu trên `app.state`

Lifespan tạo engine và `async_sessionmaker`, gắn vào `app.state.db`, dispose khi shutdown. Không kết nối thử lúc startup (engine lazy), nên app vẫn khởi động khi DB chưa lên. Pool mặc định: `pool_size=5`, `max_overflow=5`, `pool_pre_ping=True`.

### 4. Alembic async, migration tách khỏi app

Thư mục `alembic/` với `env.py` dùng async engine, đọc `DATABASE_URL`. Migration đầu `0001_create_cipher_operations`. App không gọi `create_all` hay `upgrade` lúc startup, tránh race khi chạy nhiều replica. docker-compose có service `migrate` chạy một lần trước `app`.

### 5. Ghi lịch sử bằng ASGI middleware + `request.state`

Một middleware ASGI thuần `OperationHistoryRecorder` bọc app:

- Chỉ hoạt động khi path khớp 15 route cipher (so khớp tập path cố định, không regex rộng).
- Suy `cipher`, `source` từ path; bắt `http_status` từ message `http.response.start`; đo `duration_ms`.
- Route handler và validator gán `request.state.history_operation`, `history_response_mode`, `history_input_length`, `history_output_length` khi đã biết. Route file chỉ gán `operation` sau khi `action` đã validate.
- Sau khi message body cuối được gửi, middleware ghi bản ghi với `asyncio.wait_for(…, 0.5)`, bắt mọi exception và chỉ log cảnh báo cố định.

Vì ghi sau khi response đã gửi xong, client không phải chờ DB. Đặt middleware ở ngoài cùng để bắt cả lỗi 413 từ `RequestSizeGuard`.

Phương án không chọn: FastAPI `BackgroundTasks` (không chạy khi handler raise lỗi, nên mất bản ghi lỗi); ghi trong từng handler (lặp code ở 15 route, dễ sót nhánh lỗi); decorator trên route (không bắt được lỗi từ middleware guard).

### 6. Module truy vấn nhỏ, không repository pattern

`app/history/store.py` có đúng hai hàm: `record_operation(session_factory, entry)` và `list_operations(session_factory, limit, cursor, cipher, operation)`. Không tạo interface hay repository chung, theo quy ước trong `openspec/config.yaml`.

### 7. Cursor phân trang là base64url của `(created_at, id)`

Keyset pagination `WHERE (created_at, id) < (:ts, :id) ORDER BY created_at DESC, id DESC LIMIT :limit + 1`. Lấy dư 1 dòng để biết còn trang sau. Cursor là base64url của JSON `{"t": iso, "i": id}`; giải mã lỗi thì trả 422. Không dùng offset vì chậm dần và lặp item khi có bản ghi mới chen vào.

### 8. Lỗi mới dùng hệ exception hiện có

Thêm message vào `app/errors/messages.py` và các subclass của `CaesarError` (`InvalidHistoryLimitError`, `InvalidHistoryCursorError`, `InvalidHistoryFilterError`, `HistoryUnavailableError`). Handler hiện có sẽ render envelope `{"success": false, "message": …}`, không thêm handler mới.

### 9. Test hai tầng

- Mặc định (không có `TEST_DATABASE_URL`): test unit cho cursor, suy metadata từ path, middleware với store giả, các nhánh `disabled`. Toàn bộ test cũ chạy như hiện tại.
- Test DB (đánh dấu `@pytest.mark.db`): chạy khi có `TEST_DATABASE_URL`, dựng schema bằng `alembic upgrade head`, truncate giữa các test, kiểm tra schema, ghi thật, phân trang, lọc, health `ok`/`unavailable`.
- Gate coverage 90% áp dụng cho lần chạy đầy đủ có Postgres (`docker compose up -d db` rồi `uv run pytest`).

## Risks / Trade-offs

- **[Rò rỉ dữ liệu nhạy cảm vào DB]** → Model không có cột nào chứa được nội dung; test quét mọi cột sau khi encrypt chuỗi đánh dấu; middleware không đọc body.
- **[DB chậm làm chậm cipher]** → Ghi sau khi response gửi xong, timeout 500 ms, lỗi bị nuốt.
- **[Mất bản ghi khi DB lỗi]** → Chấp nhận, vì lịch sử là best-effort. Không thêm hàng đợi hay retry ở change này.
- **[Bảng tăng không giới hạn]** → Chấp nhận ở giai đoạn này, retention là change sau. Index keyset giữ truy vấn đọc nhanh.
- **[`GET /api/history` không có auth]** → Ai truy cập được app đều xem được lịch sử chung. Chấp nhận vì dữ liệu chỉ là metadata; auth là change sau.
- **[Thêm dependency]** → 3 package phổ biến, khóa version trong `uv.lock`.

## Migration Plan

Lộ trình triển khai theo giai đoạn, mỗi giai đoạn merge độc lập được:

1. **Giai đoạn 1 — Hạ tầng** (task nhóm 1–3): dependency, config, lifespan, Alembic, docker-compose, health. Sau bước này app vẫn chạy như cũ, chỉ có thêm DB và `/api/health`.
2. **Giai đoạn 2a — Ghi lịch sử** (task nhóm 4–5): migration bảng, middleware, gắn metadata ở route.
3. **Giai đoạn 2b — Đọc lịch sử** (task nhóm 6): `GET /api/history`.
4. **Hoàn thiện** (task nhóm 7–9): test DB, tài liệu, Docker, quality gates.

Rollback: bỏ `DATABASE_URL` là tắt hoàn toàn DB mà không cần deploy lại code. Muốn xóa dữ liệu thì chạy `alembic downgrade base`.

## Open Questions

- Có cần giới hạn truy cập `GET /api/history` (ví dụ chỉ bật ở môi trường dev) trước khi có auth không? Mặc định hiện tại: luôn bật khi có DB.
- Thời gian giữ dữ liệu mong muốn cho change retention sau (ví dụ 30 hay 90 ngày)?
