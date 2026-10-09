# Proposal

## Why

Backend cần cung cấp Diffie–Hellman như một feature độc lập ngang cấp Caesar: kiểm tra/sinh tham số, tạo khóa, tính bí mật chung, so khớp hai phía và trả trace số học thực. Change này đặc tả sáu API thống nhất với hai tài liệu DH ngày 2026-10-08 và các contract FastAPI/RSA/Caesar/history hiện hành; endpoint DH–Caesar là integration dùng shared key của feature DH, không biến DH thành một mode của Caesar.

## What Changes

- Thêm lõi số học DH giáo dục cho số nguyên tối đa 128 bit: kiểm tra số nguyên tố, phân tích `q - 1`, kiểm tra nguyên căn, sinh safe prime, sinh khóa, tính bí mật chung và trace square-and-multiply trái sang phải.
- Thêm đúng sáu `POST` endpoint dưới `/api/dh`: `/params`, `/params/random`, `/keypair`, `/shared-secret`, `/exchange`, `/caesar`.
- Trả đại lượng mật mã và `shift` bằng decimal string; giữ control/index/bit là JSON integer và boolean là JSON boolean.
- `/params` manual giữ trần `q <= 10^12`; tham số sinh 16/32/64/128 bit dùng được end-to-end ở các endpoint sau, được kiểm tra độc lập, không provenance token hay server state.
- Khi thiếu `alpha`, `/params` chỉ trả gợi ý và không tự chọn; khi `alpha` được gửi nhưng sai, trả lỗi kèm gợi ý, không silent substitution.
- `/exchange` trả cả `privateKeyA` và `privateKeyB` để minh họa và đối chiếu phép tính thật, kèm cảnh báo không gửi/lưu khóa riêng ngoài bên sở hữu và phải xác thực khóa công khai để chống MITM trong hệ thống thực tế.
- `/caesar` là integration riêng nhận JSON text hoặc multipart `.txt`, luôn trả JSON; nó tính DH shared key thật rồi dùng đúng Caesar hiện hành với `K mod 26`, giới hạn file chính xác 5 MiB, UTF-8/BOM, không attachment hay `response_mode`. Các route Caesar standalone giữ nguyên route/response/integer behavior và nhận thêm decimal string canonical từ `sharedKey` DH.
- Dùng error envelope `{success:false,code,message,field}` và status 422/413/415/500 theo precedent RSA/repository thay cho quy tắc HTTP 400 trong tài liệu scope.
- Chỉ ghi metadata history cho `/api/dh/caesar`; không ghi năm endpoint DH còn lại và không bao giờ lưu tham số, khóa, nội dung, file, trace hoặc warning.
- Không thay đổi contract Caesar, RSA hoặc các cipher hiện hữu.

### Các khác biệt nguồn đã được chủ sở hữu phê duyệt

- Giới hạn file DH là 5 MiB theo contract Caesar hiện hành, không phải 1 MB trong bảng lỗi DH.
- Lỗi dùng status phân loại 422/413/415/500 và thêm `success:false`, không dùng blanket HTTP 400.
- Trần `10^12` chỉ áp dụng `/params` manual; endpoint downstream nhận và tự kiểm tra `q` tới 128 bit mà không dựa vào provenance/state.
- Trace DH công khai đi từ bit trái sang phải và phải khớp TC-04; trace RSA phải giữ nguyên.
- Thiếu `alpha` chỉ sinh suggestion, không tự điền `alpha`.

## Ngoài phạm vi

- Không làm UI, endpoint mô phỏng MITM, xác thực/chữ ký/chứng chỉ, ECDH, KDF, AES/Vigenère, nhóm DH production 2048 bit, hoặc bảo đảm an toàn production.
- Không lưu khóa hay tham số DH trong database, không tạo session/state/provenance token.
- Không thêm endpoint thứ bảy, download file, `response_mode`, trace pagination hoặc thay đổi contract cipher hiện hữu.

## Capabilities

### New Capabilities

- `diffie-hellman-core`: Số học, validation miền, random generation, key agreement và trace DH giáo dục.
- `diffie-hellman-api`: Contract request/response chính xác của sáu endpoint DH, gồm JSON/multipart Caesar.
- `diffie-hellman-error-handling`: Mã lỗi, status, message tiếng Việt, field và precedence cho DH.

### Modified Capabilities

- `operation-history`: Thêm `dh` vào metadata history nhưng chỉ ghi route biến đổi `/api/dh/caesar`, với ranh giới không lưu dữ liệu DH tuyệt đối.
- `app-runtime`: Cho request-size guard trả DH four-field error envelope trên sáu DH routes, không đổi envelope của route cũ.

## Impact

- Vùng implementation tương lai dự kiến: core/service DH, schema/route/error adapter DH, router assembly, request-size/file helpers dùng lại, history route/model/migration, OpenAPI và test DH.
- Có migration SQLite riêng nới CHECK/registries `cipher` để nhận `dh`; phải nối vào head của active `migrate-history-to-sqlite`, cập nhật continuity schema, không chạy revision PostgreSQL trên SQLite và không làm mất dữ liệu.
- Không thêm dependency nếu primality/factorization 128-bit được hiện thực nội bộ; design phải ghi rõ đây không thể reuse nguyên trạng deterministic Miller–Rabin `<2^64` của RSA.
- Hai nguồn DH ở original checkout chỉ được tham chiếu, không copy/sửa: `Trao đổi khóa Diffie-Hellman_ thuật toán và logic.md` và `Scope Backend Diffie-Hellman – Caesar_Cipher.md`.
