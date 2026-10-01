# des-text-cipher-api Specification

## Purpose
Định nghĩa hai endpoint JSON mã hóa/giải mã DES, các tham số định dạng và chế độ, giới hạn 5 MiB và mảng warnings. Nguồn: `Scope Backend_ Hệ mã hóa DES.html` §§1–2, 4–7; quyết định chủ sở hữu Q4, Q5, Q7–Q10, Q19 ngày 2026-10-01.
## Requirements
### Requirement: Hai endpoint JSON mã hóa và giải mã

Hệ thống SHALL cung cấp `POST /api/des/encrypt` và `POST /api/des/decrypt`, cùng gọi lõi DES theo operation của path. Hai endpoint nhận `application/json` và `application/*+json` như text route hiện hành; OpenAPI quảng bá `application/json` với tag `DES`. Response thành công SHALL là HTTP 200 với đúng ba field `{"success": true, "result": <chuỗi>, "warnings": [...]}`; `warnings` luôn có mặt, rỗng khi không có cảnh báo. Route và response của các cipher khác MUST NOT đổi. (Truy vết: HTML DES scope §§1, 7; quyết định chủ sở hữu Q7, Q8; main spec `columnar-text-cipher-api` về media type)

#### Scenario: Mã hóa một khối hex
- **WHEN** client gửi `POST /api/des/encrypt` với `{"text":"0123456789ABCDEF","key":"133457799BBCDFF1","inputFormat":"hex"}`
- **THEN** hệ thống trả HTTP 200 với `{"success":true,"result":"85E813540F0AB405","warnings":[]}`

#### Scenario: Giải mã ra text
- **WHEN** client gửi `POST /api/des/decrypt` với `{"text":"B1CA74BB3514268701A9ACC3E4E69FAA","key":"133457799BBCDFF1"}`
- **THEN** hệ thống trả HTTP 200 với `{"success":true,"result":"Hello World","warnings":[]}`

### Requirement: Field của request encrypt

Body của `/api/des/encrypt` SHALL là JSON object chỉ gồm các field: `text` (bắt buộc, string), `key` (bắt buộc, string), `inputFormat` (tùy chọn, `"text"` mặc định hoặc `"hex"`), `mode` (tùy chọn, `"ECB"` mặc định hoặc `"CBC"`), `iv` (tùy chọn, string hoặc null). `inputFormat="text"` mã UTF-8 rồi đệm PKCS#7; `inputFormat="hex"` dùng hex bội 16 ký tự, không đệm. Giá trị enum SHALL khớp chính xác, phân biệt hoa thường. Khi `mode="ECB"` hệ thống SHALL bỏ qua `iv` dù có giá trị gì; khi `mode="CBC"`, `iv` bắt buộc là 16 hex sau khi bỏ khoảng trắng. (Truy vết: HTML DES scope §§2, 7; quyết định chủ sở hữu Q9, Q19)

#### Scenario: Text mặc định ECB
- **WHEN** client gửi `{"text":"Hello World","key":"133457799BBCDFF1"}`
- **THEN** `result` là `B1CA74BB3514268701A9ACC3E4E69FAA`

#### Scenario: CBC có IV
- **WHEN** client gửi `{"text":"Hello World","key":"133457799BBCDFF1","mode":"CBC","iv":"0000000000000000"}`
- **THEN** `result` là `B1CA74BB351426875F9A5BCA734D9EF4`

#### Scenario: IV bị bỏ qua ở ECB
- **WHEN** client gửi `{"text":"Hello World","key":"133457799BBCDFF1","mode":"ECB","iv":"xyz"}`
- **THEN** hệ thống trả HTTP 200 với `result` giống khi không gửi `iv`

#### Scenario: Hex có khoảng trắng và chữ thường
- **WHEN** client gửi `{"text":"01234567 89abcdef","key":"133457799BBCDFF1","inputFormat":"hex"}`
- **THEN** `result` là `85E813540F0AB405`

### Requirement: Field của request decrypt

Body của `/api/des/decrypt` SHALL là JSON object chỉ gồm `text` (bắt buộc, bản mã hex), `key` (bắt buộc), `outputFormat` (tùy chọn, `"text"` mặc định hoặc `"hex"`), `mode` và `iv` với quy tắc như encrypt. Bản mã SHALL được bỏ khoảng trắng ASCII (kể cả xuống dòng) và chấp nhận chữ thường. `outputFormat="text"` gỡ PKCS#7 rồi giải mã UTF-8; `outputFormat="hex"` trả nguyên byte dạng hex in hoa. Hệ thống MUST NOT trả chuỗi rác khi padding hoặc UTF-8 sai mà trả lỗi DES-E07/E08. (Truy vết: HTML DES scope §§2, 5, 7; quyết định chủ sở hữu Q9, Q19)

#### Scenario: Giải mã ra hex
- **WHEN** client gửi `{"text":"85E813540F0AB405","key":"133457799BBCDFF1","outputFormat":"hex"}`
- **THEN** `result` là `0123456789ABCDEF`

#### Scenario: Bản mã nhiều dòng
- **WHEN** client gửi `text` là `"b1ca74bb35142687\n01a9acc3e4e69faa"` với khóa `133457799BBCDFF1`
- **THEN** `result` là `Hello World`

#### Scenario: CBC giải mã
- **WHEN** client gửi `{"text":"F02B595EB219AB97E6DB189E19AF7792","key":"133457799BBCDFF1","outputFormat":"hex","mode":"CBC","iv":"1234567890ABCDEF"}`
- **THEN** `result` là `0123456789ABCDEF0123456789ABCDEF`

### Requirement: Giới hạn 5 MiB cho text JSON

Hệ thống SHALL đo số byte UTF-8 của chuỗi `text` sau khi parse JSON. Đúng 5.242.880 byte SHALL được xử lý; từ 5.242.881 byte SHALL trả HTTP 413 `{"success":false,"message":"Dữ liệu vượt quá 5 MiB."}`. Giới hạn áp dụng cho cả `/encrypt` và `/decrypt`; vì bản mã hex dài gấp đôi dữ liệu, văn bản lớn nhất còn giải mã lại được là 2.621.439 byte UTF-8. Guard hạ tầng 64 MiB trên `Content-Length` vẫn chạy trước. (Truy vết: HTML DES scope §§1, 6 DES-E12; quyết định chủ sở hữu Q10, Q22; tiền lệ `hill-text-cipher-api`)

#### Scenario: Đúng 5 MiB được nhận
- **WHEN** `text` là chuỗi ASCII đúng 5.242.880 byte, khóa hợp lệ, `inputFormat="text"`
- **THEN** hệ thống không trả lỗi dung lượng

#### Scenario: Bản mã của văn bản lớn vượt giới hạn giải mã
- **WHEN** client mã hóa 5 MiB văn bản rồi gửi bản mã hex (10.485.776 ký tự) tới `/api/des/decrypt`
- **THEN** hệ thống trả HTTP 413 với message `Dữ liệu vượt quá 5 MiB.`

#### Scenario: Vượt 1 byte đa byte
- **WHEN** `text` có UTF-8 dài 5.242.881 byte do ký tự đa byte
- **THEN** hệ thống trả HTTP 413 với message `Dữ liệu vượt quá 5 MiB.`

### Requirement: Warnings của text API

`warnings` SHALL là mảng object có đúng `code`, `message`, `details`, theo thứ tự W01, W02, W03, mỗi mã tối đa một lần. W01 khi khóa yếu, `details={}`, message `Khóa yếu: mã hóa hai lần sẽ trả lại bản rõ. Không nên dùng.`; W02 khi khóa nửa yếu, `details={}`, message `Khóa nửa yếu: tồn tại khóa khác giải mã được bản mã của khóa này.`; W03 chỉ ở `/encrypt` với `mode="ECB"` khi bản mã có ít nhất hai khối 8 byte giống nhau, `details={"repeatedBlocks": <số khối trùng một khối trước nó>}`, message `Chế độ ECB: có khối bản mã lặp lại, lộ cấu trúc bản rõ. Cân nhắc dùng CBC.`. W01/W02 áp dụng cho cả encrypt và decrypt. Warning không chặn kết quả. (Truy vết: HTML DES scope §§5–6; quyết định chủ sở hữu Q4, Q5, Q8)

#### Scenario: W03 khi ECB lặp khối
- **WHEN** encrypt hex `0123456789ABCDEF0123456789ABCDEF` với khóa `133457799BBCDFF1`, ECB
- **THEN** `warnings` là `[{"code":"W03","message":"Chế độ ECB: có khối bản mã lặp lại, lộ cấu trúc bản rõ. Cân nhắc dùng CBC.","details":{"repeatedBlocks":1}}]`

#### Scenario: CBC không có W03
- **WHEN** encrypt cùng dữ liệu với `mode="CBC"`, IV `1234567890ABCDEF`
- **THEN** `warnings` rỗng

#### Scenario: W01 khi decrypt bằng khóa yếu
- **WHEN** decrypt `617B3A0CE8F07100` với khóa `0101010101010101`, `outputFormat="hex"`
- **THEN** `result` là `0123456789ABCDEF` và `warnings` chỉ có W01 với `details={}`

#### Scenario: W02 khóa nửa yếu
- **WHEN** encrypt hex `0123456789ABCDEF` với khóa `011F011F010E010E`
- **THEN** `result` là `6F2C1F78866CCF13` và `warnings` chỉ có W02

#### Scenario: W01 và W03 cùng lúc
- **WHEN** encrypt hex `00000000000000000000000000000000` với khóa `0000000000000000`, ECB
- **THEN** `warnings` có đúng thứ tự W01 rồi W03
