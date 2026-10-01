# des-core Specification

## Purpose
Định nghĩa thuật toán DES độc lập HTTP: bảng hằng, sinh khóa con, hàm f, mã hóa/giải mã khối, ECB/CBC, PKCS#7, UTF-8, khóa yếu và giá trị trung gian. Nguồn: `Scope Backend_ Hệ mã hóa DES.html` §§2–3, 5, 9; `Hệ mã hóa DES_ thuật toán và logic.html` §§1–8; quyết định chủ sở hữu Q1, Q5, Q6, Q14, Q20 ngày 2026-10-01.
## Requirements
### Requirement: Lõi DES tự cài đặt theo bảng chuẩn

Lõi SHALL cài DES khối 64 bit, khóa 64 bit, 16 vòng bằng đúng các bảng PC-1, PC-2, LS, IP, IP⁻¹, E, P, S1–S8 của tài liệu thuật toán. Bit 1 là bit cao nhất của ký tự hex đầu tiên; phần tử thứ i của bảng hoán vị là vị trí bit đầu vào cho bit thứ i của đầu ra. Sinh khóa: PC-1 → C0, D0 (28 bit) → dịch vòng trái theo LS → PC-2 cho K1…K16. Mỗi vòng: `Li = Ri−1`, `Ri = Li−1 ⊕ P(S(E(Ri−1) ⊕ Ki))`; hộp S lấy hàng từ bit 1 và 6, cột từ bit 2–5. Đầu ra là `IP⁻¹(R16L16)`. Giải mã dùng cùng thuật toán với khóa con theo thứ tự K16…K1. Code ứng dụng MUST NOT gọi thư viện mật mã; được dùng bảng tra dẫn xuất (ví dụ SP-box) miễn là kết quả trùng bộ test. (Truy vết: HTML DES scope §§1, 3, 11; HTML thuật toán §§1–8; quyết định chủ sở hữu Q14, Q20)

#### Scenario: Ví dụ trên slide
- **WHEN** mã hóa khối `0123456789ABCDEF` với khóa `133457799BBCDFF1`
- **THEN** kết quả là `85E813540F0AB405`
- **AND** giải mã `85E813540F0AB405` với cùng khóa cho lại `0123456789ABCDEF`

#### Scenario: Bài tập slide 21
- **WHEN** mã hóa `A1B2C3D4E5F60978` với khóa `10012334455EFA67`
- **THEN** kết quả là `C291E07ED3004A9E`

#### Scenario: Vector kinh điển
- **WHEN** mã hóa `8787878787878787` với khóa `0E329232EA6D0D73`
- **THEN** kết quả là `0000000000000000`

#### Scenario: Khóa con và các vòng khớp tài liệu
- **WHEN** sinh khóa con từ `133457799BBCDFF1` và mã hóa `0123456789ABCDEF`
- **THEN** K1 = `1B02EFFC7072`, K16 = `CB3D8B0E17F5` và mọi Kn, Ln, Rn khớp bảng "Giá trị trung gian của T01" trong scope §9
- **AND** vòng 1 có `E(R0) ⊕ K1 = 6117BA866527`, đầu ra S = `5C82B597`, f = `234AA9BB`
- **AND** C16D16 bằng C0D0

#### Scenario: Bảng hằng hợp lệ
- **WHEN** kiểm tra bảng hằng
- **THEN** PC-1 có 56, PC-2 48, IP và IP⁻¹ 64, E 48, P 32 phần tử, LS có 16 phần tử tổng 28
- **AND** IP⁻¹(IP(x)) = x và mỗi hàng của S1–S8 là một hoán vị của 0–15

### Requirement: Khóa 16 hex và bit chẵn lẻ

Khóa SHALL là chuỗi đúng 16 ký tự hex sau khi bỏ khoảng trắng ASCII (space, tab, CR, LF, FF, VT), không phân biệt hoa thường; chỉ ký tự `0–9`, `a–f`, `A–F` là hex hợp lệ. 8 bit chẵn lẻ (bit 8, 16, …, 64) bị PC-1 loại và MUST NOT được kiểm tra hoặc sửa. Khóa chuẩn hóa là chữ hoa, không khoảng trắng. (Truy vết: HTML DES scope §§2, 5, 12)

#### Scenario: Khóa khác nhau chỉ ở bit chẵn lẻ
- **WHEN** mã hóa `0123456789ABCDEF` với khóa `123456789ABCDEF0`
- **THEN** kết quả là `85E813540F0AB405`, giống khóa `133457799BBCDFF1`

#### Scenario: Khóa chữ thường có khoảng trắng
- **WHEN** khóa là `1334 5779 9bbc dff1`
- **THEN** khóa chuẩn hóa là `133457799BBCDFF1` và kết quả giống T01

### Requirement: Dữ liệu text dùng UTF-8 và PKCS#7, dữ liệu hex không đệm

Khi mã hóa văn bản, lõi SHALL mã UTF-8 rồi luôn đệm PKCS#7: thêm n byte giá trị n (1 ≤ n ≤ 8) cho đủ bội 8 byte; dữ liệu đã đủ bội 8 vẫn thêm một khối `0808080808080808`. Khi mã hóa dữ liệu hex, lõi SHALL bỏ khoảng trắng ASCII, nhận chữ thường và yêu cầu độ dài bội 16 ký tự; không đệm. Bản mã luôn là hex in hoa không khoảng trắng. Khi giải mã ra text, lõi SHALL gỡ PKCS#7 (byte cuối n trong 1–8, n byte cuối đều bằng n) rồi giải mã UTF-8 nghiêm ngặt; khi giải mã ra hex, lõi SHALL trả nguyên byte dạng hex in hoa, không gỡ padding. (Truy vết: HTML DES scope §§2–3, 5, 9)

#### Scenario: PKCS#7 thêm 5 byte
- **WHEN** mã hóa text `Hello World` với khóa `133457799BBCDFF1`, ECB
- **THEN** kết quả là `B1CA74BB3514268701A9ACC3E4E69FAA`
- **AND** giải mã ra text cho lại `Hello World`

#### Scenario: Tiếng Việt UTF-8
- **WHEN** mã hóa text `Xin chào DES!` với khóa `133457799BBCDFF1`, ECB
- **THEN** kết quả là `06602CF53D9AD6AAC800F8D8643F636C` và giải mã cho lại đúng chuỗi gốc

#### Scenario: Đủ 8 byte vẫn thêm khối padding
- **WHEN** mã hóa text `12345678` với khóa `133457799BBCDFF1`, ECB
- **THEN** kết quả là `8B96B79529CCA218FDF2E174492922F8`

#### Scenario: Hex nhiều khối ECB
- **WHEN** mã hóa hex `0123456789ABCDEF0123456789ABCDEF` với khóa `133457799BBCDFF1`, ECB
- **THEN** kết quả là `85E813540F0AB40585E813540F0AB405`

#### Scenario: Giải mã ra hex không gỡ padding
- **WHEN** giải mã `85E813540F0AB405` với khóa `133457799BBCDFF1`, đầu ra hex
- **THEN** kết quả là `0123456789ABCDEF`

#### Scenario: Padding sai khi giải mã ra text
- **WHEN** giải mã `85E813540F0AB405` với khóa `133457799BBCDFF1`, đầu ra text
- **THEN** lõi báo lỗi padding (DES-E07)

#### Scenario: Byte không phải UTF-8
- **WHEN** giải mã `09A9EB2F8878EBF8` với khóa `133457799BBCDFF1`, đầu ra text
- **THEN** sau khi gỡ padding còn `FF FE` và lõi báo lỗi UTF-8 (DES-E08)

### Requirement: Chế độ ECB và CBC

Lõi SHALL hỗ trợ ECB (mỗi khối độc lập) và CBC với IV 64 bit: mã hóa `C_i = E(P_i ⊕ C_(i−1))`, giải mã `P_i = D(C_i) ⊕ C_(i−1)`, `C_0 = IV`. Khóa con SHALL được sinh một lần cho mỗi thao tác. (Truy vết: HTML DES scope §§2–3, 8 BE-D10; quyết định chủ sở hữu Q1)

#### Scenario: CBC với text
- **WHEN** mã hóa text `Hello World`, khóa `133457799BBCDFF1`, CBC, IV `0000000000000000`
- **THEN** kết quả là `B1CA74BB351426875F9A5BCA734D9EF4`

#### Scenario: CBC với hex lặp khối
- **WHEN** mã hóa hex `0123456789ABCDEF0123456789ABCDEF`, khóa `133457799BBCDFF1`, CBC, IV `1234567890ABCDEF`
- **THEN** kết quả là `F02B595EB219AB97E6DB189E19AF7792`

#### Scenario: Round-trip ngẫu nhiên khớp thư viện chuẩn
- **WHEN** chạy 1000 lần với văn bản UTF-8, khóa và IV ngẫu nhiên ở cả ECB và CBC
- **THEN** `decrypt(encrypt(x)) = x` và bản mã trùng với kết quả của thư viện mật mã chuẩn dùng trong test

### Requirement: Nhận diện khóa yếu và nửa yếu

Lõi SHALL so sánh khóa với 4 khóa yếu (`0101010101010101`, `FEFEFEFEFEFEFEFE`, `E0E0E0E0F1F1F1F1`, `1F1F1F1F0E0E0E0E`) và 12 khóa nửa yếu (`011F011F010E010E`, `1F011F010E010E01`, `01E001E001F101F1`, `E001E001F101F101`, `01FE01FE01FE01FE`, `FE01FE01FE01FE01`, `1FE01FE00EF10EF1`, `E01FE01FF10EF10E`, `1FFE1FFE0EFE0EFE`, `FE1FFE1FFE0EFE0E`, `E0FEE0FEF1FEF1FE`, `FEE0FEE0FEF1FEF1`) sau khi xóa bit cuối mỗi byte của cả hai bên. Nhận diện không chặn thao tác. (Truy vết: HTML DES scope §6; quyết định chủ sở hữu Q6)

#### Scenario: Khóa toàn 0 là khóa yếu
- **WHEN** khóa là `0000000000000000`
- **THEN** khóa được nhận diện là khóa yếu
- **AND** mã hóa `0000000000000000` cho `8CA64DE9C1B123A7`

#### Scenario: Khóa yếu mã hai lần ra bản rõ
- **WHEN** mã hóa `0123456789ABCDEF` với khóa `0101010101010101`
- **THEN** kết quả là `617B3A0CE8F07100` và mã hóa lần nữa cho lại `0123456789ABCDEF`

#### Scenario: Khóa nửa yếu
- **WHEN** mã hóa `0123456789ABCDEF` với khóa `011F011F010E010E`
- **THEN** kết quả là `6F2C1F78866CCF13` và khóa được nhận diện là nửa yếu

#### Scenario: Khóa thường
- **WHEN** khóa là `133457799BBCDFF1`
- **THEN** khóa không yếu và không nửa yếu

### Requirement: Giá trị trung gian của một khối

Lõi SHALL tính được cho một khối 64 bit và một chiều (encrypt/decrypt): PC-1 của khóa; với mỗi n = 1…16 số bit dịch, Cn, Dn và Kn; IP của khối, L0, R0; với mỗi vòng i, số thứ tự khóa con dùng, E(Ri−1), E ⊕ K, tám bộ (hàng, cột, giá trị) của S1–S8, đầu ra S, f, Li, Ri; R16L16 và kết quả. Kết quả SHALL trùng với đường mã hóa/giải mã thông thường. (Truy vết: HTML DES scope §§7, 9 BE-D09; HTML thuật toán §§3–7; quyết định chủ sở hữu Q18)

#### Scenario: Vòng 1 của T01
- **WHEN** tính giá trị trung gian cho `0123456789ABCDEF`, khóa `133457799BBCDFF1`, chiều encrypt
- **THEN** PC-1 = `F0CCAAF556678F`, C1 = `E19955F`, D1 = `AACCF1E`, IP = `CC00CCFFF0AAF0AA`
- **AND** vòng 1 có E = `7A15557A1555`, hộp S1 tại hàng 0 cột 12 giá trị 5, hộp S2 tại hàng 1 cột 8 giá trị 12, R1 = `EF4A6544`
- **AND** R16L16 = `0A4CD99543423234`

#### Scenario: Chiều giải mã dùng khóa con đảo
- **WHEN** tính giá trị trung gian cho `85E813540F0AB405`, khóa `133457799BBCDFF1`, chiều decrypt
- **THEN** vòng 1 dùng khóa con 16, vòng 16 dùng khóa con 1 và kết quả là `0123456789ABCDEF`
