# additional-file-cipher-api Specification

## Purpose

Định nghĩa hai endpoint multipart xử lý file Vigenère và Playfair bằng chính core của luồng text, đồng thời kế thừa đầy đủ giới hạn, encoding, BOM và attachment contract đã nghiệm thu của Caesar.

## Requirements

### Requirement: Hợp đồng multipart của hai endpoint file mới

Hệ thống SHALL cung cấp `POST /api/vigenere/file` và `POST /api/playfair/file`, nhận `multipart/form-data` với `file` bắt buộc, `key` bắt buộc dưới dạng chuỗi, `action` bắt buộc bằng chính xác `encrypt` hoặc `decrypt`, và `response_mode` tùy chọn bằng `content` hoặc `file`, mặc định `content`. `action` và `response_mode` SHALL phân biệt hoa thường. Mỗi endpoint SHALL dùng cùng core tương ứng với endpoint text. (Truy vết: scope mới BE-VIG-03, BE-PLAY-03; quyết định chủ sở hữu cho change này; baseline Caesar Week 1 `file-cipher-api`)

#### Scenario: Vigenère file content mode
- **WHEN** client gửi file `.txt` chứa `Attack at dawn!`, key `LEMON`, action `encrypt` và `response_mode=content` tới `/api/vigenere/file`
- **THEN** hệ thống trả HTTP 200
- **AND** body là `{"success":true,"result":"Lxfopv ef rnhr!"}`

#### Scenario: Playfair file content mode
- **WHEN** client gửi file `.txt` chứa `HIDE THE GOLD IN THE TREE STUMP`, key `PLAYFAIR EXAMPLE`, action `encrypt` và `response_mode=content` tới `/api/playfair/file`
- **THEN** hệ thống trả HTTP 200
- **AND** body là `{"success":true,"result":"BMODZBXDNABEKUDMUIXMMOUVIF"}`

#### Scenario: Bỏ response mode mặc định content
- **WHEN** client gửi `file`, `key` và `action` hợp lệ nhưng không gửi `response_mode`
- **THEN** endpoint xử lý như `response_mode=content`

### Requirement: Content mode trả JSON đúng hai trường

Khi `response_mode=content` và request hợp lệ, endpoint SHALL trả HTTP 200 với `Content-Type: application/json` và đúng body `{"success":true,"result":"<nội dung kết quả>"}`. Nếu file đầu vào có UTF-8 BOM, BOM SHALL không xuất hiện trong chuỗi `result`. Response MUST NOT có `Content-Disposition`, `normalizedInput`, `message`, `code` hoặc metadata khác. (Truy vết: quyết định chủ sở hữu cho change này; baseline Caesar Week 1 `file-cipher-api`, `error-handling`)

#### Scenario: Content mode loại BOM khỏi result
- **WHEN** file UTF-8 có BOM chứa `Attack` được encrypt Vigenère với key `LEMON` ở content mode
- **THEN** `result` là `Lxfopv`
- **AND** `result` không bắt đầu bằng `U+FEFF`

### Requirement: File mode trả attachment do server sở hữu

Khi `response_mode=file` và request hợp lệ, endpoint SHALL trả HTTP 200 với `Content-Type: text/plain; charset=utf-8`, `Content-Disposition: attachment` và filename do server tạo. Body SHALL là bytes UTF-8 của kết quả, không bọc JSON. Client MUST dùng response attachment này làm nguồn download cho file upload thay vì tự tạo download từ preview. (Truy vết: quyết định chủ sở hữu cho change này; baseline Caesar Week 1 `file-cipher-api`, `repo_docs/frontend-integration.md`)

#### Scenario: Vigenère trả attachment
- **WHEN** client gửi `note.txt` hợp lệ tới `/api/vigenere/file` với action `encrypt` và `response_mode=file`
- **THEN** hệ thống trả attachment `note.encrypted.txt`

#### Scenario: Playfair trả attachment
- **WHEN** client gửi `secret.txt` hợp lệ tới `/api/playfair/file` với action `decrypt` và `response_mode=file`
- **THEN** hệ thống trả attachment `secret.decrypted.txt`

### Requirement: Quy tắc filename kết quả giữ nguyên baseline

Filename attachment SHALL là `<ten-goc>.encrypted.txt` cho action `encrypt` và `<ten-goc>.decrypted.txt` cho action `decrypt`. Hệ thống SHALL chỉ bỏ phần đuôi `.txt` cuối cùng không phân biệt hoa thường, giữ nguyên các dấu chấm khác và luôn dùng `.txt` viết thường cho output. Tên file MUST NOT thêm tên thuật toán hoặc dùng dấu gạch dưới. (Truy vết: quyết định chủ sở hữu cho change này; baseline Caesar Week 1 `file-cipher-api`)

#### Scenario: Tên có nhiều dấu chấm và đuôi viết hoa
- **WHEN** file đầu vào là `bao.cao.TXT`, action là `encrypt` và mode là `file`
- **THEN** filename kết quả là `bao.cao.encrypted.txt`

### Requirement: Chỉ nhận đuôi txt không phân biệt hoa thường

Hai endpoint SHALL chỉ nhận filename kết thúc bằng `.txt` không phân biệt hoa thường. File sai đuôi, không có đuôi hoặc có đuôi kép kết thúc bằng phần khác SHALL bị từ chối bằng HTTP 415 với body `{"success":false,"message":"Chỉ chấp nhận file .txt."}`. (Truy vết: scope mới BE-VIG-04, BE-PLAY-04; baseline Caesar Week 1 `file-cipher-api`)

#### Scenario: Đuôi TXT được chấp nhận
- **WHEN** filename là `DATA.TXT` và các trường khác hợp lệ
- **THEN** file vượt qua kiểm tra extension

#### Scenario: Đuôi kép nguy hiểm bị từ chối
- **WHEN** filename là `data.txt.exe`
- **THEN** hệ thống trả HTTP 415 với message `Chỉ chấp nhận file .txt.`

### Requirement: Giới hạn file chính xác 5 MiB

Giới hạn nghiệp vụ SHALL là `5 * 1024 * 1024 = 5242880` bytes nội dung file. File đúng `5242880` bytes SHALL vượt qua bước kiểm tra dung lượng; file từ `5242881` bytes trở lên MUST trả HTTP 413 với body `{"success":false,"message":"File vượt quá dung lượng tối đa 5 MB."}`. Chuỗi message cố ý dùng `5 MB` để tương thích baseline dù phép đo là MiB. (Truy vết: scope mới BE-VIG-04, BE-PLAY-04; quyết định chủ sở hữu cho change này; baseline Caesar Week 1 `file-cipher-api`)

#### Scenario: Đúng 5 MiB qua kiểm tra dung lượng
- **WHEN** file có đúng `5242880` bytes và extension hợp lệ
- **THEN** endpoint không từ chối vì dung lượng
- **AND** tiếp tục các bước validation sau

#### Scenario: 5 MiB cộng một byte bị từ chối
- **WHEN** file có `5242881` bytes
- **THEN** hệ thống trả HTTP 413 với message `File vượt quá dung lượng tối đa 5 MB.`

### Requirement: File bắt buộc, khác 0 byte và phải là UTF-8

Thiếu part `file` MUST trả HTTP 422 `Thiếu file.`; file 0 byte MUST trả HTTP 422 `File không được để trống.`; bytes không decode được bằng UTF-8 MUST trả HTTP 415 `File phải sử dụng UTF-8.`. File UTF-8 thường và UTF-8 có BOM SHALL được chấp nhận. Whitespace-only file hợp lệ với Vigenère nhưng sau normalization SHALL bị từ chối với Playfair. (Truy vết: scope mới BE-VIG-03, BE-VIG-04, BE-PLAY-03, BE-PLAY-04; baseline Caesar Week 1 `file-cipher-api`)

#### Scenario: File 0 byte bị từ chối
- **WHEN** upload có filename `.txt` nhưng không có byte nội dung
- **THEN** hệ thống trả HTTP 422 với message `File không được để trống.`

#### Scenario: Whitespace-only khác nhau theo thuật toán
- **WHEN** cùng file whitespace-only và key hợp lệ được gửi tới hai endpoint
- **THEN** Vigenère trả thành công với nội dung giữ nguyên
- **AND** Playfair trả HTTP 422 với message `Văn bản Playfair phải chứa ít nhất một chữ cái A-Z hoặc a-z.`

#### Scenario: Encoding không hợp lệ
- **WHEN** file `.txt` chứa bytes không giải mã được bằng UTF-8
- **THEN** hệ thống trả HTTP 415 với message `File phải sử dụng UTF-8.`

### Requirement: Bảo toàn trạng thái UTF-8 BOM trong attachment

File mode SHALL thêm lại UTF-8 BOM `EF BB BF` nếu và chỉ nếu file đầu vào có BOM. Content mode và dữ liệu logic đưa vào core SHALL không chứa `U+FEFF`. Hệ thống MUST NOT tự thêm BOM cho input không có BOM. (Truy vết: quyết định chủ sở hữu cho change này; baseline Caesar Week 1 `file-cipher-api`)

#### Scenario: Input có BOM thì attachment có BOM
- **WHEN** file đầu vào có UTF-8 BOM và request file mode thành công
- **THEN** body attachment bắt đầu bằng bytes `EF BB BF`

#### Scenario: Input không BOM thì attachment không BOM
- **WHEN** file đầu vào không có BOM và request file mode thành công
- **THEN** body attachment không bắt đầu bằng bytes `EF BB BF`

### Requirement: Hành vi nội dung file theo từng thuật toán

Vigenère SHALL giữ nguyên line break, whitespace, số, dấu câu và Unicode, đồng thời không làm tiến key trên các ký tự đó. Playfair SHALL normalize toàn bộ nội dung file thành stream ASCII uppercase, loại non-letter và map `J` thành `I`; do đó line break/format trong input Playfair không xuất hiện trong output. Decrypt Playfair SHALL giữ filler giữa chuỗi và bỏ đúng một filler cuối như `playfair-core`. (Truy vết: scope mới BE-VIG-03, BE-PLAY-03; quyết định chủ sở hữu cho change này)

#### Scenario: Vigenère giữ CRLF
- **WHEN** file Vigenère chứa `A\r\nA` và key `BC`
- **THEN** kết quả là `B\r\nC`
- **AND** CRLF không làm tiến key

#### Scenario: Playfair loại newline và dấu câu
- **WHEN** file Playfair chứa `HIDE\r\nTHE GOLD!` và keyword `PLAYFAIR EXAMPLE`
- **THEN** core nhận chuỗi normalized tương đương `HIDETHEGOLD`

### Requirement: Validate key, action và response mode của multipart

Key vắng mặt, `null` theo nghĩa part không có giá trị, hoặc chuỗi rỗng MUST trả HTTP 422 `Thiếu khóa.`. Key Vigenère không khớp toàn bộ `[A-Za-z]+` MUST trả lỗi key Vigenère; key Playfair không còn ASCII letter sau normalization MUST trả lỗi key Playfair. `action` thiếu hoặc khác `encrypt|decrypt` MUST trả HTTP 422 `Action phải là encrypt hoặc decrypt.`. `response_mode` khác `content|file` MUST trả HTTP 422 `Response mode phải là content hoặc file.`. (Truy vết: scope mới BE-VIG-04, BE-PLAY-04; baseline Caesar Week 1 `file-cipher-api`; quyết định chủ sở hữu cho change này)

#### Scenario: Key Vigenère multipart sai
- **WHEN** key multipart là `KEY 1`
- **THEN** hệ thống trả HTTP 422 với message `Khóa Vigenère chỉ được chứa chữ cái A-Z hoặc a-z.`

#### Scenario: Key Playfair multipart normalize thành rỗng
- **WHEN** key multipart là `123 ---`
- **THEN** hệ thống trả HTTP 422 với message `Khóa Playfair phải chứa ít nhất một chữ cái A-Z hoặc a-z.`

#### Scenario: Response mode viết hoa bị từ chối
- **WHEN** `response_mode=FILE`
- **THEN** hệ thống trả HTTP 422 với message `Response mode phải là content hoặc file.`

### Requirement: Validation Playfair sau khi đọc file

Sau khi extension, dung lượng, 0 byte và UTF-8 đã hợp lệ, endpoint Playfair SHALL áp dụng validation nội dung như endpoint text. Nội dung không còn ASCII letter, ciphertext decrypt lẻ hoặc ciphertext có digraph trùng SHALL lần lượt trả các message Playfair tương ứng với HTTP 422. (Truy vết: scope mới BE-PLAY-04, BE-PLAY-05; quyết định chủ sở hữu cho change này)

#### Scenario: File Playfair decrypt có ciphertext lẻ
- **WHEN** file hợp lệ chứa `ABC`, key hợp lệ và action `decrypt`
- **THEN** hệ thống trả HTTP 422 với message `Bản mã Playfair phải chứa số lượng chữ cái chẵn.`

### Requirement: Validation precedence của endpoint file

Sau tầng 0, hai endpoint SHALL kiểm theo thứ tự: multipart phải parse được; `file` hiện diện; `key` hiện diện; `action` hiện diện/hợp lệ về sự hiện diện; key đúng quy tắc thuật toán; `action` đúng giá trị; `response_mode` đúng giá trị; extension; 5 MiB; file 0 byte; UTF-8; cuối cùng validation nội dung Playfair sau normalization nếu áp dụng. Hệ thống MUST dừng ở lỗi đầu tiên và trả đúng một message. (Truy vết: quyết định chủ sở hữu kế thừa baseline Caesar Week 1 `error-handling`)

#### Scenario: Key sai được báo trước extension sai
- **WHEN** gửi file `bad.md` với key Vigenère `KEY 1` và action hợp lệ
- **THEN** hệ thống trả HTTP 422 với message key Vigenère
- **AND** không trả lỗi extension

#### Scenario: Encoding sai được báo trước nội dung Playfair sai
- **WHEN** file Playfair có extension/dung lượng hợp lệ nhưng bytes không phải UTF-8 và nếu đọc giả định cũng không có ASCII letter
- **THEN** hệ thống trả HTTP 415 với message `File phải sử dụng UTF-8.`

### Requirement: Mọi lỗi file vẫn là JSON

Bất kể `response_mode`, mọi lỗi SHALL trả JSON đúng hai trường `success=false` và `message`, không trả attachment, file rỗng, `code`, `detail` hoặc stack trace. (Truy vết: quyết định chủ sở hữu cho change này; baseline Caesar Week 1 `error-handling`)

#### Scenario: Lỗi ở file mode không kích hoạt download
- **WHEN** request `response_mode=file` bị từ chối vì ciphertext Playfair lẻ
- **THEN** response là JSON lỗi HTTP 422
- **AND** response không có `Content-Disposition: attachment`

### Requirement: Không thay đổi endpoint file Caesar

Việc thêm hai endpoint file mới MUST NOT thay đổi request, response, validation precedence, file limit, guard behavior, BOM, filename hoặc kết quả của `POST /api/caesar/file`. (Truy vết: quyết định chủ sở hữu cho change này; completed change `caesar-cipher-week1-mvp`)

#### Scenario: Caesar file contract vẫn giữ nguyên
- **WHEN** cùng một request Caesar file hợp lệ được gửi trước và sau change
- **THEN** response quan sát được giống hệt baseline Week 1
