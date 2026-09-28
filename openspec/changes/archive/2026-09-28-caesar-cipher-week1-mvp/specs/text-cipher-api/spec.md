## Purpose

Capability này định nghĩa hợp đồng HTTP của hai endpoint JSON dùng cho văn bản nhập từ bàn phím: `POST /api/caesar/encrypt` và `POST /api/caesar/decrypt`. Nó quy định khuôn dạng request và response thành công, quy tắc validate hai trường `text` và `key`, cùng toàn bộ hành vi quan sát được từ phía client khi request được chấp nhận hoặc bị từ chối. (Truy vết: docx §4.1, §4.2, §5)

## ADDED Requirements

### Requirement: Endpoint mã hóa văn bản

Hệ thống SHALL cung cấp endpoint `POST /api/caesar/encrypt` nhận JSON body gồm `text` và `key`, thực hiện mã hóa Caesar trên `text` với khóa `key`, và trả về văn bản đã mã hóa. Endpoint MUST là stateless: không lưu lại `text`, `key` hay kết quả sau khi request kết thúc. (Truy vết: docx §4.1, §7, §8)

#### Scenario: Mã hóa ví dụ nghiệm thu chuẩn
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "Hello World", "key": 3}`
- **THEN** hệ thống trả HTTP 200
- **AND** body phản hồi là `{"success": true, "result": "Khoor Zruog"}`

#### Scenario: Mã hóa giữ nguyên hoa thường, số và ký tự đặc biệt
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "aBc-123!xyZ", "key": 3}`
- **THEN** hệ thống trả HTTP 200
- **AND** `result` là `"dEf-123!abC"`

#### Scenario: Mã hóa hai lần cùng đầu vào cho cùng kết quả
- **WHEN** client gửi hai request `POST /api/caesar/encrypt` liên tiếp với cùng body `{"text": "Hello World", "key": 3}`
- **THEN** cả hai phản hồi đều là HTTP 200 với `result` là `"Khoor Zruog"`
- **AND** không có dữ liệu nào từ request trước ảnh hưởng tới request sau

### Requirement: Endpoint giải mã văn bản

Hệ thống SHALL cung cấp endpoint `POST /api/caesar/decrypt` nhận JSON body gồm `text` và `key`, thực hiện giải mã Caesar trên `text` với khóa `key`, và trả về văn bản đã giải mã. Giải mã MUST là phép nghịch đảo của mã hóa với cùng một khóa. (Truy vết: docx §4.2, §7)

#### Scenario: Giải mã ví dụ nghiệm thu chuẩn
- **WHEN** client gửi `POST /api/caesar/decrypt` với body `{"text": "Khoor Zruog", "key": 3}`
- **THEN** hệ thống trả HTTP 200
- **AND** body phản hồi là `{"success": true, "result": "Hello World"}`

#### Scenario: Mã hóa rồi giải mã trả lại văn bản gốc
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "Chào Thế Giới 2026!", "key": 7}` rồi gửi `POST /api/caesar/decrypt` với `text` bằng đúng `result` vừa nhận và `key` là `7`
- **THEN** cả hai request đều trả HTTP 200
- **AND** `result` của request giải mã là `"Chào Thế Giới 2026!"`

### Requirement: Hợp đồng request JSON của hai endpoint văn bản

Hai endpoint văn bản SHALL nhận request với `Content-Type: application/json` và body là một JSON object gồm hai trường: `text` (chuỗi) và `key` (số nguyên). Hệ thống MUST xử lý hai endpoint theo cùng một bộ quy tắc validate, để cùng một body sai lệch cho cùng HTTP status và cùng thông báo trên cả `encrypt` lẫn `decrypt`. (Truy vết: docx §4.1, §4.2, §5)

#### Scenario: Chấp nhận body JSON với Content-Type application/json
- **WHEN** client gửi `POST /api/caesar/encrypt` với header `Content-Type: application/json` và body `{"text": "abc", "key": 1}`
- **THEN** hệ thống trả HTTP 200
- **AND** `result` là `"bcd"`

#### Scenario: Hai endpoint dùng chung quy tắc validate
- **WHEN** client gửi cùng body `{"text": "abc"}` tới `POST /api/caesar/encrypt` và tới `POST /api/caesar/decrypt`
- **THEN** cả hai phản hồi đều là HTTP 422
- **AND** cả hai đều có `message` là `"Thiếu khóa."`

### Requirement: Hợp đồng response thành công

Khi request hợp lệ, hai endpoint văn bản SHALL trả HTTP 200 với body JSON đúng khuôn dạng `{"success": true, "result": "<văn bản kết quả>"}`. Body thành công MUST chứa đúng hai trường `success` và `result`, trong đó `success` là `true` và `result` là chuỗi; MUST NOT chứa trường `message` hay bất kỳ chi tiết kỹ thuật nào. (Truy vết: docx §4.2, §5)

#### Scenario: Khuôn dạng body thành công
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "Hello World", "key": 3}`
- **THEN** body phản hồi có đúng hai khóa là `success` và `result`
- **AND** `success` là giá trị boolean `true`
- **AND** `result` là chuỗi `"Khoor Zruog"`
- **AND** phản hồi có `Content-Type` là `application/json`

### Requirement: Khóa phải là số nguyên JSON

Trường `key` trong request body SHALL là một JSON integer khi nó có giá trị thực. Hệ thống MUST từ chối mọi kiểu dữ liệu khác — boolean, số thực (kể cả số thực có phần thập phân bằng 0), chuỗi chứa chữ số, mảng, object và các kiểu còn lại — bằng HTTP 422 kèm thông báo `"Khóa phải là số nguyên."` theo khuôn dạng error response chuẩn. Hệ thống MUST NOT tự ép kiểu chuỗi hay số thực về số nguyên. Hai trường hợp `key` bằng `null` và `key` là chuỗi rỗng MUST NOT dùng thông báo này: chúng được coi là thiếu khóa và nhận `"Thiếu khóa."` theo requirement bắt buộc có trường key. (Truy vết: docx §4.2, §5)

#### Scenario: Từ chối khóa là boolean true
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "Hello", "key": true}`
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Khóa phải là số nguyên."}`

#### Scenario: Từ chối khóa là boolean false
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "Hello", "key": false}`
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Khóa phải là số nguyên."}`

#### Scenario: Từ chối khóa là số thực có phần thập phân bằng 0
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "Hello", "key": 3.0}`
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Khóa phải là số nguyên."}`

#### Scenario: Từ chối khóa là số thực có phần thập phân khác 0
- **WHEN** client gửi `POST /api/caesar/decrypt` với body `{"text": "Khoor", "key": 3.5}`
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Khóa phải là số nguyên."}`

#### Scenario: Từ chối khóa là chuỗi chứa chữ số
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "Hello", "key": "3"}`
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Khóa phải là số nguyên."}`

#### Scenario: Từ chối khóa là chuỗi không phải số
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "Hello", "key": "ba"}`
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Khóa phải là số nguyên."}`

#### Scenario: Khóa là null được coi là thiếu khóa
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "Hello", "key": null}`
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Thiếu khóa."}`
- **AND** `key` bằng `null` được xử lý như `key` vắng mặt, đối xứng với cách `text` bằng `null` được xử lý như `text` vắng mặt

#### Scenario: Từ chối khóa là mảng hoặc object
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "Hello", "key": [3]}` hoặc `{"text": "Hello", "key": {"value": 3}}`
- **THEN** hệ thống trả HTTP 422 trong cả hai trường hợp
- **AND** body phản hồi là `{"success": false, "message": "Khóa phải là số nguyên."}`

### Requirement: Chấp nhận khóa âm, khóa bằng 0 và khóa lớn hơn 25

Hai endpoint văn bản SHALL chấp nhận mọi JSON integer làm `key`, bao gồm khóa âm, khóa bằng 0 và khóa lớn hơn 25, và trả HTTP 200 với kết quả đúng. Hệ thống MUST NOT giới hạn `key` trong khoảng 0–25 ở tầng API; quy tắc chuẩn hóa khóa thuộc về capability `caesar-core`. (Truy vết: docx §2.1, §7)

#### Scenario: Chấp nhận khóa âm
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "Hello World", "key": -23}`
- **THEN** hệ thống trả HTTP 200
- **AND** `result` là `"Khoor Zruog"`

#### Scenario: Chấp nhận khóa lớn hơn 25
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "Hello World", "key": 29}`
- **THEN** hệ thống trả HTTP 200
- **AND** `result` là `"Khoor Zruog"`

#### Scenario: Chấp nhận khóa bằng 0
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "Hello World", "key": 0}`
- **THEN** hệ thống trả HTTP 200
- **AND** `result` là `"Hello World"`

#### Scenario: Chấp nhận khóa là số nguyên rất lớn
- **WHEN** client gửi `POST /api/caesar/decrypt` với body `{"text": "Khoor Zruog", "key": 26003}`
- **THEN** hệ thống trả HTTP 200
- **AND** `result` là `"Hello World"`

### Requirement: Validate trường text

Trường `text` SHALL bắt buộc có mặt và MUST là chuỗi khác rỗng. Hệ thống MUST từ chối request khi `text` thiếu, là chuỗi rỗng, hoặc là `null`, bằng HTTP 422 kèm thông báo `"Văn bản không được để trống."` theo khuôn dạng error response chuẩn. (Truy vết: docx §5, §8)

#### Scenario: Thiếu trường text
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"key": 3}`
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Văn bản không được để trống."}`

#### Scenario: Text là chuỗi rỗng
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "", "key": 3}`
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Văn bản không được để trống."}`

#### Scenario: Text là null
- **WHEN** client gửi `POST /api/caesar/decrypt` với body `{"text": null, "key": 3}`
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Văn bản không được để trống."}`

#### Scenario: Text không phải chuỗi
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": 123, "key": 3}`
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Văn bản không được để trống."}`

### Requirement: Văn bản chỉ chứa khoảng trắng là hợp lệ

Hệ thống SHALL coi văn bản chỉ gồm khoảng trắng, tab hoặc ký tự xuống dòng là đầu vào hợp lệ và MUST NOT từ chối nó như văn bản rỗng. Trong trường hợp này hệ thống MUST trả HTTP 200 với `result` giữ nguyên chuỗi khoảng trắng đã nhận, không cắt bỏ đầu cuối. (Truy vết: docx §8)

#### Scenario: Text chỉ gồm dấu cách
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "   ", "key": 3}`
- **THEN** hệ thống trả HTTP 200
- **AND** body phản hồi là `{"success": true, "result": "   "}`

#### Scenario: Text chỉ gồm tab và xuống dòng
- **WHEN** client gửi `POST /api/caesar/decrypt` với body `{"text": "\t\n\n", "key": 5}`
- **THEN** hệ thống trả HTTP 200
- **AND** `result` là `"\t\n\n"`

#### Scenario: Khoảng trắng đầu và cuối được giữ nguyên
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "  abc  ", "key": 1}`
- **THEN** hệ thống trả HTTP 200
- **AND** `result` là `"  bcd  "`

### Requirement: Bắt buộc có trường key

Trường `key` SHALL bắt buộc có mặt và có giá trị trong request body. Khi `key` không xuất hiện, khi `key` bằng `null`, hoặc khi `key` là chuỗi rỗng, hệ thống MUST trả HTTP 422 kèm thông báo `"Thiếu khóa."` theo khuôn dạng error response chuẩn. Thông báo `"Khóa phải là số nguyên."` MUST chỉ được dùng khi `key` có giá trị thực nhưng không phải số nguyên hợp lệ. (Truy vết: docx §5)

#### Scenario: Thiếu trường key
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "Hello World"}`
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Thiếu khóa."}`

#### Scenario: Key là null
- **WHEN** client gửi `POST /api/caesar/decrypt` với body `{"text": "Hello World", "key": null}`
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Thiếu khóa."}`

#### Scenario: Key là chuỗi rỗng
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "Hello World", "key": ""}`
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Thiếu khóa."}`
- **AND** chuỗi rỗng KHÔNG được coi là một giá trị khóa sai kiểu

#### Scenario: Thiếu key được phân biệt với key sai kiểu
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "Hello"}` rồi gửi `{"text": "Hello", "key": "3"}`
- **THEN** request đầu trả `message` là `"Thiếu khóa."`
- **AND** request sau trả `message` là `"Khóa phải là số nguyên."`

### Requirement: Thứ tự ưu tiên kiểm tra khi có nhiều lỗi

Khi một request vi phạm đồng thời nhiều quy tắc validate, hệ thống SHALL trả về đúng một thông báo lỗi và MUST tuân theo thứ tự kiểm tra xác định đã quy định trong capability `error-handling`; hai endpoint văn bản MUST NOT định nghĩa một thứ tự riêng. Ngoại lệ hạ tầng duy nhất là request có `Content-Length` lớn hơn 64 MiB: tầng 0 SHALL từ chối trước khi đọc body với HTTP 413 và thông báo generic. Với mọi request không bị tầng 0 từ chối, thứ tự luồng JSON là: thân yêu cầu phải đọc được thành một object trước, rồi tới sự hiện diện của `text`, rồi sự hiện diện của `key`, rồi định dạng của `key`. Nhờ vậy phản hồi cho một request cho trước luôn xác định được. (Truy vết: docx §5; ngoại lệ hạ tầng OpenSpec được chủ sở hữu phê duyệt)

#### Scenario: Request văn bản vượt trần hạ tầng

- **WHEN** client gửi request tới một trong hai endpoint văn bản với `Content-Length` lớn hơn 64 MiB, đồng thời body cũng sai cú pháp hoặc sai field
- **THEN** tầng 0 trả HTTP 413 trước khi phân tích body
- **AND** body phản hồi là `{"success": false, "message": "Yêu cầu vượt quá dung lượng cho phép."}`
- **AND** thông báo không nêu con số 64 MiB

#### Scenario: Text rỗng và thiếu key cùng lúc
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": ""}`
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Văn bản không được để trống."}`

#### Scenario: Body là JSON object rỗng
- **WHEN** client gửi `POST /api/caesar/decrypt` với body `{}`
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Văn bản không được để trống."}`

#### Scenario: Text rỗng và key sai kiểu cùng lúc
- **WHEN** client gửi `POST /api/caesar/decrypt` với body `{"text": "", "key": "3"}`
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Văn bản không được để trống."}`

#### Scenario: Text rỗng và key null cùng lúc
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "", "key": null}`
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Văn bản không được để trống."}`

#### Scenario: Body hỏng được báo trước mọi lỗi trường
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `["Hello World", 3]`
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Dữ liệu gửi lên không hợp lệ."}`
- **AND** hệ thống không báo thiếu `text` hay thiếu `key`

### Requirement: Bảo toàn Unicode và ký tự đặc biệt qua API

Hai endpoint văn bản SHALL truyền tải văn bản Unicode nguyên vẹn: ký tự tiếng Việt có dấu, emoji, ký tự xuống dòng và ký tự đặc biệt trong `text` MUST xuất hiện nguyên vẹn trong `result`, chỉ các chữ cái ASCII `A-Z` và `a-z` bị dịch chuyển. Phản hồi MUST được mã hóa UTF-8 và MUST NOT escape ký tự non-ASCII thành chuỗi thoát trong kết quả sau khi giải mã JSON. (Truy vết: docx §2.1, §7)

#### Scenario: Văn bản tiếng Việt có dấu
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "Xin chào", "key": 3}`
- **THEN** hệ thống trả HTTP 200
- **AND** `result` là `"Alq fkàr"`

#### Scenario: Văn bản nhiều dòng giữ nguyên ký tự xuống dòng
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "abc\ndef", "key": 1}`
- **THEN** hệ thống trả HTTP 200
- **AND** `result` là `"bcd\nefg"`
- **AND** số dòng trong `result` bằng số dòng trong `text`

#### Scenario: Emoji và ký tự đặc biệt không bị thay đổi
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `{"text": "hi 🙂 @#$ 42", "key": 2}`
- **THEN** hệ thống trả HTTP 200
- **AND** `result` là `"jk 🙂 @#$ 42"`

#### Scenario: Giải mã văn bản Unicode trả lại đúng bản gốc
- **WHEN** client gửi `POST /api/caesar/decrypt` với body `{"text": "Alq fkàr", "key": 3}`
- **THEN** hệ thống trả HTTP 200
- **AND** `result` là `"Xin chào"`

### Requirement: Body không đọc được vẫn trả error response chuẩn

Khi request không bị tầng 0 từ chối vì vượt trần hạ tầng và body không parse được thành JSON object hợp lệ — body không phải JSON, JSON sai cú pháp, body rỗng, hoặc JSON hợp lệ nhưng không phải object — hai endpoint văn bản SHALL trả HTTP 422 với body `{"success": false, "message": "Dữ liệu gửi lên không hợp lệ."}`. Phản hồi MUST NOT dùng khuôn dạng lỗi mặc định của framework (ví dụ body chứa trường `detail`) và MUST NOT lộ stack trace, tên trường kỹ thuật hay thông điệp tiếng Anh. Chuỗi `Dữ liệu gửi lên không hợp lệ.` là phần bổ sung ngoài bảng lỗi docx §5 và được định nghĩa trong capability `error-handling`, nơi cũng ghi nhận việc cần cập nhật ngược chuỗi này vào tài liệu gốc. (Truy vết: docx §5, §6 — bổ sung ngoài bảng; ngoại lệ hạ tầng OpenSpec được chủ sở hữu phê duyệt)

#### Scenario: Body không phải JSON
- **WHEN** client gửi `POST /api/caesar/encrypt` với `Content-Type: application/json` và body `not json at all`
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Dữ liệu gửi lên không hợp lệ."}`
- **AND** body phản hồi không chứa khóa `detail`

#### Scenario: Body là JSON không đúng cú pháp
- **WHEN** client gửi `POST /api/caesar/decrypt` với body `{"text": "abc", "key":`
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Dữ liệu gửi lên không hợp lệ."}`

#### Scenario: Body là JSON hợp lệ nhưng không phải object
- **WHEN** client gửi `POST /api/caesar/encrypt` với body `["Hello World", 3]`
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Dữ liệu gửi lên không hợp lệ."}`

#### Scenario: Body rỗng
- **WHEN** client gửi `POST /api/caesar/encrypt` không kèm body
- **THEN** hệ thống trả HTTP 422
- **AND** body phản hồi là `{"success": false, "message": "Dữ liệu gửi lên không hợp lệ."}`

#### Scenario: Không lộ chi tiết kỹ thuật
- **WHEN** client gửi bất kỳ request sai lệch nào tới hai endpoint văn bản
- **THEN** body phản hồi không chứa stack trace, tên class, tên module hay đường dẫn file
- **AND** `message` là một câu tiếng Việt hoàn chỉnh dành cho người dùng cuối
