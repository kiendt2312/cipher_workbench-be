# history-access Specification

## Purpose

Giới hạn việc đọc lịch sử server khi project không có authentication.

## Requirements

### Requirement: Cờ HISTORY_API_ENABLED

Hệ thống SHALL đọc biến môi trường `HISTORY_API_ENABLED`. Giá trị `true`, `1`, `yes`, `on` (không phân biệt hoa thường, bỏ khoảng trắng hai đầu) SHALL bật endpoint đọc lịch sử; mọi giá trị khác hoặc không đặt biến SHALL coi là tắt. Cờ này MUST NOT ảnh hưởng việc ghi lịch sử. (Truy vết: quyết định chủ sở hữu 2026-09-28)

#### Scenario: Mặc định tắt
- **WHEN** không đặt `HISTORY_API_ENABLED`
- **THEN** endpoint đọc lịch sử bị tắt
- **AND** request cipher vẫn được ghi vào `cipher_operations` khi có DB

### Requirement: GET /api/history trả 404 khi tắt

Khi cờ tắt, `GET /api/history` SHALL trả HTTP 404 với `{"success": false, "message": "Lịch sử không được bật trên máy chủ này."}`, kiểm tra trước mọi validation query và trước trạng thái DB. Khi cờ bật, endpoint SHALL hoạt động đúng như spec `history-api`. (Truy vết: quyết định chủ sở hữu 2026-09-28)

#### Scenario: Cờ tắt với query sai
- **WHEN** cờ tắt và client gọi `GET /api/history?limit=500`
- **THEN** hệ thống trả HTTP 404 với message "Lịch sử không được bật trên máy chủ này."

#### Scenario: Cờ bật
- **WHEN** `HISTORY_API_ENABLED=true`, có DB và client gọi `GET /api/history`
- **THEN** hệ thống trả HTTP 200 theo spec `history-api`

### Requirement: Health báo trạng thái lịch sử

`GET /api/health` SHALL trả `result.history` bằng `"enabled"` khi cờ bật và `"disabled"` khi cờ tắt, bên cạnh `app` và `database` hiện có. Trường này MUST NOT ảnh hưởng HTTP status của health. (Truy vết: quyết định chủ sở hữu 2026-09-28)

#### Scenario: Health khi cờ tắt
- **WHEN** DB sẵn sàng, cờ tắt và client gọi `GET /api/health`
- **THEN** hệ thống trả HTTP 200 với `result` bằng `{"app": "ok", "database": "ok", "history": "disabled"}`
