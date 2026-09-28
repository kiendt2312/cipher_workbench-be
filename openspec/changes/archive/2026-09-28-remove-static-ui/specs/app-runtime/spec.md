## MODIFIED Requirements

### Requirement: Một tiến trình duy nhất phục vụ API

Ứng dụng SHALL phục vụ toàn bộ endpoint API, `/docs` và `/openapi.json` từ cùng một tiến trình, trên cùng một origin. Ứng dụng MUST NOT phục vụ giao diện web hay tài nguyên tĩnh của giao diện; UI thuộc project FE riêng. Ứng dụng SHALL KHÔNG cấu hình CORS: FE gọi API bằng đường dẫn tương đối `/api/...` qua proxy của dev server hoặc reverse proxy. (Truy vết: quyết định chủ sở hữu 2026-09-28)

#### Scenario: Không còn giao diện ở tuyến gốc

- **WHEN** client gửi `GET /`
- **THEN** ứng dụng trả HTTP 404

#### Scenario: Không còn tài nguyên tĩnh

- **WHEN** client gửi `GET /static/app.js`
- **THEN** ứng dụng trả HTTP 404

#### Scenario: API không trả header CORS

- **WHEN** client gọi một endpoint API
- **THEN** phản hồi không có header `access-control-allow-origin`

### Requirement: Ứng dụng lắng nghe cổng 8000

Ứng dụng SHALL lắng nghe trên cổng `8000` khi chạy ở máy local và khi chạy trong container. Tài liệu API và toàn bộ endpoint API MUST cùng được phục vụ trên cổng này; ứng dụng MUST KHÔNG dùng thêm cổng thứ hai. (Truy vết: docx §7)

#### Scenario: Truy cập ứng dụng chạy local qua cổng 8000

- **WHEN** ứng dụng được khởi chạy ở máy local
- **THEN** tài liệu API truy cập được tại `/docs` trên cổng `8000`
- **AND** các endpoint `/api/*` truy cập được trên cùng cổng `8000`

#### Scenario: Không có thành phần nào dùng cổng khác

- **WHEN** ứng dụng đang chạy và phục vụ tài liệu API và các endpoint API
- **THEN** tất cả đều truy cập được qua cổng `8000`

### Requirement: Chạy được bằng Docker với hành vi giống hệt local

Ứng dụng SHALL đóng gói và chạy được bằng Docker: từ mã nguồn trong repo có thể tạo được image và khởi chạy container mà không cần thao tác chuẩn bị thủ công nào ngoài các bước đã tài liệu hóa. Container đang chạy MUST phục vụ được `/docs` trên cổng `8000`, và hành vi quan sát được của ứng dụng — kết quả mã hóa/giải mã, HTTP status, cấu trúc phản hồi và thông báo lỗi — MUST giống hệt khi chạy local với cùng đầu vào. (Truy vết: docx §7)

#### Scenario: Truy cập ứng dụng chạy trong container

- **WHEN** image được tạo từ mã nguồn trong repo và container được khởi chạy
- **THEN** tài liệu API truy cập được tại `/docs` trên cổng `8000`

#### Scenario: Kết quả giống nhau giữa container và local

- **WHEN** gửi cùng một request tới ứng dụng chạy trong container và tới ứng dụng chạy local
- **THEN** hai phản hồi có cùng HTTP status, cùng cấu trúc và cùng nội dung kết quả

## REMOVED Requirements

### Requirement: Tuyến gốc trả về giao diện web

**Reason**: UI thuộc project FE riêng (quyết định chủ sở hữu 2026-09-28).
**Migration**: Dùng UI của project FE; xem API tại `/docs`.

## RENAMED Requirements

- FROM: `### Requirement: Một tiến trình duy nhất phục vụ cả giao diện lẫn API`
- TO: `### Requirement: Một tiến trình duy nhất phục vụ API`
