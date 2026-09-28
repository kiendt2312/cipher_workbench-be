## Context

UI Tuần 1 là HTML/CSS/JS thuần (~1.000 dòng) gắn cứng Caesar. Không có build step, không framework; test UI là kiểm tra chuỗi trong source và rendering server.

## Decisions

### 1. Giữ JS thuần và một file `app.js`

Bảng cấu hình `CIPHERS` mô tả mỗi cipher (tên, ví dụ, loại khóa, validator, serializer). Render, state và luồng request dùng chung; khác biệt nằm trong bảng này. Không thêm framework hay bundler để giữ đúng tech stack đã chốt.

### 2. Message server đưa vào trang qua JSON nhúng

`main.py` render `<script type="application/json" id="uiMessages">` chứa các message canonical cần cho kiểm tra sơ bộ. Giữ nguyên các `data-*` cũ để không phá contract Tuần 1.

### 3. Bản nháp khóa theo cipher

`state.keys[cipher]` giữ raw value của từng ô (`key` hoặc `a`/`b`). Đổi cipher chỉ đổi ô đang hiện, không mất bản nháp.

### 4. Lịch sử máy chủ tải lười

Gọi `/api/health` một lần khi mở trang; tab "Máy chủ" chỉ tải `/api/history` khi được mở hoặc bấm làm mới.

## Risks / Trade-offs

- **[Kiểm tra sơ bộ lệch server]** → Chỉ dùng để bật/tắt nút; lỗi server luôn hiện nguyên message.
- **[Lịch sử trình duyệt chứa khóa]** → Cảnh báo, công tắc tắt, nút xóa.
