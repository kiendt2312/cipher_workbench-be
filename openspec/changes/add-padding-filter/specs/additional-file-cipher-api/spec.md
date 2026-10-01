## RENAMED Requirements

- FROM: `### Requirement: Content mode trả JSON đúng hai trường`
- TO: `### Requirement: Content mode trả JSON kết quả`

## MODIFIED Requirements

### Requirement: Hợp đồng multipart của hai endpoint file mới

Hệ thống SHALL cung cấp `POST /api/vigenere/file` và `POST /api/playfair/file`, nhận `multipart/form-data` với `file` bắt buộc, `key` bắt buộc dưới dạng chuỗi, `action` bắt buộc bằng chính xác `encrypt` hoặc `decrypt`, và `response_mode` tùy chọn bằng `content` hoặc `file`, mặc định `content`. Riêng `POST /api/playfair/file` nhận thêm `strip_padding` tùy chọn bằng chính xác `true` hoặc `false`, mặc định `false`; endpoint Vigenère giữ nguyên contract và không đọc trường này. `action`, `response_mode` và `strip_padding` SHALL phân biệt hoa thường. Mỗi endpoint SHALL dùng cùng core tương ứng với endpoint text. (Truy vết: scope mới BE-VIG-03, BE-PLAY-03; quyết định chủ sở hữu cho change Playfair/Vigenère; baseline Caesar Week 1 `file-cipher-api`; quyết định chủ sở hữu ngày 2026-10-01 cho `strip_padding`)

#### Scenario: Vigenère file content mode
- **WHEN** client gửi file `.txt` chứa `Attack at dawn!`, key `LEMON`, action `encrypt` và `response_mode=content` tới `/api/vigenere/file`
- **THEN** hệ thống trả HTTP 200
- **AND** body là `{"success":true,"result":"Lxfopv ef rnhr!"}`

#### Scenario: Playfair file content mode
- **WHEN** client gửi file `.txt` chứa `HIDE THE GOLD IN THE TREE STUMP`, key `PLAYFAIR EXAMPLE`, action `encrypt` và `response_mode=content` tới `/api/playfair/file`
- **THEN** hệ thống trả HTTP 200
- **AND** body là `{"success":true,"result":"BMODZBXDNABEKUDMUIXMMOUVIF"}`

#### Scenario: Playfair file decrypt content mode có padding
- **WHEN** client gửi file `.txt` chứa `PDGW`, key `PLAYFAIR EXAMPLE`, action `decrypt` và `response_mode=content` tới `/api/playfair/file`
- **THEN** hệ thống trả HTTP 200
- **AND** body là `{"success":true,"result":"ABXQ","padding":{"count":1,"positions":[3],"filtered":"ABX"}}`

#### Scenario: Bỏ response mode mặc định content
- **WHEN** client gửi `file`, `key` và `action` hợp lệ nhưng không gửi `response_mode`
- **THEN** endpoint xử lý như `response_mode=content`

### Requirement: Content mode trả JSON kết quả

Khi `response_mode=content` và request hợp lệ, endpoint SHALL trả HTTP 200 với `Content-Type: application/json` và body `{"success":true,"result":"<nội dung kết quả>"}`. Riêng Playfair với `action=decrypt`, body SHALL có thêm `padding` theo `padding-filter`; `result` vẫn là bản thô bất kể `strip_padding`. Nếu file đầu vào có UTF-8 BOM, BOM SHALL không xuất hiện trong `result` hay `padding.filtered`. Response MUST NOT có `Content-Disposition`, `normalizedInput`, `message`, `code` hoặc metadata khác. (Truy vết: quyết định chủ sở hữu cho change Playfair/Vigenère; baseline Caesar Week 1 `file-cipher-api`, `error-handling`; quyết định chủ sở hữu (a) ngày 2026-10-01)

#### Scenario: Content mode loại BOM khỏi result
- **WHEN** file UTF-8 có BOM chứa `Attack` được encrypt Vigenère với key `LEMON` ở content mode
- **THEN** `result` là `Lxfopv`
- **AND** `result` không bắt đầu bằng `U+FEFF`

#### Scenario: strip_padding không đổi result ở content mode
- **WHEN** file chứa `PDGW` được decrypt Playfair với key `PLAYFAIR EXAMPLE`, `response_mode=content` và `strip_padding=true`
- **THEN** `result` là `ABXQ` và `padding.filtered` là `ABX`

### Requirement: File mode trả attachment do server sở hữu

Khi `response_mode=file` và request hợp lệ, endpoint SHALL trả HTTP 200 với `Content-Type: text/plain; charset=utf-8`, `Content-Disposition: attachment` và filename do server tạo. Body SHALL là bytes UTF-8 của kết quả, không bọc JSON. Với Playfair `action=decrypt`, kết quả là bản thô khi `strip_padding` vắng hoặc bằng `false`, và là bản lọc theo `playfair-core` khi `strip_padding=true`; với `action=encrypt`, `strip_padding` không ảnh hưởng kết quả. Client MUST dùng response attachment này làm nguồn download cho file upload thay vì tự tạo download từ preview. (Truy vết: quyết định chủ sở hữu cho change Playfair/Vigenère; baseline Caesar Week 1 `file-cipher-api`, `repo_docs/frontend-integration.md`; quyết định chủ sở hữu ngày 2026-10-01 cho `strip_padding`)

#### Scenario: Vigenère trả attachment
- **WHEN** client gửi `note.txt` hợp lệ tới `/api/vigenere/file` với action `encrypt` và `response_mode=file`
- **THEN** hệ thống trả attachment `note.encrypted.txt`

#### Scenario: Playfair trả attachment
- **WHEN** client gửi `secret.txt` hợp lệ tới `/api/playfair/file` với action `decrypt` và `response_mode=file`
- **THEN** hệ thống trả attachment `secret.decrypted.txt`

#### Scenario: Attachment Playfair theo strip_padding
- **WHEN** client gửi file chứa `PDGW`, key `PLAYFAIR EXAMPLE`, action `decrypt` và `response_mode=file` tới `/api/playfair/file`
- **THEN** body attachment là `ABXQ` khi không gửi `strip_padding` hoặc gửi `strip_padding=false`
- **AND** body attachment là `ABX` khi gửi `strip_padding=true`

### Requirement: Hành vi nội dung file theo từng thuật toán

Vigenère SHALL giữ nguyên line break, whitespace, số, dấu câu và Unicode, đồng thời không làm tiến key trên các ký tự đó. Playfair SHALL normalize toàn bộ nội dung file thành stream ASCII uppercase, loại non-letter và map `J` thành `I`; do đó line break/format trong input Playfair không xuất hiện trong output. Decrypt Playfair SHALL trả bản thô và nhận diện filler như `playfair-core`. (Truy vết: scope mới BE-VIG-03, BE-PLAY-03; quyết định chủ sở hữu cho change Playfair/Vigenère; yêu cầu chủ sở hữu ngày 2026-10-01)

#### Scenario: Vigenère giữ CRLF
- **WHEN** file Vigenère chứa `A\r\nA` và key `BC`
- **THEN** kết quả là `B\r\nC`
- **AND** CRLF không làm tiến key

#### Scenario: Playfair loại newline và dấu câu
- **WHEN** file Playfair chứa `HIDE\r\nTHE GOLD!` và keyword `PLAYFAIR EXAMPLE`
- **THEN** core nhận chuỗi normalized tương đương `HIDETHEGOLD`

### Requirement: Validation precedence của endpoint file

Sau tầng 0, hai endpoint SHALL kiểm theo thứ tự: multipart phải parse được; `file` hiện diện; `key` hiện diện; `action` hiện diện/hợp lệ về sự hiện diện; key đúng quy tắc thuật toán; `action` đúng giá trị; `response_mode` đúng giá trị; `strip_padding` đúng giá trị (chỉ Playfair); extension; 5 MiB; file 0 byte; UTF-8; cuối cùng validation nội dung Playfair sau normalization nếu áp dụng. Hệ thống MUST dừng ở lỗi đầu tiên và trả đúng một message. (Truy vết: quyết định chủ sở hữu kế thừa baseline Caesar Week 1 `error-handling`; quyết định chủ sở hữu ngày 2026-10-01 cho `strip_padding`)

#### Scenario: Key sai được báo trước extension sai
- **WHEN** gửi file `bad.md` với key Vigenère `KEY 1` và action hợp lệ
- **THEN** hệ thống trả HTTP 422 với message key Vigenère
- **AND** không trả lỗi extension

#### Scenario: Encoding sai được báo trước nội dung Playfair sai
- **WHEN** file Playfair có extension/dung lượng hợp lệ nhưng bytes không phải UTF-8 và nếu đọc giả định cũng không có ASCII letter
- **THEN** hệ thống trả HTTP 415 với message `File phải sử dụng UTF-8.`

#### Scenario: strip_padding sai được báo sau response mode và trước extension
- **WHEN** gửi file Playfair `bad.md` với key, action và `response_mode` hợp lệ nhưng `strip_padding=yes`
- **THEN** hệ thống trả HTTP 422 với message `Tùy chọn lọc ký tự đệm phải là true hoặc false.`
- **AND** không trả lỗi extension

## ADDED Requirements

### Requirement: Validate strip_padding của Playfair file

Khi `POST /api/playfair/file` nhận part `strip_padding` khác chính xác `true` hoặc `false` (kể cả `TRUE`, `1`, `yes` hoặc chuỗi rỗng), hệ thống MUST trả HTTP 422 với message `Tùy chọn lọc ký tự đệm phải là true hoặc false.`. Trường này SHALL được validate ở mọi `action` và `response_mode`, kể cả khi giá trị hợp lệ không ảnh hưởng kết quả. (Truy vết: quyết định chủ sở hữu ngày 2026-10-01 cho change này; baseline cách validate `response_mode`)

#### Scenario: strip_padding viết hoa bị từ chối
- **WHEN** `strip_padding=TRUE` được gửi tới `/api/playfair/file` cùng các trường hợp lệ khác
- **THEN** hệ thống trả HTTP 422 với message `Tùy chọn lọc ký tự đệm phải là true hoặc false.`

#### Scenario: strip_padding hợp lệ ở encrypt
- **WHEN** `strip_padding=true` được gửi tới `/api/playfair/file` với action `encrypt`
- **THEN** request được xử lý như khi không gửi `strip_padding`
