## 1. Vigenère Core

- [x] 1.1 Thêm module Vigenère thuần với repeating-key encrypt/decrypt, key uppercase ASCII và operation guard; hoàn thành khi vector `Attack at dawn!`/`LEMON` chạy đúng hai chiều mà module không import tầng API/file.
- [x] 1.2 Cài quy tắc case/key-index cho ASCII letter và bảo toàn mọi ký tự khác; hoàn thành khi unit tests chứng minh punctuation/Unicode/CRLF không làm tiến key và case input được giữ nguyên.
- [x] 1.3 Phủ unit tests key Vigenère lowercase/uppercase tương đương, key lặp, key invalid và tính xác định; hoàn thành khi toàn bộ scenario `vigenere-core` có assertion trực tiếp.

## 2. Playfair Core

- [x] 2.1 Thêm normalize keyword ASCII theo đúng thứ tự, deduplicate first occurrence và dựng matrix 5×5 row-major; hoàn thành khi matrix `PLAYFAIR EXAMPLE` và các case `J`, Unicode, `ß`, key rỗng sau normalize khớp spec.
- [x] 2.2 Thêm normalize plaintext và digraph preparation xác định với filler `X`, fallback `Q`, repeated-letter consume-one và odd-tail policy; hoàn thành khi `BALLOON`, `XX`, `ABX` và `ABC` cho đúng prepared stream.
- [x] 2.3 Thêm transform pair cùng hàng/cột/hình chữ nhật với wraparound cho encrypt/decrypt; hoàn thành khi unit tests khóa các vector `FP→PL`, decrypt `PB→TI` và `HI→BM`.
- [x] 2.4 Hoàn thiện Playfair encrypt/decrypt pipeline và validation ciphertext non-empty/even/no identical digraph; hoàn thành khi vector canonical và các vector `GWGW`, `PDGW` đúng, decrypt giữ filler giữa chuỗi, bỏ đúng một filler cuối (cập nhật 2026-09-28) và không phục hồi format.
- [x] 2.5 Thêm invariant/regression tests chứng minh matrix đủ 25 ô duy nhất, output digraph chẵn, core stateless và text/file cùng chuỗi logic cho cùng kết quả.

## 3. Exception Handling và Validation

- [x] 3.1 Bổ sung canonical Vietnamese messages và exception types cho key chuỗi, key Vigenère, key/text/ciphertext Playfair; hoàn thành khi mỗi lỗi ánh xạ đúng HTTP 422 và exact two-field envelope, không có `code`, `detail` hay tiếng Anh.
- [x] 3.2 Thêm raw JSON schema/parser và validation cho string key mà không đổi Caesar integer parser; hoàn thành khi presence/type/algorithm/content precedence khớp `additional-text-cipher-api` cho cả valid và multi-error cases.
- [x] 3.3 Thêm multipart scalar/content validation cho hai thuật toán mới; hoàn thành khi key/action/response-mode và Playfair post-decode checks dừng ở lỗi đầu tiên theo precedence đã chốt.
- [x] 3.4 Mở rộng tests exception handler cho 422/413/415/500, malformed JSON/multipart và `response_mode=file`; hoàn thành khi mọi lỗi route mới luôn là JSON hai trường và không lộ dữ liệu/chi tiết kỹ thuật.

## 4. HTTP Adapter cho Text

- [x] 4.1 Thêm router explicit cho `POST /api/vigenere/encrypt|decrypt` với OpenAPI request/response đúng; hoàn thành khi happy paths, Unicode/key-index và toàn bộ validation contract chạy qua integration tests.
- [x] 4.2 Thêm router explicit cho `POST /api/playfair/encrypt|decrypt`; hoàn thành khi vector canonical, X/Q collision, lossy decrypt và ba lỗi Playfair-specific chạy qua integration tests.
- [x] 4.3 Đăng ký hai router mới trong app assembly mà không sửa route contract Caesar; hoàn thành khi `/docs` có bốn endpoint text mới và regression tests xác nhận hai endpoint Caesar không đổi.

## 5. File Processing và HTTP Adapter cho File

- [x] 5.1 Tạo orchestration file cho Vigenère/Playfair bằng các helper extension/read-limit/UTF-8/BOM/filename hiện có, không lưu temporary file; hoàn thành khi cùng nội dung text/file gọi cùng core và cho cùng result logic.
- [x] 5.2 Thêm `POST /api/vigenere/file` với content/file modes; hoàn thành khi preview JSON, attachment, CRLF/Unicode, 5 MiB boundary, encoding, BOM và filename đều có integration test.
- [x] 5.3 Thêm `POST /api/playfair/file` với content/file modes; hoàn thành khi normalization mất format, bỏ filler cuối khi decrypt (cập nhật 2026-09-28), normalized-empty/odd/duplicate-ciphertext errors, BOM và attachment đều có integration test.
- [x] 5.4 Phủ file validation precedence và malformed multipart cho cả hai route; hoàn thành khi key lỗi thắng extension/size và UTF-8 lỗi thắng Playfair content validation như delta spec.

## 6. Request Guards và Runtime

- [x] 6.1 Thay hard-code route file trong request-size/multipart-completion guards bằng tập chính xác ba route file; hoàn thành khi unit/integration tests phủ Caesar, Vigenère, Playfair, bốn route text và một route không tồn tại.
- [x] 6.2 Xác minh `Content-Length > 64 MiB` trả file message cho hai route file mới và generic message cho bốn route text mới trước body parsing; hoàn thành khi status/envelope/message khớp spec và limit nghiệp vụ vẫn là 5 MiB.
- [x] 6.3 Xác minh runtime vẫn stateless, same-origin, cổng 8000 và `/docs` hoạt động mà không thêm CORS/config/dependency; hoàn thành khi runtime tests hiện tại và test endpoint discovery mới cùng xanh.

## 7. Web UI Boundary

- [x] 7.1 Giữ nguyên template/static behavior Caesar và không thêm mock/local Playfair/Vigenère, API base hay UI selector ngoài scope; hoàn thành khi UI asset regression tests xanh và diff apply không chứa thay đổi UI không được duyệt.

## 8. Regression, Quality và Docker

- [x] 8.1 Chạy toàn bộ test suite để chứng minh ba endpoint Caesar, error strings, file/BOM/filename và validation precedence Week 1 không đổi; hoàn thành khi không có regression.
- [x] 8.2 Chạy coverage backend và bổ sung test còn thiếu cho tới khi tổng coverage đạt tối thiểu 90%, đặc biệt phủ branch Playfair filler/validation và guard route classification.
- [x] 8.3 Chạy `ruff check` và `ruff format --check`; hoàn thành khi cả hai sạch và layering tests không phát hiện core phụ thuộc API/file/framework.
- [x] 8.4 Build và smoke-test Docker image hiện hành trên cổng 8000; hoàn thành khi Caesar cùng sáu endpoint mới trả đúng contract trong container mà không cần thay đổi deployment/CORS.
