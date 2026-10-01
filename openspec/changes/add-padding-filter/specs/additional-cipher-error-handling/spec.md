## MODIFIED Requirements

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
| `strip_padding` của Playfair file sai | `Tùy chọn lọc ký tự đệm phải là true hoặc false.` |
| Thiếu file part | `Thiếu file.` |
| File 0 byte | `File không được để trống.` |

Các message mới trong bảng là quyết định contract của change đã thêm chúng; các message kế thừa MUST giữ nguyên baseline. (Truy vết: scope mới BE-VIG-04, BE-VIG-05, BE-PLAY-04, BE-PLAY-05; quyết định chủ sở hữu cho change Playfair/Vigenère; baseline Caesar Week 1 `error-handling`; quyết định chủ sở hữu ngày 2026-10-01 cho message `strip_padding`)

#### Scenario: Error example tiếng Anh trong scope không được trả ra ngoài
- **WHEN** key Vigenère có ký tự không hợp lệ
- **THEN** message là `Khóa Vigenère chỉ được chứa chữ cái A-Z hoặc a-z.`
- **AND** message không phải `Vigenère key must contain letters only.`

#### Scenario: Ciphertext Playfair lẻ dùng message canonical
- **WHEN** ciphertext Playfair sau normalization có số chữ cái lẻ
- **THEN** hệ thống trả HTTP 422
- **AND** message là `Bản mã Playfair phải chứa số lượng chữ cái chẵn.`

#### Scenario: strip_padding sai dùng message canonical
- **WHEN** request Playfair file gửi `strip_padding=1`
- **THEN** hệ thống trả HTTP 422
- **AND** body là `{"success":false,"message":"Tùy chọn lọc ký tự đệm phải là true hoặc false."}`

### Requirement: Thứ tự lỗi xác định và dừng tại lỗi đầu tiên

Sau tầng 0, các endpoint mới SHALL áp dụng đúng precedence được mô tả trong `additional-text-cipher-api` và `additional-file-cipher-api`: cấu trúc body trước field; sự hiện diện trước định dạng; key/action/response mode/`strip_padding` trước validation file; extension trước size, rồi 0 byte, UTF-8 và cuối cùng validation nội dung Playfair. Hệ thống MUST trả đúng một lỗi đầu tiên, để cùng request luôn có cùng status/message. (Truy vết: quyết định chủ sở hữu kế thừa baseline Caesar Week 1 `error-handling`; quyết định chủ sở hữu ngày 2026-10-01 cho `strip_padding`)

#### Scenario: Lỗi key thắng lỗi file và Playfair content
- **WHEN** request Playfair file có key normalize thành rỗng, extension sai và nội dung không có ASCII letter
- **THEN** hệ thống trả HTTP 422 với message key Playfair
- **AND** không trả lỗi extension hoặc lỗi text Playfair

#### Scenario: Response mode sai thắng strip_padding sai
- **WHEN** request Playfair file có `response_mode=FILE` và `strip_padding=yes`
- **THEN** hệ thống trả HTTP 422 với message `Response mode phải là content hoặc file.`
