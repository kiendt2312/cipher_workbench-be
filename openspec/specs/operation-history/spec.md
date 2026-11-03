# operation-history Specification

## Purpose

Định nghĩa việc ghi lịch sử thao tác cipher dưới dạng metadata, ranh giới dữ liệu tuyệt đối không được lưu, và hành vi khi DB lỗi.

## Requirements

### Requirement: Bảng cipher_operations chỉ chứa metadata

SQLite SHALL lưu lịch sử trong bảng `cipher_operations` với đúng 11 cột logic và không thêm cột payload: `id` (SQLite `INTEGER PRIMARY KEY AUTOINCREMENT`, dương, không tái sử dụng, tối đa `2^63-1`), `created_at` (số nguyên 64-bit biểu diễn epoch microsecond UTC), `cipher` (text, CHECK thuộc `caesar`, `vigenere`, `playfair`, `affine`, `columnar`, `hill`, `des`, `rsa`, `dh`), `operation` (text nullable), `source` (text, CHECK thuộc `text`, `file`), `response_mode` (text nullable, CHECK thuộc `content`, `file`), `input_length` (integer nullable, ≥ 0), `output_length` (integer nullable, ≥ 0), `http_status` (integer), `succeeded` (integer CHECK thuộc `0`, `1`) và `duration_ms` (integer, ≥ 0). CHECK `operation` SHALL cho phép `encrypt`, `decrypt`, `validate_params`, `generate_params`, `generate_keypair`, `derive_shared_secret`, `exchange`; năm operation DH standalone mới chỉ hợp lệ khi `cipher="dh"`. `private_history_records` SHALL nhận cùng các operation đó và tiếp tục chỉ cho `sign|verify` khi `cipher="rsa"`. SQLite sequence SHALL bắt đầu sau cả max row ID và PostgreSQL identity high-water đã từng cấp. Bảng SHALL có index `(created_at, id)` và `(cipher, created_at, id)`. Adapter SHALL giữ UTC/precision/order của API và cursor. Migration mới SHALL chỉ nới CHECK, giữ mọi row, cột, index và sequence; PostgreSQL revisions MUST không chạy trên SQLite; downgrade MUST fail trước mutation nếu còn row dùng operation mới. Runtime và continuity registries SHALL cùng nhận `dh`. (Truy vết: main spec `operation-history`; quyết định chủ sở hữu Q3 ngày 2026-09-29, Q12 ngày 2026-10-01, Q16 ngày 2026-10-06; quyết định chủ sở hữu 2026-10-07; quyết định chủ sở hữu 2026-10-12 đảo D8; ngoại lệ hạ tầng được chủ sở hữu phê duyệt)

#### Scenario: Schema SQLite sau migration
- **WHEN** chạy SQLite migration từ `sqlite_0003` tới head
- **THEN** cả `cipher_operations` và `private_history_records` nhận năm operation DH mới
- **AND** mọi cột, index, row và sequence trước migration được giữ nguyên

#### Scenario: Schema sau migration
- **WHEN** chạy migration SQLite tới head
- **THEN** bảng `cipher_operations` có đúng 11 cột logic, các CHECK constraint và hai index đã định nghĩa
- **AND** CHECK `cipher` cho phép đủ `caesar`, `vigenere`, `playfair`, `affine`, `columnar`, `hill`, `des`, `rsa` và `dh`, vẫn chặn tên cipher lạ

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

#### Scenario: ID không tái sử dụng
- **WHEN** row có ID lớn nhất bị xóa rồi một row mới được thêm
- **THEN** ID mới lớn hơn mọi ID đã từng được cấp và vẫn nằm trong `1..2^63-1`

#### Scenario: High-water lớn hơn max row còn lại
- **WHEN** PostgreSQL identity đã cấp ID cao hơn max ID còn tồn tại do retention/delete
- **THEN** row SQLite mới đầu tiên có ID lớn hơn identity high-water nguồn, không chỉ lớn hơn max row được import

#### Scenario: UTC và thứ tự không đổi
- **WHEN** hai row có timestamp UTC khác nhau hoặc cùng timestamp nhưng khác ID được đọc qua `GET /api/history`
- **THEN** API trả `createdAt` ISO 8601 UTC và sắp giảm dần theo timestamp rồi ID

#### Scenario: Cursor cũ vẫn dùng được sau cutover
- **WHEN** client dùng cursor hợp lệ đã được cấp từ dữ liệu PostgreSQL trước cutover và các row đó đã được migrate giữ nguyên ID/thời điểm
- **THEN** trang SQLite bắt đầu đúng sau tuple của cursor, không lặp hoặc bỏ row do đổi precision/timezone

#### Scenario: Continuity registries nhận DH
- **WHEN** export/import hoặc verify continuity gặp row `cipher="dh"`
- **THEN** row được chấp nhận và đối soát như tám cipher trước đó
- **AND** staging schema không tạo generic DH route nào

#### Scenario: Downgrade không xóa DH âm thầm
- **WHEN** một trong hai bảng còn row dùng `cipher="dh"` hoặc operation DH standalone và downgrade về revision không cho phép chúng
- **THEN** downgrade thất bại trước khi rebuild bảng
- **AND** không row, index hoặc sequence nào bị xóa hay sửa

### Requirement: Không bao giờ lưu nội dung hay dữ liệu định danh

Hệ thống MUST NOT lưu plaintext, ciphertext, key (kể cả `a`, `b`, `p`, `q`, `e`, `d`, private/public key và DH q/alpha/X/Y/K), tên file, nội dung file, request `data`, cipher array, `textMetadata`, `originalUtf8ByteLength`, trace (kể cả per-bit/Euclid/modPow), warning, header request, IP, user agent hay message lỗi. Chỉ các cột metadata chuẩn hiện hữu được dùng. Độ dài SHALL là số Unicode code point cho nguồn text và số byte cho nguồn file. Với nguồn file truyền thống, cả `input_length` lẫn `output_length` SHALL tính UTF-8 BOM nếu file đầu vào có BOM, ở cả hai `response_mode`. Với RSA, phía cipher array SHALL là NULL: JSON text encrypt chỉ `input_length` MAY được đặt; JSON text decrypt chỉ `output_length` MAY được đặt; number để hai length NULL; multipart encrypt chỉ `input_length` MAY là raw byte gồm BOM. DH standalone SHALL chỉ lưu operation/status/timing và metadata route; `response_mode`, `input_length`, `output_length` SHALL là NULL. DH Caesar giữ length semantics hiện hữu. (Truy vết: quyết định chủ sở hữu 2026-09-28, Q16 ngày 2026-10-06; Tài liệu thuật toán DH §§2,4; Scope DH §Phạm vi; quyết định chủ sở hữu 2026-10-12)

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

### Requirement: Ghi một bản ghi cho mỗi request cipher

Hệ thống SHALL ghi đúng một row owner-scoped cho mỗi request tới 28 matcher route: `POST /api/{caesar|vigenere|playfair|affine|columnar|des}/{encrypt|decrypt|file}`, `POST /api/hill/{encrypt|decrypt}`, `POST /api/rsa/{encrypt|decrypt}` và sáu route `POST /api/dh/*`, kể cả request lỗi 413/415/422/500. `cipher` và `source` SHALL suy ra từ path/media type. `operation` SHALL lấy từ path với route text, và từ trường `action` đã validate với route file truyền thống; nếu request lỗi trước khi biết operation thì `operation` là NULL. `input_length`/`output_length` là NULL khi chưa xác định được. Hill và DES giữ nguyên semantics metadata hiện hành. RSA encrypt JSON có `source="text"`, RSA encrypt multipart có `source="file"`, RSA decrypt có `source="text"`; RSA luôn `response_mode=NULL` và length theo requirement không lưu dữ liệu ở trên. Năm route DH standalone SHALL map exact path sang operation ổn định; `/api/dh/caesar` SHALL giữ operation theo action sau validation, `source` từ media type và `response_mode=NULL`; matcher SHALL là exact special-case, không qua generic DH route generator. Request tới route khác, gồm Hill key routes, DES trace, hai RSA keygen route, OpenAPI, health và history, MUST NOT được ghi. (Truy vết: main spec `operation-history`; quyết định chủ sở hữu Q3, Q9, Q16 ngày 2026-09-29; Q12 ngày 2026-10-01; Q16 ngày 2026-10-06; Tài liệu thuật toán DH §11; Scope DH §API; quyết định chủ sở hữu 2026-10-12 đảo D8)

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

#### Scenario: RSA keygen không được ghi
- **WHEN** client gọi cả hai RSA keygen route và hai transform route
- **THEN** chỉ có hai row cho transform

#### Scenario: Sáu route DH đều được ghi
- **WHEN** client gọi thành công `/params`, `/params/random`, `/keypair`, `/shared-secret`, `/exchange` và `/caesar` dưới prefix `/api/dh`
- **THEN** có đúng sáu row mới với `cipher="dh"`
- **AND** operation lần lượt là `validate_params`, `generate_params`, `generate_keypair`, `derive_shared_secret`, `exchange` và action `encrypt|decrypt` của Caesar

#### Scenario: Exact matcher
- **WHEN** client gọi method khác POST hoặc path gần giống như `/api/dh/exchanges`
- **THEN** request đó không tạo history row

#### Scenario: DH Caesar JSON và multipart
- **WHEN** gọi `/api/dh/caesar` một lần JSON và một lần multipart
- **THEN** có hai row với source lần lượt `text` và `file`, operation theo action, response_mode null

### Requirement: Ghi lịch sử là best-effort

Việc ghi lịch sử MUST NOT thay đổi status, body hay header của response cipher. Khi SQLite lỗi, read-only, đầy đĩa, bị khóa, quá hạn 500 ms, `DATABASE_URL` không được đặt, hoặc schema chưa sẵn sàng nhận `rsa`/`dh`/operation mới, hệ thống SHALL bỏ qua row đó và chỉ log một cảnh báo không chứa dữ liệu người dùng, chuỗi kết nối hay đường dẫn file. Việc ghi SHALL diễn ra sau khi response đã gửi xong. Semantics này áp dụng cho toàn bộ route đang có hiệu lực, gồm hai RSA transform và cả sáu route DH; RSA keygen tiếp tục không ghi history và không lỗi storage nào được làm thay đổi safe best-effort transform response. (Truy vết: quyết định chủ sở hữu 2026-09-28, Q16 ngày 2026-10-06; quyết định chủ sở hữu 2026-10-07; quyết định chủ sở hữu 2026-10-12)

#### Scenario: DB tắt khi đang encrypt
- **WHEN** SQLite đã cấu hình nhưng không mở/ghi được và client gọi `POST /api/caesar/encrypt` hợp lệ
- **THEN** response giống hệt khi không có DB
- **AND** log có một cảnh báo không chứa input, key, chuỗi kết nối hay đường dẫn

#### Scenario: SQLite bị khóa khi đang encrypt
- **WHEN** SQLite được cấu hình nhưng lock cạnh tranh kéo dài quá giới hạn và client gọi `POST /api/caesar/encrypt` hợp lệ
- **THEN** response giống hệt khi không có DB
- **AND** log chỉ có cảnh báo generic không chứa input, key, URL hay đường dẫn

#### Scenario: Hết dung lượng khi ghi RSA
- **WHEN** hai RSA transform tạo response nhưng SQLite không thể commit vì hết dung lượng
- **THEN** response transform giữ nguyên status, body và header
- **AND** row history có thể bị bỏ lỡ, không có content/key/trace/error message được persist hoặc log

#### Scenario: App chạy trước migration
- **WHEN** database ở revision chưa cho phép `rsa` và RSA transform thành công
- **THEN** response transform giống hệt khi history không được cấu hình
- **AND** row RSA có thể bị bỏ lỡ, với một warning generic không chứa content/key/connection string

#### Scenario: App chạy trước migration operation DH
- **WHEN** app mới chạy trên schema chưa nhận operation DH standalone và một request DH standalone thành công
- **THEN** response DH giữ nguyên
- **AND** row có thể bị bỏ lỡ với warning không chứa path DB, connection string hoặc dữ liệu DH

#### Scenario: SQLite lỗi khi ghi DH
- **WHEN** SQLite không thể commit một row DH
- **THEN** response endpoint không đổi
- **AND** không bí mật hoặc chi tiết exception xuất hiện trong log
