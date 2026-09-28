## Why

Review phần DB (2026-09-28) tìm ra một số chỗ lệch giữa code và spec, cùng vài lỗi nhỏ ở cạnh biên. Change này sửa tất cả mà không thêm tầng hay abstraction mới.

## What Changes

- Mô tả OpenAPI cho lỗi 503 của `/api/health` dùng message tiếng Việt `Cơ sở dữ liệu không khả dụng.`.
- Lỗi 500 không bắt được: lịch sử được ghi ở nền để response 500 không phải chờ, đúng yêu cầu "ghi sau khi response đã gửi xong".
- `note_history` nhận bốn tham số có tên; gõ sai tên sẽ báo lỗi thay vì âm thầm bỏ qua.
- `output_length` của nguồn file tính cả BOM, cho khớp với `input_length`.
- Cursor có `id` vượt bigint trả 422 thay vì 503.
- Lệnh `python -m app.history.retention` khi DB lỗi in message cố định và thoát mã 1, không in traceback có thể chứa host.
- Spec: compose publish app ở cổng `8080` và Postgres ở `127.0.0.1:5433`; định nghĩa độ dài file nói rõ về BOM.

## Capabilities

### Modified Capabilities

- `database-infrastructure`: requirement docker-compose khớp cổng thực tế.
- `operation-history`: độ dài nguồn file tính cả BOM.

## Impact

- Code: `app/api/history_recorder.py`, `app/api/routes_health.py`, `app/errors/messages.py`, `app/history/cursor.py`, `app/history/retention.py`, `app/services/file_processing.py`, bốn file route file.
- Test: thêm test hồi quy cho từng điểm.
- Contract API công khai không đổi.
