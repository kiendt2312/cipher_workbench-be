# Spec Delta

## Purpose

Định nghĩa hành vi số học và giao thức Diffie–Hellman bản giáo trình, gồm tham số, khóa, bí mật chung, random generation và trace có thể kiểm chứng.

## ADDED Requirements

### Requirement: Kiểm tra tham số DH
Lõi SHALL nhận số nguyên `q, alpha`, xác nhận `q` nguyên tố và `1 < alpha < q`, rồi xác nhận `alpha` là nguyên căn bằng mọi thừa số nguyên tố phân biệt của `q-1`. (Truy vết: Tài liệu thuật toán DH §§3,12; Scope DH BE-01–BE-02; TC-01, TC-05–TC-07)

#### Scenario: Tham số giáo trình hợp lệ
- **WHEN** kiểm tra `q="23"`, `alpha="5"`
- **THEN** kết quả hợp lệ, factors là `["2","11"]`, checks chứa `5^11 mod 23 = 22` và `5^2 mod 23 = 2`

#### Scenario: q không nguyên tố
- **WHEN** kiểm tra `q="21"`, `alpha="2"`
- **THEN** lõi báo `NOT_PRIME`

#### Scenario: alpha không phải nguyên căn
- **WHEN** kiểm tra `q="23"`, `alpha="4"`
- **THEN** lõi báo `NOT_PRIMITIVE_ROOT`, ghi nhận `4^11 mod 23 = 1` và gợi ý `"5"`

### Requirement: Hai miền q manual và downstream
`/params` manual SHALL giới hạn `5 <= q <= 10^12`; lõi dùng bởi các endpoint downstream SHALL chấp nhận và tự kiểm tra `q` tối đa 128 bit, không dùng provenance token, cache hay server state. (Truy vết: Scope DH BE-02–BE-05, TC-13; quyết định chủ sở hữu DH Q1/Q4)

#### Scenario: Manual q vượt trần
- **WHEN** manual params nhận `q="1000000000039"`
- **THEN** hệ thống từ chối `Q_OUT_OF_RANGE`

#### Scenario: Generated q dùng end-to-end
- **WHEN** một safe prime 128 bit do endpoint random trả về được gửi tới keypair rồi exchange
- **THEN** mỗi endpoint tự kiểm tra q/alpha và xử lý không cần token hoặc request trước đó

### Requirement: Sinh safe prime và nguyên căn
Lõi SHALL sinh `q=2p+1` có đúng 16, 32, 64 hoặc 128 bit, với `p` và `q` là probable prime đủ mạnh cho phạm vi giáo dục, rồi chọn nguyên căn thỏa hai phép thử cho factors `2,p`. Randomness SHALL đến từ CSPRNG. (Truy vết: Tài liệu thuật toán DH §3; Scope DH BE-03, TC-08; quyết định kỹ thuật của change)

#### Scenario: Sinh tham số 32 bit
- **WHEN** yêu cầu `bits=32`
- **THEN** `q.bit_length()` bằng 32, `q=2p+1`, cả p/q qua chính sách primality và alpha qua đúng checks cho `2,p`

### Requirement: Sinh cặp khóa
Lõi SHALL chấp nhận hoặc sinh CSPRNG private key trong `2..q-2`, tính `Y=alpha^X mod q`, và chỉ trả cặp khóa khi `2 <= Y <= q-2`. Random generation SHALL resample nếu Y suy biến; input X thủ công gây Y suy biến SHALL bị từ chối. (Truy vết: Tài liệu thuật toán DH §§4,10,12; Scope DH BE-04–BE-05, TC-02–TC-03, TC-09–TC-10; `rsa-core` random-key precedent; quyết định kỹ thuật Lead)

#### Scenario: Cặp khóa nhỏ
- **WHEN** `q="23"`, `alpha="5"`, `privateKey="4"`
- **THEN** public key bằng `"4"`

#### Scenario: Private key biên trên sai
- **WHEN** `q="23"`, `alpha="5"`, `privateKey="22"`
- **THEN** lõi báo `PRIVATE_KEY_OUT_OF_RANGE`

#### Scenario: Private key tạo public key suy biến
- **WHEN** `q="23"`, `alpha="5"`, `privateKey="11"` tạo `Y="22"`
- **THEN** lõi báo `PRIVATE_KEY_WEAK` với field `privateKey`

#### Scenario: Random key luôn composable
- **WHEN** random candidate tạo Y bằng `1` hoặc `q-1`
- **THEN** generator bỏ candidate và tiếp tục tới khi cả X và Y hợp lệ

### Requirement: Tính bí mật chung
Lõi SHALL yêu cầu `2 <= otherPublicKey <= q-2` và `2 <= privateKey <= q-2`, rồi tính `K=otherPublicKey^privateKey mod q`. (Truy vết: Tài liệu thuật toán DH §§5,10,12; Scope DH BE-05, TC-02–TC-03, TC-10)

#### Scenario: Hai bên ra cùng K
- **WHEN** A dùng `q="353", X_A="97", Y_B="248"` và B dùng `q="353", X_B="233", Y_A="40"`
- **THEN** cả hai kết quả shared key bằng `"160"`

#### Scenario: Public key suy biến
- **WHEN** `q="23"`, private key `"4"`, other public key `"22"`
- **THEN** lõi báo `PUBLIC_KEY_INVALID`

### Requirement: Trace modPow DH trái sang phải
Trace DH SHALL duyệt bit exponent từ trái sang phải, ghi đầy đủ mỗi bit với exponent prefix, giá trị sau bình phương, giá trị nhân tùy chọn và result; mọi đại lượng mật mã là decimal string, row index/bit là JSON integer. Trace RSA hiện hữu MUST không đổi. (Truy vết: Tài liệu thuật toán DH §6; Scope DH BE-01, TC-04; quyết định chủ sở hữu DH)

#### Scenario: TC-04 chính xác
- **WHEN** trace `3^97 mod 353`, với `97 = 1100001₂`
- **THEN** bảy result theo thứ tự là `"3","27","23","176","265","331","40"`
- **AND** bit lần lượt là `1,1,0,0,0,0,1`

### Requirement: Mô phỏng exchange giáo dục
Exchange SHALL tạo hoặc nhận hai private key, tính hai public key và hai shared key, rồi trả `match`; private key A/B SHALL được trả công khai trong response chỉ nhằm minh họa. (Truy vết: Tài liệu thuật toán DH §§2,4–5; Scope DH luồng xử lý, BE-06, TC-02–TC-03; quyết định chủ sở hữu DH Q3)

#### Scenario: Exchange mẫu q 23
- **WHEN** exchange nhận `q="23", alpha="5", privateKeyA="4", privateKeyB="3"`
- **THEN** trả private keys `"4","3"`, public keys `"4","10"`, shared keys đều `"18"` và `match=true`

### Requirement: Dẫn xuất độ dịch Caesar
DH Caesar SHALL tính `shift=K mod 26` và gọi cùng hành vi Caesar core hiện hữu; `shift` trả dưới dạng decimal string. Nếu shift bằng 0, kết quả vẫn thành công và có warning `SHIFT_ZERO`. (Truy vết: Tài liệu thuật toán DH §§10–12; Scope DH BE-06, TC-11–TC-12; `caesar-core`; quyết định chủ sở hữu DH Q7)

#### Scenario: Caesar với K 160
- **WHEN** K bằng `"160"`, action `encrypt`, data `Hello World`
- **THEN** shift bằng `"4"` và result bằng `Lipps Asvph`

#### Scenario: Shift zero không chặn request
- **WHEN** K bằng `"52"`
- **THEN** shift bằng `"0"`, result không đổi và warning có code `SHIFT_ZERO` cùng message `K = 52 cho độ dịch 0, văn bản không đổi. Hãy chọn khóa riêng khác.`
