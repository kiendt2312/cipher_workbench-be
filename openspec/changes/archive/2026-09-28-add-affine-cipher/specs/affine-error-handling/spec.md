## Purpose

Định nghĩa error envelope, exact message/status, precedence và request guards cho ba route Affine mà không làm thay đổi contract lỗi của chín route hiện hữu.

## ADDED Requirements

### Requirement: Error envelope Affine đúng hai trường

Mọi lỗi Affine SHALL trả JSON đúng `{"success":false,"message":"<tiếng Việt>"}` với đúng hai field. Response MUST NOT có `code`, `detail`, `details`, field path, normalized key, inverse, analysis, stack trace hoặc metadata khác; lỗi trong `response_mode=file` cũng MUST là JSON và không có attachment. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed `additional-cipher-error-handling`)

#### Scenario: File mode lỗi vẫn là JSON
- **WHEN** request Affine `response_mode=file` có `a=2`
- **THEN** response là JSON lỗi HTTP 422
- **AND** không có `Content-Disposition: attachment`

### Requirement: Canonical message và status cho field Affine

Các lỗi Affine SHALL dùng chính xác mapping sau: body/framing/extra/duplicate field → HTTP 422 `Dữ liệu gửi lên không hợp lệ.`; text thiếu/null/rỗng/sai kiểu → HTTP 422 `Văn bản không được để trống.`; `a` thiếu/null/rỗng multipart → HTTP 422 `Thiếu khóa a.`; `a` sai integer type/grammar/length → HTTP 422 `Khóa a phải là số nguyên.`; `a'` không khả nghịch → HTTP 422 `Khóa a phải nguyên tố cùng nhau với 26.`; `b` thiếu/null/rỗng multipart → HTTP 422 `Thiếu khóa b.`; `b` sai integer type/grammar/length → HTTP 422 `Khóa b phải là số nguyên.`; action sai/thiếu → HTTP 422 `Action phải là encrypt hoặc decrypt.`; response mode sai → HTTP 422 `Response mode phải là content hoặc file.`. (Truy vết: quyết định chủ sở hữu cho change này; baseline message style và `affine-cipher.html` key rule)

#### Scenario: Invalid a message là static contract
- **WHEN** `a=13` sau body/text validation hợp lệ
- **THEN** response là HTTP 422 `{"success":false,"message":"Khóa a phải nguyên tố cùng nhau với 26."}`
- **AND** message không nội suy raw/normalized key hoặc gcd như demo

#### Scenario: b sai kiểu dùng message riêng
- **WHEN** JSON có `text="HELLO"`, `a=5`, `b="8"`
- **THEN** response là HTTP 422 `{"success":false,"message":"Khóa b phải là số nguyên."}`

### Requirement: Status và message file kế thừa baseline

Route file Affine SHALL trả HTTP 415 `Chỉ chấp nhận file .txt.` cho extension; HTTP 413 `File vượt quá dung lượng tối đa 5 MB.` cho content quá 5 MiB; HTTP 422 `File không được để trống.` cho 0 byte; HTTP 415 `File phải sử dụng UTF-8.` cho decode; HTTP 500 `Không thể đọc file.` cho lỗi đọc; và HTTP 500 `Đã xảy ra lỗi hệ thống.` cho lỗi không dự kiến. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed Caesar/Additional error handling)

#### Scenario: Encoding mapping giữ nguyên
- **WHEN** Affine file có extension hợp lệ nhưng bytes không phải UTF-8
- **THEN** hệ thống trả HTTP 415 với `{"success":false,"message":"File phải sử dụng UTF-8."}`

#### Scenario: Unexpected failure được che giấu
- **WHEN** một lỗi không dự kiến xảy ra trong route Affine
- **THEN** hệ thống trả HTTP 500 với message `Đã xảy ra lỗi hệ thống.`

### Requirement: Validation precedence text Affine xác định

Sau request-size guard, hai endpoint text SHALL dừng ở lỗi đầu tiên theo thứ tự: (1) media type/JSON syntax/object và member bổ sung/trùng; (2) `text` presence/type/non-empty; (3) `a` presence, integer type, normalize và gcd policy; (4) `b` presence, integer type và normalize; (5) content transformation. Hệ thống MUST trả đúng một message có priority cao nhất. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed text/error precedence)

#### Scenario: Body shape thắng text và key
- **WHEN** JSON có field thừa đồng thời text rỗng và khóa sai
- **THEN** hệ thống trả `Dữ liệu gửi lên không hợp lệ.`

#### Scenario: Text thắng a và b
- **WHEN** text rỗng, `a=2` và thiếu `b`
- **THEN** hệ thống trả `Văn bản không được để trống.`

#### Scenario: a thắng b
- **WHEN** text hợp lệ, `a=2` và `b` sai kiểu hoặc thiếu
- **THEN** hệ thống trả `Khóa a phải nguyên tố cùng nhau với 26.`

### Requirement: Validation precedence file Affine xác định

Sau request-size/multipart-completion guard, endpoint file SHALL dừng ở lỗi đầu tiên theo thứ tự: (1) multipart parse/exact allowed set/duplicate field; (2) file presence; (3) `a` presence, grammar/length, normalize và gcd; (4) `b` presence, grammar/length và normalize; (5) action presence/value; (6) response mode; (7) extension; (8) 5 MiB; (9) 0 byte; (10) UTF-8; (11) content transformation. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed file/error precedence)

#### Scenario: File presence thắng key
- **WHEN** multipart thiếu file đồng thời thiếu `a` và `b`
- **THEN** hệ thống trả HTTP 422 với message `Thiếu file.`

#### Scenario: a thắng b action và extension
- **WHEN** request có file `bad.md`, `a=2`, thiếu `b` và action sai
- **THEN** hệ thống trả HTTP 422 với message `Khóa a phải nguyên tố cùng nhau với 26.`

#### Scenario: b thắng action và extension
- **WHEN** request có file `bad.md`, `a=5`, `b=x` và action sai
- **THEN** hệ thống trả HTTP 422 với message `Khóa b phải là số nguyên.`

#### Scenario: Encoding được kiểm tra sau empty và size
- **WHEN** extension/keys/action/mode hợp lệ và file không rỗng/không quá 5 MiB nhưng bytes không phải UTF-8
- **THEN** hệ thống trả HTTP 415 với message `File phải sử dụng UTF-8.`

### Requirement: Request-size guard nhận diện ba route Affine

Theo ngoại lệ hạ tầng được chủ sở hữu phê duyệt, tầng request-size hiện hành SHALL áp trần không đổi 64 MiB cho các route mới. Một `Content-Length` decimal hợp lệ duy nhất lớn hơn 64 MiB SHALL bị từ chối trước body read: `/api/affine/file` dùng HTTP 413 `File vượt quá dung lượng tối đa 5 MB.`, còn hai route text dùng HTTP 413 `Yêu cầu vượt quá dung lượng cho phép.`. Header thiếu/trùng/sai định dạng vẫn được chuyển tiếp như baseline. (Truy vết: ngoại lệ hạ tầng được chủ sở hữu phê duyệt; completed `additional-cipher-error-handling` và runtime guard)

#### Scenario: Affine file vượt trần hạ tầng
- **WHEN** `/api/affine/file` có một `Content-Length` hợp lệ lớn hơn 64 MiB
- **THEN** guard trả HTTP 413 với file-size message trước multipart parsing

#### Scenario: Affine text vượt trần hạ tầng
- **WHEN** `/api/affine/encrypt` có một `Content-Length` hợp lệ lớn hơn 64 MiB
- **THEN** guard trả HTTP 413 với `Yêu cầu vượt quá dung lượng cho phép.` trước JSON parsing

### Requirement: Multipart completion guard nhận diện bốn route file

Multipart completion guard SHALL áp dụng cho chính xác bốn route file Caesar, Vigenère, Playfair và Affine. Affine multipart có boundary hợp lệ nhưng thiếu closing boundary SHALL trả HTTP 422 `Dữ liệu gửi lên không hợp lệ.` trước field validation. Threshold và behavior của ba route cũ MUST không đổi. (Truy vết: ngoại lệ hạ tầng được chủ sở hữu phê duyệt; completed `additional-cipher-error-handling`)

#### Scenario: Affine multipart bị cắt
- **WHEN** request `/api/affine/file` kết thúc trước declared closing boundary
- **THEN** hệ thống trả HTTP 422 với message `Dữ liệu gửi lên không hợp lệ.`
- **AND** không trả lỗi thiếu field từ body chưa hoàn chỉnh

### Requirement: Lỗi server được log an toàn và hệ thống stateless

Lỗi HTTP 500 Affine SHALL được log với endpoint, thời điểm, loại lỗi và traceback kỹ thuật nhưng MUST không log text, `a`, `b`, file content hoặc result. Request/result MUST không được lưu sau response. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed error handling/app runtime)

#### Scenario: Log 500 không chứa payload Affine
- **WHEN** lỗi hệ thống xảy ra khi xử lý Affine
- **THEN** log có metadata kỹ thuật cần thiết
- **AND** không chứa text, khóa, file content hoặc result của người dùng

### Requirement: Contract lỗi của chín route cũ không thay đổi

Việc thêm message, schema và route Affine MUST NOT sửa status, message, envelope, precedence, guard classification hoặc OpenAPI behavior của 9 route Caesar/Vigenère/Playfair. (Truy vết: quyết định chủ sở hữu cho change này; completed changes Caesar và Playfair/Vigenère)

#### Scenario: Full regression chín endpoint
- **WHEN** toàn bộ acceptance/error/guard tests của 9 route hiện hữu được chạy sau change
- **THEN** mọi test giữ nguyên kết quả
