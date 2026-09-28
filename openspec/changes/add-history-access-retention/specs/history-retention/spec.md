## Purpose

Giữ bảng `cipher_operations` trong giới hạn thời gian đã chốt.

## ADDED Requirements

### Requirement: Thời gian giữ dữ liệu

Hệ thống SHALL đọc `HISTORY_RETENTION_DAYS` (số nguyên từ 1 đến 3650, mặc định 30). Giá trị không hợp lệ SHALL làm app dừng khởi động với lỗi cấu hình rõ ràng, không chứa giá trị bí mật. Bản ghi có `created_at` cũ hơn `now() - HISTORY_RETENTION_DAYS ngày` SHALL bị xóa. (Truy vết: quyết định chủ sở hữu 2026-09-28)

#### Scenario: Mặc định 30 ngày
- **WHEN** không đặt `HISTORY_RETENTION_DAYS` và chạy purge
- **THEN** bản ghi 31 ngày tuổi bị xóa
- **AND** bản ghi 29 ngày tuổi được giữ

#### Scenario: Giá trị không hợp lệ
- **WHEN** `HISTORY_RETENTION_DAYS=0` hoặc `abc`
- **THEN** app không khởi động được và báo lỗi cấu hình

### Requirement: Purge định kỳ trong app

Khi có DB, lifespan SHALL chạy purge một lần ngay sau khi khởi động và lặp lại mỗi 6 giờ, và SHALL hủy tác vụ khi shutdown. Lỗi purge (DB tắt, timeout) SHALL chỉ được log cảnh báo không chứa chuỗi kết nối và MUST NOT làm app dừng. Không có DB thì không chạy purge. (Truy vết: quyết định chủ sở hữu 2026-09-28)

#### Scenario: DB tắt khi purge
- **WHEN** purge chạy lúc DB không kết nối được
- **THEN** app vẫn phục vụ route cipher
- **AND** log có một cảnh báo không chứa chuỗi kết nối

### Requirement: Lệnh purge chạy tay

Repository SHALL cung cấp `python -m app.history.retention`, đọc `DATABASE_URL` và `HISTORY_RETENTION_DAYS`, xóa bản ghi quá hạn, in số dòng đã xóa và thoát mã 0. Thiếu `DATABASE_URL` SHALL thoát mã khác 0 với thông báo rõ ràng. (Truy vết: quyết định chủ sở hữu 2026-09-28)

#### Scenario: Chạy tay
- **WHEN** chạy `python -m app.history.retention` với DB có 2 bản ghi quá hạn
- **THEN** lệnh in số dòng đã xóa là 2 và thoát mã 0
