# Cipher Workbench tóm tắt thay đổi và phạm vi testcase QA

Phạm vi QA gồm 9 thuật toán mật mã, chữ ký RSA và lịch sử riêng theo browser profile. Bảng dưới đây phân biệt phần sửa lỗi với chức năng bổ sung, kèm hành vi mong đợi để viết testcase.

## Điều kiện trước khi test

> **⚠️ Lưu ý trước khi test**
>
> **Build QA chưa được xác nhận có commit `9d22937`.** Nếu build chưa có thay đổi này, cần cập nhật build trước khi kiểm thử lịch sử của 5 API Diffie–Hellman standalone. Có code trong repo không đồng nghĩa môi trường QA đã triển khai.

- [ ] Ghi nhận phiên bản hoặc commit của build QA.

- [ ] Xác nhận build có thay đổi `9d22937` về lịch sử Diffie–Hellman.

- [ ] Xác nhận SQLite đã áp dụng migration `sqlite_0004` cho phạm vi history liên quan.

- [ ] Xác nhận DB writable và retention worker hoạt động khi test xóa lịch sử hết hạn.

Việc deploy và migration cần được người phụ trách môi trường xác nhận, không được coi là đã hoàn tất.

## Tóm tắt 9 thuật toán

| Feature | Đã sửa hoặc bổ sung | Trọng tâm testcase |
| --- | --- | --- |
| Caesar | **Sửa** nhận khóa DH dạng chuỗi thập phân canonical. Khóa được modulo 26; giữ hoa thường và Unicode. | So sánh `160` và `"160"`; khóa âm và lớn; từ chối boolean, float và `"0160"`. |
| Vigenère | **Bổ sung** khóa lặp; chỉ chữ ASCII làm tiến vị trí khóa. | Vector khóa `LEMON`, hoa thường, dấu câu và tiếng Việt không lệch khóa; khóa rỗng hoặc chứa số bị từ chối. |
| Playfair | **Thay đổi** decrypt giữ kết quả thô và trả riêng `padding.filtered`; hỗ trợ lọc padding khi tải file. | J thành I, chữ lặp, chuỗi lẻ, filler X và Q; bật và tắt lọc padding. Bộ lọc có thể nhầm chữ thật; không kỳ vọng phục hồi nguyên văn. |
| Affine | **Bổ sung** khóa a và b modulo 26; a phải có nghịch đảo. | `(5,8)` cho `HELLO → RCLLA`; khóa âm và lớn tương đương; `a=2` bị từ chối; Unicode giữ nguyên. |
| Columnar | **Bổ sung** khóa hoán vị và keyword, không padding hoặc mất ký tự. | `ABCDE → BDAEC` với `3 1 4 2`; keyword `BALLOON`; hàng thiếu, emoji và xuống dòng; rank trùng hoặc thiếu bị từ chối. |
| Hill | **Nâng** giới hạn text lên 5 MiB; **bổ sung** thông tin padding decrypt. | `HELP → DPLE` theo vector hàng; ma trận không khả nghịch; cấp 2 đến 4; bỏ dấu, padChar và giới hạn UTF-8. FE đọc file rồi gửi JSON, không có API upload Hill. |
| DES | **Bổ sung** ECB và CBC, text và hex, PKCS#7 và trace. | Vector chuẩn; CBC thiếu hoặc sai định dạng IV; text đủ khối vẫn thêm padding; hex không padding; khóa yếu chỉ cảnh báo. IV sai không luôn bị phát hiện. |
| RSA | **Sửa** validation UTF-8, thứ tự lỗi multipart và lỗi thiếu độ dài gốc `INVALID_LENGTH_METADATA`. | Number, char và block; Unicode, BOM và NUL; metadata thiếu hoặc sai; trường thừa hoặc trùng. Textbook RSA không bảo đảm phát hiện khóa sai. |
| Diffie–Hellman | **Làm rõ** validation và cảnh báo; **bổ sung** history cho 5 API standalone trước đó chưa được lưu. | Shared key hai bên bằng nhau; trace khớp; q, alpha và key sai; Caesar dùng `K mod 26`. History chỉ lưu metadata; lỗi DB không thay đổi kết quả DH. |

## Chữ ký RSA

Phạm vi gồm ký và xác minh raw RSA cùng RSA-PSS/SHA-256. Chữ ký phải gắn với đúng bytes nội dung.

- [ ] Ký rồi xác minh nội dung gốc với đúng public key, cho cả raw integer và RSA-PSS/SHA-256.

- [ ] Nội dung, chữ ký hoặc public key không khớp nhưng request hợp lệ trả **HTTP 200 và `valid=false`**.

- [ ] Request sai định dạng, khóa không hợp lệ hoặc số raw ngoài miền trả lỗi validation; không gộp thành `valid=false`.

- [ ] Với chữ ký chuẩn, kiểm tra BOM, LF và CRLF, khoảng trắng cuối và Unicode normalization. Ký UTF-8 của text hoặc bytes gốc của file, không tự chuẩn hóa nội dung.

- [ ] Không lưu private PEM, private exponent `d`, passphrase hoặc trace chứa bí mật vào lịch sử.

## Lịch sử riêng tư

Lịch sử thuộc **browser profile**, không phải tài khoản đăng nhập. Các tab trong cùng profile dùng chung lịch sử; profile khác phải được cô lập.

- [ ] Cùng browser profile ở hai tab nhìn thấy cùng lịch sử.

- [ ] Hai browser profile không xem, tải hoặc xóa lịch sử của nhau.

- [ ] Cipher thông thường và DH chỉ lưu metadata; không lưu secret traces.

- [ ] Lịch sử ký và xác minh lưu đúng bytes nội dung, signature và public key hoặc kết quả; không lưu private key hay passphrase.

- [ ] TTL là **5 giờ từ lúc tạo**, không phải 30 ngày; đọc hoặc tải không gia hạn TTL. Bản ghi hết hạn phải bị chặn truy cập.

- [ ] Quota **50 MiB mỗi profile và 500 MiB toàn hệ thống** có thể đẩy bản ghi cũ ra trước 5 giờ; không mặc định coi trường hợp đó là lỗi TTL.

- [ ] Khi test xóa vật lý theo deadline, xác nhận worker hoạt động và DB writable. Không mặc định việc xóa bao gồm backups.

## Testcase dùng chung

- [ ] Đầu vào rỗng, khóa sai, HTTP status và thông báo lỗi đúng contract từng thuật toán.

- [ ] Với route file có hỗ trợ: `.txt`, UTF-8, BOM, file rỗng, preview, attachment và tên file.

- [ ] Giới hạn riêng: legacy và DES file 5 MiB; Hill text 5 MiB; RSA encrypt file 1.000.000 byte và 10.000 code point.

- [ ] DH file trả JSON; không kỳ vọng cùng hành vi download như các route attachment khác.

## Căn cứ đối chiếu

Đối chiếu repo tại commit `9d22937` ngày 13 tháng 10 năm 2026. Đây là căn cứ cho hành vi backend, không phải xác nhận build QA, frontend hoặc test runtime đã pass.

Nguồn trong repo: `README.md`, `repo_docs/frontend-integration.md`, `docs/rsa-signatures-private-history.md`.

Commit liên quan: Caesar `8d20f20`; Playfair và padding `15e5dae`; Hill `4505ef7`; RSA validation `7c2d472` và `03c0c85`; DH validation `57d5766` và history `9d22937`; chữ ký RSA `db72e47`; retention deadline `502f7b2`.

