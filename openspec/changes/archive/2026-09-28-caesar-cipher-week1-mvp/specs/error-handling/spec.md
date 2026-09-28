## Purpose

Định nghĩa hợp đồng chung về khuôn dạng phản hồi và hành vi xử lý lỗi cho toàn bộ hệ thống Caesar Cipher: mọi endpoint đều trả về cùng một cấu trúc thành công/thất bại, mọi trường hợp lỗi đều được ánh xạ sang đúng HTTP status và thông báo tiếng Việt chuẩn, và không có chi tiết kỹ thuật nào bị lộ ra ngoài.

## ADDED Requirements

### Requirement: Khuôn dạng response thành công thống nhất

Mọi phản hồi thành công trả về dưới dạng JSON của các endpoint dưới `/api/caesar/` SHALL có đúng hai trường: `success` bằng `true` và `result` chứa chuỗi kết quả. Hệ thống MUST NOT thêm trường phụ nào khác vào thân phản hồi thành công. Phản hồi thành công SHALL dùng HTTP status 200. (Truy vết: docx §4.2, §5)

#### Scenario: Phản hồi thành công của endpoint văn bản

- **WHEN** một yêu cầu hợp lệ tới `POST /api/caesar/encrypt` hoặc `POST /api/caesar/decrypt` được xử lý xong
- **THEN** hệ thống trả HTTP 200 với thân JSON `{"success": true, "result": "<chuỗi kết quả>"}`
- **AND** thân phản hồi không chứa bất kỳ trường nào ngoài `success` và `result`

#### Scenario: Phản hồi thành công của endpoint file ở chế độ content

- **WHEN** một yêu cầu hợp lệ tới `POST /api/caesar/file` với `response_mode=content` được xử lý xong
- **THEN** hệ thống trả HTTP 200 với thân JSON `{"success": true, "result": "<nội dung đã xử lý>"}`
- **AND** thân phản hồi không chứa bất kỳ trường nào ngoài `success` và `result`

### Requirement: Khuôn dạng error response thống nhất

Mọi phản hồi lỗi của các endpoint dưới `/api/caesar/` SHALL là JSON có đúng hai trường: `success` bằng `false` và `message` chứa thông báo tiếng Việt dành cho người dùng cuối. Hệ thống MUST NOT trả thêm bất kỳ trường nào khác (ví dụ trường mô tả lỗi mặc định do tầng vận chuyển sinh ra, machine-readable error code, danh sách lỗi chi tiết theo từng field). Các lỗi được tầng vận chuyển tự động phát hiện trước khi vào logic nghiệp vụ (sai kiểu dữ liệu, thiếu trường bắt buộc, thân yêu cầu không phải JSON hợp lệ, hoặc vượt trần hạ tầng) cũng SHALL được chuyển về đúng khuôn dạng này. Mười ba thông báo trong docx §5 tiếp tục là tập thông báo nghiệp vụ chuẩn; thông báo `Yêu cầu vượt quá dung lượng cho phép.` là ngoại lệ hạ tầng được chủ sở hữu phê duyệt và MUST NOT được coi là thông báo nghiệp vụ thứ 14. (Truy vết: docx §5, §6; ngoại lệ hạ tầng OpenSpec được chủ sở hữu phê duyệt)

#### Scenario: Lỗi nghiệp vụ trả đúng khuôn dạng chuẩn

- **WHEN** một yêu cầu tới bất kỳ endpoint nào dưới `/api/caesar/` bị từ chối vì dữ liệu đầu vào không hợp lệ
- **THEN** hệ thống trả thân JSON `{"success": false, "message": "<thông báo tiếng Việt>"}`
- **AND** thân phản hồi không chứa trường nào khác ngoài `success` và `message`

#### Scenario: Lỗi validation tự sinh được chuẩn hóa

- **WHEN** một yêu cầu bị từ chối bởi cơ chế kiểm tra kiểu dữ liệu tự động trước khi vào logic nghiệp vụ, ví dụ `key` được gửi dưới dạng chuỗi trong `POST /api/caesar/encrypt`
- **THEN** hệ thống trả thân JSON chỉ gồm `success` và `message` theo khuôn dạng chuẩn
- **AND** thân phản hồi không chứa cấu trúc lỗi mặc định của tầng vận chuyển, không chứa trường `detail`, không liệt kê vị trí field hay tên kiểu dữ liệu

#### Scenario: Thông báo lỗi luôn bằng tiếng Việt

- **WHEN** bất kỳ phản hồi lỗi nào được trả về từ các endpoint dưới `/api/caesar/`
- **THEN** giá trị của `message` là một câu tiếng Việt mô tả được vấn đề cho người dùng cuối
- **AND** `message` không chứa thuật ngữ kỹ thuật nội bộ hay văn bản tiếng Anh do hệ thống tự sinh

### Requirement: Ánh xạ lỗi HTTP 413 cho file vượt dung lượng

Khi file tải lên vượt quá giới hạn 5 MiB, hệ thống SHALL trả HTTP status 413 kèm thông báo nguyên văn `File vượt quá dung lượng tối đa 5 MB.`. (Truy vết: docx §5)

#### Scenario: File lớn hơn 5 MiB

- **WHEN** người dùng gửi `POST /api/caesar/file` với file có kích thước lớn hơn 5 MiB
- **THEN** hệ thống trả HTTP 413
- **AND** thân phản hồi là `{"success": false, "message": "File vượt quá dung lượng tối đa 5 MB."}`

### Requirement: Ánh xạ HTTP 413 cho trần hạ tầng theo tuyến

Khi tầng 0 phát hiện `Content-Length` lớn hơn 64 MiB, hệ thống SHALL trả HTTP 413 trước khi đọc hoặc phân tích thân yêu cầu. Việc chọn thông báo MUST dựa trên tuyến request, không dựa trên `Content-Type`: tuyến API file dùng thông báo file hiện có `File vượt quá dung lượng tối đa 5 MB.`, mọi tuyến khác dùng `Yêu cầu vượt quá dung lượng cho phép.`. Thông báo generic MUST NOT nêu con số 64 MiB và cả hai phản hồi MUST giữ nguyên error envelope hai trường, không có machine-readable error code. Đây là ngoại lệ hạ tầng OpenSpec được chủ sở hữu phê duyệt; giới hạn file nghiệp vụ 5 MiB và 13 thông báo docx §5 không thay đổi. (Truy vết: ngoại lệ hạ tầng OpenSpec được chủ sở hữu phê duyệt; docx §2.4, §5)

#### Scenario: Request không phải tuyến file vượt 64 MiB

- **WHEN** request tới một tuyến không phải API file có `Content-Length` lớn hơn 64 MiB
- **THEN** hệ thống trả HTTP 413 trước khi phân tích body
- **AND** thân phản hồi là `{"success": false, "message": "Yêu cầu vượt quá dung lượng cho phép."}`
- **AND** thông báo không nêu con số 64 MiB

#### Scenario: Request tới tuyến file vượt 64 MiB

- **WHEN** request tới API file có `Content-Length` lớn hơn 64 MiB
- **THEN** hệ thống trả HTTP 413 trước khi phân tích multipart
- **AND** thân phản hồi là `{"success": false, "message": "File vượt quá dung lượng tối đa 5 MB."}`

### Requirement: Ánh xạ lỗi HTTP 415 cho file không được hỗ trợ

Khi file tải lên không đúng định dạng hoặc không đúng bảng mã được hỗ trợ, hệ thống SHALL trả HTTP status 415 kèm thông báo nguyên văn tương ứng: `Chỉ chấp nhận file .txt.` cho file sai đuôi và `File phải sử dụng UTF-8.` cho file không giải mã được bằng UTF-8. (Truy vết: docx §5)

#### Scenario: File không có đuôi .txt

- **WHEN** người dùng gửi `POST /api/caesar/file` với file không có đuôi `.txt`
- **THEN** hệ thống trả HTTP 415
- **AND** thân phản hồi là `{"success": false, "message": "Chỉ chấp nhận file .txt."}`

#### Scenario: File không phải UTF-8

- **WHEN** người dùng gửi `POST /api/caesar/file` với file có nội dung không giải mã được bằng UTF-8
- **THEN** hệ thống trả HTTP 415
- **AND** thân phản hồi là `{"success": false, "message": "File phải sử dụng UTF-8."}`

### Requirement: Ánh xạ lỗi HTTP 422 cho dữ liệu đầu vào không hợp lệ

Khi dữ liệu đầu vào thiếu, rỗng hoặc sai giá trị cho phép, hệ thống SHALL trả HTTP status 422 kèm đúng thông báo nguyên văn tương ứng trong bảng ánh xạ lỗi. Chuỗi hoặc file chỉ chứa whitespace MUST NOT bị coi là rỗng; chỉ chuỗi rỗng, giá trị null hoặc file 0 byte mới bị coi là rỗng. Trường `key` vắng mặt, bằng `null` hoặc là chuỗi rỗng MUST được coi là thiếu khóa và nhận thông báo `Thiếu khóa.`; thông báo `Khóa phải là số nguyên.` MUST chỉ được dùng khi `key` có giá trị thực nhưng không biểu diễn một số nguyên hợp lệ. Nhờ vậy `key` đối xứng với `text`: cả hai trường đều coi `null` là vắng mặt. Trường hợp thiếu `action` MUST dùng chung thông báo `Action phải là encrypt hoặc decrypt.` vì bảng lỗi chuẩn không có dòng riêng cho việc thiếu `action`. Việc từ chối đầu vào rỗng SHALL được thực hiện ở tầng API trước khi gọi tới lõi thuật toán; lõi thuật toán không chịu trách nhiệm báo lỗi cho đầu vào rỗng. (Truy vết: docx §5, §8)

#### Scenario: Thiếu hoặc rỗng text

- **WHEN** người dùng gửi `POST /api/caesar/encrypt` hoặc `POST /api/caesar/decrypt` mà thiếu `text`, hoặc `text` là null, hoặc `text` là chuỗi rỗng, hoặc `text` không phải chuỗi
- **THEN** hệ thống trả HTTP 422
- **AND** thân phản hồi là `{"success": false, "message": "Văn bản không được để trống."}`
- **AND** bảng lỗi chuẩn không có thông báo riêng cho `text` sai kiểu nên trường hợp đó dùng chung thông báo này

#### Scenario: Thiếu key, key là null hoặc key là chuỗi rỗng

- **WHEN** người dùng gửi yêu cầu mã hóa/giải mã mà không cung cấp `key`, hoặc gửi `key` bằng `null`, hoặc gửi `key` là chuỗi rỗng
- **THEN** hệ thống trả HTTP 422 trong cả ba trường hợp
- **AND** thân phản hồi là `{"success": false, "message": "Thiếu khóa."}`
- **AND** cả ba trường hợp đều cho cùng một thông báo, không phân biệt việc trường bị bỏ hẳn hay được gửi với giá trị rỗng

#### Scenario: Key có giá trị thực nhưng không phải số nguyên

- **WHEN** người dùng gửi `key` với một giá trị thực nhưng không biểu diễn số nguyên, ví dụ số thực `3.5`, boolean, chuỗi số `"3"` hoặc chuỗi chữ `abc`
- **THEN** hệ thống trả HTTP 422
- **AND** thân phản hồi là `{"success": false, "message": "Khóa phải là số nguyên."}`
- **AND** thông báo này KHÔNG được dùng cho `key` vắng mặt, `key` bằng `null` hay `key` là chuỗi rỗng, vì ba trường hợp đó thuộc về `Thiếu khóa.`

#### Scenario: Thiếu file

- **WHEN** người dùng gửi `POST /api/caesar/file` mà không đính kèm trường file
- **THEN** hệ thống trả HTTP 422
- **AND** thân phản hồi là `{"success": false, "message": "Thiếu file."}`

#### Scenario: File 0 byte

- **WHEN** người dùng gửi `POST /api/caesar/file` với file có kích thước 0 byte
- **THEN** hệ thống trả HTTP 422
- **AND** thân phản hồi là `{"success": false, "message": "File không được để trống."}`

#### Scenario: Action không hợp lệ hoặc thiếu action

- **WHEN** người dùng gửi `POST /api/caesar/file` với `action` khác `encrypt` và `decrypt`, hoặc không gửi trường `action`
- **THEN** hệ thống trả HTTP 422
- **AND** thân phản hồi là `{"success": false, "message": "Action phải là encrypt hoặc decrypt."}`
- **AND** trường hợp thiếu `action` dùng đúng thông báo này chứ không có thông báo riêng
- **AND** trường hợp lỗi này chỉ phát sinh ở `POST /api/caesar/file`, vì hai endpoint JSON mã hóa thao tác ngay trong đường dẫn URL nên không nhận trường `action`

#### Scenario: Response mode không hợp lệ

- **WHEN** người dùng gửi `POST /api/caesar/file` với `response_mode` khác `content` và `file`
- **THEN** hệ thống trả HTTP 422
- **AND** thân phản hồi là `{"success": false, "message": "Response mode phải là content hoặc file."}`

#### Scenario: Văn bản chỉ chứa whitespace vẫn hợp lệ

- **WHEN** người dùng gửi `text` chỉ gồm khoảng trắng, tab hoặc ký tự xuống dòng
- **THEN** hệ thống KHÔNG trả lỗi 422 `Văn bản không được để trống.`
- **AND** yêu cầu được xử lý bình thường theo khuôn dạng response thành công

### Requirement: Ánh xạ lỗi HTTP 422 cho thân yêu cầu không đọc được

Khi request không bị tầng 0 từ chối vì vượt trần hạ tầng và thân yêu cầu không parse được thành JSON hợp lệ, hoặc parse được nhưng sai kiểu ở tầng cấu trúc (ví dụ thân là một mảng, một chuỗi hay một số thay vì một JSON object), hệ thống SHALL trả HTTP status 422 kèm thông báo nguyên văn `Dữ liệu gửi lên không hợp lệ.`. Trong phạm vi request đã qua tầng 0, kiểm tra này SHALL diễn ra trước mọi kiểm tra trường, vì khi chưa đọc được thân yêu cầu thì không thể xác định trường nào thiếu hay sai. Đây là thông báo BỔ SUNG nằm ngoài bảng lỗi docx §5: bảng gốc không có dòng nào cho thân yêu cầu hỏng, nên chuỗi này MUST được cập nhật ngược trở lại docx §5 trước khi tài liệu gốc được coi là đầy đủ. (Truy vết: docx §5 — bổ sung ngoài bảng; ngoại lệ hạ tầng OpenSpec được chủ sở hữu phê duyệt)

#### Scenario: Thân yêu cầu không phải JSON

- **WHEN** người dùng gửi `POST /api/caesar/encrypt` với `Content-Type: application/json` và thân yêu cầu không phải JSON hợp lệ, ví dụ `not json at all` hoặc `{"text": "abc", "key":`
- **THEN** hệ thống trả HTTP 422
- **AND** thân phản hồi là `{"success": false, "message": "Dữ liệu gửi lên không hợp lệ."}`

#### Scenario: Thân yêu cầu là JSON hợp lệ nhưng không phải object

- **WHEN** người dùng gửi `POST /api/caesar/encrypt` với thân yêu cầu là mảng `["Hello World", 3]` hoặc một giá trị vô hướng như `42`
- **THEN** hệ thống trả HTTP 422
- **AND** thân phản hồi là `{"success": false, "message": "Dữ liệu gửi lên không hợp lệ."}`
- **AND** hệ thống không báo lỗi thiếu `text` hay thiếu `key`, vì cấu trúc thân yêu cầu đã sai trước khi xét tới từng trường

#### Scenario: Thân yêu cầu rỗng

- **WHEN** người dùng gửi `POST /api/caesar/decrypt` không kèm thân yêu cầu
- **THEN** hệ thống trả HTTP 422
- **AND** thân phản hồi là `{"success": false, "message": "Dữ liệu gửi lên không hợp lệ."}`

### Requirement: Thứ tự kiểm tra xác định khi nhiều lỗi xảy ra cùng lúc

Khi một yêu cầu vi phạm đồng thời nhiều quy tắc, hệ thống SHALL trả về đúng MỘT thông báo lỗi và MUST dừng ngay ở lỗi đầu tiên gặp phải theo thứ tự kiểm tra bắt buộc dưới đây; đây là hợp đồng chung cho mọi endpoint dưới `/api/caesar/` và các capability khác MUST tham chiếu tới nó thay vì tự phát biểu một thứ tự riêng. Tầng 0 là ngoại lệ duy nhất đứng trước hợp đồng validation: nếu `Content-Length` lớn hơn 64 MiB thì hệ thống SHALL trả ngay 413 với thông báo được chọn theo tuyến như requirement về trần hạ tầng. Với mọi request không bị tầng 0 từ chối, nếu thân yêu cầu không đọc được thành một object hợp lệ thì hệ thống SHALL trả ngay 422 `Dữ liệu gửi lên không hợp lệ.` và dừng. Sau đó thứ tự bắt buộc là: (1) sự hiện diện của các trường bắt buộc, theo thứ tự `text`/`file` → `key` → `action`; (2) định dạng của các trường vô hướng, theo thứ tự `key` → `action` → `response_mode`; (3) đuôi file `.txt` (415); (4) giới hạn dung lượng file 5 MiB (413); (5) file 0 byte (422); (6) giải mã UTF-8 (415). Các bước (3)–(6) MUST chỉ áp dụng cho `POST /api/caesar/file`. Thứ tự này MUST được giữ nguyên vẹn ở cả luồng JSON lẫn luồng file để cùng một yêu cầu sai lệch luôn cho cùng một HTTP status và cùng một thông báo. (Truy vết: docx §5 — docx không quy định thứ tự; ngoại lệ hạ tầng OpenSpec được chủ sở hữu phê duyệt)

#### Scenario: Key sai định dạng được báo trước lỗi đuôi file và lỗi dung lượng

- **WHEN** người dùng gửi `POST /api/caesar/file` với file `a.md` kích thước 6 MiB, `key` bằng `abc` và `action` bằng `encrypt`
- **THEN** hệ thống trả HTTP 422
- **AND** thân phản hồi là `{"success": false, "message": "Khóa phải là số nguyên."}`
- **AND** hệ thống không trả lỗi đuôi file hay lỗi dung lượng, vì định dạng `key` được kiểm ở bước (2), trước đuôi file ở bước (3)

#### Scenario: Lỗi đuôi file được báo trước lỗi dung lượng

- **WHEN** người dùng gửi `POST /api/caesar/file` với file `a.md` kích thước 6 MiB, `key` bằng `3` và `action` bằng `encrypt`
- **THEN** hệ thống trả HTTP 415
- **AND** thân phản hồi là `{"success": false, "message": "Chỉ chấp nhận file .txt."}`

#### Scenario: Lỗi dung lượng được báo trước lỗi bảng mã

- **WHEN** người dùng gửi `POST /api/caesar/file` với file `a.txt` kích thước 6 MiB có nội dung không giải mã được bằng UTF-8, kèm `key` và `action` hợp lệ
- **THEN** hệ thống trả HTTP 413
- **AND** thân phản hồi là `{"success": false, "message": "File vượt quá dung lượng tối đa 5 MB."}`

#### Scenario: Thiếu file được báo trước thiếu key và thiếu action

- **WHEN** người dùng gửi `POST /api/caesar/file` không có phần `file`, không có `key` và không có `action`
- **THEN** hệ thống trả HTTP 422
- **AND** thân phản hồi là `{"success": false, "message": "Thiếu file."}`

#### Scenario: Text rỗng được báo trước key null ở luồng JSON

- **WHEN** người dùng gửi `POST /api/caesar/encrypt` với thân yêu cầu `{"text": "", "key": null}`
- **THEN** hệ thống trả HTTP 422
- **AND** thân phản hồi là `{"success": false, "message": "Văn bản không được để trống."}`

#### Scenario: Response mode sai định dạng được báo trước lỗi file 0 byte

- **WHEN** người dùng gửi `POST /api/caesar/file` với file `rong.txt` kích thước 0 byte, `key` và `action` hợp lệ, `response_mode` bằng `download`
- **THEN** hệ thống trả HTTP 422
- **AND** thân phản hồi là `{"success": false, "message": "Response mode phải là content hoặc file."}`

### Requirement: Ánh xạ lỗi HTTP 500 cho lỗi phía hệ thống

Khi hệ thống không đọc được file đã vượt qua bước kiểm tra, hoặc khi xảy ra bất kỳ lỗi nào không nằm trong các trường hợp đã định nghĩa, hệ thống SHALL trả HTTP status 500 kèm thông báo nguyên văn tương ứng: `Không thể đọc file.` cho lỗi đọc file và `Đã xảy ra lỗi hệ thống.` cho lỗi ngoài dự kiến. (Truy vết: docx §5, §6)

#### Scenario: Lỗi đọc file

- **WHEN** hệ thống không thể đọc được nội dung file tải lên dù file đã qua các bước kiểm tra đuôi, dung lượng và bảng mã
- **THEN** hệ thống trả HTTP 500
- **AND** thân phản hồi là `{"success": false, "message": "Không thể đọc file."}`

#### Scenario: Lỗi ngoài dự kiến

- **WHEN** xảy ra một lỗi không được liệt kê trong bảng ánh xạ lỗi tại bất kỳ endpoint nào dưới `/api/caesar/`
- **THEN** hệ thống trả HTTP 500
- **AND** thân phản hồi là `{"success": false, "message": "Đã xảy ra lỗi hệ thống."}`
- **AND** phản hồi không tiết lộ nguyên nhân kỹ thuật cụ thể của lỗi

### Requirement: HTTP status phản ánh đúng loại lỗi

Hệ thống SHALL dùng HTTP status khớp với loại lỗi theo bảng ánh xạ: 413 cho vượt giới hạn file nghiệp vụ hoặc trần request hạ tầng, 415 cho định dạng/bảng mã không hỗ trợ, 422 cho dữ liệu đầu vào không hợp lệ, 500 cho lỗi phía hệ thống. Hệ thống MUST NOT trả HTTP 200 cho một phản hồi có `success` bằng `false`, và MUST NOT trả HTTP lỗi cho một phản hồi thành công. (Truy vết: docx §5, §7; ngoại lệ hạ tầng OpenSpec được chủ sở hữu phê duyệt)

#### Scenario: Không dùng 200 cho phản hồi lỗi

- **WHEN** bất kỳ phản hồi nào có `success` bằng `false`
- **THEN** HTTP status của phản hồi đó khác 200
- **AND** HTTP status đúng bằng giá trị được quy định cho trường hợp lỗi tương ứng trong bảng ánh xạ

#### Scenario: Client phân biệt được lỗi chỉ qua status

- **WHEN** giao diện hoặc một client bất kỳ nhận phản hồi từ các endpoint dưới `/api/caesar/`
- **THEN** client xác định được yêu cầu thất bại chỉ dựa vào HTTP status mà không cần đọc thân phản hồi

### Requirement: Không lộ chi tiết kỹ thuật ra bên ngoài

Hệ thống SHALL NOT bao giờ đưa stack trace, tên exception, tên module hay hàm nội bộ, đường dẫn file trên máy chủ, thông tin phiên bản thư viện hoặc bất kỳ chi tiết kỹ thuật nào khác vào thân phản hồi, header phản hồi hay giao diện người dùng. Mọi lỗi lộ ra ngoài chỉ gồm HTTP status và thông báo tiếng Việt chuẩn. (Truy vết: docx §1, §5, §6)

#### Scenario: Phản hồi lỗi không chứa stack trace

- **WHEN** một lỗi ngoài dự kiến xảy ra trong lúc xử lý yêu cầu
- **THEN** thân phản hồi chỉ chứa `success` và `message` theo khuôn dạng chuẩn
- **AND** thân phản hồi không chứa stack trace, tên exception, đường dẫn file hệ thống hay tên hàm nội bộ

#### Scenario: Giao diện không hiển thị lỗi kỹ thuật

- **WHEN** giao diện nhận một phản hồi lỗi từ các endpoint dưới `/api/caesar/`
- **THEN** giao diện chỉ hiển thị thông báo tiếng Việt lấy từ trường `message`
- **AND** không có thông tin kỹ thuật nào khác được hiển thị cho người dùng

### Requirement: Ghi log nội bộ chi tiết lỗi mà không log dữ liệu người dùng

Hệ thống SHALL ghi log phía máy chủ cho mọi lỗi phía hệ thống (HTTP 500) với đủ ngữ cảnh để debug, bao gồm loại lỗi, dấu vết ngăn xếp, endpoint được gọi và thời điểm xảy ra. Vì ứng dụng stateless và không lưu dữ liệu người dùng, log MUST NOT chứa nội dung văn bản người dùng nhập, nội dung file tải lên hoặc kết quả mã hóa/giải mã. Thông tin trong log MUST NOT được trả về cho client. Với các lỗi 4xx do đầu vào của người dùng, việc ghi log SHALL là tùy chọn và MUST NOT bị coi là một phần bắt buộc của hợp đồng. (Truy vết: docx §6, §8)

#### Scenario: Lỗi hệ thống được ghi log đầy đủ ngữ cảnh

- **WHEN** một lỗi ngoài dự kiến hoặc lỗi đọc file xảy ra
- **THEN** hệ thống ghi một bản ghi log phía máy chủ gồm loại lỗi, dấu vết ngăn xếp, endpoint được gọi và thời điểm xảy ra
- **AND** client chỉ nhận được phản hồi lỗi chuẩn, không nhận bất kỳ phần nào của bản ghi log

#### Scenario: Log không chứa dữ liệu người dùng

- **WHEN** hệ thống ghi log cho một lỗi phát sinh khi xử lý văn bản hoặc file của người dùng
- **THEN** bản ghi log không chứa nội dung văn bản đầu vào, nội dung file tải lên hay kết quả mã hóa/giải mã
- **AND** dữ liệu người dùng không được lưu lại ở bất kỳ đâu sau khi request kết thúc

### Requirement: Phản hồi lỗi luôn ở dạng JSON

Mọi phản hồi lỗi SHALL ở dạng JSON theo khuôn dạng chuẩn, bất kể yêu cầu được gửi dưới dạng JSON hay multipart, và bất kể giá trị `response_mode`. Khi `response_mode=file`, hệ thống chỉ trả tệp đính kèm trong trường hợp thành công; nếu xảy ra lỗi thì SHALL trả JSON lỗi thay vì tệp đính kèm hay tệp rỗng. (Truy vết: docx §4.3, §5)

#### Scenario: Lỗi ở yêu cầu multipart trả JSON

- **WHEN** một yêu cầu `POST /api/caesar/file` dạng multipart bị từ chối vì bất kỳ lý do nào trong bảng ánh xạ lỗi
- **THEN** hệ thống trả phản hồi JSON theo khuôn dạng `{"success": false, "message": "..."}`

#### Scenario: Lỗi khi response_mode là file vẫn trả JSON

- **WHEN** một yêu cầu `POST /api/caesar/file` với `response_mode=file` gặp lỗi
- **THEN** hệ thống trả phản hồi JSON theo khuôn dạng chuẩn kèm HTTP status tương ứng
- **AND** hệ thống không trả tệp đính kèm, không trả tệp rỗng và không gợi ý trình duyệt tải tệp xuống
