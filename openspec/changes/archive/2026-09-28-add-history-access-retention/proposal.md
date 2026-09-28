## Why

Project sẽ không có authentication. Sau change `add-postgres-persistence`, `GET /api/history` mở cho bất kỳ ai truy cập được app, và bảng `cipher_operations` tăng không giới hạn. Chủ sở hữu quyết định (2026-09-28): khóa endpoint đọc lịch sử bằng cờ cấu hình thay vì auth, giữ dữ liệu 30 ngày, và để lịch sử cá nhân của người dùng nằm trên trình duyệt thay vì trên server.

## What Changes

- Thêm biến môi trường `HISTORY_API_ENABLED` (mặc định tắt). Khi tắt, `GET /api/history` trả HTTP 404 với message tiếng Việt; việc ghi lịch sử vẫn chạy bình thường.
- `GET /api/health` thêm trường `result.history` (`enabled` hoặc `disabled`) để FE biết có nên hiện màn hình lịch sử server không.
- Thêm retention: một tác vụ nền trong lifespan xóa bản ghi cũ hơn `HISTORY_RETENTION_DAYS` (mặc định 30) lúc khởi động và định kỳ mỗi 6 giờ; thêm lệnh chạy tay `python -m app.history.retention`.
- Tài liệu FE: hướng dẫn lưu lịch sử cá nhân trên trình duyệt (`localStorage`), không gửi lên server.
- `.env.example` bật `HISTORY_API_ENABLED=true` cho môi trường dev; README ghi rõ để tắt khi deploy.

## Capabilities

### New Capabilities

- `history-access`: Cờ bật/tắt endpoint đọc lịch sử và trạng thái trong health.
- `history-retention`: Xóa định kỳ bản ghi quá hạn và lệnh chạy tay.
- `client-side-history`: Hướng dẫn FE lưu lịch sử cá nhân trên trình duyệt (chỉ tài liệu, backend không đổi).

### Modified Capabilities

- `history-api` (change `add-postgres-persistence`): thêm điều kiện HTTP 404 khi cờ tắt, kiểm tra trước mọi validation query.
- `database-infrastructure` (change `add-postgres-persistence`): response health thêm trường `history`.

## Impact

- Code: `app/config.py`, `app/api/routes_history.py`, `app/api/routes_health.py`, `app/main.py` (lifespan), `app/history/retention.py` mới, `app/errors/messages.py`/`exceptions.py`.
- Hạ tầng: `.env.example`, `docker-compose.yml` truyền thêm hai biến.
- Tài liệu: README, `repo_docs/frontend-integration.md`.
- 15 route cipher không đổi.

## Ngoài phạm vi

- Authentication, token quản trị, phân quyền.
- Lịch sử theo user trên server hoặc ID ẩn danh gửi lên server.
- Rate limiting trong app (thực hiện ở reverse proxy khi deploy).
- Retention theo giờ chính xác: bản ghi có thể tồn tại tối đa 30 ngày + 6 giờ.

## Giải quyết khác biệt giữa nguồn

- `add-postgres-persistence/design.md` để mở hai câu hỏi: giới hạn truy cập `/api/history` và thời gian giữ dữ liệu. Change này trả lời cả hai theo quyết định chủ sở hữu 2026-09-28.
- Health response đổi từ hai lên ba trường trong `result`. Đây là mở rộng tương thích ngược: client cũ bỏ qua trường mới.
