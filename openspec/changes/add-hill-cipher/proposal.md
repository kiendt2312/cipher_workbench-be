## Why

Backend hiện hỗ trợ Caesar, Vigenère, Playfair, Affine và Columnar, nhưng chưa có hệ mã Hill để FE thực hiện bài học ma trận trên Z₂₆. Change này đặc tả cách thêm Hill vào backend hiện tại mà giữ nguyên thuật toán vector hàng trong `Scope Backend_ Hệ mã hóa Hill.html` và không làm đổi contract của năm cipher đã có.

## What Changes

- Thêm lõi Hill cho ma trận cấp 2–4: chuẩn hóa khóa modulo 26, phân tích định thức/nghịch đảo/phụ hợp, mã hóa `y = x·K mod 26`, giải mã `x = y·K⁻¹ mod 26`, chia khối và dựng lại văn bản.
- Thêm đúng bốn endpoint `/api/hill/encrypt`, `/api/hill/decrypt`, `/api/hill/key/analyze`, `/api/hill/key/random`; không thêm `/api/hill/file`. FE đọc file `.txt` UTF-8 tối đa 5 MiB và gửi chuỗi `text` qua endpoint JSON.
- Hill dùng success envelope mở rộng có `success`, `result`, `blocks`, `key`, `warnings`; key endpoints dùng `success` và `result` object. Lỗi nghiệp vụ Hill dùng `success`, `message`, `code`, `details`. Năm cipher cũ giữ nguyên response hai trường.
- Hỗ trợ khóa ma trận hoặc `keyword` cùng `m`, tùy chọn `stripDiacritics` và `padChar` mặc định `X`; W01/W02/W03 là object có mã, thông báo và chi tiết.
- Giới hạn `text` theo UTF-8 tối đa đúng 5 MiB (5.242.880 byte), trả E06/413 khi vượt. Đúng 5 MiB được nhận; 5 MiB + 1 byte bị từ chối với `actualBytes` và `maxBytes` chính xác. E07 thuộc FE; thêm E10 cho options sai và E11 cho request JSON sai cấu trúc. Giữ request guard hạ tầng 64 MiB và response lỗi chung của các route khác.
- Ghi metadata của hai request biến đổi Hill vào lịch sử server, cho phép lọc `cipher=hill`, và tạo migration nới CHECK constraint của `cipher_operations`. Hai key endpoints không sinh lịch sử.
- Bổ sung unit/integration/contract tests, đo lõi và kích thước response ở biên 5 MiB, OpenAPI, README, hướng dẫn FE và client mẫu sau khi implementation đã được kiểm chứng.

## Capabilities

### New Capabilities

- `hill-core`: toán modulo/ma trận, chuẩn bị văn bản, mã hóa/giải mã, vector, padding, diacritics và cảnh báo.
- `hill-text-cipher-api`: request/response của hai endpoint JSON encrypt/decrypt, giới hạn text và OpenAPI.
- `hill-key-api`: phân tích khóa và sinh khóa ngẫu nhiên hợp lệ.
- `hill-error-handling`: mã lỗi Hill, details, precedence và ranh giới với error envelope hiện tại.

### Modified Capabilities

- `operation-history`: nhận metadata của hai route biến đổi Hill và nới ràng buộc `cipher` bằng migration; không lưu khóa, văn bản hay kết quả.
- `history-api`: cho phép bộ lọc `cipher=hill` và trả item có cipher này.

## Impact

- Khi apply trong workflow sau: thêm core/router/schema/exception cục bộ cho Hill, đăng ký router, cập nhật định tuyến lịch sử và migration, rồi cập nhật tài liệu consumer.
- Số cipher tăng từ 5 lên 6; số POST route cipher tăng từ 15 lên 18 (hai route biến đổi và một route phân tích khóa); có thêm một GET route sinh khóa. Chỉ hai POST route biến đổi được ghi lịch sử.
- Test Hill kiểm T01–T12 từ scope, bổ sung ma trận 4×4 và các trường hợp Unicode, lỗi, response, lịch sử, giới hạn, regression. Không thêm dependency runtime hoặc UI trong repo backend.

## Ngoài phạm vi

- FE implementation và test FE cho E07; backend chỉ cung cấp contract/handoff. Không tạo file endpoint Hill hoặc thay đổi file pipeline 5 MiB của các cipher khác.
- Tấn công bản rõ đã biết, Affine-Hill, ma trận cấp trên 4, bảng chữ cái mở rộng, xác thực và lưu nội dung người dùng.
- Không đổi thuật toán hoặc response của năm cipher hiện hữu; không thêm abstract cipher interface hay generalized API.

## Nguồn và quyết định ưu tiên

1. Quyết định chủ sở hữu ngày 2026-09-30 nâng riêng giới hạn `text` Hill từ 1 MiB lên đúng 5 MiB, ghi đè giới hạn cũ trong HTML nguồn và phiên bản trước của change này; HTML lịch sử không bị sửa. Mọi hành vi Hill khác và contract của năm cipher cũ giữ nguyên.
2. Các quyết định Q1–Q19 được chủ sở hữu xác nhận ngày 2026-09-29 quyết định phần tích hợp và các chỗ `Scope Backend_ Hệ mã hóa Hill.html` chưa rõ hoặc tự mâu thuẫn.
3. HTML Hill là nguồn cho toán học, quy ước vector hàng, test vector và quy tắc văn bản, trừ các điểm được quyết định ở trên: Unicode chữ Việt NFC/NFD tương đương; warning W02 chỉ đếm chữ Việt có dấu; `keyword` cần `m`; E07 ở FE; E10/E11 bổ sung; benchmark 1 giây lịch sử chỉ tính lõi ở fixture 1 MiB.
4. Các main spec OpenSpec và runtime đã nghiệm thu là nguồn cho contract dùng chung của năm cipher cũ, lịch sử metadata, request guard 64 MiB và cách tổ chức backend. Ngoại lệ Hill 5 MiB và envelope mở rộng chỉ áp dụng Hill.
