# Spec Delta

## MODIFIED Requirements

### Requirement: Endpoint GET /api/history

`GET /api/history` SHALL giữ owner scoping, pagination và response shape hiện hữu. Filter
`cipher` SHALL nhận đủ chín cipher gồm `dh`; filter `operation` SHALL nhận `encrypt`,
`decrypt`, `sign`, `verify`, `validate_params`, `generate_params`, `generate_keypair`,
`derive_shared_secret`, `exchange`. Mỗi item SHALL trả operation đã lưu mà không thêm payload
DH. (Truy vết: quyết định chủ sở hữu 2026-10-12; main specs `history-api`, `history-access`;
private-history contract hiện hành)

#### Scenario: Trang đầu mặc định
- **WHEN** profile hiện tại có 25 bản ghi và client gọi `GET /api/history`
- **THEN** hệ thống trả HTTP 200 với 20 item mới nhất và `nextCursor` khác null

#### Scenario: Trang cuối
- **WHEN** client gọi lại với cursor vừa nhận
- **THEN** trang còn lại không lặp item và `nextCursor` là null

#### Scenario: Lọc theo cipher
- **WHEN** client gọi `GET /api/history?cipher=playfair&operation=decrypt`
- **THEN** mọi item có `cipher="playfair"` và `operation="decrypt"`

#### Scenario: Lọc Hill
- **WHEN** history được bật và client gọi `GET /api/history?cipher=hill`
- **THEN** mọi item có `cipher="hill"` và `source="text"`

#### Scenario: Lọc DES
- **WHEN** history được bật, client đã gọi DES encrypt và DES file, rồi gọi
  `GET /api/history?cipher=des`
- **THEN** mọi item có `cipher="des"`, gồm item `source="text"` và item `source="file"`

#### Scenario: Lọc DH standalone
- **WHEN** profile có nhiều operation DH và client gọi
  `GET /api/history?cipher=dh&operation=exchange`
- **THEN** mọi item trả về có `cipher="dh"` và `operation="exchange"`
- **AND** item không chứa q, alpha, key, result, trace hoặc warning

#### Scenario: Owner scoping không đổi
- **WHEN** hai browser profile có history DH riêng và profile A lọc `cipher=dh`
- **THEN** chỉ row thuộc profile A được trả về

### Requirement: Validation query và lỗi tiếng Việt

Query invalid SHALL giữ HTTP 422 và message tiếng Việt hiện hữu. `cipher` ngoài chín tên hoặc
`operation` ngoài tập đã đăng ký SHALL trả `Bộ lọc lịch sử không hợp lệ.`; năm operation DH
standalone SHALL là filter hợp lệ kể cả khi chưa có row. Hành vi 404 khi history tắt và 503 khi
DB không khả dụng không đổi. (Truy vết: quyết định chủ sở hữu 2026-10-12; main specs
`history-api`, `history-access`)

#### Scenario: Operation DH hợp lệ khi chưa có row
- **WHEN** history bật, DB sẵn sàng nhưng profile chưa có row và client lọc
  `operation=derive_shared_secret`
- **THEN** hệ thống trả HTTP 200 với `items=[]` và `nextCursor=null`

#### Scenario: Operation lạ bị từ chối
- **WHEN** client gọi `GET /api/history?operation=private_key`
- **THEN** hệ thống trả HTTP 422 với message `Bộ lọc lịch sử không hợp lệ.`

#### Scenario: limit vượt giới hạn
- **WHEN** client gọi `GET /api/history?limit=500`
- **THEN** hệ thống trả HTTP 422 với message `Giới hạn phải là số nguyên từ 1 đến 100.`

#### Scenario: DB không khả dụng
- **WHEN** history bật nhưng DB không được cấu hình hoặc không mở được
- **THEN** hệ thống trả HTTP 503 với message `Lịch sử tạm thời không khả dụng.`
