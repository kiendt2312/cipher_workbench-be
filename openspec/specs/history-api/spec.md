# history-api Specification

## Purpose

Định nghĩa endpoint đọc lịch sử thao tác: phân trang, bộ lọc, envelope và lỗi.

## Requirements

### Requirement: Endpoint GET /api/history

Hệ thống SHALL cung cấp `GET /api/history` nhận query tùy chọn `limit` (số nguyên 1–100, mặc định 20), `cursor` (chuỗi opaque do server trả về), `cipher` (một trong năm tên cipher) và `operation` (`encrypt` hoặc `decrypt`). Kết quả SHALL sắp theo `created_at` giảm dần rồi `id` giảm dần. Response thành công SHALL là HTTP 200 với JSON `{"success": true, "result": {"items": [...], "nextCursor": <chuỗi hoặc null>}}`. Mỗi item SHALL có đúng các trường `id`, `createdAt` (ISO 8601 UTC), `cipher`, `operation`, `source`, `responseMode`, `inputLength`, `outputLength`, `httpStatus`, `succeeded`, `durationMs`. (Truy vết: quyết định chủ sở hữu 2026-09-28)

#### Scenario: Trang đầu mặc định
- **WHEN** DB có 25 bản ghi và client gọi `GET /api/history`
- **THEN** hệ thống trả HTTP 200 với 20 item mới nhất
- **AND** `nextCursor` khác null

#### Scenario: Trang cuối
- **WHEN** client gọi lại với `cursor` vừa nhận
- **THEN** hệ thống trả 5 item còn lại và `nextCursor` là null
- **AND** không item nào lặp lại giữa hai trang

#### Scenario: Lọc theo cipher
- **WHEN** client gọi `GET /api/history?cipher=playfair&operation=decrypt`
- **THEN** mọi item có `cipher = "playfair"` và `operation = "decrypt"`

### Requirement: Validation query và lỗi tiếng Việt

Tham số không hợp lệ SHALL trả HTTP 422 với envelope hiện hành `{"success": false, "message": …}` và message tiếng Việt: `limit` ngoài 1–100 hoặc không phải số nguyên → "Giới hạn phải là số nguyên từ 1 đến 100."; `cursor` không giải mã được → "Con trỏ phân trang không hợp lệ."; `cipher` hoặc `operation` không thuộc tập cho phép → "Bộ lọc lịch sử không hợp lệ.". Khi DB không được cấu hình hoặc không kết nối được, hệ thống SHALL trả HTTP 503 với message "Lịch sử tạm thời không khả dụng.". (Truy vết: quyết định chủ sở hữu 2026-09-28; quy ước tiếng Việt trong `openspec/config.yaml`)

#### Scenario: limit vượt giới hạn
- **WHEN** client gọi `GET /api/history?limit=500`
- **THEN** hệ thống trả HTTP 422 với message "Giới hạn phải là số nguyên từ 1 đến 100."

#### Scenario: DB không khả dụng
- **WHEN** không đặt `DATABASE_URL` và client gọi `GET /api/history`
- **THEN** hệ thống trả HTTP 503 với `{"success": false, "message": "Lịch sử tạm thời không khả dụng."}`
