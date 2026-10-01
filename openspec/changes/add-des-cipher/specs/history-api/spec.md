# history-api Delta

## MODIFIED Requirements

### Requirement: Endpoint GET /api/history

Hệ thống SHALL cung cấp `GET /api/history` nhận query tùy chọn `limit` (số nguyên 1–100, mặc định 20), `cursor` (chuỗi opaque do server trả về), `cipher` (một trong bảy tên `caesar`, `vigenere`, `playfair`, `affine`, `columnar`, `hill`, `des`) và `operation` (`encrypt` hoặc `decrypt`). Kết quả SHALL sắp theo `created_at` giảm dần rồi `id` giảm dần. Response thành công SHALL là HTTP 200 với JSON `{"success": true, "result": {"items": [...], "nextCursor": <chuỗi hoặc null>}}`. Mỗi item SHALL có đúng các trường `id`, `createdAt` (ISO 8601 UTC), `cipher`, `operation`, `source`, `responseMode`, `inputLength`, `outputLength`, `httpStatus`, `succeeded`, `durationMs`. (Truy vết: main spec `history-api`; quyết định chủ sở hữu Q3 ngày 2026-09-29; quyết định chủ sở hữu Q12 ngày 2026-10-01)

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

#### Scenario: Lọc Hill
- **WHEN** history được bật và client gọi `GET /api/history?cipher=hill`
- **THEN** mọi item có `cipher="hill"` và `source="text"`

#### Scenario: Lọc DES
- **WHEN** history được bật, client đã gọi DES encrypt và DES file, rồi gọi `GET /api/history?cipher=des`
- **THEN** mọi item có `cipher="des"`, gồm item `source="text"` và item `source="file"`
