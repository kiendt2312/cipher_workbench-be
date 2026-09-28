## Purpose

Định nghĩa phép biến đổi Affine modulo 26 xác định cho text và file, gồm chuẩn hóa hai khóa, điều kiện khả nghịch, bảo toàn dữ liệu ngoài ASCII và round-trip lossless.

## ADDED Requirements

### Requirement: Chuẩn hóa cặp khóa Affine

Hệ thống SHALL nhận hai khóa số nguyên `a`, `b` và chuẩn hóa bằng positive modulo: `a'=((a%26)+26)%26`, `b'=((b%26)+26)%26`. Mọi biểu diễn integer âm hoặc lớn ánh xạ về cùng `(a',b')` SHALL tạo cùng kết quả; hệ thống MUST NOT sửa một `a'` không hợp lệ sang residue khác. (Truy vết: quyết định chủ sở hữu cho change này; `affine-cipher.html` mục khóa/công thức; baseline Caesar Week 1 `caesar-core`)

#### Scenario: Khóa âm tương đương khóa chuẩn
- **WHEN** encrypt cùng text lần lượt bằng `(a,b)=(-21,-18)` và `(5,8)`
- **THEN** cả hai lần dùng cặp normalized `(5,8)` và tạo cùng kết quả

#### Scenario: Khóa lớn tương đương theo residue
- **WHEN** encrypt cùng text lần lượt bằng `(a,b)=(57,60)` và `(5,8)`
- **THEN** cả hai lần tạo cùng kết quả vì `57 mod 26 = 5` và `60 mod 26 = 8`

### Requirement: Khóa nhân phải khả nghịch modulo 26

Sau khi chuẩn hóa, hệ thống SHALL chỉ chấp nhận `a'` thỏa `gcd(a',26)=1`. Tập residue hợp lệ SHALL chính xác là `1,3,5,7,9,11,15,17,19,21,23,25`; `b'` SHALL chấp nhận mọi residue `0..25`. Vì vậy có đúng `12 × 26 = 312` cặp normalized hợp lệ, trong khi vô số biểu diễn integer đầu vào ánh xạ vào 312 cặp đó. (Truy vết: quyết định chủ sở hữu cho change này; `affine-cipher.html` mục điều kiện khóa/không gian khóa)

#### Scenario: Các residue a không khả nghịch bị từ chối
- **WHEN** `a` là một trong `0`, `2`, `13`, `26`
- **THEN** `a'` tương ứng không nguyên tố cùng nhau với 26 và khóa bị từ chối
- **AND** hệ thống không tự đổi `a` thành residue hợp lệ gần nhất

#### Scenario: Đếm không gian khóa normalized
- **WHEN** liệt kê mọi residue `a'` khả nghịch và mọi residue `b'`
- **THEN** có 12 lựa chọn `a'` và 26 lựa chọn `b'`
- **AND** số cặp normalized hợp lệ là 312, không phải số biểu diễn integer đầu vào

### Requirement: Công thức encrypt và decrypt Affine

Hệ thống SHALL ánh xạ `A/a=0` đến `Z/z=25`. Encrypt SHALL tính `E(x)=(a'*x+b') mod 26`. Decrypt SHALL tính `D(y)=inverse(a',26)*(y-b') mod 26` bằng positive modulo, trong đó inverse thỏa `a'*inverse(a',26) ≡ 1 (mod 26)`. (Truy vết: quyết định chủ sở hữu cho change này; `affine-cipher.html` mục mã hóa, giải mã và nghịch đảo modulo)

#### Scenario: Vector HELLO canonical
- **WHEN** encrypt `HELLO` với `(a,b)=(5,8)`
- **THEN** kết quả là `RCLLA`

#### Scenario: Decrypt vector HELLO canonical
- **WHEN** decrypt `RCLLA` với `(a,b)=(5,8)`
- **THEN** nghịch đảo của `5` modulo 26 là `21`
- **AND** kết quả là `HELLO`

#### Scenario: Mixed case và wraparound
- **WHEN** encrypt `Zz Aa` với `(a,b)=(5,8)`
- **THEN** kết quả là `Dd Ii`
- **AND** decrypt kết quả với cùng khóa trả lại `Zz Aa`

### Requirement: Chỉ biến đổi ASCII letter và bảo toàn case

Hệ thống SHALL chỉ biến đổi ký tự thuộc ASCII `A-Z` hoặc `a-z`, dùng base riêng để giữ case của từng ký tự. Whitespace, LF/CRLF, chữ số, dấu câu, chữ có dấu, emoji và mọi Unicode ngoài ASCII letter MUST được giữ nguyên đúng giá trị, thứ tự và vị trí. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed Caesar `caesar-core` và Vigenère `vigenere-core`)

#### Scenario: Unicode và emoji được bảo toàn
- **WHEN** encrypt `Hé🙂z!` với `(a,b)=(5,8)`
- **THEN** kết quả là `Ré🙂d!`
- **AND** `é`, `🙂` và `!` không thay đổi

#### Scenario: Whitespace và CRLF được bảo toàn
- **WHEN** encrypt `A \t\r\nZ` với `(a,b)=(5,8)`
- **THEN** kết quả là `I \t\r\nD`
- **AND** space, tab và cặp bytes/ký tự CRLF giữ nguyên

### Requirement: Round-trip Affine lossless với khóa hợp lệ

Với mọi chuỗi Unicode và cặp khóa hợp lệ, hệ thống SHALL bảo đảm `decrypt(encrypt(text,a,b),a,b) == text` chính xác. Khác Playfair, Affine MUST không normalize mất dữ liệu, chèn filler, đổi `J`, đổi case hoặc loại format. (Truy vết: quyết định chủ sở hữu cho change này; đối chiếu completed Playfair `playfair-core`)

#### Scenario: Round-trip chuỗi hỗn hợp chính xác
- **WHEN** text `Hello, Việt Nam 🙂\r\n123!` được encrypt rồi decrypt với `(5,8)`
- **THEN** kết quả cuối cùng bằng chính xác input ban đầu

#### Scenario: Whitespace-only là dữ liệu hợp lệ
- **WHEN** text chỉ gồm ` \t\r\n` được encrypt hoặc decrypt với khóa hợp lệ
- **THEN** operation thành công và trả nguyên chuỗi đó

### Requirement: Cùng core cho text và file và không có trạng thái

Với cùng chuỗi Unicode logic, cùng `a`, `b` và operation, luồng JSON và luồng file SHALL tạo cùng một result. Lõi Affine MUST không phụ thuộc transport, filename, response mode, BOM, request trước đó hoặc `affine-cipher.html`. (Truy vết: quyết định chủ sở hữu cho change này; baseline completed Caesar/Vigenère core)

#### Scenario: Text và file cho cùng result
- **WHEN** chuỗi `Hello\r\n🙂` từ JSON và cùng chuỗi decode từ file UTF-8 được encrypt bằng `(5,8)`
- **THEN** hai luồng tạo cùng nội dung logic
