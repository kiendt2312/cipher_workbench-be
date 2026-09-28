## Context

Change `add-postgres-persistence` đã thêm ghi lịch sử metadata và `GET /api/history`, còn để mở hai câu hỏi: giới hạn truy cập endpoint đọc và thời gian giữ dữ liệu. Project sẽ không có authentication. Chủ sở hữu chốt (2026-09-28): khóa endpoint đọc bằng cờ cấu hình, giữ dữ liệu 30 ngày, lịch sử cá nhân nằm trên trình duyệt.

## Goals / Non-Goals

**Goals:** mặc định an toàn khi deploy (không ai đọc được lịch sử chung), bảng không tăng vô hạn, FE có cách cho người dùng xem lại thao tác của mình mà không cần auth.

**Non-Goals:** auth, token quản trị, rate limiting trong app, lịch sử theo user trên server.

## Decisions

### 1. Cờ đọc tại thời điểm request

`config.history_api_enabled()` đọc biến môi trường mỗi lần gọi, giống `database_url()`. Route history và health gọi hàm này; không cần khởi động lại để test đổi cờ. Router vẫn luôn được đăng ký, nên OpenAPI ổn định; khi tắt thì route trả 404 bằng exception mới `HistoryDisabledError`, đi qua handler hiện có.

Phương án không chọn: không đăng ký router khi tắt (OpenAPI đổi theo môi trường, 404 mặc định của Starlette không theo envelope tiếng Việt); token quản trị qua header (thực chất là auth tối giản, ngoài phạm vi đã chốt).

### 2. Purge bằng tác vụ nền trong lifespan

Lifespan tạo `asyncio.Task` chạy `purge_expired` ngay lập tức rồi ngủ 6 giờ, lặp lại; shutdown thì cancel và chờ task kết thúc. `DELETE FROM cipher_operations WHERE created_at < now() - make_interval(days => :days)` dùng được index `(created_at, id)`. Nhiều replica cùng chạy vẫn an toàn vì DELETE idempotent.

Phương án không chọn: pg_cron (phải cài extension vào image Postgres), service cron riêng trong compose (thêm container chỉ cho một câu SQL), purge khi ghi (tăng latency ghi).

### 3. Retention days kiểm tra lúc khởi động

`config.history_retention_days()` trả số nguyên 1–3650, mặc định 30, và raise `ValueError` với thông điệp cố định khi sai. Lifespan gọi hàm này đầu tiên nên cấu hình sai làm app không khởi động, thay vì âm thầm giữ dữ liệu sai thời hạn.

### 4. Lịch sử cá nhân chỉ ở tài liệu FE

Backend không đổi cho phần này. Tài liệu FE mô tả schema `localStorage`, giới hạn 50 mục, nút xóa, tùy chọn tắt, và cảnh báo lịch sử chứa key.

## Risks / Trade-offs

- **[Bản ghi sống quá 30 ngày tối đa 6 giờ]** → Chấp nhận; ghi rõ trong tài liệu.
- **[Ai đọc được `.env` thì bật được cờ]** → Chấp nhận; người đó đã có quyền với server.
- **[Lịch sử trên trình duyệt chứa key]** → Mặc định bật nhưng có tùy chọn tắt, nút xóa và cảnh báo trong UI; dữ liệu không rời máy người dùng.

## Migration Plan

Không có migration schema. Deploy: không đặt `HISTORY_API_ENABLED` ở production (mặc định tắt). Dev local: `.env.example` đặt `true`. Rollback: đặt lại cờ hoặc revert code; dữ liệu đã xóa bởi purge không khôi phục được.
