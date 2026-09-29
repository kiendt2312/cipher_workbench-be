## MODIFIED Requirements

### Requirement: Một tiến trình duy nhất phục vụ API

Ứng dụng SHALL phục vụ toàn bộ endpoint API, `/docs` và `/openapi.json` từ cùng một tiến trình, trên cùng một origin. Ứng dụng MUST NOT phục vụ giao diện web hay tài nguyên tĩnh của giao diện; UI thuộc project FE riêng. Cách tích hợp khuyến nghị là FE gọi đường dẫn tương đối `/api/...` qua proxy. Mặc định ứng dụng MUST NOT gửi header CORS. Khi biến môi trường `CORS_ALLOW_ORIGINS` chứa danh sách origin chính xác (scheme `http`/`https`, host, cổng tùy chọn, không path, không wildcard), ứng dụng SHALL chỉ cho phép đúng các origin đó, chỉ method `GET`/`POST`, chỉ request header `Content-Type`, expose `Content-Disposition` và MUST NOT cho phép credentials; giá trị không hợp lệ SHALL làm ứng dụng không khởi động. (Truy vết: quyết định chủ sở hữu 2026-09-28, 2026-09-29)

#### Scenario: Không còn giao diện ở tuyến gốc

- **WHEN** client gửi `GET /`
- **THEN** ứng dụng trả HTTP 404

#### Scenario: Không còn tài nguyên tĩnh

- **WHEN** client gửi `GET /static/app.js`
- **THEN** ứng dụng trả HTTP 404

#### Scenario: API không trả header CORS

- **WHEN** `CORS_ALLOW_ORIGINS` không được đặt
- **AND** client gọi một endpoint API
- **THEN** phản hồi không có header `access-control-allow-origin`

#### Scenario: Origin được phép nhận header CORS

- **WHEN** `CORS_ALLOW_ORIGINS=https://fe.example.com`
- **AND** client gửi request với `Origin: https://fe.example.com`
- **THEN** phản hồi có `access-control-allow-origin: https://fe.example.com` và `access-control-expose-headers: Content-Disposition`
- **AND** không có `access-control-allow-credentials`

#### Scenario: Origin khác không nhận header CORS

- **WHEN** `CORS_ALLOW_ORIGINS=https://fe.example.com`
- **AND** client gửi request với `Origin: https://evil.example.com`
- **THEN** phản hồi không có header `access-control-allow-origin`

#### Scenario: Cấu hình wildcard bị từ chối

- **WHEN** `CORS_ALLOW_ORIGINS=*`
- **THEN** ứng dụng không khởi động
