## Purpose

Định nghĩa hai endpoint JSON Columnar strict, gồm exact request shape, Unicode surrogate handling, validation key và OpenAPI không gây hiểu sai.

## ADDED Requirements

### Requirement: Hai endpoint text Columnar explicit

Hệ thống SHALL cung cấp chính xác `POST /api/columnar/encrypt` và `POST /api/columnar/decrypt`, cùng gọi Columnar core theo operation tương ứng. Hai route này cùng route file SHALL là ba route Columnar duy nhất và đưa tổng inventory cipher POST route từ 12 lên 15. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed Affine route inventory)

#### Scenario: Encrypt Columnar qua API
- **WHEN** client gửi `POST /api/columnar/encrypt` với `{"text":"ABCDE","key":"3 1 4 2"}`
- **THEN** hệ thống trả HTTP 200 với body đúng `{"success":true,"result":"BDAEC"}`

#### Scenario: Decrypt Columnar qua API
- **WHEN** client gửi `POST /api/columnar/decrypt` với `{"text":"BDAEC","key":"3 1 4 2"}`
- **THEN** hệ thống trả HTTP 200 với body đúng `{"success":true,"result":"ABCDE"}`

### Requirement: Text nhận JSON media type hiện hành

Hai route text SHALL nhận `application/json` và media type `application/*+json`, cho phép media type parameter hợp lệ theo baseline. Media type khác, body malformed, JSON không phải object hoặc framing không đọc được MUST trả HTTP 422 với canonical invalid-body error trước field validation. OpenAPI SHALL chỉ quảng bá `application/json`. (Truy vết: quyết định chủ sở hữu cho change này; baseline runtime JSON decoder và completed Affine text spec)

#### Scenario: Vendor JSON được runtime nhận
- **WHEN** client gửi object hợp lệ với `Content-Type: application/vnd.example+json`
- **THEN** request được xử lý như `application/json`

#### Scenario: JSON không phải object bị từ chối
- **WHEN** body là JSON array, scalar hoặc `null`
- **THEN** hệ thống trả HTTP 422 với `{"success":false,"message":"Dữ liệu gửi lên không hợp lệ."}`

### Requirement: JSON body có chính xác text và key

Request SHALL là object có đúng hai member `text` và `key`, mỗi member xuất hiện đúng một lần. Member lạ hoặc duplicate member MUST trả HTTP 422 `Dữ liệu gửi lên không hợp lệ.` trước validation `text` hoặc `key`. Strict shape này chỉ áp dụng cho hai route Columnar và MUST NOT siết schema của tám text route hiện hữu. (Truy vết: quyết định chủ sở hữu cho change này; baseline strict Affine decoder)

#### Scenario: Unknown field thắng lỗi field
- **WHEN** body có member lạ đồng thời `text` rỗng và `key` sai
- **THEN** hệ thống trả HTTP 422 với message `Dữ liệu gửi lên không hợp lệ.`

#### Scenario: Duplicate member bị từ chối
- **WHEN** JSON chứa hai member cùng tên `text` hoặc `key`
- **THEN** hệ thống trả HTTP 422 với message `Dữ liệu gửi lên không hợp lệ.`

### Requirement: Lone JSON surrogate bị từ chối ở body stage

Mọi lone high-surrogate hoặc low-surrogate xuất hiện qua JSON escape trong member name hay string value SHALL bị từ chối bằng HTTP 422 `Dữ liệu gửi lên không hợp lệ.` trước field validation. Một high-surrogate theo ngay bởi low-surrogate hợp lệ SHALL được giải mã thành một non-BMP Unicode code point rồi tham gia transform như một phần tử. Việc ghép JSON surrogate pair MUST không được coi là Unicode normalization. (Truy vết: quyết định chủ sở hữu cho change này)

#### Scenario: Lone surrogate thắng text và key
- **WHEN** object chứa lone surrogate đồng thời thiếu hoặc sai `text`/`key`
- **THEN** hệ thống trả canonical invalid-body 422

#### Scenario: Surrogate pair hợp lệ thành một code point
- **WHEN** `text` chứa JSON escape pair `\uD83D\uDE00`
- **THEN** core nhận đúng code point `U+1F600`
- **AND** round-trip trả lại cùng Unicode string

### Requirement: Text là string khác rỗng và không trim

`text` SHALL bắt buộc có mặt, là string và khác `""`. Thiếu, `null`, sai kiểu hoặc empty string MUST trả HTTP 422 `Văn bản không được để trống.`. Hệ thống MUST không trim; whitespace-only, CR/LF và non-leading `U+FEFF` đều hợp lệ và tham gia transform. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed text API)

#### Scenario: Empty text thắng key
- **WHEN** `text=""` đồng thời key thiếu hoặc không hợp lệ
- **THEN** hệ thống trả HTTP 422 với message `Văn bản không được để trống.`

#### Scenario: Whitespace-only là text hợp lệ
- **WHEN** `text` chỉ chứa ASCII whitespace và key hợp lệ
- **THEN** request thành công mà không trim text

### Requirement: Key JSON luôn là string

`key` SHALL bắt buộc là JSON string. Thiếu, `null` hoặc string rỗng sau ASCII trim MUST trả HTTP 422 `Thiếu khóa.`; mọi kiểu JSON không phải string MUST trả HTTP 422 `Khóa phải là chuỗi.`; string có mặt nhưng vi phạm length, grammar, permutation, keyword hoặc column-count contract MUST trả HTTP 422 với canonical Columnar invalid-key message. Không được coercion number, array, object hoặc boolean thành string. (Truy vết: quyết định chủ sở hữu cho change này; baseline string-key message style)

#### Scenario: Numeric JSON key không được coercion
- **WHEN** `key` là JSON number thay vì string
- **THEN** hệ thống trả HTTP 422 với `{"success":false,"message":"Khóa phải là chuỗi."}`

#### Scenario: Invalid content dùng message Columnar duy nhất
- **WHEN** `key` là string không rỗng nhưng không tạo thành numeric permutation hoặc ASCII keyword hợp lệ
- **THEN** hệ thống trả HTTP 422 với `{"success":false,"message":"Khóa Columnar phải là hoán vị 1..m hoặc từ khóa gồm 2 đến 256 chữ cái A-Z."}`

### Requirement: Success response đúng hai field

Request hợp lệ SHALL trả HTTP 200 với JSON đúng `{"success":true,"result":"<string>"}`. Response MUST NOT chứa parsed rank, normalized key, matrix, padding, analysis, `message`, `code`, `details` hoặc field khác; server result SHALL là authority. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed text API và guide FE)

#### Scenario: Keyword response không lộ rank
- **WHEN** client encrypt bằng keyword `BALLOON`
- **THEN** response chỉ có `success` và `result`
- **AND** không chứa rank `[2,1,3,4,6,7,5]` hay metadata khác

### Requirement: OpenAPI mô tả đúng text contract

OpenAPI SHALL gắn tag chính xác `Columnar Transposition` cho hai operation, quảng bá request `application/json` với object exact `text:string,key:string`, required cả hai và không additional properties. Mô tả `key` SHALL nêu hai dạng khóa, ASCII trim, post-trim limit 2.048, `2..256` cột, separators/brace và keyword ranking; SHALL có ví dụ numeric `3 1 4 2` và keyword `BALLOON` nhưng MUST không dùng `pattern`, `oneOf` hoặc raw `maxLength`. Responses SHALL gồm đúng 200/413/422/500 với success/error schema hiện hành. (Truy vết: quyết định chủ sở hữu cho change này; baseline runtime OpenAPI)

#### Scenario: OpenAPI key không gây hiểu sai
- **WHEN** client đọc schema của hai route text Columnar
- **THEN** `key` có `type:string`, prose và hai ví dụ `3 1 4 2`, `BALLOON`
- **AND** schema không có `pattern`, `oneOf` hoặc `maxLength`

#### Scenario: OpenAPI text response inventory
- **WHEN** client đọc responses của mỗi text operation Columnar
- **THEN** status được công bố chính xác là 200, 413, 422 và 500
