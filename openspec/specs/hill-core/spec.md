# hill-core Specification

## Purpose
Định nghĩa toán học và biến đổi văn bản Hill độc lập HTTP. Nguồn: `Scope Backend_ Hệ mã hóa Hill.html` §§2–5, 9, 11; các quyết định chủ sở hữu Q4, Q5, Q7, Q8, Q12–Q14, Q16 ngày 2026-09-29.
## Requirements
### Requirement: Số học và ma trận modulo 26 theo vector hàng

Core SHALL hỗ trợ `m ∈ {2,3,4}`, ánh xạ A=0…Z=25, `mod` luôn không âm, định thức nguyên, `det mod 26`, ƯCLN, nghịch đảo định thức, ma trận phụ hợp `K*`, nghịch đảo `K⁻¹ = (det K)⁻¹ K* mod 26` và nhân vector hàng `y_j = Σ_i x_i K_ij mod 26`. Ma trận hợp lệ khi `gcd(det mod 26,26)=1`. Tất cả ma trận công bố ra ngoài SHALL có phần tử 0–25. (Truy vết: HTML Hill §2–3; quyết định chủ sở hữu xác nhận giữ nguyên thuật toán ngày 2026-09-29)

#### Scenario: Vector hàng T01
- **WHEN** K là `[[3,3],[2,5]]` và plaintext là `HELP`
- **THEN** det mod 26 bằng 9, nghịch đảo det bằng 3, phụ hợp bằng `[[5,23],[24,3]]`, K⁻¹ bằng `[[15,17],[20,9]]`
- **AND** encrypt trả `DPLE`, decrypt trả lại `HELP`

#### Scenario: Cấp ba phân biệt vector hàng và cột
- **WHEN** K là `[[6,24,1],[13,16,10],[20,17,15]]` và plaintext là `ACT`
- **THEN** encrypt trả `QRT`, không phải output của quy ước vector cột

#### Scenario: Cấp bốn
- **WHEN** K là `[[3,1,2,0],[0,5,1,4],[0,0,7,2],[0,0,0,9]]` và plaintext là `TEST`
- **THEN** det mod 26 bằng 9, encrypt trả `FNMP`, decrypt trả `TEST`
- **AND** `K·K⁻¹ ≡ I (mod 26)`

### Requirement: Chuẩn hóa khóa và từ khóa

Ma trận đầu vào SHALL vuông cấp 2–4 với mọi ô là JSON integer thực sự; core chuẩn hóa từng ô modulo 26 kể cả số âm/lớn trước khi phân tích. Keyword SHALL là đúng `m²` ký tự ASCII `[A-Za-z]`, đọc theo hàng, không trim hoặc loại dấu cách/dấu câu; `m` phải được truyền riêng khi dùng keyword. Hai dạng khóa cùng giá trị chuẩn hóa SHALL tạo cùng kết quả. Khóa không khả nghịch SHALL bị từ chối, không tự sửa. (Truy vết: HTML Hill §§4–6; quyết định chủ sở hữu Q4, Q13)

#### Scenario: Keyword HILL
- **WHEN** `keyword="HILL"` và `m=2`
- **THEN** K chuẩn hóa là `[[7,8],[11,11]]`, det mod 26 là 15
- **AND** `HILLCIPHER` mã hóa thành `HOQBYAAPHL`

#### Scenario: Phần tử âm
- **WHEN** một ô K là `-1`
- **THEN** ma trận phân tích và phản hồi dùng giá trị 25 tại ô đó

### Requirement: Chuẩn bị và dựng lại văn bản

Core SHALL chia khối chỉ trên các chữ ASCII A–Z/a–z, tính chữ thường như chữ hoa và trả đúng case ở từng vị trí chữ gốc. Dấu cách, số, dấu câu và Unicode khác SHALL giữ nguyên chỗ và không tham gia khối. Mặc định, mỗi cụm chữ Việt có dấu hợp lệ trong dạng NFC hoặc NFD SHALL được giữ nguyên trọn cụm, không tham gia khối, và tính một đơn vị cho W02; Unicode ngoài tập chữ Việt có dấu được giữ nguyên nhưng không sinh W02. Khi `stripDiacritics=true`, các cụm chữ Việt có dấu SHALL chuyển thành ASCII không dấu, `đ/Đ → d/D`, rồi tham gia mã hóa; các ký tự Unicode khác vẫn giữ nguyên. Vị trí được hiểu trên văn bản sau bước bỏ dấu nếu tùy chọn được bật. (Truy vết: HTML Hill §§4–5; quyết định chủ sở hữu Q12, Q14 ưu tiên hơn giới hạn của JavaScript tham chiếu)

#### Scenario: Dấu câu và case
- **WHEN** encrypt `Help, me!` với K T01
- **THEN** trả `Dple, se!`

#### Scenario: Dấu tiếng Việt ở hai dạng Unicode
- **WHEN** text chứa `ế` và `e` + các dấu kết hợp tương đương, và `stripDiacritics=false`
- **THEN** cả hai cụm được giữ nguyên, không tiêu thụ vị trí khối, mỗi cụm tính một lần W02
- **AND** nếu bật `stripDiacritics`, cả hai cụm trở thành `e` để tham gia khối

### Requirement: Padding, giải mã và dữ liệu từng khối

Encrypt SHALL đệm `padChar` vào cuối chuỗi chữ cho đến khi số chữ chia hết `m`; mặc định `padChar="X"`, chỉ cho phép một chữ hoa ASCII A–Z. Chữ đệm được ghép ở dạng hoa vào cuối toàn bộ văn bản kết quả, sau cả dấu câu ở cuối. Decrypt SHALL yêu cầu số chữ tham gia chia hết `m`, dùng K⁻¹, và không thêm hay xóa ký tự nào khỏi `result`; chữ đệm vẫn nằm trong `result`. Sau khi giải mã, core SHALL nhận diện ký tự đệm như sau. Gọi `n` là số chữ tham gia và `k` là số chữ liên tiếp ở cuối dãy chữ (theo thứ tự xử lý) có giá trị bằng `padChar`, không phân biệt hoa thường. Số ký tự đệm nhận diện là `min(k, m − 1)`, nằm ở các vị trí `n − count` … `n − 1`. Bản lọc là `result` bỏ đúng các chữ đó. `padChar` trên decrypt được validate và chỉ dùng cho bước nhận diện, không ảnh hưởng phép giải mã. Ciphertext không mang số chữ đã đệm, nên chữ thật trùng `padChar` ở cuối có thể bị nhận diện nhầm trong bản lọc; `result` luôn giữ chúng. Mỗi khối SHALL có `input` và `output` là vector số 0–25 đúng thứ tự xử lý; response chứa toàn bộ khối, kể cả khối có padding. (Truy vết: HTML Hill §§3–5, 7, 9; quyết định chủ sở hữu Q5, Q7, Q16; yêu cầu chủ sở hữu ngày 2026-10-01 về lọc ký tự đệm khi giải mã)

#### Scenario: Padding T06
- **WHEN** encrypt `HELLO` với K T01 và mặc định
- **THEN** trả `DPDKKB`, sinh W01 với một `X`
- **AND** decrypt bản mã trả `HELLOX`, nhận diện ký tự đệm ở vị trí `5` và bản lọc là `HELLO`

#### Scenario: Chữ đệm sau dấu câu
- **WHEN** encrypt `HELLO!` với K T01
- **THEN** kết quả là `DPDKK!B`
- **AND** decrypt `DPDKK!B` trả `HELLO!X` với bản lọc `HELLO!`

#### Scenario: Hai chữ đệm với khóa 3×3
- **WHEN** encrypt `THUDOHANOI` với K `[[6,1,3],[17,5,7],[3,2,3]]`
- **THEN** trả `HQKRJYDPDONU`, sinh W01 với hai `X`
- **AND** decrypt bản mã trả `THUDOHANOIXX`, nhận diện vị trí `10`, `11` và bản lọc là `THUDOHANOI`

#### Scenario: Nhận diện tối đa m − 1 ký tự
- **WHEN** decrypt `ACN` với K `[[6,1,3],[17,5,7],[3,2,3]]`
- **THEN** `result` là `XXX`
- **AND** chỉ vị trí `1`, `2` được nhận diện và bản lọc là `X`

#### Scenario: Nhận diện theo padChar của request decrypt
- **WHEN** encrypt `HELLO` với K T01 và `padChar="Q"` được `DPDKWS`, rồi decrypt `DPDKWS`
- **THEN** với `padChar="Q"`, `result` là `HELLOQ` và bản lọc là `HELLO`
- **AND** với `padChar` mặc định, `result` vẫn là `HELLOQ` và không nhận diện ký tự đệm nào

#### Scenario: Nhận diện không phân biệt hoa thường
- **WHEN** decrypt `dpdkkb` với K T01
- **THEN** `result` là `hellox`
- **AND** vị trí `5` được nhận diện và bản lọc là `hello`

### Requirement: Cảnh báo khóa yếu và khóa ngẫu nhiên

Core SHALL sinh W03 khi K là ma trận đơn vị hoặc K tự nghịch đảo modulo 26 (`K = K⁻¹`). Sinh khóa ngẫu nhiên SHALL tạo ma trận m×m có phần tử 0–25, khả nghịch và khác ma trận đơn vị; khóa tự nghịch đảo vẫn có thể được sinh và khi đó SHALL kèm W03. Cảnh báo không chặn kết quả. (Truy vết: HTML Hill §§5–6, 8–9; quyết định chủ sở hữu Q8, Q16)

#### Scenario: Khóa đơn vị T12
- **WHEN** K là `[[1,0],[0,1]]` và encrypt `HELP`
- **THEN** kết quả là `HELP` và warnings chứa W03

#### Scenario: 1000 khóa ngẫu nhiên
- **WHEN** sinh 1000 khóa với mỗi m trong 2, 3, 4
- **THEN** mọi khóa có `gcd(det mod 26,26)=1` và khác ma trận đơn vị

### Requirement: Vector nghiệm thu và hiệu năng lõi

Core SHALL khớp T01–T12 trong HTML Hill, cộng vector cấp bốn ở trên; với khóa hợp lệ, `K·K⁻¹ ≡ I` và decrypt(encrypt(x)) SHALL bằng văn bản đã chuẩn bị cộng padding theo quy tắc giữ vị trí/case. Kiểm thử ngẫu nhiên SHALL bao gồm 1000 khóa hợp lệ và văn bản ngẫu nhiên. Kết quả `<1 giây` cho fixture ASCII 1 MiB được giữ làm bằng chứng lịch sử. Implementation SHALL đo và báo cáo thời gian lõi cùng rủi ro kích thước response cho fixture đúng 5 MiB trên môi trường ghi rõ; không suy diễn mốc `<1 giây` thành gate cho 5 MiB. Phép đo lõi không gồm parse HTTP, JSON serialization, truyền tải mạng hoặc render FE. (Truy vết: HTML Hill §§9, 11; quyết định chủ sở hữu Q7 và override giới hạn ngày 2026-09-30)

#### Scenario: Bộ vector
- **WHEN** chạy T01–T12 bằng core ở operation tương ứng
- **THEN** mọi result, inverse, mã lỗi và warning đều khớp dữ liệu kỳ vọng trong HTML Hill
