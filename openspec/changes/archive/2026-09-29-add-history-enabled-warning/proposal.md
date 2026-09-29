## Why

`HISTORY_API_ENABLED` mặc định tắt, nhưng `.env.example` bật sẵn cho dev. Chép nguyên file đó lên môi trường dùng chung sẽ làm `GET /api/history` đọc được bởi bất kỳ ai, vì project không có authentication. Chủ sở hữu quyết định (2026-09-29): app ghi cảnh báo lúc khởi động khi cờ bật để dễ phát hiện.

## What Changes

- Khi khởi động với cờ bật, app ghi một dòng log mức WARNING có nội dung cố định; khi cờ tắt thì không ghi.
- Hành vi API và việc khởi động không đổi.

## Capabilities

### Modified Capabilities

- `history-access`: thêm requirement cảnh báo lúc khởi động.

## Impact

- Code: `app/main.py` (lifespan). Test: `tests/integration/test_history_access_retention.py`. README.
- Đã hiện thực trong commit `c33c34b`; change này ghi nhận vào spec.
