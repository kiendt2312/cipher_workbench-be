## Why

Dự án cần bổ sung hai thuật toán được giao mới, Vigenère và Playfair, trên nền backend Caesar đã được nghiệm thu. Change riêng này biến `BE Scope – Playfair & Vigenère.docx` cùng các quyết định bổ sung của chủ sở hữu thành hợp đồng thi hành được mà không sửa lại lịch sử hoặc hành vi đã chốt của Week 1.

## What Changes

- Thêm lõi Vigenère repeating-key: key chỉ gồm chữ cái ASCII, được chuẩn hóa về uppercase; chỉ `A-Z`/`a-z` trong dữ liệu bị biến đổi và làm tiến vị trí key, còn case, Unicode, số, dấu câu và whitespace được giữ nguyên.
- Thêm lõi Playfair canonical 5×5: alphabet ASCII uppercase bỏ `J`, `J` ánh xạ thành `I`, keyword được chuẩn hóa và loại trùng theo thứ tự xuất hiện, ma trận điền row-major, áp dụng rule cùng hàng/cùng cột/hình chữ nhật có wraparound.
- Chốt preprocessing Playfair xác định: bỏ ký tự ngoài ASCII letter, chia digraph, dùng filler `X` và fallback `Q` khi `X` gây va chạm với `X`; decrypt giữ filler giữa chuỗi, bỏ đúng một filler cuối (cập nhật 2026-09-28) và trả normalized plaintext, không hứa khôi phục format hoặc chính tả đầu vào.
- Thêm sáu endpoint backend mới: các cặp `POST /api/vigenere/encrypt|decrypt`, `POST /api/playfair/encrypt|decrypt`, và hai endpoint multipart `POST /api/vigenere/file`, `POST /api/playfair/file`.
- Kế thừa hợp đồng Caesar đã nghiệm thu cho JSON/multipart, response hai trường, `response_mode=content|file`, file `.txt` tối đa đúng 5 MiB, UTF-8/BOM, attachment/filename phía server, validation precedence, tính stateless và tầng bảo vệ request; chỉ thêm các lỗi 422 đặc thù cho key/text/ciphertext của hai thuật toán.
- Mở rộng nhận diện tuyến file của request-size và multipart-completion guards sang hai endpoint file mới, nhưng không thay đổi kết quả hay contract của bất kỳ endpoint `/api/caesar/*` nào.

### Quan hệ với scope và demo cũ

- `BE Scope – Playfair & Vigenère.docx` là input scope cho hai thuật toán mới; các quyết định chủ sở hữu trong change này hoàn thiện những điểm tài liệu để mở như va chạm filler `X`, output decrypt, response envelope và file flow.
- Completed change `caesar-cipher-week1-mvp` tiếp tục là baseline có thẩm quyền cho contract dùng chung. Change này chỉ tham chiếu và kế thừa, không sửa hoặc mở rộng trực tiếp bất kỳ artifact Week 1 nào.
- `Caesar_Cipher_Tool_Demo.html` là UI reference cũ: nó không định nghĩa Playfair/Vigenère và các hành vi mock/local cipher, hard-coded API base, CORS, giới hạn 1 MB hoặc download từ preview của demo MUST NOT được sao chép.
- Các error example tiếng Anh và trường `normalizedInput` tùy chọn trong scope mới không được chọn làm contract: API mới dùng thông báo tiếng Việt, error/success envelope đúng hai trường và không có `normalizedInput`.

## Capabilities

### New Capabilities

- `vigenere-core`: Quy tắc repeating-key Vigenère, chuẩn hóa/validate key, bảo toàn case và ký tự ngoài ASCII, cùng các vector encrypt/decrypt chuẩn.
- `playfair-core`: Chuẩn hóa key/input, dựng ma trận 5×5, chuẩn bị digraph với filler `X`/`Q`, ba phép biến đổi Playfair và semantics decrypt có chủ ý là lossy.
- `additional-text-cipher-api`: Hợp đồng JSON cho bốn endpoint text Playfair/Vigenère, response chuẩn và validation request.
- `additional-file-cipher-api`: Hợp đồng multipart cho hai endpoint file mới, hai response mode, giới hạn/encoding/BOM/filename và việc dùng cùng core với text.
- `additional-cipher-error-handling`: Error envelope, status/message tiếng Việt, validation precedence, lỗi thuật toán đặc thù và mở rộng guard sang các route mới.

### Modified Capabilities

Không có. Các capability Week 1 chưa được sửa; mọi yêu cầu mới nằm trong delta capability của change này.

## Impact

- **Backend dự kiến**: thêm các core/service, schema và route Playfair/Vigenère; mở rộng router registration và route classification trong request guards; tái sử dụng file-processing hiện hành mà không tạo abstract cipher hierarchy bắt buộc.
- **API**: thêm sáu endpoint dưới `/api/vigenere/` và `/api/playfair/`; đây là additive change. Ba endpoint Caesar hiện tại giữ nguyên request, response, status và thông báo.
- **Test dự kiến**: thêm unit/property-style vector tests cho hai core và API/file/guard integration tests; duy trì ngưỡng coverage backend hiện hành.
- **Dependency/hạ tầng**: không dự kiến thêm package, database, session, CORS, cổng hoặc dịch vụ triển khai mới.
- **Nguồn**: các quyết định chủ sở hữu đi kèm change này có quyền ưu tiên khi hoàn thiện hoặc giải quyết xung đột; tiếp theo là scope mới `BE Scope – Playfair & Vigenère.docx` cho hành vi hai thuật toán; baseline `openspec/changes/caesar-cipher-week1-mvp/` chi phối contract dùng chung khi hai nguồn trên không thay đổi rõ ràng.
- **Ngoài phạm vi**: sửa Caesar hoặc artifact Week 1; UI/UX chọn hay trực quan hóa thuật toán mới; abstract cipher framework/repository pattern; autokey Vigenère; Playfair 6×6 hay alphabet Unicode; khôi phục lossless format, `J` hoặc filler gốc khi decrypt; database/auth/history; CORS hoặc frontend server riêng; deploy/cloud/CI/CD và runtime docs.
