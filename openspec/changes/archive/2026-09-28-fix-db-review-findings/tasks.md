## 1. Code

- [x] 1.1 Message tiếng Việt cho mô tả 503 của health. **Xong khi:** OpenAPI trả đúng message.
- [x] 1.2 Ghi lịch sử lỗi 500 ở nền. **Xong khi:** test với store chậm 1 s thấy response 500 trả trong dưới 0,5 s và vẫn ghi `http_status = 500`.
- [x] 1.3 `note_history` dùng tham số có tên. **Xong khi:** tên sai ném `TypeError`, giá trị `None` không ghi đè.
- [x] 1.4 `output_length` file tính BOM. **Xong khi:** file có BOM cho `input_length == output_length` ở cả hai `response_mode`.
- [x] 1.5 Cursor chặn `id` vượt bigint. **Xong khi:** decode ném `InvalidHistoryCursorError`.
- [x] 1.6 Lệnh purge in message cố định khi lỗi. **Xong khi:** exit 1, stderr không chứa mật khẩu.

## 2. Spec và kiểm tra

- [x] 2.1 Sửa requirement docker-compose và định nghĩa độ dài file.
- [x] 2.2 `ruff check`, `ruff format --check`, `pytest` có `TEST_DATABASE_URL`. **Xong khi:** exit 0, coverage ≥ 90%.
