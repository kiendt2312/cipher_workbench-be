## 1. Cấu hình

- [x] 1.1 Thêm `history_api_enabled()` và `history_retention_days()` vào `app/config.py` với unit test cho mọi giá trị hợp lệ/không hợp lệ. **Xong khi:** test phủ `true/1/yes/on`, hoa thường, khoảng trắng, giá trị lạ, mặc định; retention 1, 30, 3650, 0, 3651, `abc`, rỗng.
- [x] 1.2 Cập nhật `.env.example` và `docker-compose.yml` để truyền `HISTORY_API_ENABLED`, `HISTORY_RETENTION_DAYS`. **Xong khi:** `docker compose config` hiện đủ hai biến trong service `app`.

## 2. Truy cập lịch sử

- [x] 2.1 Thêm message và `HistoryDisabledError` (404). **Xong khi:** test error contract xác nhận envelope và message.
- [x] 2.2 `GET /api/history` trả 404 khi cờ tắt, trước mọi validation. **Xong khi:** test cờ tắt với query sai vẫn ra 404, test cờ bật giữ nguyên hành vi cũ.
- [x] 2.3 `GET /api/health` thêm `result.history`. **Xong khi:** test cả hai giá trị và status không đổi theo cờ.

## 3. Retention

- [x] 3.1 Tạo `app/history/retention.py` với `purge_expired(database, days)` trả số dòng xóa. **Xong khi:** test `db` giữ bản ghi 29 ngày, xóa bản ghi 31 ngày.
- [x] 3.2 Thêm vòng purge định kỳ vào lifespan (chạy ngay, lặp 6 giờ, cancel khi shutdown, lỗi chỉ log). **Xong khi:** test với purge giả xác nhận chạy ngay khi khởi động, lỗi không làm app dừng, không chạy khi không có DB.
- [x] 3.3 Thêm `python -m app.history.retention`. **Xong khi:** test chạy lệnh thiếu `DATABASE_URL` thoát mã khác 0; test `db` in số dòng đã xóa.

## 4. Tài liệu

- [x] 4.1 README: hai biến mới, mặc định tắt khi deploy, retention, lệnh purge tay. **Xong khi:** các lệnh trong README chạy đúng.
- [x] 4.2 Tài liệu FE: health có `history`, 404 khi tắt, lịch sử cá nhân trên trình duyệt (schema, giới hạn 50, nút xóa, tắt lưu, try/catch). **Xong khi:** ví dụ khớp response thật.
- [x] 4.3 Ghi kết quả hai câu hỏi mở vào `add-postgres-persistence/design.md`. **Xong khi:** mục Open Questions trỏ tới change này.

## 5. Quality gates

- [x] 5.1 `ruff check`, `ruff format --check`, `pytest` có `TEST_DATABASE_URL`. **Xong khi:** exit 0, coverage ≥ 90%.
- [x] 5.2 Chạy `docker compose up -d --build`, kiểm tra health, history khi bật/tắt cờ và log purge. **Xong khi:** hành vi đúng spec.
