## Purpose

Định nghĩa hợp đồng HTTP JSON nghiêm ngặt cho hai endpoint Affine text, gồm exact body, integer không mất chính xác, validation xác định và response hai trường.

## ADDED Requirements

### Requirement: Hai endpoint text Affine explicit

Hệ thống SHALL cung cấp chính xác `POST /api/affine/encrypt` và `POST /api/affine/decrypt` cho text Affine. Hai route SHALL nhận `Content-Type: application/json`, gọi cùng Affine core theo đúng operation và đưa tổng số route cipher từ 9 lên 11 trước khi tính route file, không thêm route generalized hoặc versioned khác. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed `additional-text-cipher-api`)

#### Scenario: Encrypt Affine qua API
- **WHEN** client gửi `POST /api/affine/encrypt` với body `{"text":"HELLO","a":5,"b":8}`
- **THEN** hệ thống trả HTTP 200
- **AND** body là `{"success":true,"result":"RCLLA"}`

#### Scenario: Decrypt Affine qua API
- **WHEN** client gửi `POST /api/affine/decrypt` với body `{"text":"RCLLA","a":5,"b":8}`
- **THEN** hệ thống trả HTTP 200
- **AND** body là `{"success":true,"result":"HELLO"}`

### Requirement: JSON body có chính xác text a b

Request thành công SHALL có JSON object chứa chính xác ba member `text`, `a`, `b`, mỗi member xuất hiện đúng một lần. Member bổ sung, duplicate member, JSON không phải object, JSON malformed hoặc media type không phải `application/json`/`application/*+json` MUST bị từ chối theo body-framing contract trước field validation. Member thiếu MUST bị từ chối ở bước field tương ứng theo thứ tự `text → a → b`, để giữ message thiếu field đã đặc tả. Việc strict-field này chỉ áp dụng cho Affine mới và MUST NOT thay đổi cách 6 endpoint text hiện hữu xử lý field bổ sung. (Truy vết: quyết định chủ sở hữu cho change này; baseline runtime decoder/error handling)

#### Scenario: Field bổ sung bị từ chối
- **WHEN** body là `{"text":"HELLO","a":5,"b":8,"analysis":true}`
- **THEN** hệ thống trả HTTP 422 với body `{"success":false,"message":"Dữ liệu gửi lên không hợp lệ."}`

#### Scenario: JSON không phải object bị từ chối
- **WHEN** body JSON là một array hoặc scalar hợp lệ về cú pháp
- **THEN** hệ thống trả HTTP 422 với message `Dữ liệu gửi lên không hợp lệ.`

### Requirement: Text bắt buộc là string khác rỗng và không trim

Trường `text` SHALL bắt buộc có mặt và là string khác `""`. Thiếu, `null`, sai kiểu hoặc chuỗi rỗng MUST trả HTTP 422 với message `Văn bản không được để trống.`. Hệ thống MUST NOT trim; whitespace-only và newline-only SHALL hợp lệ. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed Caesar `text-cipher-api` và runtime)

#### Scenario: Empty text bị từ chối trước khóa
- **WHEN** body có `text=""`, đồng thời `a` và `b` cũng không hợp lệ
- **THEN** hệ thống trả HTTP 422 với message `Văn bản không được để trống.`

#### Scenario: Whitespace-only không bị trim
- **WHEN** body là `{"text":" \r\n","a":5,"b":8}`
- **THEN** request thành công và `result` là `" \r\n"`

### Requirement: a và b là true JSON integer không giới hạn JS safe integer

`a` và `b` SHALL là JSON integer token thật. Hệ thống MUST từ chối numeric string, float kể cả `5.0`, boolean, `null`, array, object và mọi kiểu khác; MUST không ép kiểu. JSON integer hợp lệ không bị giới hạn bởi JavaScript safe integer và SHALL được xử lý theo residue modulo 26 mà không phụ thuộc việc dựng một machine integer có kích thước giới hạn. FE MUST dùng serialization không làm mất chính xác cho giá trị ngoài safe range. (Truy vết: quyết định chủ sở hữu cho change này; baseline Caesar Week 1 `text-cipher-api` và integer-token design)

#### Scenario: Numeric string float và boolean bị từ chối
- **WHEN** `a` hoặc `b` lần lượt là `"5"`, `5.0`, `true` hoặc `false`
- **THEN** hệ thống trả HTTP 422 với message integer tương ứng cho field ưu tiên đầu tiên

#### Scenario: Integer ngoài JS safe range được chấp nhận
- **WHEN** client gửi integer token `9007199254741017` cho `a` và `9007199254740994` cho `b`, với residues tương ứng là `5` và `8`
- **THEN** hệ thống xử lý đúng như `(5,8)` mà không mất chính xác

#### Scenario: Integer rất dài được giảm modulo an toàn
- **WHEN** `a` hoặc `b` là JSON integer token hợp lệ dài hơn giới hạn chuyển đổi integer mặc định của runtime
- **THEN** hệ thống tính residue theo chữ số và không nới giới hạn an toàn toàn tiến trình

### Requirement: Cả a và b bắt buộc và không có server default

Hệ thống MUST yêu cầu cả `a` và `b` trên mọi request. Thiếu hoặc `null` ở `a` SHALL trả `Thiếu khóa a.`; thiếu hoặc `null` ở `b` SHALL trả `Thiếu khóa b.`. Giá trị có mặt nhưng sai kiểu SHALL lần lượt trả `Khóa a phải là số nguyên.` hoặc `Khóa b phải là số nguyên.`. UI có thể gợi ý `(5,8)` nhưng server MUST không điền default. (Truy vết: quyết định chủ sở hữu cho change này; baseline error message style)

#### Scenario: Thiếu a không dùng default demo
- **WHEN** body là `{"text":"HELLO","b":8}`
- **THEN** hệ thống trả HTTP 422 với message `Thiếu khóa a.`
- **AND** server không dùng `a=5`

#### Scenario: Thiếu b không dùng default demo
- **WHEN** body là `{"text":"HELLO","a":5}`
- **THEN** hệ thống trả HTTP 422 với message `Thiếu khóa b.`
- **AND** server không dùng `b=8`

### Requirement: a được kiểm tra khả nghịch trước b

Sau kiểm tra presence/type của `a`, hệ thống SHALL normalize `a` và từ chối residue không thỏa `gcd(a',26)=1` bằng HTTP 422 với message `Khóa a phải nguyên tố cùng nhau với 26.`. Lỗi `a` MUST được trả trước mọi lỗi `b`; `b` chỉ cần là integer và không có policy gcd. (Truy vết: quyết định chủ sở hữu cho change này; `affine-cipher.html` điều kiện khóa)

#### Scenario: Invalid a thắng lỗi b
- **WHEN** body có `a=2` và thiếu `b`
- **THEN** hệ thống trả HTTP 422 với message `Khóa a phải nguyên tố cùng nhau với 26.`

#### Scenario: b bất kỳ được chuẩn hóa
- **WHEN** body có `a=5` và `b=-18`
- **THEN** request dùng `b'=8` và không từ chối vì dấu hoặc độ lớn

### Requirement: Success response và server authority

Request hợp lệ SHALL trả HTTP 200 và JSON đúng hai field `success=true`, `result=<string>`. Response MUST NOT chứa normalized key, inverse, formula steps, analysis metadata, `message`, `code`, `details` hoặc field khác. Server result SHALL là nguồn chính thức; computation trong demo/client không có quyền runtime. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed `additional-text-cipher-api` và guide FE)

#### Scenario: Unicode success envelope không có metadata
- **WHEN** client encrypt `Hé🙂z!` với `(5,8)`
- **THEN** body đúng bằng `{"success":true,"result":"Ré🙂d!"}`

### Requirement: OpenAPI mô tả exact Affine text contract

OpenAPI SHALL công bố hai route Affine text với request object required gồm `text:string`, `a:integer`, `b:integer`, không cho additional properties, và response 200/413/422/500 theo envelope hiện hành. OpenAPI MUST không công bố default cho `a` hoặc `b`. (Truy vết: quyết định chủ sở hữu cho change này; baseline runtime `/openapi.json`)

#### Scenario: OpenAPI không có key default
- **WHEN** client đọc `/openapi.json`
- **THEN** cả hai operation Affine text yêu cầu `text`, `a`, `b`
- **AND** schema không có default `5` hoặc `8`

### Requirement: Sáu endpoint text hiện hữu không thay đổi

Việc thêm Affine MUST NOT thay đổi path, request schema, acceptance of existing fields, result, status, error message hoặc validation precedence của các endpoint text Caesar, Vigenère và Playfair. (Truy vết: quyết định chủ sở hữu cho change này; completed changes Caesar và Playfair/Vigenère)

#### Scenario: Regression text ba cipher hiện hữu
- **WHEN** toàn bộ request acceptance hiện tại của sáu endpoint text được chạy sau change
- **THEN** mọi response quan sát được giống baseline trước change
