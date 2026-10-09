# additional-text-cipher-api Specification

## Purpose

Định nghĩa hợp đồng HTTP JSON cho bốn endpoint text Vigenère và Playfair, gồm request/response, validation xác định và khả năng tương thích với response conventions của Caesar.

## Requirements

### Requirement: Endpoint text Vigenère

Hệ thống SHALL cung cấp `POST /api/vigenere/encrypt` và `POST /api/vigenere/decrypt`. Mỗi endpoint SHALL nhận `Content-Type: application/json` với JSON object gồm `text` và `key`, đều là chuỗi; SHALL gọi đúng operation của Vigenère repeating-key; và SHALL hoạt động stateless. (Truy vết: scope mới BE-VIG-02, BE-VIG-06; baseline Caesar Week 1 `text-cipher-api`)

#### Scenario: Encrypt Vigenère qua API
- **WHEN** client gửi `POST /api/vigenere/encrypt` với body `{"text":"Attack at dawn!","key":"LEMON"}`
- **THEN** hệ thống trả HTTP 200
- **AND** body là `{"success":true,"result":"Lxfopv ef rnhr!"}`

#### Scenario: Decrypt Vigenère qua API
- **WHEN** client gửi `POST /api/vigenere/decrypt` với body `{"text":"Lxfopv ef rnhr!","key":"LEMON"}`
- **THEN** hệ thống trả HTTP 200
- **AND** body là `{"success":true,"result":"Attack at dawn!"}`

### Requirement: Endpoint text Playfair

Hệ thống SHALL cung cấp `POST /api/playfair/encrypt` và `POST /api/playfair/decrypt`. Mỗi endpoint SHALL nhận `Content-Type: application/json` với JSON object gồm `text` và `key`, đều là chuỗi; SHALL áp dụng đúng normalization và operation Playfair; và SHALL hoạt động stateless. (Truy vết: scope mới BE-PLAY-02, BE-PLAY-06; baseline Caesar Week 1 `text-cipher-api`)

#### Scenario: Encrypt Playfair qua API
- **WHEN** client gửi `POST /api/playfair/encrypt` với body `{"text":"HIDE THE GOLD IN THE TREE STUMP","key":"PLAYFAIR EXAMPLE"}`
- **THEN** hệ thống trả HTTP 200
- **AND** body là `{"success":true,"result":"BMODZBXDNABEKUDMUIXMMOUVIF"}`

#### Scenario: Decrypt Playfair qua API giữ filler giữa chuỗi
- **WHEN** client gửi `POST /api/playfair/decrypt` với body `{"text":"BMODZBXDNABEKUDMUIXMMOUVIF","key":"PLAYFAIR EXAMPLE"}`
- **THEN** hệ thống trả HTTP 200
- **AND** body là `{"success":true,"result":"HIDETHEGOLDINTHETREXESTUMP"}`

#### Scenario: Decrypt Playfair qua API bỏ filler cuối
- **WHEN** client gửi `POST /api/playfair/decrypt` với body `{"text":"PDGW","key":"PLAYFAIR EXAMPLE"}`
- **THEN** hệ thống trả HTTP 200
- **AND** body là `{"success":true,"result":"ABX"}`

### Requirement: Success response JSON đúng hai trường

Mọi response thành công của bốn endpoint text mới SHALL trả HTTP 200 và JSON đúng hai trường `success` bằng `true` và `result` là chuỗi. Response MUST NOT chứa `message`, `code`, `normalizedInput`, matrix, prepared text hoặc metadata khác. (Truy vết: scope mới BE-VIG-06, BE-PLAY-06; quyết định chủ sở hữu cho change này; baseline Caesar Week 1 `error-handling`)

#### Scenario: Không thêm normalizedInput cho Playfair
- **WHEN** một request Playfair text hợp lệ được xử lý thành công
- **THEN** response chỉ có hai key `success` và `result`
- **AND** response không có key `normalizedInput`

### Requirement: Validate trường text dùng chung

Trường `text` SHALL bắt buộc có mặt và là chuỗi khác rỗng. Nếu `text` vắng mặt, `null`, chuỗi rỗng hoặc không phải chuỗi, hệ thống MUST trả HTTP 422 với body chính xác `{"success":false,"message":"Văn bản không được để trống."}`. Vigenère SHALL chấp nhận chuỗi chỉ chứa whitespace; Playfair SHALL đi tiếp tới bước kiểm tra dữ liệu sau normalization. (Truy vết: scope mới BE-VIG-04, BE-PLAY-04; baseline Caesar Week 1 `text-cipher-api`, `error-handling`)

#### Scenario: Text thiếu được báo trước key
- **WHEN** client gửi `{}` tới một endpoint text mới
- **THEN** hệ thống trả HTTP 422
- **AND** body là `{"success":false,"message":"Văn bản không được để trống."}`

#### Scenario: Whitespace-only hợp lệ với Vigenère
- **WHEN** client gửi Vigenère text gồm khoảng trắng, tab hoặc newline với key hợp lệ
- **THEN** hệ thống trả HTTP 200
- **AND** `result` giống hệt `text`

#### Scenario: Whitespace-only không hợp lệ với Playfair
- **WHEN** client gửi Playfair text chỉ gồm whitespace với key hợp lệ
- **THEN** hệ thống trả HTTP 422
- **AND** body là `{"success":false,"message":"Văn bản Playfair phải chứa ít nhất một chữ cái A-Z hoặc a-z."}`

### Requirement: Validate sự hiện diện và kiểu key chuỗi

Trường `key` SHALL bắt buộc có mặt và là chuỗi. Nếu key vắng mặt, `null` hoặc là chuỗi rỗng, hệ thống MUST trả HTTP 422 với body `{"success":false,"message":"Thiếu khóa."}`. Nếu key có giá trị nhưng không phải chuỗi, hệ thống MUST trả HTTP 422 với body `{"success":false,"message":"Khóa phải là chuỗi."}`. Hệ thống MUST NOT ép số, boolean, mảng hoặc object thành chuỗi. (Truy vết: scope mới BE-VIG-04, BE-PLAY-04; quyết định chủ sở hữu cho change này; baseline Caesar Week 1 `error-handling`)

#### Scenario: Key null được coi là thiếu
- **WHEN** client gửi text hợp lệ và `"key":null`
- **THEN** hệ thống trả HTTP 422
- **AND** body là `{"success":false,"message":"Thiếu khóa."}`

#### Scenario: Key số không được ép kiểu
- **WHEN** client gửi text hợp lệ và `"key":123`
- **THEN** hệ thống trả HTTP 422
- **AND** body là `{"success":false,"message":"Khóa phải là chuỗi."}`

### Requirement: Validate key Vigenère theo alphabet ASCII

Sau khi key đã qua kiểm tra sự hiện diện và kiểu chuỗi, endpoint Vigenère MUST từ chối key chứa bất kỳ ký tự nào ngoài `A-Z`/`a-z` bằng HTTP 422 với body `{"success":false,"message":"Khóa Vigenère chỉ được chứa chữ cái A-Z hoặc a-z."}`. Chuỗi chỉ chứa whitespace thuộc trường hợp này, không phải trường hợp thiếu key. (Truy vết: scope mới BE-VIG-01, BE-VIG-04, BE-VIG-05; quyết định chủ sở hữu cho change này)

#### Scenario: Key Vigenère có khoảng trắng bị từ chối
- **WHEN** client gửi text hợp lệ với key `LE MON`
- **THEN** hệ thống trả HTTP 422
- **AND** body là `{"success":false,"message":"Khóa Vigenère chỉ được chứa chữ cái A-Z hoặc a-z."}`

#### Scenario: Key Vigenère Unicode bị từ chối
- **WHEN** client gửi text hợp lệ với key `KHÓA`
- **THEN** hệ thống trả HTTP 422 với cùng thông báo key Vigenère ASCII

### Requirement: Validate key Playfair sau normalization

Sau khi key đã qua kiểm tra sự hiện diện và kiểu chuỗi, endpoint Playfair SHALL normalize key theo `playfair-core`. Nếu không còn ASCII letter, hệ thống MUST trả HTTP 422 với body `{"success":false,"message":"Khóa Playfair phải chứa ít nhất một chữ cái A-Z hoặc a-z."}`. Khoảng trắng hoặc ký tự không hợp lệ SHALL được bỏ qua nếu key vẫn còn ít nhất một ASCII letter. (Truy vết: scope mới BE-PLAY-01, BE-PLAY-04, BE-PLAY-05; quyết định chủ sở hữu cho change này)

#### Scenario: Key Playfair có khoảng trắng được normalize
- **WHEN** client gửi key `PLAYFAIR EXAMPLE` cùng text Playfair hợp lệ
- **THEN** request không bị từ chối vì khoảng trắng trong key

#### Scenario: Key Playfair không còn ký tự hợp lệ
- **WHEN** client gửi key `123 — đỏ` cùng text Playfair hợp lệ
- **THEN** hệ thống trả HTTP 422
- **AND** body là `{"success":false,"message":"Khóa Playfair phải chứa ít nhất một chữ cái A-Z hoặc a-z."}`

### Requirement: Validate text và ciphertext Playfair sau normalization

Sau khi text/key cơ bản và key Playfair hợp lệ, hệ thống SHALL normalize `text`. Nếu không còn ASCII letter, hệ thống MUST trả HTTP 422 với message `Văn bản Playfair phải chứa ít nhất một chữ cái A-Z hoặc a-z.`. Riêng decrypt, nếu số chữ cái sau normalization là lẻ, hệ thống MUST trả HTTP 422 với message `Bản mã Playfair phải chứa số lượng chữ cái chẵn.`; nếu một digraph có hai chữ giống nhau, hệ thống MUST trả HTTP 422 với message `Bản mã Playfair không được chứa cặp hai chữ cái giống nhau.`. (Truy vết: scope mới BE-PLAY-04, BE-PLAY-05; quyết định chủ sở hữu cho change này)

#### Scenario: Playfair text không còn ASCII letter
- **WHEN** client gửi `{"text":"123 — đỏ","key":"MONARCHY"}` tới endpoint Playfair encrypt
- **THEN** hệ thống trả HTTP 422
- **AND** body là `{"success":false,"message":"Văn bản Playfair phải chứa ít nhất một chữ cái A-Z hoặc a-z."}`

#### Scenario: Playfair ciphertext có độ dài lẻ
- **WHEN** client gửi `{"text":"ABC","key":"MONARCHY"}` tới endpoint Playfair decrypt
- **THEN** hệ thống trả HTTP 422
- **AND** body là `{"success":false,"message":"Bản mã Playfair phải chứa số lượng chữ cái chẵn."}`

#### Scenario: Playfair ciphertext có digraph trùng
- **WHEN** client gửi `{"text":"AABC","key":"MONARCHY"}` tới endpoint Playfair decrypt
- **THEN** hệ thống trả HTTP 422
- **AND** body là `{"success":false,"message":"Bản mã Playfair không được chứa cặp hai chữ cái giống nhau."}`

### Requirement: Body JSON không đọc được dùng lỗi chuẩn

Nếu request không bị tầng bảo vệ kích thước từ chối trước và body rỗng, sai cú pháp JSON, hoặc JSON hợp lệ nhưng không phải object, endpoint text mới SHALL trả HTTP 422 với body `{"success":false,"message":"Dữ liệu gửi lên không hợp lệ."}`. Phản hồi MUST NOT chứa `detail`, tiếng Anh hoặc chi tiết kỹ thuật. (Truy vết: baseline Caesar Week 1 `text-cipher-api`, `error-handling`; quyết định chủ sở hữu kế thừa contract)

#### Scenario: JSON sai cú pháp
- **WHEN** client gửi body `{"text":"abc","key":` tới một endpoint text mới
- **THEN** hệ thống trả HTTP 422
- **AND** body là `{"success":false,"message":"Dữ liệu gửi lên không hợp lệ."}`

### Requirement: Validation precedence của endpoint text

Sau tầng 0, endpoint text mới SHALL kiểm theo thứ tự: body phải là JSON object hợp lệ; `text` hiện diện/đúng kiểu/khác rỗng; `key` hiện diện; `key` đúng kiểu chuỗi; key đúng quy tắc thuật toán; rồi validation Playfair sau normalization nếu áp dụng. Hệ thống MUST dừng ở lỗi đầu tiên và trả đúng một message. (Truy vết: baseline Caesar Week 1 `error-handling`; scope mới BE-VIG-04, BE-PLAY-04; quyết định chủ sở hữu cho change này)

#### Scenario: Text lỗi được báo trước key lỗi
- **WHEN** client gửi `{"text":"","key":123}` tới một endpoint text mới
- **THEN** hệ thống trả HTTP 422
- **AND** message là `Văn bản không được để trống.`

#### Scenario: Key lỗi được báo trước normalized Playfair text
- **WHEN** client gửi `{"text":"123","key":"---"}` tới endpoint Playfair encrypt
- **THEN** hệ thống trả HTTP 422
- **AND** message là `Khóa Playfair phải chứa ít nhất một chữ cái A-Z hoặc a-z.`

### Requirement: Không thay đổi endpoint Caesar

Việc thêm bốn endpoint text mới MUST NOT thay đổi route, response schema, status, message, key integer hoặc kết quả của `POST /api/caesar/encrypt` và `POST /api/caesar/decrypt`. Caesar chỉ có thêm compatibility input cho decimal string ASCII canonical do DH trả về; đây không phải string-key contract của Vigenère/Playfair. (Truy vết: quyết định chủ sở hữu cho change này; completed change `caesar-cipher-week1-mvp`; tương thích `sharedKey` DH ngày 2026-10-09)

#### Scenario: Caesar vẫn dùng key integer
- **WHEN** client gửi request Caesar đã hợp lệ trước change
- **THEN** response sau change giống hệt baseline Week 1
- **AND** Caesar không nhận arbitrary string key chỉ vì Vigenère/Playfair dùng key chuỗi; ngoại lệ duy nhất là decimal string DH canonical `"0"` / `[1-9][0-9]*`
