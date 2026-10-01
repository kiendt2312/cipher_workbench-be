## MODIFIED Requirements

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
