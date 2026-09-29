## ADDED Requirements

### Requirement: Cảnh báo lúc khởi động khi cờ bật

Khi ứng dụng khởi động với `HISTORY_API_ENABLED` bật, hệ thống SHALL ghi đúng một dòng log mức WARNING nói rằng `GET /api/history` đọc được mà không cần xác thực và cần tắt trên môi trường dùng chung hoặc công khai. Khi cờ tắt, hệ thống MUST NOT ghi cảnh báo này. Cảnh báo MUST NOT chặn khởi động hay thay đổi hành vi API. (Truy vết: quyết định chủ sở hữu 2026-09-29)

#### Scenario: Cờ bật
- **WHEN** ứng dụng khởi động với `HISTORY_API_ENABLED=true`
- **THEN** log có một dòng WARNING bắt đầu bằng `HISTORY_API_ENABLED is on`
- **AND** ứng dụng vẫn khởi động và phục vụ request bình thường

#### Scenario: Cờ tắt
- **WHEN** ứng dụng khởi động với `HISTORY_API_ENABLED` tắt hoặc không đặt
- **THEN** log không có cảnh báo này
