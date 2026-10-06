# Spec Delta

## MODIFIED Requirements

### Requirement: Bảng cipher_operations chỉ chứa metadata

Hệ thống SHALL lưu lịch sử trong bảng `cipher_operations` với đúng các cột: `id` (bigint identity, khóa chính), `created_at` (timestamptz, mặc định thời điểm hiện tại), `cipher` (text, CHECK thuộc `caesar`, `vigenere`, `playfair`, `affine`, `columnar`, `hill`, `des`, `rsa`), `operation` (text nullable, CHECK thuộc `encrypt`, `decrypt`), `source` (text, CHECK thuộc `text`, `file`), `response_mode` (text nullable, CHECK thuộc `content`, `file`), `input_length` (integer nullable, ≥ 0), `output_length` (integer nullable, ≥ 0), `http_status` (smallint), `succeeded` (boolean), `duration_ms` (integer, ≥ 0). Bảng SHALL có index B-tree trên `(created_at, id)` và trên `(cipher, created_at)`; PostgreSQL quét ngược các index này cho truy vấn mới nhất trước. Migration mới SHALL chỉ nới CHECK của `cipher`, giữ nguyên mọi row và cấu trúc khác; không sửa migration `0001`–`0003` đã áp dụng. (Truy vết: main spec `operation-history`, `alembic/versions/0001_create_cipher_operations.py`; quyết định chủ sở hữu Q3 ngày 2026-09-29, Q12 ngày 2026-10-01, Q16 ngày 2026-10-06)

#### Scenario: Schema sau migration

- **WHEN** chạy `alembic upgrade head`
- **THEN** bảng `cipher_operations` có đúng 11 cột trên, các CHECK constraint và hai index
- **AND** CHECK `cipher` cho phép `hill`, `des` và `rsa` bên cạnh năm giá trị cũ

#### Scenario: Migration giữ dữ liệu cũ

- **WHEN** bảng đang có bản ghi Caesar và chạy migration Hill
- **THEN** bản ghi cũ còn nguyên và có thể thêm bản ghi `cipher="hill"`

#### Scenario: Migration DES

- **WHEN** bảng đang có bản ghi Caesar và Hill rồi chạy migration DES
- **THEN** bản ghi cũ còn nguyên, có thể thêm bản ghi `cipher="des"` và CHECK vẫn chặn tên cipher lạ

#### Scenario: Migration RSA

- **WHEN** schema đang ở revision `0003` với row cipher cũ và chạy `alembic upgrade head`
- **THEN** mọi row cũ còn nguyên và có thể insert `cipher="rsa"`
- **AND** CHECK vẫn từ chối tên cipher lạ

#### Scenario: Downgrade không xóa RSA âm thầm

- **WHEN** bảng còn row `cipher="rsa"` và chạy downgrade về `0003`
- **THEN** migration thất bại khi tạo lại CHECK cũ thay vì xóa hoặc sửa row
- **AND** operator phải xử lý row RSA theo chính sách dữ liệu trước khi retry downgrade

### Requirement: Không bao giờ lưu nội dung hay dữ liệu định danh

Hệ thống MUST NOT lưu plaintext, ciphertext, key (kể cả `a`, `b`, `p`, `q`, `e`, `d`, private/public key), tên file, nội dung file, request `data`, cipher array, `textMetadata`, `originalUtf8ByteLength`, per-bit/Euclid trace, header request, IP, user agent hay message lỗi. Chỉ các cột metadata chuẩn hiện hữu được dùng. Độ dài SHALL là số Unicode code point cho nguồn text và số byte cho nguồn file. Với nguồn file truyền thống, cả `input_length` lẫn `output_length` SHALL tính UTF-8 BOM nếu file đầu vào có BOM, ở cả hai `response_mode`. Với RSA, phía cipher array SHALL là NULL: JSON text encrypt chỉ `input_length` MAY được đặt; JSON text decrypt chỉ `output_length` MAY được đặt; number để hai length NULL; multipart encrypt chỉ `input_length` MAY là raw byte gồm BOM. (Truy vết: quyết định chủ sở hữu 2026-09-28, Q16 ngày 2026-10-06; `openspec/config.yaml`)

#### Scenario: Không lưu nội dung

- **WHEN** client encrypt `"Attack at dawn!"` với key `"LEMON"` qua `POST /api/vigenere/encrypt`
- **THEN** bản ghi mới có `cipher = "vigenere"`, `operation = "encrypt"`, `source = "text"`, `input_length = 15`, `output_length = 15`, `http_status = 200`, `succeeded = true`
- **AND** không cột nào trong DB chứa `Attack`, `LEMON` hay `Lxfopv`

#### Scenario: File có BOM

- **WHEN** client gửi file `.txt` gồm BOM và `"é"` tới `POST /api/caesar/file` với `action = encrypt`
- **THEN** bản ghi mới có `input_length = 5` và `output_length = 5`

#### Scenario: RSA text encrypt không lưu cipher array

- **WHEN** JSON RSA encrypt text thành công
- **THEN** row có thể có `input_length` bằng số code point, nhưng `output_length` là NULL
- **AND** row không chứa text, key, blocks, cipher array, byte-length metadata hoặc trace

#### Scenario: RSA multipart không lưu filename hoặc file content

- **WHEN** multipart RSA encrypt `.txt` thành công
- **THEN** row có `source="file"`, `input_length` bằng số raw byte gồm BOM và `output_length=NULL`
- **AND** row không chứa filename, file content, key hoặc cipher array

### Requirement: Ghi một bản ghi cho mỗi request cipher

Hệ thống SHALL ghi đúng một row cho mỗi request tới 22 route biến đổi `POST /api/{caesar|vigenere|playfair|affine|columnar|des}/{encrypt|decrypt|file}`, `POST /api/hill/{encrypt|decrypt}` và `POST /api/rsa/{encrypt|decrypt}`, kể cả request lỗi 413/415/422/500. `cipher` và `source` SHALL suy ra từ path/media type. `operation` SHALL lấy từ path với route text, và từ trường `action` đã validate với route file truyền thống; nếu request lỗi trước khi biết operation thì `operation` là NULL. `input_length`/`output_length` là NULL khi chưa xác định được. Hill và DES giữ nguyên semantics metadata hiện hành. RSA encrypt JSON có `source="text"`, RSA encrypt multipart có `source="file"`, RSA decrypt có `source="text"`; RSA luôn `response_mode=NULL` và length theo requirement không lưu dữ liệu ở trên. Request tới route khác, gồm Hill key routes, DES trace, hai RSA keygen route, OpenAPI, health và history, MUST NOT được ghi. (Truy vết: main spec `operation-history`; quyết định chủ sở hữu Q3, Q9, Q16 ngày 2026-09-29; Q12 ngày 2026-10-01; Q16 ngày 2026-10-06)

#### Scenario: Request lỗi vẫn được ghi

- **WHEN** client gửi `POST /api/vigenere/encrypt` với key `"LE MON"`
- **THEN** response vẫn là HTTP 422 với message hiện hành
- **AND** bản ghi mới có `http_status = 422`, `succeeded = false`, `output_length` là NULL

#### Scenario: File lỗi trước khi validate action

- **WHEN** client gửi `POST /api/caesar/file` có `action=encrypt` nhưng thiếu `key`
- **THEN** response vẫn là HTTP 422 với message hiện hành
- **AND** bản ghi mới có `source = "file"`, `http_status = 422` và `operation` là NULL

#### Scenario: Route không phải cipher

- **WHEN** client gọi `GET /api/health` hoặc `GET /`
- **THEN** không có bản ghi mới

#### Scenario: Hill chỉ ghi hai route biến đổi

- **WHEN** client gọi Hill encrypt thành công rồi gọi key/analyze và key/random
- **THEN** chỉ có một bản ghi mới với `cipher="hill"`, `source="text"`, `operation="encrypt"`
- **AND** history không lưu text, khóa, result, blocks hoặc warnings

#### Scenario: DES ghi route biến đổi, không ghi trace

- **WHEN** client gọi DES encrypt `Hello World` thành công rồi gọi `/api/des/trace`
- **THEN** chỉ có một bản ghi mới với `cipher="des"`, `source="text"`, `operation="encrypt"`, `input_length=11`, `output_length=32`
- **AND** history không lưu text, khóa, IV, result hoặc warnings

#### Scenario: RSA success và error đều được ghi

- **WHEN** client gọi transform RSA thành công rồi một transform RSA lỗi validation
- **THEN** có hai row với đúng operation/status/succeeded tương ứng
- **AND** không có partial result hay error message trong row lỗi

#### Scenario: Keygen vẫn bị loại

- **WHEN** client gọi cả hai RSA keygen route và hai transform route
- **THEN** chỉ có hai row cho transform

### Requirement: Ghi lịch sử là best-effort

Việc ghi lịch sử MUST NOT thay đổi status, body hay header của response cipher. Khi DB lỗi, quá hạn 500 ms, `DATABASE_URL` không được đặt, hoặc schema cũ từ chối `rsa`, hệ thống SHALL bỏ qua bản ghi đó, chỉ log một cảnh báo không chứa dữ liệu người dùng hay chuỗi kết nối. Việc ghi SHALL diễn ra sau khi response đã gửi xong. (Truy vết: quyết định chủ sở hữu 2026-09-28 và Q16 ngày 2026-10-06)

#### Scenario: DB tắt khi đang encrypt

- **WHEN** DB đã cấu hình nhưng không kết nối được và client gọi `POST /api/caesar/encrypt` hợp lệ
- **THEN** response giống hệt khi không có DB
- **AND** log có một cảnh báo không chứa input, key hay chuỗi kết nối

#### Scenario: App chạy trước migration

- **WHEN** database ở revision `0003` và RSA transform thành công
- **THEN** response transform giống hệt khi history không được cấu hình
- **AND** row RSA có thể bị bỏ lỡ, với một warning generic không chứa content/key/connection string
