# hill-key-api Specification

## Purpose
Định nghĩa phân tích và sinh khóa Hill để FE hiển thị và kiểm tra khóa trước khi biến đổi. Nguồn: HTML Hill §§1–2, 4–8; quyết định chủ sở hữu Q4, Q8–Q9, Q13, Q16, Q18–Q19 ngày 2026-09-29.
## Requirements
### Requirement: Phân tích khóa qua POST

Hệ thống SHALL cung cấp `POST /api/hill/key/analyze` nhận JSON object đúng một trong `{key}` hoặc `{keyword,m}` với cùng quy tắc validate/chuẩn hóa khóa như encrypt/decrypt. Không nhận `text` hoặc `options`. Khóa hợp lệ trả HTTP 200 với `success:true`, `result` chứa đúng `matrix`, `m`, `det`, `gcd`, `detInverse`, `adjugate`, `inverse`, và `warnings` chứa W03 nếu khóa yếu. Khóa không khả nghịch trả E04 với det và gcd, không trả inverse giả. (Truy vết: HTML Hill §§1, 4, 7; quyết định chủ sở hữu Q4, Q8, Q9, Q16, Q18)

#### Scenario: Phân tích T01
- **WHEN** POST `{"key":[[3,3],[2,5]]}`
- **THEN** result có `matrix=[[3,3],[2,5]]`, `m=2`, `det=9`, `gcd=1`, `detInverse=3`, `adjugate=[[5,23],[24,3]]`, `inverse=[[15,17],[20,9]]`
- **AND** `warnings=[]`

#### Scenario: Khóa không khả nghịch
- **WHEN** POST `{"key":[[2,4],[1,3]]}`
- **THEN** HTTP 422/E04 với `details.det=2`, `details.gcd=2`

### Requirement: Sinh khóa qua GET với m bắt buộc

Hệ thống SHALL cung cấp `GET /api/hill/key/random?m=<2|3|4>`; `m` bắt buộc xuất hiện đúng một lần và phải là số nguyên ASCII trong khoảng 2–4, nếu không trả E08. Response thành công SHALL có `success:true`, `result` cùng schema phân tích khóa ở trên và `warnings` gồm W03 nếu khóa ngẫu nhiên tự nghịch đảo. Mọi khóa sinh ra SHALL khả nghịch và khác ma trận đơn vị; không có yêu cầu loại trừ khóa tự nghịch đảo. Endpoint SHALL không lưu trạng thái người dùng hoặc ghi lịch sử cipher. (Truy vết: HTML Hill §§5, 7–8; quyết định chủ sở hữu Q3, Q8, Q9, Q16, Q19)

#### Scenario: Sinh m=3
- **WHEN** GET `/api/hill/key/random?m=3`
- **THEN** HTTP 200 có ma trận 3×3 trong 0–25, `gcd(det,26)=1` và ma trận khác I

#### Scenario: Thiếu hoặc trùng m
- **WHEN** GET `/api/hill/key/random` hoặc `?m=2&m=3`
- **THEN** HTTP 422/E08

### Requirement: Hợp đồng phân tích khóa nhất quán

Ba nơi trả phân tích khóa (trường `key` của encrypt/decrypt, `result` của analyze/random) SHALL dùng cùng tên trường, cùng giá trị chuẩn hóa và cùng định nghĩa W03. Random SHALL dùng nguồn ngẫu nhiên phù hợp cho việc sinh khóa của công cụ học tập; tính khả nghịch luôn được kiểm tra trước khi trả, không dựa vào xác suất của một lần sinh. (Truy vết: HTML Hill §§1, 5, 7–8; quyết định chủ sở hữu Q8, Q9, Q16)

#### Scenario: Cùng khóa, cùng phân tích
- **WHEN** analyze và encrypt cùng nhận K T01
- **THEN** `analyze.result` bằng `encrypt.key`

