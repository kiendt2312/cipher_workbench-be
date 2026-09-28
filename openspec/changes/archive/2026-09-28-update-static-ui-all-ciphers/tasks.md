## 1. Template và style

- [x] 1.1 Thêm bộ chọn cipher, ô khóa theo cipher (một ô hoặc `a`/`b`), cảnh báo Playfair, khu lịch sử hai tab; truyền message qua JSON nhúng. **Xong khi:** trang render đủ phần tử, test render xanh.

## 2. Logic UI

- [x] 2.1 Bảng cấu hình 5 cipher, state khóa theo cipher, kiểm tra sơ bộ, serializer JSON/multipart. **Xong khi:** encrypt/decrypt text và file chạy đúng cho cả 5 cipher trên trình duyệt thật.
- [x] 2.2 Lịch sử trên máy này theo §17. **Xong khi:** thêm, giới hạn 50, xóa, tắt lưu, dùng lại hoạt động; storage lỗi không làm hỏng UI.
- [x] 2.3 Lịch sử máy chủ. **Xong khi:** tab chỉ hiện khi health cho phép; lọc và tải thêm hoạt động.

## 3. Test và tài liệu

- [x] 3.1 Viết lại `tests/integration/test_ui_assets.py`. **Xong khi:** giữ các guard Tuần 1 (không mock, không host cứng, khóa control, timeout, tên file từ server) và thêm guard cho 5 cipher, lịch sử.
- [x] 3.2 Kiểm tra bằng trình duyệt headless trên compose. **Xong khi:** đủ 5 cipher text, một luồng file, hai loại lịch sử.
- [x] 3.3 README và tài liệu FE bỏ "UI Caesar-only". **Xong khi:** không còn câu mâu thuẫn.
