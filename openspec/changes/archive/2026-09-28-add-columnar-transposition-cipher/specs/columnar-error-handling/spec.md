## Purpose

Định nghĩa canonical error, validation precedence, request guards, safe logging và regression boundary cho ba route Columnar mới.

## ADDED Requirements

### Requirement: Error envelope đúng hai field

Mọi lỗi Columnar SHALL trả JSON đúng `{"success":false,"message":"<tiếng Việt>"}` với chính xác hai field. Response MUST NOT có `code`, `detail`, `details`, field path, parsed rank, key, matrix, stack trace hoặc metadata khác; lỗi ở `response_mode=file` cũng MUST không có attachment. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed Affine error handling)

#### Scenario: Một lỗi chỉ có envelope canonical
- **WHEN** một request Columnar thất bại ở bất kỳ validation stage nào
- **THEN** body chỉ chứa `success=false` và một `message` canonical

### Requirement: Canonical key messages

Columnar SHALL dùng chính xác: key thiếu, `null` hoặc empty sau ASCII trim → HTTP 422 `Thiếu khóa.`; key sai wire type → HTTP 422 `Khóa phải là chuỗi.`; key string vi phạm length, numeric grammar/permutation, keyword grammar hoặc `2..256` bound → HTTP 422 `Khóa Columnar phải là hoán vị 1..m hoặc từ khóa gồm 2 đến 256 chữ cái A-Z.`. (Truy vết: quyết định chủ sở hữu cho change này; baseline canonical missing/string-key messages)

#### Scenario: Invalid key content không lộ parser detail
- **WHEN** key có duplicate rank, malformed brace hoặc keyword sai grammar
- **THEN** response là canonical Columnar invalid-key 422
- **AND** message không nội suy raw key hay nguyên nhân parser nội bộ

### Requirement: Canonical body text và file messages

Body/framing/media/object/exact-shape/duplicate/surrogate invalid SHALL dùng HTTP 422 `Dữ liệu gửi lên không hợp lệ.`; text thiếu/null/rỗng/sai kiểu SHALL dùng HTTP 422 `Văn bản không được để trống.`. File SHALL kế thừa: missing file 422 `Thiếu file.`; extension 415 `Chỉ chấp nhận file .txt.`; size 413 `File vượt quá dung lượng tối đa 5 MB.`; zero byte 422 `File không được để trống.`; encoding 415 `File phải sử dụng UTF-8.`; read failure 500 `Không thể đọc file.`; unexpected failure 500 `Đã xảy ra lỗi hệ thống.`. Action/mode SHALL dùng canonical baseline messages. (Truy vết: quyết định chủ sở hữu cho change này; completed Caesar/Affine error contracts)

#### Scenario: Unexpected failure được che giấu
- **WHEN** lỗi không dự kiến xảy ra trong route Columnar
- **THEN** hệ thống trả HTTP 500 `{"success":false,"message":"Đã xảy ra lỗi hệ thống."}`

#### Scenario: Encoding error giữ mapping baseline
- **WHEN** Columnar file có filename/scalar fields hợp lệ nhưng bytes invalid UTF-8
- **THEN** hệ thống trả HTTP 415 `{"success":false,"message":"File phải sử dụng UTF-8."}`

### Requirement: Validation precedence text xác định

Hai endpoint text SHALL dừng ở đúng một lỗi ưu tiên cao nhất theo thứ tự: (1) global request-size guard; (2) media type, JSON syntax/framing/object, exact shape, duplicate field và surrogate validity; (3) `text`; (4) key missing/empty; (5) key wire type; (6) key content; (7) transform. (Truy vết: quyết định chủ sở hữu cho change này)

#### Scenario: Shape thắng text và key
- **WHEN** body có member lạ đồng thời text rỗng và key sai kiểu
- **THEN** hệ thống trả canonical invalid-body 422

#### Scenario: Text thắng key
- **WHEN** text rỗng đồng thời key thiếu hoặc không hợp lệ
- **THEN** hệ thống trả `Văn bản không được để trống.`

#### Scenario: Missing key thắng key type/content
- **WHEN** text hợp lệ và key vắng, `null` hoặc empty sau trim
- **THEN** hệ thống trả `Thiếu khóa.`

### Requirement: Validation precedence file xác định

Endpoint file SHALL dừng ở đúng một lỗi ưu tiên cao nhất theo thứ tự: (1) request-size và multipart-completion guards, multipart parse, exact shape và duplicate field; (2) file presence/type; (3) key missing/empty, wire type rồi content; (4) action; (5) response mode; (6) extension; (7) raw 5 MiB limit; (8) zero byte; (9) strict UTF-8; (10) transform. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed Affine file precedence)

#### Scenario: File thắng key action và extension
- **WHEN** multipart thiếu file đồng thời key/action sai
- **THEN** hệ thống trả `Thiếu file.`

#### Scenario: Key thắng action và extension
- **WHEN** file là `bad.md`, key content sai và action sai
- **THEN** hệ thống trả canonical Columnar invalid-key 422

#### Scenario: Response mode thắng extension
- **WHEN** file là `bad.md`, key/action hợp lệ và response mode sai
- **THEN** hệ thống trả `Response mode phải là content hoặc file.`

#### Scenario: Size thắng empty và encoding
- **WHEN** extension/scalars hợp lệ và raw file vượt 5 MiB dù content khác cũng invalid
- **THEN** hệ thống trả canonical file-too-large 413

### Requirement: Global request-size guard giữ trần 64 MiB

Theo ngoại lệ hạ tầng được chủ sở hữu phê duyệt, guard hiện hành SHALL áp trần không đổi 64 MiB cho ba route Columnar. Một `Content-Length` decimal hợp lệ duy nhất lớn hơn 64 MiB SHALL bị từ chối trước body read: file route dùng HTTP 413 `File vượt quá dung lượng tối đa 5 MB.`, hai text route dùng HTTP 413 `Yêu cầu vượt quá dung lượng cho phép.`. Header thiếu, trùng hoặc sai định dạng SHALL được chuyển tiếp như baseline. (Truy vết: ngoại lệ hạ tầng được chủ sở hữu phê duyệt; completed Affine guard contract)

#### Scenario: Columnar file vượt trần hạ tầng
- **WHEN** `/api/columnar/file` có một `Content-Length` hợp lệ lớn hơn 64 MiB
- **THEN** guard trả file-size 413 trước multipart parsing

#### Scenario: Columnar text vượt trần hạ tầng
- **WHEN** `/api/columnar/encrypt` có một `Content-Length` hợp lệ lớn hơn 64 MiB
- **THEN** guard trả generic request-size 413 trước JSON parsing

### Requirement: Multipart completion guard nhận diện đúng năm file route

Multipart completion guard và file-route classification SHALL áp dụng cho chính xác năm route file Caesar, Vigenère, Playfair, Affine và Columnar. Columnar multipart có boundary hợp lệ nhưng thiếu closing boundary SHALL trả HTTP 422 `Dữ liệu gửi lên không hợp lệ.` trước field validation. Threshold và behavior của bốn route cũ MUST không đổi. (Truy vết: quyết định chủ sở hữu cho change này; completed Affine guard contract)

#### Scenario: Columnar multipart bị cắt
- **WHEN** request `/api/columnar/file` kết thúc trước declared closing boundary
- **THEN** hệ thống trả canonical invalid-body 422 thay vì lỗi field

#### Scenario: Allowlist có đúng năm route
- **WHEN** guard route inventory được kiểm tra
- **THEN** tập file route gồm đúng Caesar, Vigenère, Playfair, Affine và Columnar file paths

### Requirement: Lỗi được log an toàn và xử lý stateless

Lỗi HTTP 500 Columnar SHALL được log với metadata kỹ thuật cần thiết nhưng MUST không log raw text, raw key, file content hoặc result. Hệ thống MUST không lưu input, key, file, parsed rank hoặc result sau response; preview và download SHALL là hai request độc lập. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed error handling/app runtime)

#### Scenario: Log 500 không chứa payload Columnar
- **WHEN** lỗi hệ thống xảy ra khi xử lý một payload có marker bí mật trong text, key, file hoặc result
- **THEN** log không chứa các marker đó

### Requirement: Mười hai route hiện hữu không thay đổi

Việc thêm Columnar MUST NOT thay đổi path, schema, acceptance, result, status, message, precedence, guard classification, OpenAPI behavior hoặc statelessness của 12 cipher POST route Caesar, Vigenère, Playfair và Affine. Toàn bộ app SHALL có chính xác 15 cipher POST routes sau change và không có generalized/versioned route mới. (Truy vết: quyết định chủ sở hữu cho change này; completed OpenSpec/runtime/tests hiện tại)

#### Scenario: Full regression mười hai route
- **WHEN** toàn bộ acceptance/error/guard/OpenAPI tests hiện hữu được chạy sau change
- **THEN** mọi test giữ nguyên kết quả
- **AND** route inventory chỉ tăng bằng ba path Columnar đã duyệt
