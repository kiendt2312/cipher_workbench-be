## Purpose

Định nghĩa phép biến đổi Vigenère repeating-key xác định cho text và file, bao gồm chuẩn hóa key ASCII, bảo toàn case và quy tắc không làm tiến key trên ký tự ngoài ASCII.

## ADDED Requirements

### Requirement: Chuẩn hóa và kiểm tra key Vigenère

Key Vigenère SHALL là một chuỗi khác rỗng chỉ gồm các ký tự ASCII `A-Z` hoặc `a-z`. Hệ thống SHALL chuẩn hóa từng ký tự key sang uppercase để ánh xạ `A=0` đến `Z=25`; SHALL KHÔNG trim, bỏ qua, transliterate hoặc tự sửa ký tự ngoài tập này. Key có khoảng trắng, dấu câu, chữ số, chữ có dấu hoặc Unicode khác MUST bị coi là không hợp lệ. Không có giới hạn độ dài nghiệp vụ riêng ngoài các giới hạn request dùng chung. (Truy vết: scope mới BE-VIG-01, BE-VIG-04; quyết định chủ sở hữu cho change này)

#### Scenario: Key chữ thường và chữ hoa tương đương
- **WHEN** cùng plaintext được biến đổi lần lượt với key `lemon` và `LEMON`
- **THEN** hai kết quả giống hệt nhau
- **AND** key logic dùng cho cả hai trường hợp là `LEMON`

#### Scenario: Key có ký tự ngoài ASCII letter không được tự sửa
- **WHEN** key là `LE MON`, `KEY1` hoặc `KHÓA`
- **THEN** key bị coi là không hợp lệ
- **AND** hệ thống không trim khoảng trắng, bỏ chữ số hoặc chuyển chữ có dấu thành ASCII

### Requirement: Công thức Vigenère repeating-key

Với mỗi chữ cái ASCII đầu vào ở vị trí được mã hóa, hệ thống SHALL ánh xạ chữ cái và ký tự key tương ứng về `0..25`. Encrypt SHALL tính `Cᵢ = (Pᵢ + Kᵢ) mod 26`; decrypt SHALL tính `Pᵢ = (Cᵢ - Kᵢ) mod 26`. Khi hết key, hệ thống SHALL quay lại ký tự đầu tiên của key và lặp cho tới hết dữ liệu. Cùng input, key và operation MUST luôn cho cùng output, không phụ thuộc trạng thái hoặc request trước đó. (Truy vết: scope mới BE-VIG-01; quyết định chủ sở hữu cho change này)

#### Scenario: Vector encrypt chuẩn Attack at dawn
- **WHEN** encrypt plaintext `Attack at dawn!` với key `LEMON`
- **THEN** kết quả là `Lxfopv ef rnhr!`

#### Scenario: Vector decrypt chuẩn Attack at dawn
- **WHEN** decrypt ciphertext `Lxfopv ef rnhr!` với key `LEMON`
- **THEN** kết quả là `Attack at dawn!`

#### Scenario: Key lặp lại khi ngắn hơn dữ liệu
- **WHEN** encrypt plaintext `AAAAAA` với key `ABC`
- **THEN** key stream trên sáu chữ cái là `ABCABC`
- **AND** kết quả là `ABCABC`

### Requirement: Chỉ chữ cái ASCII làm tiến key

Hệ thống SHALL chỉ biến đổi ký tự trong `A-Z` hoặc `a-z`, và SHALL chỉ tăng chỉ số key khi đã xử lý một ký tự thuộc hai tập đó. Whitespace, chữ số, dấu câu, newline, chữ có dấu, emoji và mọi Unicode ngoài ASCII letter MUST được giữ nguyên đúng giá trị và vị trí, đồng thời MUST NOT tiêu thụ một ký tự key. (Truy vết: scope mới BE-VIG-01, BE-VIG-03)

#### Scenario: Dấu câu không làm tiến key
- **WHEN** encrypt plaintext `A-A` với key `BC`
- **THEN** kết quả là `B-C`
- **AND** dấu `-` không làm key stream bỏ qua ký tự `C`

#### Scenario: Unicode được giữ nguyên và không làm tiến key
- **WHEN** encrypt plaintext `AéA` với key `BC`
- **THEN** kết quả là `BéC`
- **AND** ký tự `é` được giữ nguyên

### Requirement: Bảo toàn case của dữ liệu

Mỗi chữ cái ASCII sau biến đổi SHALL giữ loại case của ký tự đầu vào: uppercase cho input `A-Z`, lowercase cho input `a-z`. Việc chuẩn hóa key sang uppercase MUST NOT ép case của dữ liệu. (Truy vết: scope mới BE-VIG-01)

#### Scenario: Vector chuẩn giữ case
- **WHEN** encrypt plaintext `Attack` với key `LEMON`
- **THEN** kết quả là `Lxfopv`
- **AND** ký tự đầu kết quả là uppercase còn các ký tự sau giữ lowercase tương ứng

### Requirement: Cùng core cho text và nội dung file

Với cùng chuỗi Unicode đã đọc từ request JSON hoặc từ file UTF-8, cùng key và operation, hệ thống SHALL tạo cùng một kết quả Vigenère. Lõi Vigenère SHALL không phụ thuộc filename, transport, response mode hoặc trạng thái BOM. (Truy vết: scope mới BE-VIG-01, BE-VIG-03; baseline Caesar Week 1 `caesar-core`)

#### Scenario: Text và file cho kết quả giống nhau
- **WHEN** chuỗi `Attack at dawn!` từ JSON và cùng chuỗi đọc từ file được encrypt với key `LEMON`
- **THEN** cả hai luồng tạo nội dung logic `Lxfopv ef rnhr!`
