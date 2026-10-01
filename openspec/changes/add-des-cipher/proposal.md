## Why

Backend hiện hỗ trợ Caesar, Vigenère, Playfair, Affine, Columnar và Hill nhưng chưa có hệ mã khối hiện đại nào để FE minh họa cấu trúc Feistel, hộp S và hoán vị. Change này thêm DES theo `Scope Backend_ Hệ mã hóa DES.html` và `Hệ mã hóa DES_ thuật toán và logic.html`, tự cài đặt lõi thuật toán và giữ nguyên contract của sáu cipher đã có.

## What Changes

- Thêm lõi DES tự cài đặt chỉ bằng thư viện chuẩn: bảng PC-1, PC-2, LS, IP, IP⁻¹, E, P, S1–S8; sinh 16 khóa con; hàm f; 16 vòng Feistel; giải mã bằng khóa con đảo thứ tự. Không dùng thư viện mật mã trong code ứng dụng.
- Mở rộng cho dữ liệu nhiều khối: chế độ ECB (mặc định) và CBC với IV 16 hex; văn bản UTF-8 luôn đệm PKCS#7; chế độ hex một hoặc nhiều khối không đệm để làm bài tập slide.
- Thêm đúng bốn endpoint `POST /api/des/encrypt`, `/api/des/decrypt`, `/api/des/file`, `/api/des/trace`. Response thành công là `{success, result, warnings}`; `/trace` có thêm `trace` chứa toàn bộ giá trị trung gian của một khối.
- Lỗi DES dùng envelope hai trường `{success:false, message}` như năm cipher cổ điển, HTTP 422 cho validation và 413 khi vượt 5 MiB; mã DES-E01…E13 chỉ dùng để đặt tên test. Cảnh báo W01 (khóa yếu), W02 (khóa nửa yếu), W03 (ECB có khối mã lặp) là object `{code, message, details}` như Hill.
- `/api/des/file` dùng lại toàn bộ pipeline file hiện hành (415/413/422, BOM, `Content-Disposition`, tên `.encrypted.txt`/`.decrypted.txt`) và được đưa vào guard 64 MiB và multipart completion guard cho route file.
- Ghi metadata của ba route biến đổi DES vào lịch sử, cho phép lọc `cipher=des`, thêm migration `0003` nới CHECK `cipher`. `/api/des/trace` không ghi lịch sử.
- Thêm `cryptography` vào nhóm dependency dev để đối chiếu kết quả trong test; cập nhật README, hướng dẫn FE và TypeScript helper.

## Capabilities

### New Capabilities

- `des-core`: bảng hằng, sinh khóa con, hàm f, mã hóa/giải mã một khối, ECB/CBC, PKCS#7, UTF-8, khóa yếu/nửa yếu và giá trị trung gian cho trace.
- `des-text-cipher-api`: request/response JSON của `/api/des/encrypt` và `/api/des/decrypt`, giới hạn 5 MiB và warnings.
- `des-file-cipher-api`: endpoint multipart `/api/des/file` kế thừa contract file hiện hành.
- `des-trace-api`: endpoint `/api/des/trace` trả mọi giá trị trung gian của đúng một khối.
- `des-error-handling`: bảng lỗi/message/status, thứ tự ưu tiên, request guard và ranh giới với envelope của các cipher khác.

### Modified Capabilities

- `operation-history`: nhận metadata của `/api/des/encrypt`, `/decrypt`, `/file` và nới CHECK `cipher` bằng migration mới; không ghi `/trace`, khóa, IV hay nội dung.
- `history-api`: bộ lọc `cipher` chấp nhận `des`.

## Impact

- Code: thêm `app/core/des.py`, schema/router DES, message DES, đăng ký router ở `app/main.py`, thêm `/api/des/file` vào phân loại route file của guard, cập nhật `CIPHERS` và route lịch sử, migration `0003`.
- API: số cipher tăng từ 6 lên 7; thêm 4 POST route DES, trong đó 3 route biến đổi được ghi lịch sử. Route và response của sáu cipher cũ không đổi.
- Dependency: chỉ thêm `cryptography` vào nhóm dev; không thêm dependency runtime.
- Tài liệu: README, `repo_docs/frontend-integration.md`, `repo_docs/examples/cipher-api.ts`.

## Ngoài phạm vi

- 3DES, AES; các chế độ CFB, OFB, CTR; sinh khóa từ mật khẩu (KDF); xác thực bản mã (MAC).
- Demo vét cạn khóa, thám mã vi sai hoặc tuyến tính.
- Kiểm tra hoặc tự sửa bit chẵn lẻ của khóa.
- Bản cài tối ưu thứ hai (bitslice, numpy) hoặc thư viện mật mã trong runtime.
- UI/FE implementation; không đổi thuật toán, route hay response của sáu cipher hiện có; không thêm abstract cipher interface.

## Nguồn và quyết định ưu tiên

1. Quyết định chủ sở hữu Q1–Q22 ngày 2026-10-01 (liệt kê bên dưới) giải quyết các chỗ scope DES chưa rõ hoặc khác quy ước repo.
2. `Scope Backend_ Hệ mã hóa DES.html` là nguồn cho tham số, đặc tả thuật toán, bảng lỗi/cảnh báo, API contract, test vector T01–T20 và tiêu chí nghiệm thu, trừ các điểm bị quyết định ở mục 1 thay thế.
3. `Hệ mã hóa DES_ thuật toán và logic.html` là nguồn cho bảng hoán vị, hộp S, quy ước bit và giá trị trung gian của hai ví dụ slide.
4. Các main spec OpenSpec đã nghiệm thu là nguồn cho envelope lỗi chung, pipeline file, guard 64 MiB, lịch sử metadata và cách tổ chức backend.

### Quyết định chủ sở hữu ngày 2026-10-01

| # | Quyết định |
|---|---|
| Q1 | Một change gồm toàn bộ BE-D01…D10, có cả CBC (D10) và trace (D09). |
| Q2 | Tên change `add-des-cipher`. |
| Q3 | Message DES-E05/E06 dùng chủ ngữ trung tính "Dữ liệu hex…" cho bản rõ hex, bản mã và khối trace. |
| Q4 | W01/W02 trả ở mọi thao tác dùng khóa: encrypt, decrypt, file hai chiều và trace. |
| Q5 | W03 chỉ khi mã hóa ECB (JSON và file) và bản mã đầu ra có ít nhất hai khối giống nhau. |
| Q6 | So sánh khóa yếu/nửa yếu sau khi xóa bit chẵn lẻ (mask `FEFEFEFEFEFEFEFE`). |
| Q7 | Lỗi theo năm cipher cổ điển: HTTP 422 cho validation, 413 cho vượt 5 MiB, body đúng `{success:false, message}`, không có `code`. |
| Q8 | Response thành công luôn có mảng `warnings`; mỗi phần tử là `{code, message, details}` như Hill, thứ tự W01 → W02 → W03; W03 có `details.repeatedBlocks`. |
| Q9 | Body JSON strict: field lạ, trùng hoặc sai kiểu trả 422 `Dữ liệu gửi lên không hợp lệ.`; field camelCase; enum khớp chính xác, sai trả DES-E10. |
| Q10 | Giới hạn 5 MiB cho JSON đo bằng byte UTF-8 của chuỗi gốc như Hill; đúng 5.242.880 byte được nhận; vượt trả 413 `Dữ liệu vượt quá 5 MiB.`. |
| Q11 | `/api/des/file` dùng lại pipeline file hiện hành: thứ tự kiểm tra, message 415/413/422, BOM, `Content-Disposition`, tên `.encrypted.txt`/`.decrypted.txt`; multipart field set strict `file, key, action, mode, iv, response_mode`; `warnings` chỉ có ở `response_mode=content`. |
| Q12 | Ghi lịch sử encrypt/decrypt/file, thêm migration `0003`; `/trace` không ghi lịch sử. |
| Q13 | Thứ tự lỗi: giới hạn dung lượng → body → E10 → E02/E03/E04 → E09 → E01/E05/E06 → E07/E08; `/trace` dùng E13 cho khối. |
| Q14 | Thêm `cryptography` vào nhóm dev, chỉ dùng trong `tests/` để đối chiếu; lõi chỉ dùng thư viện chuẩn. |
| Q15 | Archive `add-hill-cipher` trước khi viết change này (đã thực hiện, `2026-10-01-add-hill-cipher`). |
| Q16 | Ghi đầy đủ nội dung quyết định và bảng khác biệt nguồn trong proposal. |
| Q17 | Cập nhật README và hướng dẫn FE trong nhóm task Docs riêng. |
| Q18 | `/trace` theo mẫu scope §7, thêm `warnings` và khóa đã chuẩn hóa; giải mã có `subkey` 16 → 1; `block` cho phép khoảng trắng; body strict. |
| Q19 | `/decrypt` nhận `text, key, outputFormat, mode, iv`; `iv` bị bỏ qua khi mode ECB ở mọi endpoint. |
| Q20 | Một bản cài duy nhất dùng bảng tra (SP-box) và thư viện chuẩn; tiêu chí "5 MiB dưới 2 giây" của scope được ghi đè bằng số đo thực tế (khoảng 6 giây mỗi chiều). |
| Q21 | Hiệu năng đo thủ công và ghi Evidence trong `tasks.md`; không có performance test tự động. |
| Q22 | Giữ giới hạn 5 MiB cho cả chiều giải mã (JSON và file) dù bản mã hex dài gấp đôi bản rõ; văn bản lớn nhất còn giải mã lại được là 2.621.439 byte UTF-8. Tài liệu FE nêu rõ giới hạn này. |

### Khác biệt giữa scope DES và quy ước repo

| Scope DES nói | Change này làm | Căn cứ |
|---|---|---|
| Lỗi validation HTTP 400 | HTTP 422; E12 vẫn 413 | Q7 |
| E05/E06 "Bản mã chỉ được…" | "Dữ liệu hex chỉ được…" | Q3 |
| E11 một message chung cho file | Message file hiện hành: 415 `.txt`/UTF-8, 422 file rỗng, 413 `File vượt quá dung lượng tối đa 5 MB.` | Q11 |
| File kết quả `<tên>.des.txt` | `<tên>.encrypted.txt` / `<tên>.decrypted.txt` | Q11 |
| Mảng `warnings` không nêu hình dạng | Object `{code, message, details}` | Q8 |
| File 5 MiB xử lý dưới 2 giây | Ghi đè bằng số đo thực tế, không có performance gate | Q20, Q21 |
| E12 đứng đầu luồng xử lý | Giới hạn chỉ đo được sau khi parse JSON; body hỏng về cú pháp vẫn trả 422 trước | Q13, tiền lệ Hill |
