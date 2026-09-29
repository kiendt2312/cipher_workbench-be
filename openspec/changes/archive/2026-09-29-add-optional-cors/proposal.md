## Why

Sau khi bỏ UI static, FE là project riêng. Proxy `/api` vẫn là cách khuyến nghị, nhưng khi FE deploy ở origin khác mà không có reverse proxy thì trình duyệt chặn request. Chủ sở hữu quyết định (2026-09-29): cho phép bật CORS bằng cấu hình, mặc định vẫn tắt.

## What Changes

- Biến môi trường `CORS_ALLOW_ORIGINS`: danh sách origin chính xác, cách nhau bằng dấu phẩy. Rỗng hoặc không đặt thì không có header CORS (hành vi hiện tại).
- Khi bật: chỉ các origin trong danh sách, chỉ `GET`/`POST`, chỉ header `Content-Type`, expose `Content-Disposition`, không credentials.
- Giá trị không phải origin chính xác (`*`, wildcard, thiếu scheme, có path hoặc `/` cuối) làm app không khởi động.
- CORS là middleware ngoài cùng để response từ guard (413) vẫn có header CORS.
- `docker-compose.yml`, `.env.example`, README, tài liệu FE.

## Capabilities

### Modified Capabilities

- `app-runtime`: requirement "Một tiến trình duy nhất phục vụ API" cho phép CORS tùy chọn thay vì cấm hẳn.

## Impact

- Code: `app/config.py`, `app/main.py`.
- Test: `tests/integration/test_cors.py`.
- Contract API không đổi khi không đặt biến.

## Ngoài phạm vi

- CORS có credentials, cookie hay mở cho mọi origin.
- Header CORS trên response 500 ngoài dự kiến (do `ServerErrorMiddleware` của Starlette nằm ngoài mọi middleware); tài liệu FE ghi rõ.
