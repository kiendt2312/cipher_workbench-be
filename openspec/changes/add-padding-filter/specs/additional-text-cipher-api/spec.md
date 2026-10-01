## RENAMED Requirements

- FROM: `### Requirement: Success response JSON đúng hai trường`
- TO: `### Requirement: Success response JSON của endpoint text`

## MODIFIED Requirements

### Requirement: Endpoint text Playfair

Hệ thống SHALL cung cấp `POST /api/playfair/encrypt` và `POST /api/playfair/decrypt`. Mỗi endpoint SHALL nhận `Content-Type: application/json` với JSON object gồm `text` và `key`, đều là chuỗi; SHALL áp dụng đúng normalization và operation Playfair; và SHALL hoạt động stateless. Decrypt SHALL trả bản thô trong `result` và bản lọc trong `padding` theo `playfair-core` và `padding-filter`. (Truy vết: scope mới BE-PLAY-02, BE-PLAY-06; baseline Caesar Week 1 `text-cipher-api`; yêu cầu chủ sở hữu ngày 2026-10-01)

#### Scenario: Encrypt Playfair qua API
- **WHEN** client gửi `POST /api/playfair/encrypt` với body `{"text":"HIDE THE GOLD IN THE TREE STUMP","key":"PLAYFAIR EXAMPLE"}`
- **THEN** hệ thống trả HTTP 200
- **AND** body là `{"success":true,"result":"BMODZBXDNABEKUDMUIXMMOUVIF"}`

#### Scenario: Decrypt Playfair qua API giữ filler giữa chuỗi
- **WHEN** client gửi `POST /api/playfair/decrypt` với body `{"text":"BMODZBXDNABEKUDMUIXMMOUVIF","key":"PLAYFAIR EXAMPLE"}`
- **THEN** hệ thống trả HTTP 200
- **AND** body là `{"success":true,"result":"HIDETHEGOLDINTHETREXESTUMP","padding":{"count":1,"positions":[19],"filtered":"HIDETHEGOLDINTHETREESTUMP"}}`
- **AND** `result` giữ filler giữa chuỗi, chỉ `padding.filtered` bỏ nó

#### Scenario: Decrypt Playfair qua API bỏ filler cuối
- **WHEN** client gửi `POST /api/playfair/decrypt` với body `{"text":"PDGW","key":"PLAYFAIR EXAMPLE"}`
- **THEN** hệ thống trả HTTP 200
- **AND** body là `{"success":true,"result":"ABXQ","padding":{"count":1,"positions":[3],"filtered":"ABX"}}`
- **AND** filler cuối chỉ bị bỏ trong `padding.filtered`, `result` vẫn giữ nó

### Requirement: Success response JSON của endpoint text

Mọi response thành công của bốn endpoint text Vigenère/Playfair SHALL trả HTTP 200. Vigenère encrypt/decrypt và Playfair encrypt SHALL trả JSON đúng hai trường: `success` bằng `true` và `result` là chuỗi. Playfair decrypt SHALL trả JSON đúng ba trường `success`, `result` và `padding`, trong đó `padding` theo `padding-filter`. Response MUST NOT chứa `message`, `code`, `normalizedInput`, matrix, prepared text hoặc metadata khác. (Truy vết: scope mới BE-VIG-06, BE-PLAY-06; baseline Caesar Week 1 `error-handling`; yêu cầu chủ sở hữu ngày 2026-10-01 và quyết định (a) cho change này)

#### Scenario: Không thêm normalizedInput cho Playfair
- **WHEN** một request Playfair decrypt text hợp lệ được xử lý thành công
- **THEN** response chỉ có ba key `success`, `result` và `padding`
- **AND** response không có key `normalizedInput`

#### Scenario: Vigenère và Playfair encrypt giữ hai trường
- **WHEN** một request Vigenère encrypt/decrypt hoặc Playfair encrypt hợp lệ được xử lý thành công
- **THEN** response chỉ có hai key `success` và `result`
