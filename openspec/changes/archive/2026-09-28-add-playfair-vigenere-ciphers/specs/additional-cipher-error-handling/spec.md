## Purpose

Chuẩn hóa lỗi của toàn bộ endpoint Playfair/Vigenère theo contract Caesar đã nghiệm thu, bổ sung message thuật toán cần thiết và mở rộng tầng bảo vệ request sang các route mới.

## ADDED Requirements

### Requirement: Error response luôn đúng hai trường và bằng tiếng Việt

Mọi lỗi từ sáu endpoint mới SHALL trả JSON đúng hai trường: `success` bằng `false` và `message` là chuỗi tiếng Việt dành cho người dùng cuối. Response MUST NOT có `code`, `detail`, danh sách lỗi field, `normalizedInput`, stack trace hoặc chi tiết kỹ thuật. Quy tắc này SHALL áp dụng cho JSON, multipart và cả request `response_mode=file`. (Truy vết: scope mới BE-VIG-05, BE-VIG-06, BE-PLAY-05, BE-PLAY-06; quyết định chủ sở hữu cho change này; baseline Caesar Week 1 `error-handling`)

#### Scenario: Validation error không có machine code
- **WHEN** một endpoint mới từ chối input bằng HTTP 422
- **THEN** body chỉ có `success` và `message`
- **AND** body không có `code` hoặc `detail`

#### Scenario: File mode lỗi vẫn trả JSON
- **WHEN** request file với `response_mode=file` gặp bất kỳ lỗi nào
- **THEN** hệ thống trả JSON error envelope
- **AND** không trả attachment hoặc header gợi ý download

### Requirement: Bảng message 422 dùng chung và theo thuật toán

Hệ thống SHALL dùng nguyên văn các message sau cho lỗi HTTP 422 tương ứng:

| Trường hợp | Message |
|---|---|
| Body JSON/multipart không đọc được | `Dữ liệu gửi lên không hợp lệ.` |
| Text thiếu, null, rỗng hoặc sai kiểu | `Văn bản không được để trống.` |
| Key thiếu, null hoặc chuỗi rỗng | `Thiếu khóa.` |
| Key JSON có giá trị nhưng không phải chuỗi | `Khóa phải là chuỗi.` |
| Key Vigenère chứa ký tự ngoài ASCII letter | `Khóa Vigenère chỉ được chứa chữ cái A-Z hoặc a-z.` |
| Key Playfair không còn ASCII letter sau normalize | `Khóa Playfair phải chứa ít nhất một chữ cái A-Z hoặc a-z.` |
| Playfair text không còn ASCII letter sau normalize | `Văn bản Playfair phải chứa ít nhất một chữ cái A-Z hoặc a-z.` |
| Playfair ciphertext có số chữ cái lẻ | `Bản mã Playfair phải chứa số lượng chữ cái chẵn.` |
| Playfair ciphertext có digraph trùng | `Bản mã Playfair không được chứa cặp hai chữ cái giống nhau.` |
| Action thiếu hoặc sai | `Action phải là encrypt hoặc decrypt.` |
| Response mode sai | `Response mode phải là content hoặc file.` |
| Thiếu file part | `Thiếu file.` |
| File 0 byte | `File không được để trống.` |

Các message mới trong bảng là quyết định contract của change này; các message kế thừa MUST giữ nguyên baseline. (Truy vết: scope mới BE-VIG-04, BE-VIG-05, BE-PLAY-04, BE-PLAY-05; quyết định chủ sở hữu cho change này; baseline Caesar Week 1 `error-handling`)

#### Scenario: Error example tiếng Anh trong scope không được trả ra ngoài
- **WHEN** key Vigenère có ký tự không hợp lệ
- **THEN** message là `Khóa Vigenère chỉ được chứa chữ cái A-Z hoặc a-z.`
- **AND** message không phải `Vigenère key must contain letters only.`

#### Scenario: Ciphertext Playfair lẻ dùng message canonical
- **WHEN** ciphertext Playfair sau normalization có số chữ cái lẻ
- **THEN** hệ thống trả HTTP 422
- **AND** message là `Bản mã Playfair phải chứa số lượng chữ cái chẵn.`

### Requirement: Ánh xạ status file giữ nguyên baseline

Hai endpoint file mới SHALL trả HTTP 415 với `Chỉ chấp nhận file .txt.` cho extension không hỗ trợ và `File phải sử dụng UTF-8.` cho encoding không hỗ trợ; HTTP 413 với `File vượt quá dung lượng tối đa 5 MB.` cho nội dung file vượt 5 MiB; HTTP 500 với `Không thể đọc file.` cho lỗi đọc file và `Đã xảy ra lỗi hệ thống.` cho lỗi hệ thống không dự kiến. Mọi trường hợp còn lại trong bảng 422 SHALL dùng HTTP 422. (Truy vết: scope mới BE-VIG-04, BE-VIG-05, BE-PLAY-04, BE-PLAY-05; baseline Caesar Week 1 `error-handling`)

#### Scenario: Encoding không hỗ trợ trả 415
- **WHEN** endpoint file không decode được bytes bằng UTF-8
- **THEN** hệ thống trả HTTP 415
- **AND** body là `{"success":false,"message":"File phải sử dụng UTF-8."}`

#### Scenario: Lỗi hệ thống được che giấu
- **WHEN** một lỗi không dự kiến xảy ra trong endpoint mới
- **THEN** hệ thống trả HTTP 500
- **AND** body là `{"success":false,"message":"Đã xảy ra lỗi hệ thống."}`

### Requirement: Trần request 64 MiB nhận diện các route mới

Theo ngoại lệ hạ tầng đã được chủ sở hữu phê duyệt trong Week 1 và được chấp nhận mở rộng cho change này, tầng 0 SHALL từ chối request có một `Content-Length` hợp lệ lớn hơn 64 MiB trước khi đọc body. Với `/api/vigenere/file` và `/api/playfair/file`, message SHALL là `File vượt quá dung lượng tối đa 5 MB.`; với bốn endpoint text mới, message SHALL là `Yêu cầu vượt quá dung lượng cho phép.`. Cả hai dùng HTTP 413 và error envelope hai trường. Trần 64 MiB MUST NOT thay đổi giới hạn nghiệp vụ file 5 MiB. (Truy vết: quyết định chủ sở hữu cho change này; ngoại lệ hạ tầng được chủ sở hữu phê duyệt trong baseline Caesar Week 1 `app-runtime`, `error-handling`)

#### Scenario: Request Vigenère file vượt trần hạ tầng
- **WHEN** request tới `/api/vigenere/file` có `Content-Length` lớn hơn 64 MiB
- **THEN** tầng 0 trả HTTP 413 trước khi parse multipart
- **AND** message là `File vượt quá dung lượng tối đa 5 MB.`

#### Scenario: Request Playfair text vượt trần hạ tầng
- **WHEN** request tới `/api/playfair/encrypt` có `Content-Length` lớn hơn 64 MiB
- **THEN** tầng 0 trả HTTP 413 trước khi parse JSON
- **AND** message là `Yêu cầu vượt quá dung lượng cho phép.`

### Requirement: Multipart completion guard nhận diện ba route file

Tầng kiểm tra multipart framing SHALL áp dụng cùng hành vi cho chính xác ba route `POST /api/caesar/file`, `POST /api/vigenere/file` và `POST /api/playfair/file`. Multipart có boundary hợp lệ nhưng thiếu closing boundary SHALL bị từ chối trước field validation bằng HTTP 422 và body `{"success":false,"message":"Dữ liệu gửi lên không hợp lệ."}`. Việc mở rộng route recognition MUST NOT thay đổi cách route Caesar hiện tại được xử lý. (Truy vết: quyết định chủ sở hữu cho change này; baseline Caesar Week 1 request guard và `error-handling`)

#### Scenario: Multipart Vigenère bị cắt giữa chừng
- **WHEN** request tới `/api/vigenere/file` kết thúc trước closing boundary đã khai báo
- **THEN** hệ thống trả HTTP 422 với message `Dữ liệu gửi lên không hợp lệ.`
- **AND** không báo thiếu field dựa trên body chưa hoàn chỉnh

#### Scenario: Route không phải file không bị multipart guard phân loại nhầm
- **WHEN** request tới một route khác ba route file
- **THEN** multipart completion guard không áp contract route file cho request đó

### Requirement: Thứ tự lỗi xác định và dừng tại lỗi đầu tiên

Sau tầng 0, các endpoint mới SHALL áp dụng đúng precedence được mô tả trong `additional-text-cipher-api` và `additional-file-cipher-api`: cấu trúc body trước field; sự hiện diện trước định dạng; key/action/response mode trước validation file; extension trước size, rồi 0 byte, UTF-8 và cuối cùng validation nội dung Playfair. Hệ thống MUST trả đúng một lỗi đầu tiên, để cùng request luôn có cùng status/message. (Truy vết: quyết định chủ sở hữu kế thừa baseline Caesar Week 1 `error-handling`)

#### Scenario: Lỗi key thắng lỗi file và Playfair content
- **WHEN** request Playfair file có key normalize thành rỗng, extension sai và nội dung không có ASCII letter
- **THEN** hệ thống trả HTTP 422 với message key Playfair
- **AND** không trả lỗi extension hoặc lỗi text Playfair

### Requirement: Log nội bộ và tính stateless giữ nguyên

Lỗi HTTP 500 từ endpoint mới SHALL được log với endpoint, thời điểm, loại lỗi và traceback phục vụ debug, nhưng log MUST NOT chứa plaintext, ciphertext, key, nội dung file hoặc result. Dữ liệu request và kết quả MUST NOT được lưu sau khi response kết thúc. Lỗi 4xx có thể không log; nếu log MUST không chứa payload người dùng. (Truy vết: scope mới BE-VIG-05, BE-PLAY-05; baseline Caesar Week 1 `error-handling`, `app-runtime`)

#### Scenario: Log 500 không chứa dữ liệu mật mã
- **WHEN** lỗi hệ thống xảy ra khi xử lý Playfair hoặc Vigenère
- **THEN** server có log kỹ thuật cần thiết
- **AND** log không chứa text, key, file content hoặc result của người dùng

### Requirement: Contract lỗi Caesar không thay đổi

Việc thêm message và route mới MUST NOT sửa tập message, status mapping, precedence hoặc error envelope của `/api/caesar/encrypt`, `/api/caesar/decrypt` và `/api/caesar/file`. (Truy vết: quyết định chủ sở hữu cho change này; completed change `caesar-cipher-week1-mvp`)

#### Scenario: Request Caesar lỗi giữ nguyên message
- **WHEN** một request Caesar trước đây trả lỗi canonical
- **THEN** sau change request vẫn trả cùng HTTP status và cùng body
