# Spec Delta

## MODIFIED Requirements

### Requirement: Bảng cipher_operations chỉ chứa metadata

SQLite SHALL giữ đúng 11 cột logic của active `migrate-history-to-sqlite` và cho phép `cipher` thuộc `caesar`, `vigenere`, `playfair`, `affine`, `columnar`, `hill`, `des`, `rsa`, `dh`. Migration `alembic_sqlite` SHALL chỉ nới CHECK, giữ mọi row/index/cột/sequence; PostgreSQL revisions MUST không chạy trên SQLite. Runtime và continuity registries SHALL cùng nhận `dh`. (Truy vết: cả hai tài liệu DH về không lưu khóa; active `migrate-history-to-sqlite`; quyết định owner D8)

#### Scenario: Schema sau migration
- **WHEN** chạy SQLite migration tới head từ baseline có RSA
- **THEN** bảng vẫn có đúng 11 cột logic và hai index hiện hữu
- **AND** CHECK cho phép cả `rsa` và `dh`, vẫn chặn tên lạ

#### Scenario: Migration giữ dữ liệu cũ
- **WHEN** SQLite có row của mọi cipher cũ và chạy migration DH
- **THEN** mọi row cũ còn nguyên và có thể insert `cipher="dh"`

#### Scenario: Migration DES
- **WHEN** source có bản ghi Caesar, Hill và DES rồi import vào SQLite
- **THEN** bản ghi cũ còn nguyên, có thể thêm bản ghi `cipher="des"` và CHECK vẫn chặn tên cipher lạ

#### Scenario: Continuity registries nhận DH
- **WHEN** export/import hoặc verify continuity gặp row `cipher="dh"`
- **THEN** row được chấp nhận và đối soát như tám cipher trước đó
- **AND** staging schema không tạo generic DH route nào

#### Scenario: Downgrade không xóa DH âm thầm
- **WHEN** bảng còn row `cipher="dh"` và downgrade về revision không cho phép DH
- **THEN** downgrade thất bại thay vì xóa/sửa row
- **AND** operator phải xử lý row theo chính sách dữ liệu trước khi retry

### Requirement: Không bao giờ lưu nội dung hay dữ liệu định danh

Hệ thống MUST NOT lưu plaintext, ciphertext, key (gồm p/q/e/d, DH q/alpha/X/Y/K), tên/nội dung file, request data, cipher arrays, trace, warning, header, IP, user agent hay message lỗi. Length giữ semantics hiện hữu; DH JSON dùng Unicode code point, DH file dùng raw/output UTF-8 bytes gồm BOM như Caesar content mode. (Truy vết: Tài liệu thuật toán DH §§2,4; Scope DH §Phạm vi; active SQLite `operation-history`; owner D8)

#### Scenario: Không lưu nội dung
- **WHEN** Vigenère encrypt `Attack at dawn!` với key `LEMON`
- **THEN** metadata lengths/status được ghi nhưng không cột nào chứa input, key hoặc result

#### Scenario: File có BOM
- **WHEN** Caesar nhận file gồm BOM và `é`
- **THEN** input/output length đều bằng 5 byte

#### Scenario: RSA không lưu cipher array
- **WHEN** RSA text transform thành công
- **THEN** row không chứa text, key, blocks, cipher array, length metadata hoặc trace

#### Scenario: DH JSON Caesar không lưu bí mật
- **WHEN** `/api/dh/caesar` JSON thành công với data `Hello World`
- **THEN** row chỉ có metadata chuẩn, input/output length bằng 11
- **AND** row không chứa q, private/public/shared key, shift, data, result, trace hoặc warning

#### Scenario: DH file có BOM
- **WHEN** DH Caesar nhận file gồm UTF-8 BOM và `é`
- **THEN** source là `file`, input/output length đều bằng 5 byte
- **AND** row không chứa filename hoặc file content

### Requirement: Ghi một bản ghi cho mỗi request cipher

Hệ thống SHALL ghi các transform route hiện hữu cùng đúng `/api/dh/caesar`, kể cả lỗi 413/415/422/500. DH source suy từ media type, operation từ action sau validation, `response_mode=NULL`; matcher SHALL là exact special-case, không qua generic DH route generator; năm DH route còn lại MUST không được ghi. (Truy vết: Tài liệu thuật toán DH §11; Scope DH §API; active SQLite `operation-history`; owner D8)

#### Scenario: Request lỗi vẫn được ghi
- **WHEN** Vigenère encrypt lỗi validation
- **THEN** có một row với status 422, succeeded false và output length null

#### Scenario: File lỗi trước khi validate action
- **WHEN** Caesar file lỗi trước khi action được validate
- **THEN** row có source file, status tương ứng và operation null

#### Scenario: Route không phải cipher
- **WHEN** gọi health hoặc root
- **THEN** không có row mới

#### Scenario: Hill chỉ ghi hai route biến đổi
- **WHEN** gọi Hill encrypt rồi hai key routes
- **THEN** chỉ có một row cho encrypt và không lưu data/key/result

#### Scenario: DES ghi route biến đổi, không ghi trace
- **WHEN** gọi DES encrypt rồi DES trace
- **THEN** chỉ có một row DES encrypt

#### Scenario: RSA keygen không được ghi
- **WHEN** gọi hai RSA keygen và hai RSA transform
- **THEN** chỉ có hai row transform

#### Scenario: Chỉ DH Caesar được ghi
- **WHEN** gọi thành công cả sáu endpoint DH
- **THEN** có đúng một row mới cho `/api/dh/caesar` với `cipher="dh"`
- **AND** params, params/random, keypair, shared-secret và exchange không tạo row

#### Scenario: DH Caesar JSON và multipart
- **WHEN** gọi `/api/dh/caesar` một lần JSON và một lần multipart
- **THEN** có hai row với source lần lượt `text` và `file`, operation theo action, response_mode null

### Requirement: Ghi lịch sử là best-effort

Việc ghi history MUST NOT đổi status/body/header. Khi SQLite lỗi, read-only, đầy đĩa, bị khóa, quá hạn 500 ms, không cấu hình DB, hoặc schema chưa nhận `dh`, hệ thống SHALL bỏ row và chỉ log warning không chứa dữ liệu, connection string hay file path; ghi diễn ra sau response. (Truy vết: cả hai tài liệu DH về dữ liệu bí mật; active SQLite `operation-history`; owner D8)

#### Scenario: DB tắt khi đang encrypt
- **WHEN** DB đã cấu hình nhưng không kết nối được và gọi cipher transform hợp lệ
- **THEN** response giống khi history tắt và log chỉ có warning an toàn

#### Scenario: App chạy trước migration DH
- **WHEN** database chưa cho phép `dh` và DH Caesar thành công
- **THEN** response DH không đổi dù row có thể bị bỏ lỡ
- **AND** warning không chứa q, keys, content hoặc connection string
