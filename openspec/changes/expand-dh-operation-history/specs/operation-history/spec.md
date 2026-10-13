# Spec Delta

## MODIFIED Requirements

### Requirement: Bảng cipher_operations chỉ chứa metadata

SQLite SHALL giữ schema metadata hiện hữu và cho phép operation `encrypt`, `decrypt`,
`validate_params`, `generate_params`, `generate_keypair`, `derive_shared_secret`,
`exchange` trong `cipher_operations`; năm operation mới chỉ hợp lệ khi `cipher="dh"`.
`private_history_records` SHALL nhận cùng các operation đó, tiếp tục chỉ cho `sign|verify`
khi `cipher="rsa"`. Migration mới SHALL giữ mọi row, cột, index và sequence, và downgrade
MUST fail trước mutation nếu còn row dùng operation mới. (Truy vết: quyết định chủ sở hữu
2026-10-12 đảo D8; main spec `operation-history`; SQLite revisions `sqlite_0001..0003`)

#### Scenario: Schema SQLite sau migration
- **WHEN** chạy SQLite migration từ `sqlite_0003` tới head
- **THEN** cả `cipher_operations` và `private_history_records` nhận năm operation DH mới
- **AND** mọi cột, index, row và sequence trước migration được giữ nguyên

#### Scenario: Schema sau migration
- **WHEN** chạy `alembic upgrade head`
- **THEN** bảng `cipher_operations` giữ đúng 11 cột metadata, các CHECK constraint và hai index
- **AND** CHECK `cipher` tiếp tục cho phép `hill`, `des`, `rsa` và `dh`

#### Scenario: Migration giữ dữ liệu cũ
- **WHEN** database có các bản ghi cipher hiện hữu và chạy migration operation DH
- **THEN** mọi bản ghi cũ còn nguyên
- **AND** có thể thêm bản ghi `cipher="dh"` với operation standalone hợp lệ

#### Scenario: Migration DES
- **WHEN** database có bản ghi Caesar, Hill và DES rồi chạy migration operation DH
- **THEN** mọi bản ghi cũ còn nguyên và CHECK vẫn chặn tên cipher lạ

#### Scenario: Ràng buộc operation theo cipher
- **WHEN** insert `operation="exchange"` với `cipher="dh"`
- **THEN** row được chấp nhận
- **AND** cùng operation với cipher khác bị CHECK constraint từ chối

#### Scenario: Downgrade không xóa operation DH
- **WHEN** một trong hai bảng còn row dùng operation DH standalone và downgrade về `sqlite_0003`
- **THEN** downgrade thất bại trước khi rebuild bảng
- **AND** không row, index hoặc sequence nào bị xóa hay sửa

### Requirement: Không bao giờ lưu nội dung hay dữ liệu định danh

Hệ thống MUST NOT lưu plaintext, ciphertext, key, DH q/alpha/private/public/shared key,
filename/content, request/response body, trace, warning, header, IP, user agent hay message
lỗi. DH standalone SHALL chỉ lưu operation/status/timing và metadata route; `response_mode`,
`input_length`, `output_length` SHALL là NULL. DH Caesar giữ length semantics hiện hữu.
(Truy vết: quyết định chủ sở hữu 2026-10-12; quyết định privacy 2026-09-28; DH source §§2,4)

#### Scenario: DH standalone không lưu bí mật
- **WHEN** client gọi thành công cả params, params/random, keypair, shared-secret và exchange
- **THEN** năm row chỉ chứa metadata chuẩn với operation tương ứng
- **AND** không row nào chứa q, alpha, private/public/shared key, bit size, result, trace hoặc warning
- **AND** `response_mode`, `input_length`, `output_length` đều là NULL

#### Scenario: DH standalone lỗi vẫn không lưu input
- **WHEN** request DH standalone lỗi validation hoặc domain
- **THEN** row chỉ ghi operation route, status, succeeded=false và duration
- **AND** không lưu field name, message lỗi hoặc giá trị request

#### Scenario: DH Caesar giữ privacy hiện hữu
- **WHEN** `/api/dh/caesar` JSON hoặc multipart hoàn tất
- **THEN** row giữ operation encrypt/decrypt và length semantics hiện hữu
- **AND** không lưu q, keys, shift, data, result, filename, trace hoặc warning

#### Scenario: Không lưu nội dung
- **WHEN** client encrypt `"Attack at dawn!"` với key `"LEMON"` qua
  `POST /api/vigenere/encrypt`
- **THEN** row chỉ chứa metadata và độ dài hiện hữu
- **AND** không cột nào trong DB chứa `Attack`, `LEMON` hay `Lxfopv`

#### Scenario: File có BOM
- **WHEN** client gửi file `.txt` gồm BOM và `"é"` tới `POST /api/caesar/file` với
  `action=encrypt`
- **THEN** bản ghi mới có `input_length=5` và `output_length=5`

### Requirement: Ghi một bản ghi cho mỗi request cipher

Hệ thống SHALL ghi đúng một owner-scoped row cho mỗi POST tới sáu route DH, kể cả lỗi
413/415/422/500. Năm route standalone SHALL map exact path sang operation ổn định; DH Caesar
SHALL giữ operation theo action sau validation. Route gần giống hoặc method khác MUST không
được ghi. Việc ghi các cipher/RSA route hiện hữu không đổi. (Truy vết: quyết định chủ sở hữu
2026-10-12 đảo D8; main spec `operation-history`; DH API contract sáu route)

#### Scenario: Sáu route DH đều được ghi
- **WHEN** client gọi thành công `/params`, `/params/random`, `/keypair`, `/shared-secret`,
  `/exchange` và `/caesar` dưới prefix `/api/dh`
- **THEN** có đúng sáu row mới với `cipher="dh"`
- **AND** operation lần lượt là `validate_params`, `generate_params`, `generate_keypair`,
  `derive_shared_secret`, `exchange` và action `encrypt|decrypt` của Caesar

#### Scenario: Exact matcher
- **WHEN** client gọi method khác POST hoặc path gần giống như `/api/dh/exchanges`
- **THEN** request đó không tạo history row

#### Scenario: Request lỗi vẫn được ghi
- **WHEN** một endpoint DH standalone trả lỗi trước khi parse body hoàn tất
- **THEN** có đúng một row với operation suy từ exact route, status tương ứng và succeeded=false

#### Scenario: File lỗi trước khi validate action
- **WHEN** client gửi `POST /api/caesar/file` có `action=encrypt` nhưng thiếu `key`
- **THEN** response vẫn là HTTP 422 với message hiện hành
- **AND** row mới có `source="file"`, `http_status=422` và `operation` là NULL

#### Scenario: Route không phải cipher
- **WHEN** client gọi `GET /api/health` hoặc `GET /`
- **THEN** không có bản ghi mới

#### Scenario: Hill chỉ ghi hai route biến đổi
- **WHEN** client gọi Hill encrypt thành công rồi gọi key/analyze và key/random
- **THEN** chỉ có một row mới với `cipher="hill"`, `source="text"`, `operation="encrypt"`
- **AND** history không lưu text, khóa, result, blocks hoặc warnings

#### Scenario: DES ghi route biến đổi, không ghi trace
- **WHEN** client gọi DES encrypt `Hello World` thành công rồi gọi `/api/des/trace`
- **THEN** chỉ có một row mới với `cipher="des"`, `source="text"`,
  `operation="encrypt"`, `input_length=11`, `output_length=32`
- **AND** history không lưu text, khóa, IV, result hoặc warnings

### Requirement: Ghi lịch sử là best-effort

Việc ghi history MUST NOT đổi status, body hoặc header của response. Khi SQLite lỗi, read-only,
đầy, khóa, timeout 500 ms, không cấu hình DB hoặc schema chưa nhận operation mới, hệ thống SHALL
bỏ row và chỉ log warning redacted. Quy tắc này áp dụng cho cả sáu route DH. (Truy vết: quyết
định chủ sở hữu 2026-10-12; quyết định best-effort 2026-09-28)

#### Scenario: App chạy trước migration operation DH
- **WHEN** app mới chạy trên schema `sqlite_0003` và một DH standalone request thành công
- **THEN** response DH giữ nguyên
- **AND** row có thể bị bỏ lỡ với warning không chứa path DB, connection string hoặc dữ liệu DH

#### Scenario: SQLite lỗi khi ghi DH
- **WHEN** SQLite không thể commit một row DH
- **THEN** response endpoint không đổi
- **AND** không bí mật hoặc chi tiết exception xuất hiện trong log

#### Scenario: DB tắt khi đang encrypt
- **WHEN** DB đã cấu hình nhưng không kết nối được và client gọi
  `POST /api/caesar/encrypt` hợp lệ
- **THEN** response giống hệt khi không có DB
- **AND** log có một cảnh báo không chứa input, key hay chuỗi kết nối
