## Why

Tuần 1 cần giao một ứng dụng web Caesar Cipher hoàn chỉnh cho mục đích học tập và minh họa thuật toán: người dùng nhập văn bản từ bàn phím hoặc tải file `.txt`, mã hóa/giải mã, xem kết quả và tải kết quả xuống. Hiện dự án mới chỉ có tài liệu scope (`BE Scope – Week 1 Caesar Cipher MVP.docx` v1.0) và một mockup giao diện chạy backend giả lập (`Caesar_Cipher_Tool_Demo.html`) — chưa có dòng code sản phẩm nào. Change này biến scope đã thống nhất thành đặc tả thi hành được để team bắt đầu build.

## What Changes

- Xây dựng module **Caesar Core** với một interface duy nhất `transform_text(text, key, operation)`, chuẩn hóa key về 0–25 bằng modulo 26, chỉ dịch ASCII `A-Z`/`a-z`, giữ nguyên mọi ký tự khác (số, Unicode, tiếng Việt, whitespace, ký tự đặc biệt).
- Xây dựng **3 HTTP endpoint**: `POST /api/caesar/encrypt`, `POST /api/caesar/decrypt` (JSON) và `POST /api/caesar/file` (multipart, có `response_mode` = `content` | `file`).
- Xây dựng **File Processing**: kiểm tra đuôi `.txt`, giới hạn 5 MiB, decode UTF-8/UTF-8 BOM, sinh file kết quả `<ten-goc>.encrypted.txt` / `<ten-goc>.decrypted.txt`, giữ BOM nếu đầu vào có BOM.
- Chuẩn hóa **response & error**: mọi phản hồi theo `{success, result}` hoặc `{success, message}`; toàn bộ 13 trường hợp lỗi trả đúng HTTP status và thông báo tiếng Việt theo docx §5; không để stack trace lộ ra giao diện.
- Xây dựng **Web UI** phục vụ từ chính FastAPI (same-origin, không cần CORS), bám theo mockup `Caesar_Cipher_Tool_Demo.html`: hai chế độ Encoder/Decoder, hai nguồn đầu vào Text/File, kéo-thả file, tô màu hoa/thường/ký tự khác, bảng dịch chuyển bảng chữ cái, tab Phân tích, copy/clear/download, thanh trạng thái và thông báo.
- Đóng gói chạy được **local và Docker** trên cổng 8000, truy cập được `/` (giao diện) và `/docs` (OpenAPI), kèm test coverage backend tối thiểu 90% và Ruff check/format sạch.

### Mâu thuẫn giữa docx v1.0 và HTML demo — cách giải quyết

`BE Scope – Week 1 Caesar Cipher MVP.docx` v1.0 là **source of truth**. Mockup HTML phải sửa lại cho khớp:

| Điểm | docx v1.0 (áp dụng) | HTML demo (phải sửa) |
|---|---|---|
| Dung lượng tối đa | 5 MiB | 1 MB → sửa thành 5 MiB |
| Tên file tải về | `<ten-goc>.encrypted.txt` | `<ten-goc>_encrypted.txt` → đổi sang dấu chấm |
| Thông báo lỗi | Theo đúng bảng docx §5 | Chuỗi rút gọn khác → thay bằng chuỗi chuẩn |
| `response_mode` | Có, `content` \| `file`, mặc định `content` | Không gửi → bổ sung |
| Origin | Same-origin, không CORS | `API_BASE=http://localhost:8080` → dùng đường dẫn tương đối |
| UTF-8 BOM | Giữ BOM ở file tải xuống | Không xử lý → bổ sung |

Tài liệu `BE Scope – Week 1 Caesar Cipher MVP.before-ui-update.docx` đã bị thay thế bởi v1.0 và **không** được dùng làm căn cứ.

## Capabilities

### New Capabilities

- `caesar-core`: Thuật toán Caesar và chuẩn hóa key — interface `transform_text`, quy tắc dịch ký tự, quy tắc giữ nguyên. Dùng chung cho cả luồng văn bản và luồng file.
- `text-cipher-api`: Hai endpoint JSON `POST /api/caesar/encrypt` và `POST /api/caesar/decrypt` — hợp đồng request/response và validate `text`/`key`.
- `file-cipher-api`: Endpoint `POST /api/caesar/file` — validate file (đuôi, kích thước, encoding), hai chế độ phản hồi `content`/`file`, quy tắc đặt tên file kết quả và giữ UTF-8 BOM.
- `error-handling`: Khuôn dạng error response chuẩn và ánh xạ đầy đủ 13 trường hợp lỗi sang HTTP status + thông báo tiếng Việt; che giấu chi tiết kỹ thuật, log nội bộ.
- `web-ui`: Giao diện web phục vụ từ FastAPI — chế độ mã hóa/giải mã, nguồn đầu vào text/file, hiển thị kết quả, copy/download/làm mới, trạng thái đang xử lý, responsive và dùng được bằng bàn phím.
- `app-runtime`: Cách chạy và phục vụ ứng dụng — cổng 8000, tuyến `/` và `/docs`, chạy local và bằng Docker, tính stateless.

### Modified Capabilities

Không có. Đây là change đầu tiên của dự án, chưa tồn tại spec nào trong `openspec/specs/`.

## Impact

- **Code**: Tạo mới toàn bộ source tree (`app/` cho backend, `app/static/` + `app/templates/` cho UI, `tests/` cho test).
- **API**: Thêm mới 3 endpoint dưới tiền tố `/api/caesar/`; chưa có consumer bên ngoài nên không có breaking change.
- **Dependency**: Python 3.12, FastAPI, uvicorn, python-multipart, Jinja2; dev: pytest, pytest-cov, httpx, ruff. Quản lý bằng `uv` qua `pyproject.toml` — `uv` **chưa được cài** trên máy hiện tại, cần cài trước khi bắt đầu.
- **Hạ tầng**: Thêm `Dockerfile` (multi-stage) và `.dockerignore`; cổng 8000 cho cả local lẫn container.
- **Tài liệu**: Mockup `Caesar_Cipher_Tool_Demo.html` chuyển thành tài sản tham chiếu, được port thành UI thật với 6 điểm sửa nêu trên.
- **Ngoài phạm vi (docx §8)**: không database, không authentication, không lịch sử thao tác, không React, không CI/CD, không triển khai cloud, không CORS. Không tạo abstract cipher interface hay repository pattern ở Tuần 1 — chỉ thêm seam khi một feature tương lai thực sự cần implementation thứ hai.
