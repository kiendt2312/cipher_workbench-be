# Spec Delta

## MODIFIED Requirements

### Requirement: Cấu hình DB qua biến môi trường và tùy chọn

Hệ thống SHALL đọc storage runtime từ biến môi trường `DATABASE_URL`. Giá trị runtime được hỗ trợ SHALL là URL `sqlite+aiosqlite` trỏ tới file tuyệt đối trên filesystem cục bộ của backend; URL tương đối, database in-memory và dialect khác MUST bị từ chối khi khởi động. Preflight Linux SHALL canonicalize path, từ chối symlink ngoài data root, kiểm tra parent/quyền và từ chối filesystem remote đã nhận diện; nếu không xác định được mount an toàn thì SHALL fail-closed. Khi biến rỗng, hệ thống SHALL khởi động bình thường, không mở DB. Chuỗi kết nối và đường dẫn tuyệt đối MUST NOT xuất hiện trong log/response/OpenAPI. Đây là ngoại lệ hạ tầng được chủ sở hữu phê duyệt ngày 2026-10-07. (Truy vết: quyết định chủ sở hữu 2026-10-07; quyết định chủ sở hữu 2026-09-28 về chế độ DB tùy chọn)

#### Scenario: Không có DATABASE_URL

- **WHEN** app khởi động mà không đặt `DATABASE_URL`
- **THEN** app khởi động thành công
- **AND** `POST /api/caesar/encrypt` với input hợp lệ trả kết quả giống hệt trước change

#### Scenario: SQLite cục bộ hợp lệ

- **WHEN** `DATABASE_URL` là URL `sqlite+aiosqlite` tới file tuyệt đối nằm trên filesystem cục bộ ghi được của backend
- **THEN** app khởi động và dùng đúng file đó cho history

#### Scenario: Storage runtime không được hỗ trợ

- **WHEN** `DATABASE_URL` là URL PostgreSQL, SQLite in-memory, đường dẫn tương đối, symlink thoát data root hoặc path trên network filesystem đã nhận diện
- **THEN** app không khởi động và báo lỗi cấu hình generic
- **AND** log không chứa chuỗi kết nối hay đường dẫn tuyệt đối

#### Scenario: Không xác định được mount an toàn

- **WHEN** preflight trên deployment Linux không xác định được filesystem của data path là local
- **THEN** app fail-closed trước khi mở SQLite và không tự tạo file

#### Scenario: Chuỗi kết nối không lộ ra ngoài

- **WHEN** file SQLite không thể mở và client gọi `GET /api/health` trong trường hợp app vẫn đang phục vụ
- **THEN** body response không chứa đường dẫn file hay chuỗi `DATABASE_URL`

### Requirement: Vòng đời engine qua lifespan

Khi `DATABASE_URL` được đặt hợp lệ, hệ thống SHALL tạo đúng một async engine SQLAlchemy cho SQLite trong lifespan startup và SHALL dispose engine khi shutdown. Runtime được hỗ trợ SHALL là một tiến trình backend dùng một pool kết nối bị giới hạn để tuần tự hóa thao tác ghi vào một file cục bộ; triển khai nhiều backend process hoặc nhiều máy cùng mở file nằm ngoài phạm vi hỗ trợ. App SHALL không tự tạo file rỗng nếu database chưa tồn tại và SHALL vẫn phục vụ route cipher khi file/schema tạm thời không sẵn sàng; lỗi đó chỉ được phản ánh qua health/history và MUST NOT đổi response cipher. (Truy vết: quyết định chủ sở hữu 2026-10-07 về một backend và SQLite cục bộ; quyết định chủ sở hữu 2026-09-28 về lifespan/best-effort)

#### Scenario: DB chưa sẵn sàng lúc khởi động

- **WHEN** `DATABASE_URL` hợp lệ nhưng file SQLite không tồn tại, không đọc được hoặc chưa có schema head và app khởi động
- **THEN** app không tự tạo/ghi đè file và vẫn phục vụ route cipher
- **AND** `GET /api/health` báo database `unavailable` và history trả lỗi hiện hành

#### Scenario: Engine được dispose

- **WHEN** app khởi động rồi shutdown với SQLite đã cấu hình
- **THEN** đúng một engine được tạo và được dispose khi shutdown

#### Scenario: File tạm thời bị khóa sau startup

- **WHEN** một lock cạnh tranh làm thao tác history không hoàn thành trong giới hạn cho phép
- **THEN** route cipher vẫn trả status, body và header như khi history không được cấu hình
- **AND** health/history phản ánh DB không khả dụng theo contract hiện hành nếu probe tương ứng thất bại

#### Scenario: Nhiều process không thuộc cấu hình hỗ trợ

- **WHEN** operator cấu hình nhiều backend process cùng mở một file SQLite
- **THEN** tài liệu vận hành và kiểm tra cấu hình nêu rõ cấu hình này không được hỗ trợ

### Requirement: Migration bằng Alembic, tách khỏi startup

Schema SQLite SHALL được quản lý bằng một Alembic migration root/baseline riêng cho SQLite và MUST NOT chạy nối tiếp các revision PostgreSQL `0001`–`0004` trên file SQLite. App MUST NOT tự tạo, tự migrate, stamp hoặc ghi đè database khi khởi động. Migration SQLite SHALL chạy bằng lệnh riêng trước app, SHALL có thể chạy lặp lại an toàn trên database đã ở head, và downgrade phá hủy dữ liệu MUST NOT là một bước rollback vận hành tự động. Chuỗi migration PostgreSQL hiện hữu SHALL được giữ nguyên để đọc nguồn, đối soát và rollback. (Truy vết: quyết định chủ sở hữu 2026-10-07 về bảo toàn dữ liệu/DB cũ; Alembic 1.20 batch guidance; quyết định chủ sở hữu 2026-09-28 về migration tách startup)

#### Scenario: Tạo SQLite mới

- **WHEN** chạy migration SQLite tới head trên file đích mới
- **THEN** schema history được tạo đúng một lần và revision SQLite ở head

#### Scenario: Chạy migration lặp lại

- **WHEN** chạy migration SQLite tới head lần nữa trên file đã ở head
- **THEN** lệnh thành công và không xóa, nhân đôi hay thay đổi row history

#### Scenario: Không chạy migration PostgreSQL trên SQLite

- **WHEN** operator chuẩn bị một file SQLite mới theo tài liệu
- **THEN** không revision PostgreSQL `0001`–`0004` nào được thực thi hoặc giả stamp trên file đó

#### Scenario: Upgrade rồi downgrade

- **WHEN** trên một SQLite disposable trống, test chạy migration tới head rồi explicit downgrade theo migration SQLite
- **THEN** hai chiều migration chạy theo contract được test và không gọi revision PostgreSQL
- **AND** thao tác downgrade phá hủy này không xuất hiện trong runbook rollback production

#### Scenario: App không tự sửa schema

- **WHEN** app khởi động với file chưa migrate hoặc sai revision
- **THEN** app không tự tạo/sửa bảng và không ghi đè file
- **AND** lỗi được báo generic mà không lộ đường dẫn

### Requirement: docker-compose cho môi trường local

Repository SHALL có `docker-compose.yml` chạy migration SQLite một lần rồi chạy đúng một process `app`, cùng mount một named volume/thư mục dữ liệu cục bộ vào đường dẫn ghi được ổn định. Stack mặc định MUST NOT khởi động PostgreSQL. Service `app` SHALL publish cổng container `8000` ra máy host ở `${APP_HOST_PORT:-8080}` và frontend SHALL tiếp tục chỉ gọi HTTP API. Compose MUST NOT tự động xóa volume PostgreSQL cũ; nếu còn service PostgreSQL để export/rollback thì service đó SHALL ở profile legacy không khởi động mặc định. Retirement sau cutover SHALL dùng procedure project-scoped riêng, không gắn destructive cleanup vào startup/shutdown mặc định. (Truy vết: quyết định chủ sở hữu 2026-10-07 về hai máy/SQLite và quyết định retirement sau transfer thành công)

#### Scenario: Chạy stack SQLite mới

- **WHEN** chạy `docker compose up` theo tài liệu với volume dữ liệu mới
- **THEN** migration hoàn tất trước app và `GET http://localhost:8080/api/health` trả HTTP 200 với database `ok`
- **AND** restart/recreate container không làm mất row history đã ghi

#### Scenario: Chạy toàn bộ stack

- **WHEN** chạy `docker compose up` với cấu hình SQLite mẫu
- **THEN** `GET http://localhost:8080/api/health` trả HTTP 200 với database `ok`
- **AND** stack chỉ cần app, migrate tuần tự và volume SQLite trong đường chạy mặc định

#### Scenario: Stack mặc định không chạy PostgreSQL

- **WHEN** chạy compose mà không chọn profile legacy
- **THEN** không có PostgreSQL container nào được khởi động

#### Scenario: FE không truy cập file SQLite

- **WHEN** người dùng thao tác từ máy frontend
- **THEN** frontend chỉ gọi `/api/...` qua HTTP tới backend
- **AND** file/volume SQLite không được mount, copy hoặc expose sang máy frontend
