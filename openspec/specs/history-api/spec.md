# history-api Specification

## Purpose

Định nghĩa endpoint đọc lịch sử thao tác: phân trang, bộ lọc, envelope và lỗi.
## Requirements
### Requirement: Endpoint GET /api/history

Hệ thống SHALL cung cấp `GET /api/history` owner-scoped theo browser-profile hiện hữu, nhận query tùy chọn `limit` (số nguyên 1–100, mặc định 20), `cursor` (chuỗi opaque do server trả về), `cipher` (một trong chín tên `caesar`, `vigenere`, `playfair`, `affine`, `columnar`, `hill`, `des`, `rsa`, `dh`) và `operation` (`encrypt`, `decrypt`, `sign`, `verify`, `validate_params`, `generate_params`, `generate_keypair`, `derive_shared_secret`, `exchange`). Kết quả SHALL sắp theo `created_at` giảm dần rồi `id` giảm dần. Response thành công SHALL là HTTP 200 với JSON `{"success": true, "result": {"items": [...], "nextCursor": <chuỗi hoặc null>}}`. Mỗi item SHALL có đúng các trường `id`, `createdAt` (ISO 8601 UTC), `cipher`, `operation`, `source`, `responseMode`, `inputLength`, `outputLength`, `httpStatus`, `succeeded`, `durationMs`. Row RSA SHALL dùng `operation="encrypt"|"decrypt"`, `source="text"|"file"`, `responseMode=null` và length nullable theo `operation-history`. Mỗi item SHALL trả operation đã lưu mà không thêm payload DH. (Truy vết: main spec `history-api`; quyết định chủ sở hữu Q3 ngày 2026-09-29, Q12 ngày 2026-10-01, Q16 ngày 2026-10-06 và quyết định chủ sở hữu 2026-10-12)

#### Scenario: Trang đầu mặc định
- **WHEN** profile hiện tại có 25 bản ghi và client gọi `GET /api/history`
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

#### Scenario: Lọc RSA
- **WHEN** history được bật, có row RSA và client gọi `GET /api/history?cipher=rsa`
- **THEN** mọi item trả về có `cipher="rsa"`
- **AND** có thể gồm JSON transform `source="text"` và multipart encrypt `source="file"`

#### Scenario: Lọc DH standalone
- **WHEN** profile có nhiều operation DH và client gọi `GET /api/history?cipher=dh&operation=exchange`
- **THEN** mọi item trả về có `cipher="dh"` và `operation="exchange"`
- **AND** item không chứa q, alpha, key, result, trace hoặc warning

#### Scenario: Owner scoping không đổi
- **WHEN** hai browser profile có history DH riêng và profile A lọc `cipher=dh`
- **THEN** chỉ row thuộc profile A được trả về

### Requirement: Validation query và lỗi tiếng Việt

Tham số không hợp lệ SHALL trả HTTP 422 với envelope hiện hành `{"success": false, "message": …}` và message tiếng Việt: `limit` ngoài 1–100 hoặc không phải số nguyên → "Giới hạn phải là số nguyên từ 1 đến 100."; `cursor` không giải mã được → "Con trỏ phân trang không hợp lệ."; `cipher` ngoài chín tên đã đăng ký hoặc `operation` không thuộc tập cho phép → "Bộ lọc lịch sử không hợp lệ.". Khi DB không được cấu hình hoặc không kết nối được, hệ thống SHALL trả HTTP 503 với message "Lịch sử tạm thời không khả dụng.". `cipher=rsa`, `cipher=dh` và năm operation DH standalone SHALL là filter hợp lệ kể cả khi chưa có row; hành vi 404 khi history tắt không đổi. (Truy vết: quyết định chủ sở hữu 2026-09-28, Q16 ngày 2026-10-06 và quyết định chủ sở hữu 2026-10-12; quy ước tiếng Việt trong `openspec/config.yaml`)

#### Scenario: limit vượt giới hạn
- **WHEN** client gọi `GET /api/history?limit=500`
- **THEN** hệ thống trả HTTP 422 với message "Giới hạn phải là số nguyên từ 1 đến 100."

#### Scenario: DB không khả dụng
- **WHEN** history bật nhưng DB không được cấu hình hoặc không mở được
- **THEN** hệ thống trả HTTP 503 với message `Lịch sử tạm thời không khả dụng.`

#### Scenario: RSA filter hợp lệ khi chưa có row
- **WHEN** history được bật, database sẵn sàng nhưng chưa có row RSA và client gọi `GET /api/history?cipher=rsa`
- **THEN** HTTP 200 với `items=[]` và `nextCursor=null`

#### Scenario: Operation DH hợp lệ khi chưa có row
- **WHEN** history bật, DB sẵn sàng nhưng profile chưa có row và client lọc `operation=derive_shared_secret`
- **THEN** hệ thống trả HTTP 200 với `items=[]` và `nextCursor=null`

#### Scenario: Operation lạ bị từ chối
- **WHEN** client gọi `GET /api/history?operation=private_key`
- **THEN** hệ thống trả HTTP 422 với message `Bộ lọc lịch sử không hợp lệ.`
