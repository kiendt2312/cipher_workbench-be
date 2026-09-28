## Why

Backend hiện có ba cipher và 9 endpoint nhưng chưa có Affine Cipher để phục vụ mục tiêu học thuật toán trong `affine-cipher.html`. Change này xác lập contract backend đầy đủ cho Affine theo hành vi đã nghiệm thu của runtime/OpenSpec hiện tại, dùng demo chỉ làm tham chiếu thuật toán và không để demo ghi đè contract API/file/error.

## What Changes

- Thêm lõi Affine modulo 26 cho ASCII `A-Z`/`a-z`, giữ case và bảo toàn mọi ký tự khác; chuẩn hóa hai khóa integer theo modulo 26, chỉ chấp nhận `a'` nguyên tố cùng nhau với 26 và bảo đảm round-trip text lossless với khóa hợp lệ.
- Thêm đúng ba route `POST /api/affine/encrypt`, `POST /api/affine/decrypt` và `POST /api/affine/file`, đưa tổng số route cipher từ 9 lên 12; không thêm generalized cipher API, factory, registry hoặc hierarchy rộng.
- Định nghĩa JSON body Affine chính xác gồm `text`, `a`, `b`: `a`/`b` là JSON integer thật, không có default server, hỗ trợ biểu diễn integer âm/rất lớn mà không mất chính xác và từ chối field bổ sung chỉ trong schema Affine mới. Hành vi nhận field bổ sung hiện tại của Caesar/Vigenère/Playfair không bị thay đổi.
- Kế thừa toàn bộ file contract hiện hành cho `.txt`, UTF-8, giới hạn đúng 5 MiB, BOM, CRLF/newline, hai response mode, hai request preview/download và filename attachment do server tạo; multipart Affine dùng chính xác `file`, `a`, `b`, `action`, `response_mode`, trong đó `a`/`b` là signed-decimal string tối đa 32 ký tự.
- Mở rộng request-size guard lớn hơn 64 MiB và multipart-completion guard tới route file Affine nhưng giữ nguyên mọi threshold và hành vi của 9 route cũ.
- Giữ nguyên success envelope `{success:true,result}` và error envelope `{success:false,message}`; thêm validation/error Affine tiếng Việt với thứ tự xác định và chỉ trả lỗi ưu tiên cao nhất.
- Bổ sung kiểm thử core/API/file/error/guard/OpenAPI cho Affine, đồng thời chạy regression đầy đủ cho 9 endpoint hiện hữu; sau implementation mới đồng bộ README và `repo_docs/frontend-integration.md` từ 9 lên 12 endpoint.
- Giữ `affine-cipher.html` ở trạng thái reference-only, không commit/copy/import vào runtime và không dùng phép tính phía client/demo làm nguồn kết quả chính thức.

## Capabilities

### New Capabilities

- `affine-core`: Công thức Affine, chuẩn hóa/kiểm tra khóa, bảo toàn ký tự và các vector/round-trip bắt buộc.
- `affine-text-cipher-api`: Hai endpoint JSON Affine, exact request schema, response và validation field theo thứ tự.
- `affine-file-cipher-api`: Endpoint multipart Affine kế thừa đầy đủ contract file/attachment hiện hành với hai khóa mang giá trị số nguyên, biểu diễn trên wire bằng signed-decimal string theo contract multipart.
- `affine-error-handling`: Message/status/precedence Affine, error envelope và việc mở rộng hai request guard mà không làm đổi 9 endpoint cũ.

### Modified Capabilities

Không có. Repository chưa có main spec Affine; change tạo delta specs mới và không sửa các completed change Caesar, Vigenère hoặc Playfair.

## Impact

- Khi apply trong một workflow sau: thêm Affine core và HTTP adapters/schemas, nối router vào app assembly, mở rộng tập route của request guards, bổ sung canonical message/exception khi cần, tái sử dụng helper file hiện tại và chỉ extract shared code khi có lặp thực tế.
- OpenAPI sẽ mô tả 12 route cipher, Affine JSON integer không giới hạn JS safe integer ở wire contract, multipart `a`/`b` tối đa 32 ký tự và hai success mode của file.
- Test scope gồm unit/integration cho Affine và regression toàn bộ Caesar/Vigenère/Playfair; không thêm dependency, database, auth, CORS hay thay đổi deployment.
- README và guide FE chỉ được cập nhật trong apply sau khi implementation đã được xác minh; planning-only workflow này chỉ tạo artifact dưới `openspec/changes/add-affine-cipher/`.

## Ngoài phạm vi

- Không triển khai FE, không sửa UI static, không đưa `affine-cipher.html` vào source/runtime và không thêm client-side production cipher.
- Không đổi contract, source hoặc artifact của Week 1 hay completed change Playfair/Vigenère; không archive OpenSpec change nào.
- Không thêm versioned/generalized endpoint, algorithm registry/factory/interface rộng, CORS, authentication, database, lưu lịch sử, telemetry phân tích hoặc deployment mới.
- Không thay đổi giới hạn file 5 MiB, trần request 64 MiB, envelope, filename, BOM hoặc validation behavior đã nghiệm thu của 9 endpoint hiện hữu.

## Giải quyết khác biệt giữa nguồn

- Thứ tự ưu tiên bắt buộc là: (1) completed OpenSpec và runtime hiện tại; (2) README và `repo_docs/frontend-integration.md` hiện tại; (3) `affine-cipher.html` chỉ làm tham chiếu thuật toán/UI giáo dục. Nguồn ở mức thấp hơn không được ghi đè nguồn ở mức cao hơn.
- `affine-cipher.html` chỉ cung cấp công thức, vector `HELLO → RCLLA`, tập residue `a` khả nghịch và gợi ý UI `a=5`, `b=8`; default UI, tính toán JavaScript, message động và giới hạn kiểu `Number` của demo không trở thành contract backend.
- Completed OpenSpec/runtime hiện tại cùng README và guide FE quyết định envelope, status/message style, file flow, guard, server authority và ranh giới runtime; khi có mâu thuẫn, các nguồn này luôn thắng demo Affine.
