## Purpose

Định nghĩa endpoint multipart Columnar kế thừa exact contract file, byte, BOM, preview/download và attachment đã được backend nghiệm thu.

## ADDED Requirements

### Requirement: Endpoint file Columnar có exact multipart shape

Hệ thống SHALL cung cấp `POST /api/columnar/file`. Multipart SHALL chỉ cho phép đúng `file`, `key`, `action` và optional `response_mode`; mỗi field xuất hiện tối đa một lần. Field lạ hoặc duplicate MUST trả HTTP 422 `Dữ liệu gửi lên không hợp lệ.` trước field/content validation. `response_mode` vắng SHALL mặc định `content`. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed Affine file API)

#### Scenario: Canonical file content mode
- **WHEN** client gửi `data.txt` chứa `ABCDE`, `key="3 1 4 2"`, `action=encrypt`, `response_mode=content`
- **THEN** hệ thống trả HTTP 200 với `{"success":true,"result":"BDAEC"}`

#### Scenario: Unknown hoặc duplicate multipart field bị từ chối
- **WHEN** multipart hợp lệ khác nhưng có field lạ hoặc lặp một field đã cho phép
- **THEN** hệ thống trả HTTP 422 với message `Dữ liệu gửi lên không hợp lệ.`

### Requirement: File phải là upload part có filename

`file` SHALL bắt buộc có mặt và là upload part có tham số filename. Thiếu field trả HTTP 422 `Thiếu file.`; part tên `file` không có filename parameter nên được parse như scalar MUST trả HTTP 422 `Dữ liệu gửi lên không hợp lệ.`. Upload part có `filename=""` vẫn đi qua bước type và SHALL thất bại ở extension bằng HTTP 415 `Chỉ chấp nhận file .txt.`. MIME upload MUST bị bỏ qua khi xác định validity; filename và bytes là authority. (Truy vết: quyết định chủ sở hữu cho change này; baseline runtime multipart behavior)

#### Scenario: Thiếu file thắng key
- **WHEN** multipart thiếu `file` đồng thời key/action sai hoặc thiếu
- **THEN** hệ thống trả HTTP 422 với message `Thiếu file.`

#### Scenario: Filename rỗng là lỗi extension
- **WHEN** upload part có `filename=""` và các scalar field hợp lệ
- **THEN** hệ thống trả HTTP 415 với message `Chỉ chấp nhận file .txt.`

### Requirement: Key multipart dùng cùng contract string Columnar

`key` SHALL là scalar multipart string và dùng cùng ASCII trim, post-trim limit 2.048, numeric-permutation/keyword grammar, ranking và `2..256` bound như text API. Thiếu, `null` hoặc empty sau trim SHALL trả `Thiếu khóa.`; part không phải scalar string SHALL trả `Khóa phải là chuỗi.`; content không hợp lệ SHALL trả canonical Columnar invalid-key message. (Truy vết: quyết định chủ sở hữu cho change này; `columnar-core` và quyết định chủ sở hữu)

#### Scenario: Keyword và numeric key có parity
- **WHEN** cùng file được gửi với keyword hoặc numeric key tương ứng cùng rank
- **THEN** endpoint tạo cùng result

#### Scenario: Key quá 2.048 ký tự bị từ chối trước action
- **WHEN** key sau trim dài 2.049 ký tự đồng thời action sai
- **THEN** endpoint trả canonical Columnar invalid-key 422

### Requirement: Action và response mode phân biệt hoa thường

`action` SHALL là chính xác `encrypt` hoặc `decrypt`; thiếu hoặc sai trả HTTP 422 `Action phải là encrypt hoặc decrypt.`. `response_mode`, nếu có, SHALL là chính xác `content` hoặc `file`; sai trả HTTP 422 `Response mode phải là content hoặc file.`. Hai field phân biệt hoa thường. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed file API)

#### Scenario: Action viết hoa bị từ chối
- **WHEN** `action=ENCRYPT` sau các field ưu tiên trước đã hợp lệ
- **THEN** hệ thống trả HTTP 422 với message `Action phải là encrypt hoặc decrypt.`

#### Scenario: Response mode vắng và sai
- **WHEN** `response_mode` vắng
- **THEN** endpoint dùng `content`
- **AND** giá trị `FILE` bị từ chối bằng canonical response-mode 422

### Requirement: Chỉ nhận filename txt không phân biệt hoa thường

Filename SHALL kết thúc bằng suffix `.txt` không phân biệt hoa thường sau khi các scalar field hợp lệ; double extension như `.txt.exe` MUST bị từ chối. MIME khai báo không được thay đổi quyết định này. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed file API)

#### Scenario: TXT hoa hợp lệ bất kể MIME
- **WHEN** filename là `DATA.TXT`, MIME tùy ý và bytes/scalar fields hợp lệ
- **THEN** file qua bước extension

#### Scenario: Double extension bị từ chối
- **WHEN** filename là `data.txt.exe`
- **THEN** hệ thống trả HTTP 415 `Chỉ chấp nhận file .txt.`

### Requirement: Giới hạn file chính xác 5 MiB và zero byte

Hệ thống SHALL đếm raw uploaded bytes, gồm UTF-8 BOM nếu có. File đúng 5.242.880 byte SHALL được nhận; 5.242.881 byte trở lên SHALL trả HTTP 413 `File vượt quá dung lượng tối đa 5 MB.`; raw zero byte SHALL trả HTTP 422 `File không được để trống.`. File chỉ gồm ba byte BOM không phải zero-byte và SHALL hợp lệ. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed file API)

#### Scenario: Boundary 5 MiB
- **WHEN** raw file có đúng 5.242.880 byte
- **THEN** file qua bước size
- **AND** file 5.242.881 byte bị từ chối bằng canonical file-too-large 413

#### Scenario: BOM-only hợp lệ
- **WHEN** raw file đúng bằng `EF BB BF`
- **THEN** input text logic là chuỗi rỗng nhưng request không bị coi là empty file

### Requirement: File decode strict UTF-8 và bảo toàn code point

Sau size/empty checks, bytes SHALL được decode strict UTF-8 mà không universal-newline conversion. Invalid UTF-8 MUST trả HTTP 415 `File phải sử dụng UTF-8.`. Leading UTF-8 BOM SHALL được coi là metadata và bỏ khỏi text logic; non-leading `U+FEFF` SHALL là code point bình thường tham gia transform. CR, LF và CRLF SHALL được giữ như các code point riêng. (Truy vết: quyết định chủ sở hữu cho change này; baseline file helper contract)

#### Scenario: Invalid UTF-8 bị từ chối
- **WHEN** file `.txt` không rỗng chứa byte sequence UTF-8 không hợp lệ
- **THEN** hệ thống trả HTTP 415 với message `File phải sử dụng UTF-8.`

#### Scenario: Non-leading BOM tham gia transform
- **WHEN** decoded text có `U+FEFF` không ở đầu
- **THEN** code point đó được Columnar core hoán vị như mọi code point khác

### Requirement: Content mode trả exact JSON và không khôi phục BOM

Khi `response_mode=content`, request hợp lệ SHALL trả HTTP 200 `application/json` với đúng `{"success":true,"result":"<result>"}` và không có `Content-Disposition`. Leading BOM metadata của input MUST không xuất hiện trong `result`; parsed rank, key, matrix hoặc metadata khác cũng MUST không xuất hiện. (Truy vết: quyết định chủ sở hữu cho change này; baseline file content mode)

#### Scenario: Preview bỏ leading BOM metadata
- **WHEN** file input có leading BOM và text `ABCDE`
- **THEN** preview result là transform của `ABCDE` và không bắt đầu bằng `U+FEFF`

### Requirement: File mode trả attachment UTF-8 do server sở hữu

Khi `response_mode=file`, request hợp lệ SHALL trả HTTP 200, raw result bytes với `Content-Type: text/plain; charset=utf-8` và `Content-Disposition: attachment`. Attachment SHALL khôi phục leading BOM nếu và chỉ nếu input có leading BOM. Client MUST gửi request download riêng; preview không mang trạng thái server và không được dùng để tự dựng authoritative attachment. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed file API và guide FE)

#### Scenario: Attachment giữ BOM có điều kiện
- **WHEN** cùng nội dung lần lượt được upload có và không có leading BOM
- **THEN** attachment tương ứng có và không có prefix `EF BB BF`

#### Scenario: Lỗi file mode vẫn là JSON
- **WHEN** request `response_mode=file` thất bại validation hoặc transform
- **THEN** response dùng JSON error envelope và không có attachment

### Requirement: Filename attachment kế thừa baseline

Server SHALL tạo filename `<basename>.encrypted.txt` hoặc `<basename>.decrypted.txt`, loại path component, chỉ bỏ suffix `.txt` cuối cùng không phân biệt hoa thường, giữ các dấu chấm trước đó và luôn dùng `.txt` viết thường. Tên MUST không thêm `columnar` và không dùng underscore suffix. (Truy vết: quyết định chủ sở hữu cho change này; baseline file helper contract)

#### Scenario: Tên nhiều dấu chấm và đuôi hoa
- **WHEN** file `bao.cao.TXT` được encrypt
- **THEN** attachment filename là `bao.cao.encrypted.txt`

#### Scenario: Decrypt suffix
- **WHEN** file `secret.txt` được decrypt
- **THEN** attachment filename là `secret.decrypted.txt`

### Requirement: OpenAPI mô tả đúng file contract

OpenAPI SHALL gắn tag `Columnar Transposition`; request multipart SHALL là exact object required `file,key,action`, optional `response_mode`, không additional properties. `key` SHALL có `type:string`, prose cùng ví dụ numeric `3 1 4 2` và keyword `BALLOON`, không có `pattern`, `oneOf` hoặc raw `maxLength`; action/mode SHALL công bố enum và mode default `content`. Responses SHALL là đúng 200/413/415/422/500; response 200 SHALL công bố cả `application/json` và `text/plain`, các lỗi SHALL công bố JSON. (Truy vết: quyết định chủ sở hữu cho change này; baseline runtime OpenAPI)

#### Scenario: File OpenAPI media và status
- **WHEN** client đọc operation `/api/columnar/file`
- **THEN** response 200 có JSON và text/plain
- **AND** toàn bộ response status là 200, 413, 415, 422, 500
- **AND** key schema có hai ví dụ `3 1 4 2`, `BALLOON`
