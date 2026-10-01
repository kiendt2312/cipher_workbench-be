# hill-text-cipher-api Specification

## Purpose
Định nghĩa hai API biến đổi text Hill và dữ liệu FE cần để giải thích từng bước. Nguồn: HTML Hill §§1, 4–7, 11; quyết định chủ sở hữu Q1–Q2, Q4–Q7, Q9, Q11, Q16–Q18 ngày 2026-09-29.
## Requirements
### Requirement: Hai endpoint biến đổi JSON tường minh

Hệ thống SHALL cung cấp đúng `POST /api/hill/encrypt` và `POST /api/hill/decrypt`, dùng chung core Hill theo operation của path. Hai endpoint nhận `application/json` và `application/*+json` hợp lệ như text route hiện hành; OpenAPI quảng bá `application/json`. Không có `/api/hill/file`; FE đọc `.txt` UTF-8 và gửi nội dung qua trường `text`. Không thêm generalized API hoặc thay đổi route của cipher khác. (Truy vết: HTML Hill §§1, 7; quyết định chủ sở hữu Q1, Q2; main spec `columnar-text-cipher-api` về media type)

#### Scenario: Encrypt T01
- **WHEN** POST `/api/hill/encrypt` với `{"text":"HELP","key":[[3,3],[2,5]]}`
- **THEN** HTTP 200 có `result="DPLE"` và các khối `[7,4]→[3,15]`, `[11,15]→[11,4]`

#### Scenario: Không có file route
- **WHEN** client gọi `POST /api/hill/file`
- **THEN** route không tồn tại; FE gửi chuỗi qua endpoint text sau khi đọc file

### Requirement: Request body có đúng một dạng khóa

Request encrypt/decrypt SHALL là một JSON object có đúng một trong hai dạng: `{text,key,options?}` hoặc `{text,keyword,m,options?}`. `key` là ma trận JSON; `keyword` là chuỗi; `m` chỉ xuất hiện cùng `keyword`. `text` SHALL là chuỗi JSON, không coerce kiểu. `options` nếu có SHALL là object chỉ có `stripDiacritics` boolean và `padChar` một ký tự uppercase ASCII A–Z; mặc định tương ứng `false` và `"X"`. Top-level member lạ/trùng hoặc có cả `key` lẫn `keyword` SHALL bị từ chối theo mã ở `hill-error-handling`. (Truy vết: HTML Hill §§4, 7; quyết định chủ sở hữu Q4, Q5, Q10, Q13, Q18)

#### Scenario: Keyword có m
- **WHEN** request dùng `{"text":"HILLCIPHER","keyword":"HILL","m":2}`
- **THEN** xử lý bằng K `[[7,8],[11,11]]` và trả `HOQBYAAPHL`

#### Scenario: Tùy chọn padding
- **WHEN** request encrypt `HELLO` với K T01 và `options.padChar="Q"`
- **THEN** phần văn bản chuẩn bị được đệm một Q và W01 nêu `char="Q"`

### Requirement: Giới hạn text đúng 5 MiB UTF-8

Sau khi JSON đã giải mã thành chuỗi, hệ thống SHALL đo `len(text.encode("utf-8"))` trên chuỗi gốc trước normalization, bỏ dấu, chuẩn bị khối và nhân ma trận. Đúng 5 MiB = `5 * 1024 * 1024` = 5.242.880 byte SHALL được nhận; 5.242.881 byte hoặc lớn hơn SHALL trả HTTP 413/E06 với `details.actualBytes` và `details.maxBytes=5242880` chính xác. Giới hạn này chỉ áp dụng Hill; file FE SHALL được kiểm theo byte gốc cùng ngưỡng, còn giới hạn và hành vi của năm file endpoint backend hiện có giữ nguyên. Request bị tầng guard chung 64 MiB chặn trước khi parse tiếp tục dùng response hạ tầng hiện hành. (Truy vết: quyết định chủ sở hữu ngày 2026-09-30 ghi đè giới hạn 1 MiB trong HTML Hill §§1, 6, 11 và quyết định Q1/Q6/Q11; `app/config.py` và `app/api/request_size_guard.py` cho baseline)

#### Scenario: Vượt một byte
- **WHEN** `text` ASCII dài 5.242.881 byte được gửi tới encrypt
- **THEN** HTTP 413/E06 với `details.actualBytes=5242881`, `details.maxBytes=5242880`, không có kết quả cipher

#### Scenario: Đúng giới hạn
- **WHEN** `text` hợp lệ có UTF-8 dài đúng 5.242.880 byte được gửi tới encrypt
- **THEN** request không bị từ chối bởi E06

#### Scenario: UTF-8 đa byte
- **WHEN** `text` gồm ký tự UTF-8 đa byte có số code point dưới 5.242.880 nhưng tổng byte là 5.242.881
- **THEN** HTTP 413/E06 với số byte thực tế chính xác

### Requirement: Success response Hill có dữ liệu giải thích

Encrypt/decrypt SHALL trả HTTP 200 với đúng năm trường top-level `success:true`, `result:string`, `blocks:array`, `key:object`, `warnings:array`. `blocks` SHALL liệt kê tất cả khối, mỗi item có đúng `input:number[m]`, `output:number[m]` theo A=0…Z=25 và thứ tự xử lý. `key` SHALL có `matrix`, `m`, `det`, `gcd`, `detInverse`, `adjugate`, `inverse`; ma trận và det đã chuẩn hóa mod 26. Mỗi warning SHALL có `code`, `message`, `details`; các warning phát sinh được sắp theo thứ tự W01, W02, W03. Không cắt bớt `blocks` theo độ dài text. Các response của năm cipher cũ SHALL giữ nguyên đúng hai trường. (Truy vết: HTML Hill §§1, 7, 11; quyết định chủ sở hữu Q2, Q7, Q9, Q16; main spec `columnar-text-cipher-api` về baseline cũ)

#### Scenario: Không có warning
- **WHEN** encrypt `HELP` với K T01
- **THEN** `warnings=[]`, `blocks` có đúng hai item và `key.matrix=[[3,3],[2,5]]`

#### Scenario: Padding và dấu Việt
- **WHEN** encrypt văn bản có số chữ lẻ và một chữ Việt có dấu được giữ nguyên
- **THEN** `warnings` chứa W01 rồi W02, mỗi warning có `code,message,details` và `blocks` gồm cả chữ đệm

### Requirement: OpenAPI và hợp đồng FE

OpenAPI SHALL gắn hai operation vào tag `Hill`, mô tả hai request variant, options/default, giới hạn 5 MiB, quy ước vector hàng, success schema mở rộng và error 413/422/500. Hướng dẫn FE SHALL mô tả cách đọc `.txt` UTF-8 ở client, kiểm đuôi file và byte length tối đa 5.242.880, xử lý E07 tại FE khi decode UTF-8 thất bại, gọi endpoint JSON, và dùng helper client Hill riêng để giữ `blocks/key/warnings` thay vì chỉ lấy chuỗi `result`. Không đổi `transformText` của năm cipher cũ. (Truy vết: quyết định chủ sở hữu ngày 2026-09-30; HTML Hill §§1, 6–7; quyết định Q1, Q2, Q6, Q9; `repo_docs/frontend-integration.md` và `repo_docs/examples/cipher-api.ts` baseline)

#### Scenario: E07 thuộc FE
- **WHEN** người dùng chọn `.txt` không đọc được UTF-8
- **THEN** FE hiển thị E07 và không gửi request Hill
- **AND** backend không khai báo E07 như response có thể phát sinh của bốn API Hill
