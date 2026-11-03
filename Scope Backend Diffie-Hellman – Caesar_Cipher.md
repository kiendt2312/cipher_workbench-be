# Scope Backend Diffie-Hellman – Caesar\_Cipher

Oct 8, 2026 · @Hieu Anh

Đợt này chỉ làm Backend cho Diffie-Hellman: kiểm tra và sinh tham số chung, sinh cặp khóa, tính khóa bí mật chung, rồi dùng khóa đó làm độ dịch cho Caesar của tuần 1. Không làm giao diện.

## Phạm vi

Chỉ làm module tính toán và API. Mọi kết quả trả về dạng JSON, kiểm tra bằng unit test hoặc Postman.

- Kiểm tra q nguyên tố và α là nguyên căn của q, hoặc sinh q, α ngẫu nhiên theo số bit.
- Sinh cặp khóa cho một bên: khóa riêng X nhập tay hoặc sinh ngẫu nhiên, khóa công khai Y = α^X mod q.
- Tính khóa bí mật K từ khóa riêng của mình và khóa công khai của bên kia.
- Mô phỏng trọn một phiên A và B trong một request, trả K của hai bên để đối chiếu.
- Dùng K làm khóa Caesar: độ dịch = K mod 26, gọi lại `CaesarService` của tuần 1.
- Trả kèm các bước tính (bảng bình phương và nhân, các phép thử nguyên căn) để giao diện dùng lại.
- Bắt lỗi với mã lỗi và câu thông báo tiếng Việt.

Ngoài phạm vi: toàn bộ giao diện, chống tấn công người đứng giữa (chữ ký số, chứng chỉ), ECDH, băm K qua hàm dẫn xuất khóa, lưu khóa vào database, tham số thật cỡ 2048 bit. Đây là Diffie-Hellman bản giáo trình để học, không dùng cho dữ liệu thật.

Vì là công cụ học, API trả cả khóa riêng X để giao diện hiển thị. Trong hệ thống thật, X không bao giờ rời máy của bên sở hữu.

## Luồng xử lý

&#91;embedded content: luồng gọi API · 2 bên, 6 lời gọi\]

Khóa riêng X không bao giờ đi qua kênh công khai. Mỗi bên ghép X của mình với Y của bên kia nên đều ra K = α^(X\_A·X\_B) mod q. /exchange gộp toàn bộ luồng này vào một request để demo.

## Backend

Làm theo thứ tự BE-01 → BE-08, bước sau dùng kết quả bước trước. Nếu module số học của RSA đã xong thì BE-01 chỉ cần bổ sung phần phân tích thừa số và kiểm tra nguyên căn.

| ID | Task | Chi tiết | Xong khi | Phụ thuộc |
| --- | --- | --- | --- | --- |
| BE-01 | Module số học | modPow (trả các dòng theo bit), isPrime (chia thử với số ≤ 10¹², Miller–Rabin với số lớn hơn), phân tích thừa số q − 1, isPrimitiveRoot: α là nguyên căn khi α^((q−1)/f) mod q ≠ 1 với mọi thừa số nguyên tố f của q − 1. Dùng số nguyên lớn | Qua TC-01, TC-04 | – |
| BE-02 | Kiểm tra tham số q, α | Kiểm tra 5 ≤ q ≤ 10¹², q nguyên tố, 1 < α < q, α là nguyên căn. Trả thừa số của q − 1 và từng phép thử. Thiếu α hoặc α sai thì gợi ý nguyên căn nhỏ nhất | Qua TC-01, TC-05 → TC-07, TC-13 | BE-01 |
| BE-03 | Sinh tham số ngẫu nhiên | Nhận số bit (16, 32, 64, 128). Sinh q = 2p + 1 với p cũng nguyên tố: q − 1 chỉ có hai thừa số 2 và p, nên kiểm tra nguyên căn chỉ cần 2 phép thử | q đúng số bit, qua TC-08 | BE-01 |
| BE-04 | Sinh cặp khóa | Nhận q, α, X tùy chọn. Không có X thì sinh ngẫu nhiên trong 2 ≤ X ≤ q − 2. Trả X, Y và bảng modPow | Qua TC-02, TC-03, TC-09 | BE-02 |
| BE-05 | Tính khóa bí mật | Nhận q, X của mình, Y của bên kia. Chặn Y ngoài khoảng 2 … q − 2. Trả K và bảng modPow | Qua TC-02, TC-03, TC-10 | BE-01 |
| BE-06 | Mô phỏng phiên và nối Caesar | /exchange chạy đủ A và B, trả match = (K\_A = K\_B). /caesar lấy K, độ dịch = K mod 26, gọi `CaesarService` tuần 1. Độ dịch bằng 0 thì trả cảnh báo | Qua TC-11, TC-12 | BE-04, BE-05, Caesar tuần 1 |
| BE-07 | Mã lỗi và validation | Mọi lỗi trả HTTP 400 với mã lỗi theo bảng Bắt lỗi. Văn bản và file dùng lại giới hạn của Caesar tuần 1 | Mỗi dòng bảng Bắt lỗi có 1 test | BE-02 → BE-06 |
| BE-08 | Unit test | Viết test cho toàn bộ bảng test case | Tất cả TC-01 → TC-13 qua | BE-01 → BE-07 |

## API

Mọi số gửi và nhận dưới dạng chuỗi, vì số lớn trong JSON sẽ bị làm tròn khi vượt 2⁵³.

| Endpoint | Request | Response |
| --- | --- | --- |
| POST /api/dh/params | `{q, alpha}` (alpha có thể bỏ trống) | `{q, alpha, factors[], primitiveRootChecks[], suggestedAlpha}` |
| POST /api/dh/params/random | `{bits}` | giống /params, thêm `{p}` |
| POST /api/dh/keypair | `{q, alpha, privateKey?}` | `{privateKey, publicKey, steps[]}` |
| POST /api/dh/shared-secret | `{q, privateKey, otherPublicKey}` | `{sharedKey, steps[]}` |
| POST /api/dh/exchange | `{q, alpha, privateKeyA?, privateKeyB?}` | `{publicKeyA, publicKeyB, sharedKeyA, sharedKeyB, match, steps{}}` |
| POST /api/dh/caesar | `{q, privateKey, otherPublicKey, action: "encrypt" \| "decrypt", data}` | `{sharedKey, shift, result, warning?}` |

/caesar không cần α vì K = Y\_bên\_kia^X mod q. Văn bản cho /caesar có thể gửi bằng trường `data` hoặc upload file .txt qua multipart/form-data (trường `file`), giống Caesar tuần 1.

Lỗi trả HTTP 400 với `{code, message, field}`. Cảnh báo không chặn request, nó nằm trong trường `warning` của response thành công.

## Bắt lỗi

Khóa riêng được chặn trong khoảng 2 … q − 2 thay vì chỉ X < q như slide: X = 1 làm Y = α (lộ ngay X), X = q − 1 làm Y = 1.

| Mã lỗi | Trường hợp | Thông báo |
| --- | --- | --- |
| NOT\_INTEGER | q, α, X hoặc Y không phải số nguyên dương | "Giá trị phải là số nguyên dương." |
| Q\_OUT\_OF\_RANGE | q < 5, hoặc q > 10¹² khi nhập tay | "q phải từ 5 đến 10¹², hoặc dùng sinh tham số ngẫu nhiên." |
| NOT\_PRIME | q không phải số nguyên tố | "q = 21 không phải số nguyên tố." |
| ALPHA\_OUT\_OF\_RANGE | α ≤ 1 hoặc α ≥ q | "α phải thỏa 1 < α < q = 23." |
| NOT\_PRIMITIVE\_ROOT | α không phải nguyên căn của q | "α = 4 không phải nguyên căn của 23. Gợi ý α = 5." |
| BITS\_INVALID | Số bit không thuộc 16, 32, 64, 128 | "Chỉ hỗ trợ 16, 32, 64 hoặc 128 bit." |
| PRIVATE\_KEY\_OUT\_OF\_RANGE | X ≤ 1 hoặc X ≥ q − 1 | "Khóa riêng phải thỏa 2 ≤ X ≤ q − 2 = 21." |
| PUBLIC\_KEY\_INVALID | Y của bên kia ngoài 2 … q − 2. Y = 1 hoặc q − 1 khiến K chỉ còn 1 hoặc q − 1, đoán được ngay | "Khóa công khai của bên kia không hợp lệ." |
| EMPTY\_INPUT | Trường data hoặc file rỗng (/caesar) | "Dữ liệu đầu vào đang rỗng." |
| FILE\_INVALID | File không phải .txt hoặc > 1 MB | "Chỉ nhận file .txt tối đa 1 MB." |
| SHIFT\_ZERO (cảnh báo) | K mod 26 = 0, bản mã trùng bản rõ | "K = 52 cho độ dịch 0, văn bản không đổi. Hãy chọn khóa riêng khác." |

## Test case

Các giá trị dưới đây đã được tính và chạy kiểm tra. TC-03 là ví dụ trong giáo trình Stallings, cùng ký hiệu q, α, X, Y với slide.

| ID | Đầu vào | Kết quả mong đợi |
| --- | --- | --- |
| TC-01 | q = 23, α = 5 | Hợp lệ; q − 1 = 2 × 11; 5² mod 23 = 2 và 5¹¹ mod 23 = 22, cả hai ≠ 1 |
| TC-02 | q = 23, α = 5, X\_A = 4, X\_B = 3 | Y\_A = 4, Y\_B = 10, K\_A = K\_B = 18 |
| TC-03 | q = 353, α = 3, X\_A = 97, X\_B = 233 | Y\_A = 40, Y\_B = 248, K\_A = K\_B = 160 |
| TC-04 | modPow 3^97 mod 353 | 97 = 1100001₂; các dòng theo bit: 3, 27, 23, 176, 265, 331, 40 |
| TC-05 | q = 21, α = 2 | Lỗi NOT\_PRIME |
| TC-06 | q = 23, α = 4 | Lỗi NOT\_PRIMITIVE\_ROOT (4¹¹ mod 23 = 1), gợi ý α = 5 |
| TC-07 | q = 23, α = 25 | Lỗi ALPHA\_OUT\_OF\_RANGE |
| TC-08 | Sinh ngẫu nhiên 32 bit | q đúng 32 bit, q và p = (q − 1) / 2 đều nguyên tố, α qua 2 phép thử; /exchange trả match = true |
| TC-09 | q = 23, α = 5, X = 22 | Lỗi PRIVATE\_KEY\_OUT\_OF\_RANGE |
| TC-10 | q = 23, X = 4, Y bên kia = 22 | Lỗi PUBLIC\_KEY\_INVALID |
| TC-11 | /caesar: q = 353, X\_A = 97, Y\_B = 248, encrypt "Hello World" | K = 160, độ dịch 4, kết quả "Lipps Asvph"; B giải mã với X\_B = 233, Y\_A = 40 ra "Hello World" |
| TC-12 | q = 353, α = 3, X\_A = 97, X\_B = 25 | Y\_B = 89, K = 52, độ dịch 0, cảnh báo SHIFT\_ZERO |
| TC-13 | q = 1000000000039 (13 chữ số), nhập tay | Lỗi Q\_OUT\_OF\_RANGE |

## Câu hỏi mở

- [ ] Diffie-Hellman là tuần mấy và deadline khi nào?
- [ ] Backend vẫn là Spring Boot như tuần 1? Nếu đúng, `BigInteger` có sẵn `modPow` và `isProbablePrime`, nhưng vẫn cần tự viết modPow để trả bảng từng bước.
- [ ] Có cần thêm endpoint mô phỏng tấn công người đứng giữa để demo điểm yếu của DH không?
- [ ] K mod 26 chỉ cho 26 độ dịch nên chỉ để minh họa. Tuần sau có dùng K cho thuật toán mạnh hơn (Vigenère, AES) không?
