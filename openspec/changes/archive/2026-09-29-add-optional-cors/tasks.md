## 1. Code và test

- [x] 1.1 `config.cors_allow_origins()` đọc và kiểm tra `CORS_ALLOW_ORIGINS`. **Xong khi:** giá trị sai ném `ValueError`, rỗng trả tuple rỗng.
- [x] 1.2 Gắn `CORSMiddleware` ngoài cùng trong `app/main.py` khi có origin. **Xong khi:** test xác nhận origin cho phép có header, origin khác không có, preflight chỉ nhận GET/POST, 413 vẫn có header, mặc định không có header.
- [x] 1.3 Truyền biến qua compose và `.env.example`.

## 2. Tài liệu và kiểm tra

- [x] 2.1 README và tài liệu FE (mục 0.0a).
- [x] 2.2 `ruff check`, `ruff format --check`, `pytest` có `TEST_DATABASE_URL`. **Xong khi:** exit 0, coverage ≥ 90%.
