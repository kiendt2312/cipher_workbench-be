## Purpose

Định nghĩa hành vi lõi của thuật toán Caesar: một phép biến đổi duy nhất nhận văn bản, khóa và thao tác, chuẩn hóa khóa về khoảng 0–25, chỉ dịch chữ cái ASCII và giữ nguyên mọi ký tự còn lại. Lõi này là nguồn kết quả chung cho cả luồng nhập văn bản từ bàn phím lẫn luồng xử lý file `.txt`.

## ADDED Requirements

### Requirement: Interface biến đổi Caesar duy nhất

Hệ thống SHALL cung cấp một phép biến đổi Caesar duy nhất, dùng chung cho mọi luồng, nhận ba đầu vào: văn bản cần xử lý, khóa dịch chuyển là số nguyên có dấu và thao tác cần thực hiện. Hệ thống SHALL hỗ trợ đúng hai thao tác: mã hóa (`encrypt`) và giải mã (`decrypt`); mọi giá trị thao tác khác MUST bị từ chối là đầu vào không hợp lệ (việc ánh xạ sang HTTP status và thông báo lỗi thuộc đặc tả xử lý lỗi). Mã hóa SHALL dịch mỗi chữ cái ASCII tiến `key` vị trí, giải mã SHALL dịch lùi `key` vị trí, và giải mã MUST là phép nghịch đảo chính xác của mã hóa khi dùng cùng một khóa. (Truy vết: docx §2.1, §6)

#### Scenario: Mã hóa văn bản với khóa hợp lệ

- **WHEN** gọi phép biến đổi với văn bản `abc`, khóa `3` và thao tác mã hóa
- **THEN** kết quả trả về là `def`

#### Scenario: Giải mã văn bản với khóa hợp lệ

- **WHEN** gọi phép biến đổi với văn bản `def`, khóa `3` và thao tác giải mã
- **THEN** kết quả trả về là `abc`

#### Scenario: Giải mã là nghịch đảo của mã hóa với cùng khóa

- **WHEN** mã hóa một văn bản bất kỳ với khóa `k`
- **AND** giải mã kết quả vừa nhận được cũng với khóa `k`
- **THEN** văn bản thu được giống hệt văn bản gốc, không sai khác một ký tự nào

#### Scenario: Thao tác không thuộc hai giá trị được hỗ trợ

- **WHEN** gọi phép biến đổi với thao tác không phải mã hóa hoặc giải mã
- **THEN** phép biến đổi không được thực hiện
- **AND** đầu vào bị báo là không hợp lệ thay vì trả về một kết quả nào đó

### Requirement: Chuẩn hóa khóa về khoảng 0–25 bằng modulo 26

Hệ thống SHALL chuẩn hóa mọi khóa số nguyên về khoảng `0–25` bằng phép modulo 26 trước khi dịch ký tự, chấp nhận cả khóa âm lẫn khóa lớn hơn 25 mà không báo lỗi. Phép modulo MUST luôn cho kết quả không âm: với khóa âm, giá trị chuẩn hóa là `key mod 26` được quy về khoảng `0–25` (ví dụ `-3` tương đương `23`, `-29` tương đương `23`). Hai khóa có cùng giá trị chuẩn hóa MUST cho ra kết quả giống hệt nhau. (Truy vết: docx §2.1, §7)

#### Scenario: Khóa âm được chuẩn hóa thành khóa dương tương đương

- **WHEN** mã hóa văn bản `abc` với khóa `-3`
- **THEN** kết quả giống hệt khi mã hóa `abc` với khóa `23`
- **AND** kết quả là `xyz`

#### Scenario: Khóa âm có trị tuyệt đối lớn hơn 26

- **WHEN** mã hóa văn bản `abc` với khóa `-29`
- **THEN** khóa được chuẩn hóa về `23` chứ không phải một giá trị âm
- **AND** kết quả là `xyz`

#### Scenario: Khóa lớn hơn 25 được chuẩn hóa

- **WHEN** mã hóa văn bản `abc` với khóa `29`
- **THEN** khóa được chuẩn hóa về `3`
- **AND** kết quả là `def`

#### Scenario: Khóa bằng 26 tương đương khóa 0

- **WHEN** mã hóa văn bản `Hello World` với khóa `26`
- **THEN** khóa được chuẩn hóa về `0`
- **AND** kết quả giống hệt văn bản đầu vào `Hello World`

#### Scenario: Khóa bằng 0 giữ nguyên văn bản

- **WHEN** mã hóa hoặc giải mã văn bản `Hello World` với khóa `0`
- **THEN** kết quả giống hệt văn bản đầu vào, kể cả chữ hoa, khoảng trắng và dấu câu

### Requirement: Chỉ dịch chữ cái ASCII và wrap vòng quanh bảng chữ cái

Hệ thống SHALL chỉ dịch chuyển các ký tự thuộc hai dải ASCII `A-Z` và `a-z`. Khi dịch vượt quá cuối bảng chữ cái, ký tự MUST quay vòng về đầu bảng chữ cái cùng dải (`Z` cộng 1 thành `A`, `z` cộng 1 thành `a`); khi dịch vượt quá đầu bảng chữ cái, ký tự MUST quay vòng về cuối bảng chữ cái cùng dải (`A` trừ 1 thành `Z`, `a` trừ 1 thành `z`). Hệ thống MUST giữ nguyên kiểu chữ hoa/chữ thường của từng ký tự: chữ hoa sau khi dịch vẫn là chữ hoa, chữ thường sau khi dịch vẫn là chữ thường, và hai dải không bao giờ lẫn sang nhau. (Truy vết: docx §2.1, §7)

#### Scenario: Wrap vòng quanh ở cuối bảng chữ cái

- **WHEN** mã hóa văn bản `Zz` với khóa `1`
- **THEN** kết quả là `Aa`

#### Scenario: Wrap vòng quanh ở đầu bảng chữ cái khi giải mã

- **WHEN** giải mã văn bản `Aa` với khóa `1`
- **THEN** kết quả là `Zz`

#### Scenario: Giữ nguyên chữ hoa và chữ thường của từng ký tự

- **WHEN** mã hóa văn bản `AbCdEf` với khóa `2`
- **THEN** kết quả là `CdEfGh`
- **AND** từng vị trí ký tự giữ đúng kiểu hoa/thường như văn bản gốc

#### Scenario: Toàn bộ bảng chữ cái được dịch đúng

- **WHEN** mã hóa văn bản `abcdefghijklmnopqrstuvwxyz` với khóa `13`
- **THEN** kết quả là `nopqrstuvwxyzabcdefghijklm`

### Requirement: Giữ nguyên mọi ký tự không phải chữ cái ASCII

Hệ thống MUST giữ nguyên tại đúng vị trí cũ mọi ký tự không thuộc dải `A-Z` hoặc `a-z`, bao gồm khoảng trắng, tab, ký tự xuống dòng (cả `LF` lẫn cặp `CRLF`), chữ số, dấu câu, ký tự đặc biệt, chữ tiếng Việt có dấu, emoji và mọi ký tự Unicode ngoài ASCII. Văn bản kết quả MUST có cùng số ký tự và cùng thứ tự ký tự với văn bản đầu vào. (Truy vết: docx §2.1, §7)

#### Scenario: Giữ nguyên chữ số, dấu câu và ký tự đặc biệt

- **WHEN** mã hóa văn bản `abc 123 !@#$%^&*()` với khóa `3`
- **THEN** kết quả là `def 123 !@#$%^&*()`
- **AND** các chữ số và ký tự đặc biệt không bị dịch chuyển

#### Scenario: Giữ nguyên khoảng trắng, tab và xuống dòng kể cả CRLF

- **WHEN** mã hóa văn bản chứa khoảng trắng, ký tự tab, xuống dòng `LF` và cặp xuống dòng `CRLF` với một khóa bất kỳ
- **THEN** mọi ký tự khoảng trắng, tab và xuống dòng giữ nguyên đúng loại và đúng vị trí
- **AND** cặp `CRLF` không bị chuyển thành `LF` hay bị tách rời

#### Scenario: Giữ nguyên tiếng Việt có dấu, emoji và Unicode ngoài ASCII

- **WHEN** mã hóa văn bản `Xin chào Việt Nam 🎉 café` với khóa `5`
- **THEN** các ký tự tiếng Việt có dấu, emoji và ký tự Unicode ngoài ASCII giữ nguyên không đổi
- **AND** chỉ các chữ cái ASCII trong văn bản bị dịch chuyển

#### Scenario: Độ dài và thứ tự ký tự không đổi

- **WHEN** mã hóa hoặc giải mã một văn bản bất kỳ với một khóa bất kỳ
- **THEN** văn bản kết quả có đúng số ký tự như văn bản đầu vào
- **AND** mọi ký tự không phải chữ cái ASCII nằm ở đúng vị trí như trong văn bản đầu vào

### Requirement: Xử lý văn bản rỗng và văn bản chỉ chứa whitespace

Hệ thống SHALL coi văn bản chỉ chứa whitespace là đầu vào hợp lệ và MUST trả về nguyên trạng văn bản đó, không cắt bỏ hay thay đổi bất kỳ ký tự khoảng trắng nào. Khi nhận văn bản rỗng, lõi SHALL trả về văn bản rỗng mà không phát sinh lỗi; việc từ chối văn bản rỗng là quy tắc kiểm tra đầu vào của tầng API, không phải của lõi. (Truy vết: docx §2.1, §8)

#### Scenario: Văn bản chỉ chứa whitespace được trả về nguyên trạng

- **WHEN** mã hóa văn bản chỉ gồm các khoảng trắng, tab và xuống dòng với khóa `7`
- **THEN** kết quả giống hệt văn bản đầu vào
- **AND** không có lỗi nào phát sinh

#### Scenario: Văn bản rỗng được lõi xử lý an toàn

- **WHEN** gọi phép biến đổi với văn bản rỗng và một khóa bất kỳ
- **THEN** kết quả là văn bản rỗng
- **AND** không có lỗi nào phát sinh ở lõi

### Requirement: Tiêu chí nghiệm thu Hello World với khóa 3

Hệ thống MUST cho ra đúng kết quả nghiệm thu chuẩn của dự án: mã hóa `Hello World` với khóa `3` cho ra `Khoor Zruog`, và giải mã `Khoor Zruog` với khóa `3` cho lại `Hello World`. (Truy vết: docx §7)

#### Scenario: Mã hóa Hello World với khóa 3

- **WHEN** mã hóa văn bản `Hello World` với khóa `3`
- **THEN** kết quả là chính xác `Khoor Zruog`

#### Scenario: Giải mã Khoor Zruog với khóa 3

- **WHEN** giải mã văn bản `Khoor Zruog` với khóa `3`
- **THEN** kết quả là chính xác `Hello World`

### Requirement: Kết quả nhất quán và xác định bất kể nguồn đầu vào

Hệ thống MUST cho ra kết quả giống hệt nhau cho cùng bộ (văn bản, khóa, thao tác) bất kể văn bản đến từ bàn phím hay từ nội dung file `.txt` đã được đọc. Phép biến đổi MUST là xác định và không phụ thuộc trạng thái: gọi nhiều lần với cùng đầu vào luôn cho cùng kết quả, và kết quả của một lần gọi không bị ảnh hưởng bởi các lần gọi trước đó. (Truy vết: docx §2.1, §7, §8)

#### Scenario: Cùng nội dung từ bàn phím và từ file cho kết quả giống hệt

- **WHEN** biến đổi một nội dung văn bản nhập từ bàn phím với khóa `k` và thao tác `op`
- **AND** biến đổi đúng nội dung đó lấy từ một file `.txt` với cùng khóa `k` và cùng thao tác `op`
- **THEN** hai kết quả giống hệt nhau đến từng ký tự

#### Scenario: Gọi lặp lại cho kết quả ổn định

- **WHEN** gọi phép biến đổi nhiều lần liên tiếp với cùng văn bản, cùng khóa và cùng thao tác
- **THEN** mọi lần gọi đều trả về cùng một kết quả
- **AND** không có trạng thái nào từ lần gọi trước làm thay đổi kết quả lần gọi sau
