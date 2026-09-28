## MODIFIED Requirements

### Requirement: Ứng dụng stateless, không lưu dữ liệu người dùng

Ứng dụng SHALL hoạt động stateless với nội dung người dùng: sau khi một request kết thúc, ứng dụng MUST KHÔNG lưu giữ văn bản đầu vào, key, tên file, file tải lên hay kết quả mã hóa/giải mã ở bất kỳ nơi nào có thể truy xuất lại, và MUST KHÔNG có phiên làm việc (session). Khi đặt `DATABASE_URL`, ứng dụng SHALL chỉ được lưu metadata thao tác theo capability `operation-history`, và chỉ đọc lại metadata đó qua `GET /api/history` theo `history-api` và `history-access`. Mỗi request SHALL được xử lý độc lập: hai request giống hệt nhau MUST cho kết quả giống hệt nhau, và kết quả của một request MUST KHÔNG bị ảnh hưởng bởi các request trước đó, bởi thứ tự gửi request hay bởi dữ liệu lịch sử. (Truy vết: docx §8; quyết định chủ sở hữu 2026-09-28)

#### Scenario: Hai request giống nhau cho kết quả giống nhau

- **WHEN** gửi cùng một request mã hóa hai lần liên tiếp
- **THEN** cả hai lần đều trả về cùng một kết quả và cùng HTTP status

#### Scenario: Request không bị ảnh hưởng bởi request trước đó

- **WHEN** gửi một request mã hóa với văn bản và khóa bất kỳ
- **AND** sau đó gửi một request khác với văn bản và khóa khác
- **THEN** kết quả của request sau chỉ phụ thuộc vào đầu vào của chính nó, không phụ thuộc vào request trước

#### Scenario: Không truy xuất lại được nội dung sau khi request kết thúc

- **WHEN** người dùng tải lên một file và nhận kết quả xử lý
- **THEN** ứng dụng không giữ lại file đã tải lên, key hay kết quả đó sau khi phản hồi được trả về
- **AND** không có endpoint nào trả lại nội dung của thao tác đã hoàn tất

#### Scenario: Lịch sử chỉ chứa metadata

- **WHEN** client đọc `GET /api/history` hoặc xem schema `HistoryItem` trong OpenAPI
- **THEN** không có trường nào chứa văn bản, key, `a`, `b`, tên file, nội dung file hay kết quả
- **AND** endpoint duy nhất liên quan tới lịch sử là `/api/history`
