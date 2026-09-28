## Purpose

Định nghĩa thuật toán Columnar Transposition không padding và ngôn ngữ khóa xác định, bảo toàn chính xác mọi Unicode code point qua encrypt/decrypt.

## ADDED Requirements

### Requirement: Encrypt ghi theo hàng và đọc cột theo rank

Hệ thống SHALL coi phần tử thứ `j` của khóa là rank của cột vật lý `j`. Encrypt SHALL đặt từng Unicode code point của plaintext theo thứ tự row-major vào `m` cột rồi nối các cột vật lý theo rank tăng dần `1..m`, đọc mỗi cột từ trên xuống và bỏ qua ô không tồn tại. Hệ thống MUST không thêm padding. (Truy vết: quyết định chủ sở hữu cho change này; HTML upload mục thuật toán encrypt)

#### Scenario: Vector bài giảng sáu cột
- **WHEN** encrypt `khoacongnghethongtin` với khóa rank `[3,6,2,1,5,4]`
- **THEN** kết quả đúng bằng `agnonokntioetchghghn`

#### Scenario: Hàng cuối không đủ không được padding
- **WHEN** encrypt `ABCDE` với khóa rank `[3,1,4,2]`
- **THEN** kết quả đúng bằng `BDAEC`
- **AND** output có cùng số Unicode code point với input

### Requirement: Decrypt dùng độ dài cột vật lý

Decrypt SHALL tính `r=floor(n/m)` và `s=n mod m`; mỗi cột vật lý có index nhỏ hơn `s` dài `r+1`, các cột còn lại dài `r`. Hệ thống SHALL cắt ciphertext theo thứ tự rank `1..m`, đặt từng đoạn vào đúng cột vật lý, rồi đọc row-major để khôi phục plaintext. Độ dài MUST phụ thuộc vị trí vật lý của cột, không phụ thuộc rank đọc. (Truy vết: quyết định chủ sở hữu cho change này; HTML upload mục thuật toán decrypt)

#### Scenario: Decrypt hàng không đều
- **WHEN** decrypt `BDAEC` với khóa rank `[3,1,4,2]`
- **THEN** kết quả đúng bằng `ABCDE`

#### Scenario: Mọi vector canonical decrypt chính xác
- **WHEN** decrypt ciphertext của từng canonical vector bằng chính khóa đã encrypt
- **THEN** hệ thống trả lại chính xác chuỗi input ban đầu, gồm whitespace, CR/LF, combining mark và emoji

### Requirement: Bảo toàn Unicode code point không normalization

Mỗi Unicode code point SHALL tham gia phép hoán vị như một phần tử, gồm chữ hoa/thường, dấu câu, space, tab, CR, LF, non-leading `U+FEFF`, combining mark và non-BMP code point. Hệ thống MUST không normalize Unicode, bỏ dấu, đổi case, ghép grapheme cluster hoặc giữ CRLF thành một đơn vị; vì vậy ciphertext có thể tách CR/LF, base/combining mark hoặc chuỗi hiển thị. (Truy vết: quyết định chủ sở hữu cho change này)

#### Scenario: Whitespace và CRLF tham gia độc lập
- **WHEN** encrypt chuỗi `A B\r\nC!` với khóa rank `[2,1,3]`
- **THEN** kết quả đúng bằng ` \nA\r!BC`

#### Scenario: Non-BMP và chữ có dấu là code point
- **WHEN** encrypt `😀A𝄞é` với khóa rank `[2,1,3]`
- **THEN** kết quả đúng bằng `A😀é𝄞`

#### Scenario: Combining sequence có thể bị tách
- **WHEN** input chứa một base code point theo sau bởi combining mark
- **THEN** hai code point được hoán vị độc lập
- **AND** decrypt khôi phục đúng sequence ban đầu mà không normalize

### Requirement: Khóa được trim đúng ASCII whitespace và có giới hạn

Parser SHALL yêu cầu `key` là string, trim ở hai đầu chỉ sáu ký tự ASCII space, tab, CR, LF, form feed và vertical tab, rồi đánh giá phần còn lại. Non-ASCII whitespace MUST không bị trim. Chuỗi sau trim phải dài từ 1 đến đúng 2.048 Unicode code point; chuỗi rỗng sau trim là missing key, còn dài 2.049 trở lên là invalid key content. (Truy vết: quyết định chủ sở hữu cho change này)

#### Scenario: Sáu loại ASCII whitespace ngoài được trim
- **WHEN** một khóa hợp lệ được bao quanh bởi space, tab, CR, LF, form feed hoặc vertical tab
- **THEN** parser xử lý cùng khóa như khi không có các ký tự ngoài đó

#### Scenario: Non-ASCII whitespace không được trim
- **WHEN** khóa keyword được bao quanh bởi non-breaking space `U+00A0`
- **THEN** khóa không khớp `[A-Za-z]+` và bị từ chối

#### Scenario: Biên độ dài khóa sau trim
- **WHEN** key sau ASCII trim dài đúng 2.048 ký tự
- **THEN** key qua bước giới hạn độ dài và tiếp tục được kiểm tra grammar/nội dung
- **AND** key dài 2.049 ký tự bị từ chối

### Requirement: Grammar khóa số là hoán vị token 1 đến m

Parser SHALL nhận khóa số khi toàn bộ phần sau trim là các token decimal không dấu, ngăn cách bởi một hoặc nhiều comma và/hoặc ASCII whitespace, với tùy chọn đúng một cặp brace ngoài `{...}`. Token MUST dùng ASCII digit, không có leading zero, dấu, decimal point hay exponent; separator MUST không tạo token rỗng; brace MUST cân bằng, đúng vị trí và không lồng. Dãy SHALL có `2 <= m <= 256` và là hoán vị chính xác của `1..m`, nên compact digits, duplicate hoặc số ngoài range đều bị từ chối. (Truy vết: quyết định chủ sở hữu cho change này)

#### Scenario: Các separator và brace hợp lệ
- **WHEN** key lần lượt là `3 6 2 1 5 4`, `3,6,2,1,5,4`, `3, 6\t2\n1,5 4` hoặc `{3 6 2 1 5 4}`
- **THEN** mọi biểu diễn được parse thành `[3,6,2,1,5,4]`

#### Scenario: Compact digits không phải danh sách rank
- **WHEN** key là `312`
- **THEN** parser không diễn giải thành `[3,1,2]` và từ chối key

#### Scenario: Token và brace sai bị từ chối
- **WHEN** key chứa leading zero, dấu, decimal, exponent, empty token, malformed/nested brace hoặc Unicode digit
- **THEN** parser từ chối key

#### Scenario: Dãy không phải exact permutation bị từ chối
- **WHEN** dãy có duplicate, thiếu rank, rank `0`, rank lớn hơn `m`, ít hơn 2 hoặc nhiều hơn 256 token
- **THEN** parser từ chối key

### Requirement: Keyword ASCII được xếp rank ổn định

Nếu input không tạo thành khóa số hợp lệ, parser SHALL chỉ nhận keyword khi toàn bộ chuỗi sau trim khớp `[A-Za-z]+`. Keyword SHALL có `2 <= m <= 256`; rank được gán theo thứ tự chữ cái A-Z không phân biệt hoa thường, và ký tự trùng nhau MUST phá hòa từ trái sang phải. (Truy vết: quyết định chủ sở hữu cho change này; HTML upload hàm keyword ranking)

#### Scenario: BALLOON có ranking canonical
- **WHEN** key là `BALLOON`
- **THEN** rank đúng bằng `[2,1,3,4,6,7,5]`

#### Scenario: Keyword không phân biệt hoa thường
- **WHEN** cùng một keyword được gửi ở các biến thể hoa/thường
- **THEN** mọi biến thể tạo cùng dãy rank

#### Scenario: Keyword ngoài ASCII hoặc ngoài bound bị từ chối
- **WHEN** key chứa digit, punctuation, whitespace bên trong, chữ có dấu, ít hơn 2 hoặc nhiều hơn 256 chữ cái
- **THEN** parser từ chối key

### Requirement: Số cột có thể lớn hơn độ dài text

Mọi khóa hợp lệ với `2 <= m <= 256` SHALL được chấp nhận dù `m > len(text)`. Cột không có code point SHALL đóng góp chuỗi rỗng và decrypt MUST vẫn khôi phục exact input. Core SHALL biến đổi chuỗi rỗng thành chuỗi rỗng để hỗ trợ file chỉ có BOM. (Truy vết: quyết định chủ sở hữu cho change này)

#### Scenario: Khóa dài hơn text
- **WHEN** encrypt `XY` với khóa rank `[3,1,2,4]`
- **THEN** kết quả đúng bằng `YX`
- **AND** decrypt `YX` bằng cùng khóa trả đúng `XY`

#### Scenario: Core xử lý chuỗi rỗng
- **WHEN** core encrypt hoặc decrypt chuỗi rỗng với khóa hợp lệ
- **THEN** kết quả là chuỗi rỗng

### Requirement: Keyword canonical và exact round-trip

Với mọi text và khóa hợp lệ, `decrypt(encrypt(text,key),key)` SHALL bằng chính xác text ban đầu theo chuỗi Unicode code point. (Truy vết: quyết định chủ sở hữu cho change này)

#### Scenario: Vector keyword BALLOON
- **WHEN** encrypt `MEET ME AT NOON` với keyword `BALLOON`
- **THEN** kết quả đúng bằng `EAM NETT EO NMO`
- **AND** decrypt kết quả bằng `BALLOON` trả đúng `MEET ME AT NOON`
