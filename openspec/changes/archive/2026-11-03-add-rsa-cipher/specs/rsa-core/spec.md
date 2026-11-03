# Spec Delta

## Purpose

Định nghĩa lõi textbook RSA phục vụ học tập: số học modular, sinh khóa nhỏ, biến đổi từng block và ánh xạ lossless giữa Unicode/UTF-8 với các block số thập phân trong giới hạn đã chốt.

## ADDED Requirements

### Requirement: Số học RSA chính xác trên số nguyên

Hệ thống SHALL tính `gcd`, Euclid mở rộng, nghịch đảo modulo và lũy thừa modulo bằng số nguyên chính xác, không chuyển qua số thực. Với `modPow(base, exponent, modulus)`, kết quả SHALL bằng `base^exponent mod modulus`; bảng giải thích SHALL duyệt bit của exponent từ thấp lên cao theo square-and-multiply và ghi đầy đủ mọi bit, không cắt bớt. (Truy vết: PDF RSA trang 1 BE-01, trang 2 BE-01; HTML RSA §2–§3 và dòng 188–213; quyết định chủ sở hữu Q6, Q11)

#### Scenario: Vector số học TC-02
- **WHEN** tính `88^7 mod 187`
- **THEN** kết quả là `11`
- **AND** tính `11^23 mod 187` cho kết quả `88`

#### Scenario: Bảng square-and-multiply đầy đủ
- **WHEN** tính modPow với exponent có 128 bit
- **THEN** bảng giải thích có đúng một dòng cho mỗi bit từ bit 0 tới bit cao nhất
- **AND** không có marker truncation, cursor hoặc phần bị lược bỏ

### Requirement: Sinh khóa thủ công theo p, q, e

Với `p,q,e` hợp lệ, hệ thống SHALL yêu cầu `p` và `q` là hai số nguyên tố khác nhau, tính `n=p*q`, `phi=(p-1)*(q-1)`, yêu cầu `1 < e < phi` và `gcd(e,phi)=1`, rồi tính `d=e^-1 mod phi`. Manual `p` và `q` MUST không vượt `10^12`; giới hạn này không áp dụng cho prime do endpoint random tự sinh. Khi `e` không nguyên tố cùng nhau với `phi`, hệ thống SHALL xác định số lẻ nhỏ nhất từ 3 trở lên thỏa range và coprime để làm gợi ý. (Truy vết: PDF RSA trang 2 BE-02, trang 3–4 bảng lỗi; HTML RSA §2 và dòng 218–245; quyết định chủ sở hữu Q1, Q14)

#### Scenario: Sinh khóa TC-01
- **WHEN** sinh khóa với `p=17`, `q=11`, `e=7`
- **THEN** `n=187`, `phi=160`, `d=23`

#### Scenario: Sinh khóa TC-03
- **WHEN** sinh khóa với `p=61`, `q=53`, `e=17`
- **THEN** `n=3233`, `phi=3120`, `d=2753`

#### Scenario: Gợi ý e cho TC-08
- **WHEN** kiểm tra `p=17`, `q=11`, `e=10`
- **THEN** validation xác định `gcd(10,160)=10`
- **AND** gợi ý `e=3`

### Requirement: Sinh khóa ngẫu nhiên đúng modulus bit length

Hệ thống SHALL sinh cặp prime khác nhau cho đúng một trong các modulus bit length `16`, `32`, `64`, `128`; kết quả `n=p*q` MUST có chính xác số bit yêu cầu. Hệ thống SHALL ưu tiên `e=65537` khi `1 < 65537 < phi` và coprime với `phi`; nếu không, SHALL chọn số lẻ nhỏ nhất từ 3 trở lên thỏa hai điều kiện. Mỗi kết quả SHALL thỏa `e*d mod phi = 1`, và mọi giá trị trả về SHALL nằm trong trần `2^128-1`. (Truy vết: PDF RSA trang 2 BE-03 và câu hỏi mở trang 5; HTML RSA §2 về `e=65537`; quyết định chủ sở hữu Q1, Q14)

#### Scenario: Sinh modulus 16 bit
- **WHEN** yêu cầu random key với `bits=16`
- **THEN** `n.bit_length()` bằng 16
- **AND** `p` và `q` khác nhau, `gcd(e,phi)=1`, `e*d mod phi=1`

#### Scenario: Fallback e khi 65537 ngoài range
- **WHEN** `phi <= 65537` trong quá trình sinh key
- **THEN** hệ thống không chọn `65537`
- **AND** chọn số lẻ nhỏ nhất từ 3 trở lên coprime với `phi`

### Requirement: Biến đổi một block textbook RSA

Encrypt một block SHALL tính `C=P^e mod n` và yêu cầu `0 <= P < n`. Decrypt một block SHALL tính `P=C^d mod n` và yêu cầu `0 <= C < n`. Mọi operand `n,e,d,P,C` MUST không vượt `2^128-1`. Lõi MUST NOT áp dụng OAEP, PKCS#1 v1.5 padding, chữ ký hoặc encoding hex/base64. (Truy vết: PDF RSA trang 1 BE-05, trang 3 API, trang 4 TC-02/04/05; HTML RSA §3; quyết định chủ sở hữu Q10, Q14)

#### Scenario: TC-04
- **WHEN** encrypt `P=65` với `e=17`, `n=3233`
- **THEN** ciphertext là `2790`
- **AND** decrypt `2790` với `d=2753`, `n=3233` trả `65`

#### Scenario: P bằng n bị từ chối
- **WHEN** encrypt `P=187` với `n=187`
- **THEN** lõi từ chối vì `P` không nhỏ hơn `n`

### Requirement: Chế độ char dùng Unicode code point lossless

Trong `mode=char`, hệ thống SHALL duyệt chuỗi theo Unicode code point, ánh xạ mỗi code point thành đúng một block `P`, yêu cầu từng `P<n`, và bảo toàn chính xác thứ tự cùng giá trị code point khi decrypt. Hệ thống MUST NOT trim, normalize Unicode, đổi case, đổi newline hoặc thêm/bỏ `U+FEFF`; surrogate không ghép cặp trong input MUST bị từ chối trước biến đổi. Sau RSA decrypt, mỗi `P` MUST là Unicode scalar hợp lệ (`0..D7FF` hoặc `E000..10FFFF`); giá trị khác SHALL gây `DECODE_FAILED`, không được serialize thành surrogate hoặc ký tự thay thế. (Truy vết: PDF RSA trang 2 BE-04, TC-10/11; HTML RSA §4 và dòng 273–292; quyết định chủ sở hữu Q8, Q9, Q12; quyết định kỹ thuật lossless Unicode)

#### Scenario: Whitespace và newline được giữ nguyên
- **WHEN** char mode round-trip chuỗi `" A\r\nB\n "`
- **THEN** plaintext sau decrypt bằng byte-for-byte cùng chuỗi Unicode đầu vào

#### Scenario: BOM là plaintext
- **WHEN** char mode round-trip chuỗi bắt đầu bằng `U+FEFF`
- **THEN** block đầu tiên biểu diễn code point `65279`
- **AND** plaintext decrypt vẫn bắt đầu bằng `U+FEFF`

#### Scenario: TC-10 vượt modulus
- **WHEN** char mode encrypt `"Việt"` với `n=187`
- **THEN** hệ thống từ chối vì code point `ệ` bằng `7879` không nhỏ hơn `n`

#### Scenario: Char decrypt ra surrogate

- **WHEN** một cipher item hợp lệ theo range giải mã thành `P=55296` (`U+D800`)
- **THEN** hệ thống từ chối bằng `DECODE_FAILED`
- **AND** không thay bằng `U+FFFD`

### Requirement: Chế độ block ghép UTF-8 big-endian và phục hồi theo byte length

Trong `mode=block`, hệ thống SHALL mã hóa plaintext thành UTF-8 nghiêm ngặt, chọn `k` lớn nhất sao cho `256^k <= n-1`, chia byte thành các nhóm `k`, ghép mỗi nhóm big-endian và đệm `0x00` bên phải cho block cuối thiếu byte. `n<=256` MUST bị từ chối. Khi decrypt, mỗi block số sau RSA SHALL được biểu diễn thành đúng `k` byte big-endian; `originalUtf8ByteLength` SHALL xác định chính xác số byte có nghĩa, gồm cả BOM nếu plaintext có `U+FEFF`. Hệ thống SHALL chỉ bỏ `len(cipher)*k-originalUtf8ByteLength` byte padding, yêu cầu các byte đó đều là `0x00`, rồi decode strict UTF-8. (Truy vết: PDF RSA trang 1 mục chia khối, trang 2 BE-04, TC-12/13; quyết định chủ sở hữu Q9, Q12, Q13)

#### Scenario: TC-12
- **WHEN** block mode encrypt `"Hi!"` với `n=67591`, `e=3`
- **THEN** `k=2`, plaintext blocks là `18537` và `8448`
- **AND** ciphertext là `37222` và `6468`
- **AND** decrypt với `d=44715` và `originalUtf8ByteLength=3` trả `"Hi!"`

#### Scenario: Trailing NUL thật được giữ
- **WHEN** block mode round-trip plaintext `"A\u0000"`
- **THEN** `originalUtf8ByteLength=2`
- **AND** decrypt chỉ bỏ zero-padding nằm sau byte NUL thật
- **AND** plaintext kết thúc bằng `U+0000`

#### Scenario: BOM tính vào byte length
- **WHEN** plaintext là `U+FEFF` theo sau bởi `A`
- **THEN** `originalUtf8ByteLength=4`
- **AND** decrypt phục hồi đúng `U+FEFFA`

#### Scenario: Metadata không khớp padding
- **WHEN** metadata yêu cầu bỏ các byte cuối nhưng ít nhất một byte cần bỏ khác `0x00`
- **THEN** hệ thống từ chối thay vì làm mất dữ liệu

#### Scenario: Plaintext block không vừa k byte

- **WHEN** một cipher item hợp lệ theo range giải mã thành số lớn hơn hoặc bằng `256^k`
- **THEN** hệ thống từ chối bằng `DECODE_FAILED` thay vì mở rộng block width

### Requirement: Giới hạn độ dài lõi

Plaintext text SHALL có từ 1 đến 10.000 Unicode code point. Number SHALL có đúng một block; char cipher SHALL có từ 1 đến 10.000 item; block cipher SHALL có từ 1 đến 40.000 item. Sau block decrypt, plaintext UTF-8 hợp lệ nhưng vượt 10.000 code point MUST bị từ chối. `originalUtf8ByteLength` của block decrypt SHALL là JSON integer từ 1 đến 40.000 và SHALL thỏa `ceil(originalUtf8ByteLength/k)=len(cipher)`. (Truy vết: PDF RSA trang 2 BE-06; quyết định chủ sở hữu Q8, Q13, Q14)

#### Scenario: Đúng 10.000 code point
- **WHEN** text hợp lệ có đúng 10.000 Unicode code point
- **THEN** không bị từ chối bởi giới hạn text

#### Scenario: Vượt char collection một item
- **WHEN** char decrypt nhận 10.001 cipher item
- **THEN** request bị từ chối trước biến đổi modular

#### Scenario: Block metadata không khớp số block
- **WHEN** `k=2`, cipher có hai item nhưng `originalUtf8ByteLength=2`
- **THEN** request bị từ chối vì hai block không phải canonical package cho hai byte
