Mục lục

1. [Tổng quan](#tong-quan)
2. [Sơ đồ giao thức](#so-do)
3. [Bước 1: Tham số q, α](#tham-so)
4. [Bước 2: Cặp khóa](#cap-khoa)
5. [Bước 3: Khóa bí mật K](#khoa-chung)
6. [Lũy thừa modulo nhanh](#modpow)
7. [Ví dụ giáo trình](#vi-du)
8. [Vì sao an toàn](#an-toan)
9. [Người đứng giữa](#mitm)
10. [Trường hợp đặc biệt](#bat-loi)
11. [Nối với Caesar](#caesar)
12. [Mã giả](#ma-gia)
13. [Diffie-Hellman ngày nay](#thuc-te)
14. [Máy tính từng bước](#may-tinh)

# Trao đổi khóa Diffie-Hellman: thuật toán và logic

Tổng hợp từ bài giảng An toàn thông tin (slide 28, Thiết lập Diffie-Hellman). Mọi con số trong tài liệu được tính lại bằng bản cài đặt độc lập.

YA = αXA mod q YB = αXB mod q K = YBXA mod q = YAXB mod q

Dự án

Caesar_Cipher

Loại

Thỏa thuận khóa

Bài toán khó

Logarit rời rạc

Công bố

1976

Bí mật, chỉ một bên biết Công khai, kẻ nghe lén cũng thấy Khóa chung, cả hai bên tự tính

## 1Tổng quan

Diffie-Hellman (Whitfield Diffie và Martin Hellman, 1976) là giao thức thỏa thuận khóa. Hai bên chưa có bí mật chung nào, chỉ trao đổi qua kênh công khai, nhưng cuối cùng cả hai có cùng một khóa bí mật K.

DH không tự mã hóa dữ liệu. Nó giải quyết bài toán phân phối khóa: mã đối xứng (Caesar, DES, AES) cần hai bên có chung khóa từ trước, còn gửi khóa qua mạng thì kẻ nghe lén lấy được. Với DH, khóa K được tạo ra ở cả hai đầu mà không bao giờ đi qua mạng. Sau đó K mới được dùng làm khóa cho hệ mã đối xứng.

### Ký hiệu

| Ký hiệu | Ý nghĩa | Ai biết |
| --- | --- | --- |
| q | Số nguyên tố đủ lớn, mọi phép tính lấy mod q | Công khai |
| α | Nguyên căn của q (phần tử sinh) | Công khai |
| XA, XB | Khóa riêng, chọn ngẫu nhiên | Chỉ A, chỉ B |
| YA, YB | Khóa công khai, Y = αX mod q | Công khai |
| K | Khóa bí mật chung | A và B, tự tính |

Slide gọi YA là "khóa chung" ở dòng tính toán, nhưng dòng cuối slide gọi đúng là khóa công khai. Trong tài liệu này, "khóa chung" chỉ K.

## 2Sơ đồ giao thức

Chỉ q, α và hai khóa công khai đi qua kênh. Khóa riêng nằm yên ở mỗi bên và được dùng lại ở bước cuối (đường nét đứt).

## 3Bước 1: Tham số chung q và α

Hai bên thống nhất công khai một số nguyên tố q và một nguyên căn α của q. Mọi phép tính sau đó lấy dư cho q, nên kết quả luôn nằm trong khoảng 1 … q − 1.

**Nguyên căn** là số α mà dãy α1, α2, …, αq−1 mod q đi qua mọi số từ 1 đến q − 1, mỗi số đúng một lần (một hoán vị). Nhờ vậy khóa công khai Y có thể là bất kỳ giá trị nào, và kẻ tấn công phải xét đủ q − 1 khả năng. Thử với q = 23:

α =

Ô dưới là k, ô trên là αk mod 23. Ô màu cam là lần đầu dãy quay về 1; ô đỏ là giá trị lặp lại.

### Kiểm tra nguyên căn nhanh

Không cần liệt kê cả dãy. Phân tích q − 1 ra thừa số nguyên tố. α là nguyên căn khi và chỉ khi α(q−1)/p mod q ≠ 1 với mọi thừa số nguyên tố p của q − 1.

| q = 23, q − 1 = 2 × 11 | α22/2 = α11 mod 23 | α22/11 = α2 mod 23 | Kết luận |
| --- | --- | --- | --- |
| α = 5 | 22 | 2 | Nguyên căn |
| α = 4 | 1 | 16 | Không phải: chỉ sinh 11 giá trị |

Mẹo khi sinh tham số: chọn q = 2p + 1 với p cũng nguyên tố (safe prime, ví dụ 23 = 2 × 11 + 1). Khi đó q − 1 chỉ có hai thừa số 2 và p, nên chỉ cần 2 phép thử.

## 4Bước 2: Mỗi bên sinh cặp khóa

1. **A chọn ngẫu nhiên khóa riêng XA và giữ kín**Không gửi đi, không lưu ở đâu khác.
2. **A tính YA = αXA mod q và gửi cho B**Ai nghe lén cũng thấy YA, nhưng không suy ngược được XA (mục 8).
3. **B làm tương tự**Chọn XB, gửi YB = αXB mod q cho A. Hai bên làm song song, không cần chờ nhau.

q = 23, α = 5 XA = 4`YA = 54 mod 23 = 625 mod 23 = 4` XB = 3`YB = 53 mod 23 = 125 mod 23 = 10`

Slide chỉ yêu cầu XA \< q. Khi cài đặt nên chặn trong 2 ≤ X ≤ q − 2: X = 1 cho Y = α nên lộ X ngay; X = q − 1 (hoặc 0) cho Y = 1 với mọi α, theo định lý Fermat nhỏ.

## 5Bước 3: Tính khóa bí mật K

Mỗi bên ghép khóa riêng của mình với khóa công khai của bên kia:

```
KA = YBXA mod q = (αXB)XA mod q = αXA·XB mod q
KB = YAXB mod q = (αXA)XB mod q = αXA·XB mod q
```

Hai vế phải giống nhau vì phép nhân số mũ giao hoán (XA·XB = XB·XA). Bước "lấy mod rồi mới lũy thừa" là hợp lệ vì (a mod q)n mod q = an mod q.

A tính`104 mod 23 = 10000 mod 23 = 18` B tính`43 mod 23 = 64 mod 23 = 18`

Cả hai ra K = 18, trong khi kênh chỉ thấy 23, 5, 4 và 10.

## 6Lũy thừa modulo nhanh

397 đã có 47 chữ số; với q cỡ 2048 bit thì X cũng cỡ 2048 bit, không thể tính αX rồi mới lấy dư. Thuật toán bình phương và nhân xử lý từng bit của số mũ, lấy dư sau mỗi phép nhân nên số không bao giờ vượt q².

1. **Viết số mũ X dưới dạng nhị phân**Duyệt các bit từ trái sang phải, bắt đầu với r = 1.
2. **Mỗi bit: r = r² mod q**Bình phương tương ứng với dịch số mũ sang trái một bit.
3. **Bit bằng 1: r = r · α mod q**Cộng thêm 1 vào số mũ. Tổng số phép nhân không quá 2 × số bit của X.

Ví dụ 397 mod 353, với 97 = 11000012:

| Bit | Số mũ đã xử lý | r² mod 353 | × 3 mod 353 | r |
| --- | --- | --- | --- | --- |
| 1 | 1 | 1 | 3 | 3 |
| 1 | 3 | 9 | 27 | 27 |
| 0 | 6 | 23 | – | 23 |
| 0 | 12 | 176 | – | 176 |
| 0 | 24 | 265 | – | 265 |
| 0 | 48 | 331 | – | 331 |
| 1 | 97 | 131 | 40 | **40** |

7 bit, 9 phép nhân thay vì 96. Máy tính ở mục 14 in bảng này cho mọi phép tính.

## 7Ví dụ giáo trình

Ví dụ trong giáo trình Stallings, dùng cùng ký hiệu với slide: q = 353, α = 3, XA = 97, XB = 233.

| Bước | Bên A | Bên B |
| --- | --- | --- |
| Khóa riêng | XA = 97 | XB = 233 |
| Khóa công khai | YA = 397 mod 353 = 40 | YB = 3233 mod 353 = 248 |
| Nhận được | YB = 248 | YA = 40 |
| Khóa chung | K = 24897 mod 353 = 160 | K = 40233 mod 353 = 160 |

q = 353, α = 3, XA = 97, XB = 233 → `K = 160`

Kẻ nghe lén chỉ thấy `353, 3, 40, 248`.

## 8Vì sao an toàn: bài toán logarit rời rạc

Muốn có K, kẻ nghe lén cần XA hoặc XB, tức phải tìm X thỏa αX ≡ Y (mod q). Đây là bài toán logarit rời rạc.

- **Chiều thuận nhanh:** tính Y từ X chỉ tốn khoảng 2 × log2X phép nhân (mục 6).
- **Chiều nghịch chậm:** với q đủ lớn, chưa có thuật toán hiệu quả. Vét cạn phải thử tới q − 1 giá trị; các thuật toán tốt hơn (baby-step giant-step, index calculus) vẫn quá chậm khi q cỡ 2048 bit.

| Cỡ q | Số lần thử khi vét cạn | Thực tế |
| --- | --- | --- |
| 353 (9 bit) | tối đa 352 | Tức thì. Thử ở mục 14: tìm ra XA = 97 sau 97 lần |
| 32 bit | khoảng 4,3 tỷ | Vài giây đến vài phút trên máy tính thường |
| 2048 bit | khoảng 22048 | Không khả thi với mọi máy tính hiện có |

Chính xác hơn, an toàn dựa trên bài toán Diffie-Hellman: biết αXA và αXB, tìm αXA·XB. Hiện chưa biết cách giải nào nhanh hơn đáng kể so với giải logarit rời rạc.

## 9Điểm yếu: tấn công người đứng giữa

DH gốc không xác thực ai đang gửi Y. Kẻ C đứng giữa có thể chặn cả hai khóa công khai và thay bằng khóa của mình. Ví dụ với q = 23, α = 5, XA = 4, XB = 3, C chọn XC = 6 nên YC = 56 mod 23 = 8.

| Ai | Nhận được | Tính ra | Thực chất |
| --- | --- | --- | --- |
| A | 8 (tưởng là YB) | 84 mod 23 = 2 | Khóa chung với C, C tính 46 mod 23 = 2 |
| B | 8 (tưởng là YA) | 83 mod 23 = 6 | Khóa chung với C, C tính 106 mod 23 = 6 |

C giải mã tin của A bằng khóa 2, đọc hoặc sửa, rồi mã lại bằng khóa 6 gửi cho B. A và B không phát hiện được gì. Cách khắc phục là xác thực khóa công khai: ký số Y bằng khóa dài hạn hoặc chứng chỉ, như trong giao thức Station-to-Station và TLS.

## 10Trường hợp đặc biệt khi cài đặt

Danh sách mã lỗi đầy đủ nằm trong [Scope Backend Diffie-Hellman](https://claude.ai/code/artifact/d7142eee-cfb7-437e-aad4-cfa7210ae2d9).

| Trường hợp | Hậu quả | Xử lý |
| --- | --- | --- |
| q không nguyên tố (q = 21) | Không đảm bảo có nguyên căn, cấu trúc nhóm yếu | Báo lỗi NOT_PRIME |
| α không phải nguyên căn (α = 4, q = 23) | Y chỉ rơi vào 11 trong 22 giá trị | Báo lỗi, gợi ý α = 5 |
| X = 1 | Y = α, lộ X ngay | Chặn, yêu cầu 2 ≤ X ≤ q − 2 |
| X = 0 hoặc q − 1 | Y = 1 với mọi α | Chặn như trên |
| Y nhận được là 1 hoặc q − 1 | K chỉ còn 1 hoặc q − 1, đoán được ngay | Báo lỗi PUBLIC_KEY_INVALID |
| K mod 26 = 0 (q = 353, XA = 97, XB = 25 cho K = 52) | Caesar dịch 0, bản mã trùng bản rõ | Cảnh báo SHIFT_ZERO |
| Số vượt 253 trong JSON | Bị làm tròn, sai kết quả | Gửi và nhận số dạng chuỗi |

## 11Nối với Caesar của tuần 1

Sau khi trao đổi, cả hai bên có cùng K. Lấy độ dịch Caesar = K mod 26 rồi gọi lại bộ mã Caesar đã làm ở tuần 1.

K`160` Độ dịch`160 mod 26 = 4` A mã hóa`"Hello World" → "Lipps Asvph"` B giải mã`B tự có K = 160, dịch ngược 4 → "Hello World"`

Caesar chỉ có 26 độ dịch nên vét cạn tức thì. Ghép DH với Caesar để minh họa luồng "trao đổi khóa rồi mã đối xứng". Trong thực tế, K được băm qua hàm dẫn xuất khóa để ra khóa AES.

## 12Mã giả

```
// Mọi số dùng số nguyên lớn (Java: BigInteger, JS: BigInt)
modPow(base, exp, q):
    r = 1; base = base mod q
    for bit in binary(exp) from left to right:
        r = r * r mod q
        if bit == 1: r = r * base mod q
    return r

isPrimitiveRoot(alpha, q):
    for p in primeFactors(q - 1):
        if modPow(alpha, (q - 1) / p, q) == 1: return false
    return true

generateKeyPair(q, alpha):
    X = random in [2, q - 2]                 // giữ kín
    Y = modPow(alpha, X, q)                  // gửi đi
    return (X, Y)

sharedSecret(q, myX, otherY):
    require 2 <= otherY <= q - 2
    return modPow(otherY, myX, q)            // K

caesarShift(K) = K mod 26                    // cảnh báo nếu bằng 0
```

## 13Diffie-Hellman ngày nay

- **Tham số thật:** q từ 2048 bit trở lên, thường dùng các nhóm đã chuẩn hóa sẵn với q là safe prime (ví dụ ffdhe2048 trong [RFC 7919](https://www.rfc-editor.org/rfc/rfc7919)).
- **ECDH:** cùng ý tưởng nhưng trên đường cong elliptic, khóa ngắn hơn nhiều với cùng mức an toàn. X25519 ([RFC 7748](https://www.rfc-editor.org/rfc/rfc7748)) dùng khóa 32 byte.
- **Khóa tạm thời mỗi phiên:** TLS 1.3 ([RFC 8446](https://www.rfc-editor.org/rfc/rfc8446)) trao đổi khóa bằng (EC)DHE, tạo X mới cho mỗi phiên. Nhờ vậy, lộ khóa dài hạn về sau cũng không giải mã được các phiên cũ (forward secrecy).

## 14Máy tính Diffie-Hellman từng bước

Nhập tham số hoặc chọn ví dụ. Mọi phép tính chạy ngay trong trình duyệt bằng số nguyên lớn.

#### Tham số và khóa riêng

q (số nguyên tố)

α (nguyên căn)

XA (riêng của A)

XB (riêng của B)

#### Kết quả

YA`–` YB`–` K của A`–` K của B`–` Độ dịch Caesar`–`

#### Bảng bình phương và nhân

Phép tính:

| Bit | r² mod q | × cơ số mod q | r |
| --- | --- | --- | --- |

#### Kẻ nghe lén thử vét cạn XA

Chỉ dùng thông tin công khai q, α, YA, YB: thử lần lượt k = 1, 2, … cho tới khi αk mod q = YA.

#### Dùng K cho Caesar

Văn bản A gửi A mã hóa bằng độ dịch từ K của A

B giải mã bằng độ dịch từ K của B

Dự án Caesar_Cipher · Tài liệu tham chiếu cho Scope Backend Diffie-Hellman · Số liệu ví dụ đã được tính và đối chiếu bằng bản cài đặt độc lập.