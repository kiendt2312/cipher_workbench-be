# hill-error-handling Specification

## Purpose
Định nghĩa mã lỗi/cảnh báo Hill, thứ tự ưu tiên và giới hạn ảnh hưởng lên hệ thống hiện tại. Nguồn: HTML Hill §§5–7, 11; quyết định chủ sở hữu Q2, Q5–Q6, Q8–Q12, Q14–Q18 ngày 2026-09-29.
## Requirements
### Requirement: Lỗi nghiệp vụ Hill có envelope riêng

Lỗi nghiệp vụ của bốn API Hill SHALL trả JSON `{ "success":false, "message":<tiếng Việt>, "code":<E-code>, "details":<object> }`; `details` SHALL có đủ dữ liệu an toàn để FE hiển thị mà không chứa text gốc, keyword, ma trận khóa gốc hoặc stack trace. E01–E05, E08–E11 dùng HTTP 422; E06 dùng HTTP 413. E07 không thể phát sinh ở backend vì FE đọc file. Lỗi 500 bất ngờ và lỗi guard hạ tầng 64 MiB trước khi parse body tiếp tục dùng envelope chung `{success:false,message}`; không giả thành E-code nghiệp vụ. Các route ngoài Hill SHALL giữ nguyên status và envelope hiện hành. (Truy vết: HTML Hill §§1, 6–7; quyết định chủ sở hữu Q1, Q2, Q6, Q9–Q11, Q18; main spec `error-handling` và `app/api/request_size_guard.py` baseline)

#### Scenario: E04 có details
- **WHEN** encrypt với K có det mod 26 bằng 13
- **THEN** HTTP 422, `code="E04"`, `details.det=13`, `details.gcd=13`, `details.divisor=13`

#### Scenario: Cipher cũ giữ envelope
- **WHEN** một route Caesar, Vigenère, Playfair, Affine hoặc Columnar trả lỗi
- **THEN** body tiếp tục chỉ có `success` và `message`

### Requirement: Bảng lỗi Hill và chi tiết tối thiểu

Hệ thống SHALL dùng bảng sau; `message` bằng tiếng Việt và không nhúng dữ liệu người dùng. Các template của HTML Hill được giữ ở nơi phù hợp; E06 được viết theo giới hạn text thay vì file, E10/E11 là bổ sung đã duyệt. (Truy vết: HTML Hill §6; quyết định chủ sở hữu Q6, Q10, Q11, Q17–Q18)

| Code | Điều kiện | HTTP | `details` tối thiểu |
|---|---|---:|---|
| E01 | `text` thiếu, null, rỗng hoặc chỉ whitespace | 422 | `{}` |
| E02 | Sau tùy chọn bỏ dấu, không có chữ A–Z để xử lý | 422 | `{}` |
| E03 | Khóa ma trận thiếu/sai hình dạng/ô không phải integer, hoặc có cả `key` và `keyword` | 422 | `reason`; với ô sai có thêm `row`,`column` (1-based) |
| E04 | `gcd(det mod 26,26) ≠ 1` | 422 | `det`,`gcd`,`divisor` (2 nếu det chẵn, ngược lại 13) |
| E05 | Decrypt có số chữ tham gia không chia hết m | 422 | `n`,`m` |
| E06 | UTF-8 của `text` vượt 5.242.880 byte | 413 | `actualBytes`,`maxBytes` |
| E08 | `m` bắt buộc nhưng thiếu, sai kiểu hoặc ngoài 2–4; ma trận cấp ngoài 2–4 | 422 | `min=2`,`max=4`, `m` nếu có dạng số nguyên |
| E09 | Keyword sai kiểu, chứa ký tự ngoài `[A-Za-z]` hoặc không đúng m² ký tự | 422 | `m`,`expected`,`actual` (số chữ ASCII hợp lệ nếu là string, `null` nếu sai kiểu) |
| E10 | `options` sai kiểu, field lạ, `stripDiacritics` không boolean hoặc `padChar` không phải một chữ A–Z hoa | 422 | `field` |
| E11 | Content-Type không phải JSON được hỗ trợ, JSON hỏng/không phải object, `text` sai kiểu khác null, top-level field lạ/trùng, hoặc JSON string có lone surrogate | 422 | `{}` |

E01 hiển thị `Nhập văn bản hoặc tải file .txt để bắt đầu.`; E02 `Văn bản không có chữ cái nào để mã hóa. Hill chỉ xử lý A–Z.`; E04 chứa det và ước chung 2 hoặc 13; E05 chứa n và m; E06 `Văn bản vượt quá giới hạn 5 MiB.`; E08 `Cấp ma trận khóa phải từ 2 đến 4.`; E09 nêu số chữ cần và số chữ hợp lệ; E10 `Tùy chọn Hill không hợp lệ.`; E11 dùng message chung `Dữ liệu gửi lên không hợp lệ.`. E03 SHALL nêu vị trí ô nếu lỗi thuộc một ô. (Truy vết: quyết định chủ sở hữu ngày 2026-09-30 ghi đè giới hạn trong HTML Hill §6; quyết định Q6, Q10, Q11, Q18)

#### Scenario: Whitespace-only
- **WHEN** encrypt nhận `text="  \t\n"` và K hợp lệ
- **THEN** HTTP 422/E01

#### Scenario: Không có chữ
- **WHEN** encrypt nhận `text="123 !!"` và K hợp lệ
- **THEN** HTTP 422/E02

#### Scenario: Hai dạng khóa cùng xuất hiện
- **WHEN** request có cả `key` và `keyword`
- **THEN** HTTP 422/E03, không chạy cipher

#### Scenario: JSON duplicate member
- **WHEN** JSON chứa hai member `text`
- **THEN** HTTP 422/E11 trước mọi kiểm tra field

### Requirement: Thứ tự ưu tiên validation ổn định

Đối với hai route biến đổi, hệ thống SHALL chọn một lỗi theo thứ tự: (1) guard hạ tầng 64 MiB nếu đã chặn; (2) media/JSON/object/duplicate/unknown/surrogate E11; (3) giới hạn byte text E06 nếu text là string; (4) text thiếu/null/blank E01, text sai kiểu E11; (5) hình dạng/giá trị khóa E03/E08/E09; (6) options E10; (7) khả nghịch E04; (8) không có chữ A–Z E02; (9) độ dài ciphertext E05. Analyze và random bỏ các bước không có trong request tương ứng. Lỗi 500 không được lộ chi tiết nội bộ. (Truy vết: HTML Hill §§3–6; quyết định chủ sở hữu Q10, Q15, Q17–Q18; guard hạ tầng trong main spec `error-handling`)

#### Scenario: Text rỗng và khóa sai
- **WHEN** encrypt có `text=""` và K sai
- **THEN** HTTP 422/E01

#### Scenario: Khóa không khả nghịch và text không có chữ
- **WHEN** encrypt có `text="123"` và K với det chẵn
- **THEN** HTTP 422/E04

### Requirement: Warning có mã, message và details

Warning SHALL không chặn response 200, mỗi item có đúng `code`, `message`, `details`, theo thứ tự W01 rồi W02 rồi W03. W01 khi encrypt thêm padding, `details={count,char,m}`; W02 khi `stripDiacritics=false` và có cụm chữ Việt có dấu được giữ nguyên, `details={count}`; W03 khi khóa đơn vị hoặc tự nghịch đảo, `details={reason:"identity"|"self_inverse"}`. W03 áp dụng cả encrypt, decrypt, analyze và random; W01 chỉ encrypt; W02 chỉ route biến đổi có text. (Truy vết: HTML Hill §§5–6, 8; quyết định chủ sở hữu Q5, Q8, Q12, Q14, Q16)

#### Scenario: Hai warning cùng lúc
- **WHEN** encrypt một text cần một ký tự đệm, có một chữ Việt có dấu được giữ nguyên, với khóa đơn vị
- **THEN** warnings có đúng thứ tự W01, W02, W03 và mỗi warning có details tương ứng
