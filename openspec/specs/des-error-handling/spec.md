# des-error-handling Specification

## Purpose
Định nghĩa envelope, bảng lỗi, message, HTTP status và thứ tự ưu tiên lỗi cho bốn route DES, cùng request guard và ranh giới với contract lỗi của các cipher hiện có. Nguồn: `Scope Backend_ Hệ mã hóa DES.html` §§4–6; main spec `error-handling`, `affine-error-handling`, `columnar-error-handling`; quyết định chủ sở hữu Q3, Q7, Q9–Q11, Q13 ngày 2026-10-01.
## Requirements
### Requirement: Envelope lỗi DES đúng hai trường

Mọi lỗi của bốn route DES SHALL trả JSON đúng `{"success":false,"message":"<tiếng Việt>"}`. Response MUST NOT có `code`, `details`, khóa, IV, dữ liệu người dùng hay stack trace; mã DES-Exx chỉ dùng để đặt tên test và tài liệu. Lỗi ở `response_mode=file` cũng là JSON, không có attachment. Envelope và status của các route Caesar, Vigenère, Playfair, Affine, Columnar và Hill MUST NOT đổi. (Truy vết: HTML DES scope §6; quyết định chủ sở hữu Q7; main spec `error-handling`)

#### Scenario: Lỗi khóa không có code
- **WHEN** encrypt với khóa `13345779`
- **THEN** body là đúng `{"success":false,"message":"Khóa phải đúng 16 ký tự hex (64 bit), hiện có 8."}`

#### Scenario: Hill giữ envelope riêng
- **WHEN** một route Hill trả lỗi nghiệp vụ sau change này
- **THEN** body vẫn có `success`, `message`, `code`, `details` như trước

### Requirement: Bảng lỗi DES

Hệ thống SHALL dùng chính xác bảng sau. `{n}` là số ký tự sau khi bỏ khoảng trắng ASCII; `{name}` là tên field. (Truy vết: HTML DES scope §6; quyết định chủ sở hữu Q3, Q7, Q10, Q11)

| Mã | Điều kiện | HTTP | message |
|---|---|---:|---|
| Body | Content-Type không phải JSON được hỗ trợ, JSON hỏng, không phải object, field lạ hoặc trùng; `text`, `key`, `block` không phải string và khác null; `iv` không phải string và khác null | 422 | `Dữ liệu gửi lên không hợp lệ.` |
| DES-E01 | `text` thiếu/null/rỗng; với dữ liệu hex (encrypt `inputFormat=hex`, decrypt, file decrypt) còn rỗng sau khi bỏ khoảng trắng | 422 | `Nhập văn bản hoặc tải file .txt để bắt đầu.` |
| DES-E02 | `key` thiếu/null hoặc rỗng sau khi bỏ khoảng trắng | 422 | `Thiếu khóa. Khóa DES gồm 16 ký tự hex (64 bit).` |
| DES-E03 | Khóa có ký tự ngoài `0–9`, `a–f`, `A–F` | 422 | `Khóa chỉ được chứa ký tự hex 0–9, A–F.` |
| DES-E04 | Khóa hex không đủ hoặc thừa so với 16 ký tự | 422 | `Khóa phải đúng 16 ký tự hex (64 bit), hiện có {n}.` |
| DES-E05 | Dữ liệu hex (bản rõ hex, bản mã) có ký tự không hợp lệ | 422 | `Dữ liệu hex chỉ được chứa ký tự hex 0–9, A–F.` |
| DES-E06 | Độ dài dữ liệu hex không phải bội của 16 | 422 | `Dữ liệu hex phải có độ dài là bội của 16 ký tự hex (64 bit), hiện có {n}.` |
| DES-E07 | Giải mã ra text nhưng PKCS#7 sai | 422 | `Padding không hợp lệ: sai khóa hoặc bản mã bị hỏng.` |
| DES-E08 | Giải mã ra byte không phải UTF-8 | 422 | `Kết quả giải mã không phải văn bản UTF-8 hợp lệ. Thử outputFormat = hex.` |
| DES-E09 | `mode=CBC` mà `iv` thiếu/null hoặc không phải đúng 16 hex sau khi bỏ khoảng trắng | 422 | `IV phải đúng 16 ký tự hex khi dùng chế độ CBC.` |
| DES-E10 | `inputFormat`, `outputFormat`, `mode`, `operation` không thuộc giá trị cho phép (gồm sai kiểu và null) | 422 | `Tham số {name} không hợp lệ.` |
| DES-E11 | Lỗi file | 415/413/422/500 | Message file hiện hành theo `des-file-cipher-api` |
| DES-E12 | UTF-8 của `text` hoặc `block` vượt 5.242.880 byte | 413 | `Dữ liệu vượt quá 5 MiB.` |
| DES-E13 | `/trace` với `block` không phải đúng 16 hex | 422 | `Trace chỉ áp dụng cho đúng 1 khối 16 ký tự hex.` |

#### Scenario: Khóa 8 ký tự (T14)
- **WHEN** encrypt `{"text":"abc","key":"13345779"}`
- **THEN** HTTP 422 với message `Khóa phải đúng 16 ký tự hex (64 bit), hiện có 8.`

#### Scenario: Khóa có ký tự G (T15)
- **WHEN** encrypt `{"text":"abc","key":"133457799BBCDFFG"}`
- **THEN** HTTP 422 với message `Khóa chỉ được chứa ký tự hex 0–9, A–F.`

#### Scenario: Bản mã 15 ký tự (T16)
- **WHEN** decrypt `{"text":"85E813540F0AB40","key":"133457799BBCDFF1"}`
- **THEN** HTTP 422 với message `Dữ liệu hex phải có độ dài là bội của 16 ký tự hex (64 bit), hiện có 15.`

#### Scenario: Padding sai (T17)
- **WHEN** decrypt `{"text":"85E813540F0AB405","key":"133457799BBCDFF1"}`
- **THEN** HTTP 422 với message `Padding không hợp lệ: sai khóa hoặc bản mã bị hỏng.`

#### Scenario: Không phải UTF-8 (T19)
- **WHEN** decrypt `{"text":"09A9EB2F8878EBF8","key":"133457799BBCDFF1"}`
- **THEN** HTTP 422 với message `Kết quả giải mã không phải văn bản UTF-8 hợp lệ. Thử outputFormat = hex.`

#### Scenario: Text rỗng (T20)
- **WHEN** encrypt `{"text":"","key":"133457799BBCDFF1"}`
- **THEN** HTTP 422 với message `Nhập văn bản hoặc tải file .txt để bắt đầu.`

#### Scenario: Thiếu khóa
- **WHEN** encrypt `{"text":"abc"}`
- **THEN** HTTP 422 với message `Thiếu khóa. Khóa DES gồm 16 ký tự hex (64 bit).`

#### Scenario: Hex sai ký tự
- **WHEN** encrypt `{"text":"0123456789ABCDEZ","key":"133457799BBCDFF1","inputFormat":"hex"}`
- **THEN** HTTP 422 với message `Dữ liệu hex chỉ được chứa ký tự hex 0–9, A–F.`

#### Scenario: CBC thiếu IV
- **WHEN** encrypt `{"text":"abc","key":"133457799BBCDFF1","mode":"CBC"}`
- **THEN** HTTP 422 với message `IV phải đúng 16 ký tự hex khi dùng chế độ CBC.`

#### Scenario: Mode sai
- **WHEN** encrypt `{"text":"abc","key":"133457799BBCDFF1","mode":"cbc"}`
- **THEN** HTTP 422 với message `Tham số mode không hợp lệ.`

#### Scenario: Text sai kiểu
- **WHEN** encrypt `{"text":123,"key":"133457799BBCDFF1"}`
- **THEN** HTTP 422 với message `Dữ liệu gửi lên không hợp lệ.`

### Requirement: Thứ tự ưu tiên lỗi JSON

Ba route JSON DES SHALL dừng ở lỗi đầu tiên theo thứ tự: (1) guard hạ tầng 64 MiB; (2) lỗi body; (3) DES-E12; (4) DES-E10 theo thứ tự field `inputFormat`/`outputFormat`, `mode`, `operation`; (5) DES-E02, DES-E03, DES-E04; (6) DES-E09 khi `mode=CBC`; (7) dữ liệu: DES-E01, DES-E05, DES-E06, hoặc DES-E13 với `/trace`; (8) khi xử lý: DES-E07 rồi DES-E08. (Truy vết: HTML DES scope §4; quyết định chủ sở hữu Q13; tiền lệ `hill-error-handling` về đo dung lượng sau parse)

#### Scenario: Body thắng mọi lỗi khác
- **WHEN** JSON có field lạ, text rỗng và khóa sai
- **THEN** HTTP 422 với message `Dữ liệu gửi lên không hợp lệ.`

#### Scenario: Mode sai thắng khóa sai
- **WHEN** `mode="XYZ"` và khóa `abc`
- **THEN** HTTP 422 với message `Tham số mode không hợp lệ.`

#### Scenario: Khóa thắng IV và dữ liệu
- **WHEN** text rỗng, khóa 8 ký tự hex, `mode="CBC"`, không có IV
- **THEN** HTTP 422 với message `Khóa phải đúng 16 ký tự hex (64 bit), hiện có 8.`

#### Scenario: IV thắng dữ liệu
- **WHEN** text rỗng, khóa hợp lệ, `mode="CBC"`, không có IV
- **THEN** HTTP 422 với message `IV phải đúng 16 ký tự hex khi dùng chế độ CBC.`

#### Scenario: Ký tự sai thắng độ dài
- **WHEN** decrypt bản mã `XYZ`
- **THEN** HTTP 422 với message `Dữ liệu hex chỉ được chứa ký tự hex 0–9, A–F.`

### Requirement: Thứ tự ưu tiên lỗi file

Route file DES SHALL dừng ở lỗi đầu tiên theo thứ tự: (1) guard 64 MiB và multipart completion guard; (2) multipart parse, exact field set, field trùng; (3) thiếu file; (4) DES-E02, DES-E03, DES-E04; (5) `action`; (6) `response_mode`; (7) DES-E10 cho `mode`; (8) DES-E09 khi `mode=CBC`; (9) extension; (10) 5 MiB; (11) file rỗng; (12) UTF-8; (13) nội dung: DES-E01, DES-E05, DES-E06 khi decrypt; (14) DES-E07 rồi DES-E08. (Truy vết: quyết định chủ sở hữu Q11, Q13; baseline `affine-error-handling` file precedence)

#### Scenario: Thiếu file thắng khóa
- **WHEN** multipart thiếu file và thiếu `key`
- **THEN** HTTP 422 với message `Thiếu file.`

#### Scenario: Khóa thắng action và extension
- **WHEN** file `bad.md`, khóa `ABC`, `action=foo`
- **THEN** HTTP 422 với message `Khóa phải đúng 16 ký tự hex (64 bit), hiện có 3.`

#### Scenario: Mode sai thắng extension
- **WHEN** file `bad.md`, khóa và action hợp lệ, `mode=OFB`
- **THEN** HTTP 422 với message `Tham số mode không hợp lệ.`

### Requirement: Request guard nhận diện route DES

Theo ngoại lệ hạ tầng được chủ sở hữu phê duyệt, guard `Content-Length` 64 MiB SHALL áp dụng cho bốn route DES: `/api/des/file` trả HTTP 413 `File vượt quá dung lượng tối đa 5 MB.`; `/api/des/encrypt`, `/api/des/decrypt`, `/api/des/trace` trả HTTP 413 `Yêu cầu vượt quá dung lượng cho phép.`. Multipart completion guard và phân loại route file SHALL áp dụng cho chính xác sáu route file Caesar, Vigenère, Playfair, Affine, Columnar và DES; multipart DES thiếu closing boundary trả HTTP 422 `Dữ liệu gửi lên không hợp lệ.`. (Truy vết: ngoại lệ hạ tầng được chủ sở hữu phê duyệt; main spec `columnar-error-handling`, `app-runtime`)

#### Scenario: File DES vượt trần hạ tầng
- **WHEN** `/api/des/file` có một `Content-Length` hợp lệ lớn hơn 64 MiB
- **THEN** guard trả HTTP 413 với message `File vượt quá dung lượng tối đa 5 MB.` trước khi parse multipart

#### Scenario: Text DES vượt trần hạ tầng
- **WHEN** `/api/des/encrypt` có một `Content-Length` hợp lệ lớn hơn 64 MiB
- **THEN** guard trả HTTP 413 với message `Yêu cầu vượt quá dung lượng cho phép.`

#### Scenario: Multipart DES bị cắt
- **WHEN** request `/api/des/file` kết thúc trước closing boundary
- **THEN** HTTP 422 với message `Dữ liệu gửi lên không hợp lệ.`

### Requirement: Lỗi server an toàn và không lộ khóa

Lỗi bất ngờ trong route DES SHALL trả HTTP 500 `Đã xảy ra lỗi hệ thống.`. Log MUST NOT chứa text, khóa, IV, nội dung file hay kết quả. (Truy vết: HTML DES scope §§5, 11; main spec `error-handling`)

#### Scenario: Log 500 không chứa khóa
- **WHEN** một lỗi không dự kiến xảy ra khi xử lý DES
- **THEN** response là HTTP 500 với message `Đã xảy ra lỗi hệ thống.`
- **AND** log không chứa khóa, IV, text hay kết quả
