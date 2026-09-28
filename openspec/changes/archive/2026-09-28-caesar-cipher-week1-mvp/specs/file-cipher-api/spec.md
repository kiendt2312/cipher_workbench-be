## Purpose

Capability này định nghĩa hợp đồng của endpoint `POST /api/caesar/file`: cách nhận file `.txt` qua `multipart/form-data`, toàn bộ quy tắc kiểm tra tên file, dung lượng và encoding, hai chế độ phản hồi `content`/`file`, quy tắc đặt tên file kết quả và quy tắc giữ UTF-8 BOM. Mục tiêu là để người dùng mã hóa hoặc giải mã nội dung một file văn bản, xem trước kết quả và tải kết quả xuống mà không có bất kỳ dữ liệu nào được lưu lại sau request.

## ADDED Requirements

### Requirement: Hợp đồng multipart của endpoint xử lý file

Hệ thống SHALL cung cấp endpoint `POST /api/caesar/file` nhận `multipart/form-data` với các trường: `file` (bắt buộc, file `.txt`), `key` (bắt buộc, số nguyên có dấu), `action` (bắt buộc, nhận đúng một trong hai giá trị `encrypt` hoặc `decrypt`) và `response_mode` (tùy chọn, nhận `content` hoặc `file`, mặc định `content`). Endpoint SHALL áp dụng cùng quy tắc biến đổi Caesar như luồng nhập văn bản từ bàn phím, bao gồm chuẩn hóa key về 0–25 và hỗ trợ key âm hoặc key lớn hơn 25. (Truy vết: docx §4.3, §2.1, §2.4)

#### Scenario: Yêu cầu hợp lệ đầy đủ trường

- **WHEN** client gửi `POST /api/caesar/file` dạng `multipart/form-data` với `file` là một file `.txt` chứa `Hello World`, `key` là `3`, `action` là `encrypt` và `response_mode` là `content`
- **THEN** hệ thống trả HTTP 200
- **AND** thân phản hồi là JSON `{"success": true, "result": "Khoor Zruog"}`

#### Scenario: Bỏ qua response_mode thì mặc định là content

- **WHEN** client gửi yêu cầu hợp lệ có `file`, `key` và `action` nhưng không gửi trường `response_mode`
- **THEN** hệ thống xử lý như `response_mode` bằng `content`
- **AND** trả HTTP 200 với thân phản hồi JSON `{"success": true, "result": "<nội dung đã biến đổi>"}`

#### Scenario: Giải mã nội dung file

- **WHEN** client gửi file `.txt` chứa `Khoor Zruog` với `key` là `3` và `action` là `decrypt`
- **THEN** hệ thống trả HTTP 200
- **AND** `result` bằng `Hello World`

#### Scenario: Key âm và key lớn hơn 25 trên luồng file

- **WHEN** client gửi file `.txt` chứa `Hello World` với `action` là `encrypt` và `key` là `-23`, sau đó gửi lại cùng file với `key` là `29`
- **THEN** cả hai lần đều trả HTTP 200
- **AND** cả hai lần `result` đều bằng `Khoor Zruog`

### Requirement: Chế độ phản hồi content

Khi `response_mode` là `content` và mọi kiểm tra đầu vào đều qua, hệ thống SHALL trả HTTP 200 với thân phản hồi JSON theo success response chuẩn `{"success": true, "result": "<nội dung đã biến đổi>"}`, trong đó `result` là toàn bộ nội dung văn bản của file sau khi mã hóa hoặc giải mã. Nếu file đầu vào có UTF-8 BOM thì BOM SHALL bị loại khỏi `result` vì BOM là dấu hiệu encoding chứ không phải ký tự nội dung. (Truy vết: docx §4.3, §3.2)

#### Scenario: Mode content trả JSON preview

- **WHEN** client gửi file `.txt` không có BOM, `action` là `encrypt` và `response_mode` là `content`
- **THEN** hệ thống trả HTTP 200 với `Content-Type` là `application/json`
- **AND** thân phản hồi chứa `success` bằng `true` và `result` là nội dung đã mã hóa
- **AND** phản hồi không có header `Content-Disposition`

#### Scenario: Mode content loại BOM khỏi result

- **WHEN** client gửi file `.txt` có UTF-8 BOM ở đầu, nội dung văn bản sau BOM là `Hello`, `key` là `3`, `action` là `encrypt` và `response_mode` là `content`
- **THEN** hệ thống trả HTTP 200
- **AND** `result` bằng `Khoor` và không chứa ký tự BOM `U+FEFF` ở đầu

### Requirement: Chế độ phản hồi file trả attachment

Khi `response_mode` là `file` và mọi kiểm tra đầu vào đều qua, hệ thống SHALL trả HTTP 200 với nội dung file kết quả dưới dạng attachment: header `Content-Type` bằng `text/plain; charset=utf-8` và header `Content-Disposition` chứa `attachment` cùng tên file kết quả. Thân phản hồi SHALL là các byte của nội dung đã biến đổi được mã hóa UTF-8, không bọc trong JSON. (Truy vết: docx §4.3, §3.2)

#### Scenario: Mode file trả attachment text/plain

- **WHEN** client gửi file `ghi-chu.txt` chứa `Hello World`, `key` là `3`, `action` là `encrypt` và `response_mode` là `file`
- **THEN** hệ thống trả HTTP 200
- **AND** header `Content-Type` bằng `text/plain; charset=utf-8`
- **AND** header `Content-Disposition` chứa `attachment` và tên file `ghi-chu.encrypted.txt`
- **AND** thân phản hồi là các byte UTF-8 của `Khoor Zruog`, không phải JSON

### Requirement: Quy tắc đặt tên file kết quả

Tên file kết quả trong mode `file` SHALL là `<ten-goc>.encrypted.txt` khi `action` là `encrypt` và `<ten-goc>.decrypted.txt` khi `action` là `decrypt`, trong đó `<ten-goc>` là tên file gốc đã bỏ phần đuôi `.txt` cuối cùng. Ký tự nối giữa `<ten-goc>` và `encrypted`/`decrypted` SHALL là dấu CHẤM `.`, KHÔNG phải dấu gạch dưới `_`. Đuôi của tên file kết quả SHALL luôn là `.txt` viết thường, bất kể tên file gốc viết hoa hay thường. (Truy vết: docx §2.4, §4.3)

#### Scenario: Tên file kết quả khi mã hóa

- **WHEN** client gửi file `ghi-chu.txt` với `action` là `encrypt` và `response_mode` là `file`
- **THEN** tên file trong `Content-Disposition` là `ghi-chu.encrypted.txt`
- **AND** tên file đó KHÔNG phải `ghi-chu_encrypted.txt`

#### Scenario: Tên file kết quả khi giải mã

- **WHEN** client gửi file `ghi-chu.txt` với `action` là `decrypt` và `response_mode` là `file`
- **THEN** tên file trong `Content-Disposition` là `ghi-chu.decrypted.txt`

#### Scenario: Đuôi gốc viết hoa được chuẩn hóa về .txt thường

- **WHEN** client gửi file `BaoCao.TXT` với `action` là `encrypt` và `response_mode` là `file`
- **THEN** tên file trong `Content-Disposition` là `BaoCao.encrypted.txt`

#### Scenario: Tên gốc có nhiều dấu chấm

- **WHEN** client gửi file `bao.cao.v2.txt` với `action` là `encrypt` và `response_mode` là `file`
- **THEN** tên file trong `Content-Disposition` là `bao.cao.v2.encrypted.txt`

### Requirement: Kiểm tra đuôi file .txt không phân biệt hoa thường

Hệ thống SHALL chỉ chấp nhận file có tên kết thúc bằng đuôi `.txt`, so sánh KHÔNG phân biệt hoa thường. File có tên không kết thúc bằng `.txt` — bao gồm đuôi khác, đuôi kép kết thúc bằng phần mở rộng khác, hoặc tên file không có đuôi — SHALL bị từ chối với HTTP 415 và thông báo `Chỉ chấp nhận file .txt.` (Truy vết: docx §2.4, §5)

#### Scenario: Chấp nhận mọi biến thể hoa thường của đuôi txt

- **WHEN** client lần lượt gửi các file tên `a.txt`, `a.TXT` và `a.Txt` với `key` và `action` hợp lệ
- **THEN** cả ba yêu cầu đều vượt qua kiểm tra đuôi file và được xử lý bình thường với HTTP 200

#### Scenario: Từ chối file có đuôi khác

- **WHEN** client gửi file tên `a.md` với `key` và `action` hợp lệ
- **THEN** hệ thống trả HTTP 415
- **AND** thân phản hồi là JSON `{"success": false, "message": "Chỉ chấp nhận file .txt."}`

#### Scenario: Từ chối file có đuôi kép nguy hiểm

- **WHEN** client gửi file tên `a.txt.exe` với `key` và `action` hợp lệ
- **THEN** hệ thống trả HTTP 415
- **AND** `message` bằng `Chỉ chấp nhận file .txt.`

#### Scenario: Từ chối file không có đuôi

- **WHEN** client gửi file tên `readme` không có phần mở rộng, với `key` và `action` hợp lệ
- **THEN** hệ thống trả HTTP 415
- **AND** `message` bằng `Chỉ chấp nhận file .txt.`

### Requirement: Giới hạn dung lượng file 5 MiB

Hệ thống SHALL giữ nguyên giới hạn nghiệp vụ cho nội dung file đầu vào tối đa 5 MiB, tương đương `5 * 1024 * 1024` = `5242880` bytes. File có kích thước nhỏ hơn hoặc bằng `5242880` bytes SHALL được chấp nhận; file lớn hơn `5242880` bytes SHALL bị handler từ chối với HTTP 413 và thông báo `File vượt quá dung lượng tối đa 5 MB.` Thông báo này SHALL được giữ nguyên văn theo bảng lỗi chuẩn dù đơn vị thực tế là MiB. Ngoài giới hạn nghiệp vụ này, request tới tuyến API file có `Content-Length` lớn hơn trần hạ tầng 64 MiB SHALL bị tầng 0 từ chối trước khi parse multipart nhưng vẫn dùng chính thông báo file nói trên; trần hạ tầng MUST NOT thay thế hoặc nới giới hạn 5 MiB của handler. (Truy vết: docx §2.4, §5, §7; ngoại lệ hạ tầng OpenSpec được chủ sở hữu phê duyệt)

#### Scenario: File đúng 5 MiB được chấp nhận

- **WHEN** client gửi file `.txt` có kích thước đúng `5242880` bytes với `key` và `action` hợp lệ
- **THEN** hệ thống trả HTTP 200
- **AND** trả kết quả đã biến đổi theo `response_mode` yêu cầu

#### Scenario: File 5 MiB cộng 1 byte bị từ chối

- **WHEN** client gửi file `.txt` có kích thước `5242881` bytes với `key` và `action` hợp lệ
- **THEN** hệ thống trả HTTP 413
- **AND** thân phản hồi là JSON `{"success": false, "message": "File vượt quá dung lượng tối đa 5 MB."}`

#### Scenario: Request file vượt trần hạ tầng

- **WHEN** client gửi request tới API file có `Content-Length` lớn hơn 64 MiB, bất kể multipart còn có lỗi field nào khác
- **THEN** tầng 0 trả HTTP 413 trước khi phân tích multipart
- **AND** body phản hồi là `{"success": false, "message": "File vượt quá dung lượng tối đa 5 MB."}`

### Requirement: Kiểm tra encoding UTF-8

Hệ thống SHALL chấp nhận file nội dung UTF-8 thường và UTF-8 có BOM. Nếu chuỗi byte của file không decode được bằng UTF-8 — ví dụ file mã hóa latin-1 chứa byte ngoài ASCII hoặc file nhị phân — hệ thống SHALL từ chối với HTTP 415 và thông báo `File phải sử dụng UTF-8.` (Truy vết: docx §2.4, §5)

#### Scenario: Chấp nhận UTF-8 thường

- **WHEN** client gửi file `.txt` mã hóa UTF-8 không BOM chứa tiếng Việt `Xin chào thế giới`
- **THEN** hệ thống trả HTTP 200
- **AND** nội dung kết quả giữ nguyên các ký tự tiếng Việt

#### Scenario: Chấp nhận UTF-8 có BOM

- **WHEN** client gửi file `.txt` bắt đầu bằng chuỗi byte BOM `EF BB BF` rồi tới nội dung UTF-8 hợp lệ
- **THEN** hệ thống trả HTTP 200
- **AND** nội dung được đọc đúng, không coi BOM là ký tự nội dung

#### Scenario: Từ chối file không decode được bằng UTF-8

- **WHEN** client gửi file `.txt` nhỏ hơn 5 MiB chứa chuỗi byte mã hóa latin-1 không hợp lệ theo UTF-8, hoặc file nhị phân đổi tên thành `.txt`, với `key` và `action` hợp lệ
- **THEN** hệ thống trả HTTP 415
- **AND** thân phản hồi là JSON `{"success": false, "message": "File phải sử dụng UTF-8."}`

### Requirement: Giữ nguyên trạng thái UTF-8 BOM ở file tải xuống

Trong mode `file`, nội dung file trả về SHALL phản chiếu đúng trạng thái BOM của file đầu vào: nếu file đầu vào bắt đầu bằng UTF-8 BOM thì các byte trả về SHALL bắt đầu bằng BOM `EF BB BF`; nếu file đầu vào không có BOM thì hệ thống SHALL KHÔNG tự thêm BOM vào kết quả. (Truy vết: docx §2.4)

#### Scenario: File đầu vào có BOM thì file tải xuống giữ BOM

- **WHEN** client gửi file `.txt` có UTF-8 BOM với `response_mode` là `file`
- **THEN** hệ thống trả HTTP 200
- **AND** ba byte đầu của thân phản hồi là `EF BB BF`
- **AND** phần còn lại là nội dung đã biến đổi mã hóa UTF-8

#### Scenario: File đầu vào không có BOM thì kết quả không thêm BOM

- **WHEN** client gửi file `.txt` không có BOM với `response_mode` là `file`
- **THEN** hệ thống trả HTTP 200
- **AND** thân phản hồi KHÔNG bắt đầu bằng byte `EF BB BF`

### Requirement: Kiểm tra sự hiện diện và nội dung rỗng của file

Hệ thống SHALL từ chối yêu cầu thiếu trường `file` với HTTP 422 và thông báo `Thiếu file.`, và từ chối file có kích thước 0 byte với HTTP 422 và thông báo `File không được để trống.` Việc từ chối đầu vào rỗng SHALL được quyết định ở tầng endpoint này, trước khi nội dung được đưa qua bước biến đổi Caesar; quy tắc biến đổi không chịu trách nhiệm báo lỗi rỗng. File chỉ chứa ký tự khoảng trắng, tab hoặc xuống dòng SHALL được coi là HỢP LỆ; chỉ file đúng 0 byte mới bị coi là rỗng. (Truy vết: docx §5, §8)

#### Scenario: Thiếu trường file

- **WHEN** client gửi `multipart/form-data` chỉ có `key` và `action`, không có phần `file`
- **THEN** hệ thống trả HTTP 422
- **AND** thân phản hồi là JSON `{"success": false, "message": "Thiếu file."}`

#### Scenario: File 0 byte

- **WHEN** client gửi file `rong.txt` có kích thước 0 byte với `key`, `action` và `response_mode` hợp lệ
- **THEN** hệ thống trả HTTP 422
- **AND** thân phản hồi là JSON `{"success": false, "message": "File không được để trống."}`

#### Scenario: File chỉ chứa whitespace vẫn hợp lệ

- **WHEN** client gửi file `.txt` có nội dung đúng 3 byte khoảng trắng, hoặc file chỉ chứa khoảng trắng, tab và ký tự xuống dòng, với `key` và `action` hợp lệ
- **THEN** hệ thống trả HTTP 200
- **AND** hệ thống KHÔNG trả lỗi `File không được để trống.`
- **AND** nội dung kết quả giữ nguyên toàn bộ các ký tự whitespace đó

### Requirement: Kiểm tra trường key trong yêu cầu multipart

Hệ thống SHALL yêu cầu trường `key` là số nguyên có dấu. Nếu thiếu `key` hoặc `key` là chuỗi rỗng, hệ thống SHALL trả HTTP 422 với thông báo `Thiếu khóa.` Nếu `key` có mặt nhưng không biểu diễn một số nguyên — ví dụ chữ cái hoặc số thực — hệ thống SHALL trả HTTP 422 với thông báo `Khóa phải là số nguyên.` (Truy vết: docx §4.3, §5)

#### Scenario: Thiếu key

- **WHEN** client gửi yêu cầu có `file` và `action` hợp lệ nhưng không có trường `key`
- **THEN** hệ thống trả HTTP 422
- **AND** thân phản hồi là JSON `{"success": false, "message": "Thiếu khóa."}`

#### Scenario: Key là chuỗi rỗng

- **WHEN** client gửi yêu cầu có `file` và `action` hợp lệ, trường `key` được gửi nhưng là chuỗi rỗng
- **THEN** hệ thống trả HTTP 422
- **AND** thân phản hồi là JSON `{"success": false, "message": "Thiếu khóa."}`
- **AND** hệ thống KHÔNG trả thông báo `Khóa phải là số nguyên.` cho trường hợp này

#### Scenario: Key là chữ

- **WHEN** client gửi `key` bằng `abc`
- **THEN** hệ thống trả HTTP 422
- **AND** thân phản hồi là JSON `{"success": false, "message": "Khóa phải là số nguyên."}`

#### Scenario: Key là số thực

- **WHEN** client gửi `key` bằng `3.5`
- **THEN** hệ thống trả HTTP 422
- **AND** `message` bằng `Khóa phải là số nguyên.`

#### Scenario: Key âm có dấu được chấp nhận

- **WHEN** client gửi `key` bằng `-3` cùng file và `action` hợp lệ
- **THEN** hệ thống trả HTTP 200

### Requirement: Kiểm tra trường action và response_mode

Hệ thống SHALL chỉ chấp nhận `action` bằng `encrypt` hoặc `decrypt`; giá trị khác hoặc thiếu `action` SHALL trả HTTP 422 với thông báo `Action phải là encrypt hoặc decrypt.` Hệ thống SHALL chỉ chấp nhận `response_mode` bằng `content` hoặc `file`; giá trị khác SHALL trả HTTP 422 với thông báo `Response mode phải là content hoặc file.` Việc so khớp giá trị của `action` và `response_mode` SHALL phân biệt hoa thường, tương phản có chủ ý với việc kiểm tra đuôi `.txt` vốn KHÔNG phân biệt hoa thường. (Truy vết: docx §4.3, §5)

#### Scenario: Action không hợp lệ

- **WHEN** client gửi `action` bằng `ENCRYPT` hoặc `ma-hoa` hoặc bỏ trống trường `action`
- **THEN** hệ thống trả HTTP 422
- **AND** thân phản hồi là JSON `{"success": false, "message": "Action phải là encrypt hoặc decrypt."}`

#### Scenario: Response mode không hợp lệ

- **WHEN** client gửi `response_mode` bằng `download`, `json` hoặc `CONTENT` viết hoa
- **THEN** hệ thống trả HTTP 422
- **AND** thân phản hồi là JSON `{"success": false, "message": "Response mode phải là content hoặc file."}`

### Requirement: Thứ tự kiểm tra đầu vào theo hợp đồng chung

Endpoint `POST /api/caesar/file` MUST áp dụng đúng thứ tự kiểm tra xác định đã quy định trong capability `error-handling` và MUST NOT định nghĩa một thứ tự riêng. Ngoại lệ hạ tầng duy nhất là request có `Content-Length` lớn hơn 64 MiB: tầng 0 SHALL từ chối trước khi parse multipart với HTTP 413 và thông báo file. Với mọi request không bị tầng 0 từ chối, thứ tự luồng file là: sự hiện diện của `file` → `key` → `action`; rồi định dạng của `key` → `action` → `response_mode`; rồi đuôi file `.txt` (415); rồi giới hạn nội dung file 5 MiB (413); rồi file 0 byte (422); cuối cùng là giải mã UTF-8 (415). Hệ thống SHALL dừng ở lỗi đầu tiên gặp phải và trả đúng một thông báo duy nhất. (Truy vết: docx §5 — thứ tự do quyết định hợp nhất bổ sung; ngoại lệ hạ tầng OpenSpec được chủ sở hữu phê duyệt)

#### Scenario: Key sai định dạng được báo trước lỗi đuôi file và dung lượng

- **WHEN** client gửi file `a.md` kích thước 6 MiB với `key` bằng `abc` và `action` bằng `encrypt`
- **THEN** hệ thống trả HTTP 422
- **AND** thân phản hồi là JSON `{"success": false, "message": "Khóa phải là số nguyên."}`

#### Scenario: Lỗi đuôi file được báo trước lỗi dung lượng

- **WHEN** client gửi file `a.md` kích thước 6 MiB với `key` bằng `3` và `action` bằng `encrypt`
- **THEN** hệ thống trả HTTP 415
- **AND** thân phản hồi là JSON `{"success": false, "message": "Chỉ chấp nhận file .txt."}`

#### Scenario: Lỗi dung lượng được báo trước lỗi bảng mã

- **WHEN** client gửi file `a.txt` kích thước 6 MiB có nội dung không giải mã được bằng UTF-8, với `key` và `action` hợp lệ
- **THEN** hệ thống trả HTTP 413
- **AND** thân phản hồi là JSON `{"success": false, "message": "File vượt quá dung lượng tối đa 5 MB."}`

#### Scenario: Response mode sai định dạng được báo trước lỗi file 0 byte

- **WHEN** client gửi file `rong.txt` kích thước 0 byte với `key` và `action` hợp lệ và `response_mode` bằng `download`
- **THEN** hệ thống trả HTTP 422
- **AND** thân phản hồi là JSON `{"success": false, "message": "Response mode phải là content hoặc file."}`

### Requirement: Lỗi đọc file trả về lỗi hệ thống

Nếu hệ thống không đọc được chuỗi byte của file đã tải lên vì sự cố kỹ thuật, hệ thống SHALL trả HTTP 500 với thông báo `Không thể đọc file.` và SHALL KHÔNG để lộ chi tiết kỹ thuật hay stack trace ra phản hồi. (Truy vết: docx §5)

#### Scenario: Không đọc được luồng dữ liệu của file

- **WHEN** quá trình đọc nội dung file đã tải lên thất bại vì lỗi vào/ra
- **THEN** hệ thống trả HTTP 500
- **AND** thân phản hồi là JSON `{"success": false, "message": "Không thể đọc file."}`
- **AND** phản hồi không chứa stack trace hoặc tên lỗi kỹ thuật

### Requirement: Mọi lỗi đều trả JSON kể cả trong mode file

Mọi trường hợp lỗi của endpoint `POST /api/caesar/file` SHALL trả error response chuẩn `{"success": false, "message": "<thông báo>"}` với `Content-Type` là `application/json`, KỂ CẢ khi yêu cầu đặt `response_mode` bằng `file`. Hệ thống SHALL KHÔNG bao giờ trả attachment cho một yêu cầu lỗi: phản hồi lỗi SHALL không có header `Content-Disposition` dạng `attachment` và không có `Content-Type` là `text/plain`. (Truy vết: docx §4.3, §5)

#### Scenario: Lỗi đuôi file trong mode file vẫn trả JSON

- **WHEN** client gửi file `a.md` với `key` và `action` hợp lệ và `response_mode` bằng `file`
- **THEN** hệ thống trả HTTP 415 với `Content-Type` là `application/json`
- **AND** thân phản hồi là JSON `{"success": false, "message": "Chỉ chấp nhận file .txt."}`
- **AND** phản hồi không có header `Content-Disposition` dạng `attachment`

#### Scenario: Lỗi dung lượng trong mode file vẫn trả JSON

- **WHEN** client gửi file `.txt` kích thước `5242881` bytes với `key` và `action` hợp lệ và `response_mode` bằng `file`
- **THEN** hệ thống trả HTTP 413 với thân phản hồi JSON `{"success": false, "message": "File vượt quá dung lượng tối đa 5 MB."}`
- **AND** phản hồi không phải attachment

#### Scenario: Lỗi khóa trong mode file vẫn trả JSON

- **WHEN** client gửi file `.txt` hợp lệ nhưng `key` bằng `abc` và `response_mode` bằng `file`
- **THEN** hệ thống trả HTTP 422 với thân phản hồi JSON `{"success": false, "message": "Khóa phải là số nguyên."}`
- **AND** phản hồi không phải attachment

### Requirement: Bảo toàn nội dung văn bản sau khi biến đổi

Nội dung file kết quả SHALL giữ nguyên cấu trúc của nội dung gốc ngoài phần ký tự ASCII chữ cái được dịch: ký tự xuống dòng, khoảng trắng, chữ số, ký tự đặc biệt, ký tự tiếng Việt và mọi ký tự Unicode ngoài `A-Z`/`a-z` SHALL không bị thay đổi, và số lượng cũng như thứ tự dòng SHALL được giữ nguyên. Kiểu ký tự kết thúc dòng SHALL được bảo toàn nguyên trạng: chuỗi `\r\n` trong file đầu vào SHALL KHÔNG bị chuẩn hóa thành `\n`, và file đầu vào chỉ dùng `\n` SHALL KHÔNG bị tự thêm `\r`. (Truy vết: docx §2.1, §2.4)

#### Scenario: Giữ nguyên xuống dòng và số dòng

- **WHEN** client gửi file `.txt` gồm ba dòng văn bản với `key` là `3` và `action` là `encrypt`
- **THEN** nội dung kết quả cũng gồm đúng ba dòng, giữ nguyên vị trí các ký tự xuống dòng

#### Scenario: Giữ nguyên tiếng Việt và ký tự đặc biệt

- **WHEN** client gửi file `.txt` chứa `Xin chào ABC 123 !@#` với `key` là `3` và `action` là `encrypt`
- **THEN** các ký tự tiếng Việt có dấu, chữ số `123` và ký tự đặc biệt `!@#` giữ nguyên trong kết quả
- **AND** chỉ các ký tự ASCII chữ cái bị dịch

#### Scenario: Giữ nguyên ký tự kết thúc dòng CRLF

- **WHEN** client gửi file `.txt` dùng ký tự kết thúc dòng CRLF (`\r\n`) với `key` là `3`, `action` là `encrypt` và `response_mode` là `file`
- **THEN** nội dung kết quả vẫn dùng CRLF ở đúng các vị trí xuống dòng như file gốc
- **AND** số byte `0D` và số byte `0A` trong kết quả bằng đúng số byte tương ứng trong file gốc
- **AND** không có chuỗi `\r\n` nào bị chuẩn hóa thành `\n`

#### Scenario: Không tự thêm CR vào file dùng LF

- **WHEN** client gửi file `.txt` chỉ dùng ký tự kết thúc dòng LF (`\n`) với `response_mode` là `file`
- **THEN** nội dung kết quả chỉ chứa `\n` ở các vị trí xuống dòng
- **AND** kết quả không chứa thêm byte `0D` nào so với file gốc

#### Scenario: Mã hóa rồi giải mã cùng khóa khôi phục nội dung gốc

- **WHEN** client mã hóa một file `.txt` với `key` là `7`, sau đó gửi nội dung kết quả trở lại endpoint với `key` là `7` và `action` là `decrypt`
- **THEN** nội dung nhận được bằng đúng nội dung văn bản của file gốc

### Requirement: Không lưu trữ file và kết quả sau request

Ứng dụng SHALL xử lý file hoàn toàn trong phạm vi một request và SHALL KHÔNG lưu file đã tải lên, nội dung file hay kết quả biến đổi ở bất kỳ vị trí lưu trữ lâu dài nào sau khi phản hồi được trả về. Hệ thống SHALL KHÔNG cung cấp bất kỳ cách nào để truy xuất lại nội dung hoặc kết quả của một request đã kết thúc. (Truy vết: docx §8)

#### Scenario: Không còn dấu vết sau khi request kết thúc

- **WHEN** một yêu cầu `POST /api/caesar/file` hoàn tất và phản hồi đã được trả về
- **THEN** không có file tải lên hay file kết quả nào còn tồn tại trên hệ thống
- **AND** không có endpoint nào cho phép truy xuất lại nội dung hoặc kết quả của request đó

#### Scenario: Các request độc lập với nhau

- **WHEN** client gửi hai yêu cầu liên tiếp với hai file và hai khóa khác nhau
- **THEN** kết quả của mỗi yêu cầu chỉ phụ thuộc vào dữ liệu của chính yêu cầu đó
- **AND** yêu cầu sau không bị ảnh hưởng bởi file hay kết quả của yêu cầu trước
