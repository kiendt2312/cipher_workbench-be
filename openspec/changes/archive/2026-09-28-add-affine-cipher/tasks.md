## 1. Baseline và test đặc tả

- [x] 1.1 Ghi nhận bằng test/fixture hiện có rằng app có đúng 9 route cipher và 6 text + 3 file endpoint Caesar/Vigenère/Playfair giữ nguyên schema, success/error envelope và precedence; hoàn thành khi các characterization test chạy xanh trên baseline trước khi nối Affine.
- [x] 1.2 Thêm unit test thất bại cho chuẩn hóa/invertibility và core vectors: `HELLO ↔ RCLLA`, mixed case/wrap, Unicode/emoji, khóa âm/lớn tương đương, `a ∈ {0,2,13,26}`, whitespace/CRLF và exact round-trip; hoàn thành khi test bao phủ đủ 12 residue `a'`, 26 residue `b'` và giải thích/khẳng định 312 cặp normalized.

## 2. Affine Core

- [x] 2.1 Tạo `app/core/affine.py` với positive-modulo normalization, kiểm tra `gcd(a',26)=1` và modular inverse không thêm dependency; hoàn thành khi unit test nhận đúng 12 residue khả nghịch, từ chối `a` không hợp lệ thay vì sửa khóa, và khóa âm/lớn cho cùng normalized pair.
- [x] 2.2 Cài đặt transform encrypt/decrypt chỉ cho ASCII `A-Z`/`a-z`, giữ case và nguyên trạng mọi ký tự khác; hoàn thành khi toàn bộ vector core, Unicode/emoji, whitespace/CRLF và lossless round-trip của mục 1.2 chạy xanh.

## 3. Schema, validation và exception Affine

- [x] 3.1 Bổ sung model/decoder JSON Affine riêng, giữ raw integer token tùy ý, từ chối malformed/non-object/member lạ-trùng và không coercion string/float/bool/null, đồng thời giữ sentinel cho member thiếu; hoàn thành khi request thành công chỉ có đúng `text`, `a`, `b`, integer ngoài JS safe range cho residue `(5,8)` chạy đúng, integer rất dài giảm modulo không đổi giới hạn toàn tiến trình, và schema cũ vẫn nhận field lạ như baseline.
- [x] 3.2 Bổ sung parser/validator tuần tự cho `text → a → b`, gồm empty-vs-whitespace, missing-vs-type và gcd của `a`; hoàn thành khi test nhiều lỗi đồng thời luôn trả đúng lỗi ưu tiên cao nhất và server không áp default `5,8`.
- [x] 3.3 Thêm tối thiểu message/exception tiếng Việt cho `a`/`b` và nối vào error handler hiện tại; hoàn thành khi mọi lỗi Affine trả đúng status cùng envelope chính xác `{success:false,message}`, không có `code`, `details`, normalized key hay field thừa, trong khi mapping lỗi cũ không đổi.
- [x] 3.4 Thêm validator multipart Affine cho exact field set `file,a,b,action,response_mode`, signed-decimal grammar và giới hạn 32 ký tự sau trim; hoàn thành khi validator thực thi đúng thứ tự `file → a → b → action → response_mode`, mặc định riêng `response_mode=content`, và không có default cho khóa.

## 4. HTTP adapter text và OpenAPI

- [x] 4.1 Thêm router/handler `POST /api/affine/encrypt` và `POST /api/affine/decrypt` gọi chung Affine core qua decoder/validator mới; hoàn thành khi hai route trả đúng hai field success cho canonical, mixed/Unicode, whitespace-only và negative/large equivalent keys.
- [x] 4.2 Include router text Affine trong app assembly mà không thêm generalized/versioned route; hoàn thành khi route inventory có 11 route cipher trước route file, không có path ngoài danh sách đã chốt và 6 text endpoint cũ không đổi.
- [x] 4.3 Khai báo OpenAPI cho hai route text với required `text:string`, `a:integer`, `b:integer`, `additionalProperties=false`, không default khóa và response 200/413/422/500; hoàn thành khi integration test đọc `/openapi.json` và đối chiếu exact schema/envelope.

## 5. HTTP adapter file và guards

- [x] 5.1 Thêm `POST /api/affine/file` dùng raw form validation Affine rồi tái sử dụng helper extension/read-limit/UTF-8/BOM/filename/attachment hiện tại; hoàn thành khi cùng input logic cho text/file cho cùng result và không có pipeline/file helper song song không cần thiết.
- [x] 5.2 Cài đặt cả `response_mode=content|file` cho encrypt/decrypt, giữ preview/download là hai request stateless riêng; hoàn thành khi content trả exact JSON, attachment trả exact UTF-8 bytes, media type và server-owned filename `<basename>.encrypted.txt`/`.decrypted.txt` kể cả tên nhiều dấu chấm.
- [x] 5.3 Thêm `/api/affine/file` vào phân loại file của request-size guard và allowlist multipart-completion hiện có, để hai route text Affine tiếp tục nhận guard global với message generic; hoàn thành khi >64 MiB bị chặn đúng message cho text/file, multipart bị cắt trả framing error, và threshold cùng ba file route cũ giữ nguyên.
- [x] 5.4 Include router file Affine trong app assembly; hoàn thành khi inventory có đúng 12 route cipher gồm đúng ba path Affine và không có factory, registry, broad hierarchy hay thay đổi CORS/auth/database/deployment.

## 6. Integration và boundary tests Affine

- [x] 6.1 Phủ integration test text cho canonical decrypt-back, mixed case/wrap, Unicode/emoji, negative/large residues, true-integer rejection matrix, missing/additional/duplicate fields, empty-vs-whitespace và priority `body → text → a → b`; hoàn thành khi status/message/body chính xác từng case và chỉ có một lỗi được trả.
- [x] 6.2 Phủ multipart validation tests cho exact/duplicate field set, signed-decimal/32-char boundary, invalid `a`, action/mode và priority nhiều lỗi; hoàn thành khi status/message/body khớp thứ tự `framing → file → a → b → action → response_mode` và chỉ có một lỗi được trả.
- [x] 6.3 Phủ file content-processing tests cho `.txt`, upload `filename=""` (415), part `file` không có filename parameter (422 framing), 0 byte, đúng 5,242,880 raw bytes (kể cả BOM), 5,242,881 bytes, UTF-8, CRLF/newline, whitespace-only và Unicode; hoàn thành khi mọi parser/byte/content boundary khớp delta spec.
- [x] 6.4 Phủ attachment tests cho encrypt/decrypt, BOM có/không có, exact output bytes, filename thường/đuôi viết hoa/nhiều dấu chấm/path component/Unicode và header an toàn; hoàn thành khi basename/suffix do server tạo đúng và content mode không thêm BOM metadata ngoài result.
- [x] 6.5 Phủ guard, 500/log-safety, stateless và OpenAPI tests cho Affine; hoàn thành khi payload/key/content/result không xuất hiện trong log lỗi, OpenAPI công bố đúng 12 route cipher, và file operation có required `file,a,b,action`, optional/default `response_mode=content`, `additionalProperties=false`, signed-decimal string `a`/`b` tối đa 32 ký tự, hai success media type cùng toàn bộ error response 413/415/422/500 dạng JSON.

## 7. Hồi quy và quality gate

- [x] 7.1 Chạy toàn bộ test suite, gồm toàn bộ acceptance/error/guard/OpenAPI tests của 9 endpoint cũ; hoàn thành khi tất cả test xanh và không có thay đổi quan sát được ở Caesar/Vigenère/Playfair.
- [x] 7.2 Chạy Ruff check, Ruff format check và pytest coverage theo command chuẩn repository; hoàn thành khi không có lỗi lint/format và coverage backend đạt tối thiểu 90% mà không dùng exclusion mới để che code Affine.
- [x] 7.3 Rà soát dependency/layering và diff implementation; hoàn thành khi không thêm dependency, generalized API/factory/registry/class hierarchy, UI runtime import, persistence, CORS/auth/database/deployment, và chỉ extract shared code nơi repetition thực tế đã được test bảo vệ.

## 8. Đồng bộ tài liệu sau khi implementation đã xác minh

- [x] 8.1 Chỉ sau khi mục 7 đạt, cập nhật mọi section stale trong README (cipher/route inventory, endpoint tables, schemas, examples, file/error/guard notes và test/usage text) từ 3 cipher/9 endpoint lên 4 cipher/12 endpoint với ba route Affine, exact key schemas, `(5,8)` chỉ là gợi ý, canonical/round-trip vectors và không gian 312 normalized pairs; hoàn thành khi không còn claim cũ và README không coi demo/client là result authority.
- [x] 8.2 Cập nhật mọi section stale trong `repo_docs/frontend-integration.md` (overview/tree, route/type/table, request examples, error/authority, migration và checklist) từ 3 cipher/9 endpoint lên 4 cipher/12 endpoint, gồm JSON true-integer/precision warning, multipart signed-decimal 32 ký tự, hai request preview/download, attachment filename/BOM và error precedence; hoàn thành khi không còn claim cũ và guide không yêu cầu FE implementation trong backend change.
- [x] 8.3 Kiểm tra integrity cuối cùng; hoàn thành khi `affine-cipher.html`, các untracked source/reference file, Week 1 và completed Playfair/Vigenère OpenSpec không bị sửa/copy/import/stage, không archive change và diff chỉ chứa implementation/test/docs được change cho phép.
