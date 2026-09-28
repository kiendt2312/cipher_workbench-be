## Context

Xem `proposal.md` để biết động lực và phạm vi. Baseline tại HEAD hiện có một pure Caesar core, hai route module riêng cho text/file, validation thủ công để giữ precedence xác định, các helper file độc lập framework, exception handler chung và hai ASGI guard. UI same-origin hiện chỉ phục vụ Caesar.

Nguồn hành vi mới là `BE Scope – Playfair & Vigenère.docx` cùng quyết định chủ sở hữu đã ghi vào delta specs. Scope mới là tài liệu backend chưa được version trong metadata và đang nằm ngoài Git; vì vậy change artifacts phải tự chứa toàn bộ quyết định cần thiết cho apply. Completed change `caesar-cipher-week1-mvp` vẫn là baseline bất biến cho contract dùng chung.

Change đi qua nhiều seam — core, validation, HTTP routes, file response, error mapping, OpenAPI và request guards — nên cần design trước apply. Không có data migration hoặc dependency ngoài mới.

## Goals / Non-Goals

**Goals:**

- Thêm hai pure algorithm core có hành vi xác định và test độc lập transport.
- Thêm sáu endpoint additive mà không làm đổi ba endpoint Caesar.
- Dùng lại file byte/UTF-8/BOM/filename primitives và canonical response/error conventions hiện tại.
- Giữ validation precedence quan sát được ở một nơi rõ ràng cho text và file.
- Mở rộng guard theo route một cách tường minh và regression-test được.

**Non-Goals:**

- Không sửa thuật toán, schema, route hoặc UI behavior Caesar.
- Không xây base class, plugin registry, strategy framework hoặc repository pattern cho cipher.
- Không thêm UI chọn Playfair/Vigenère, CORS, frontend server riêng, database hay persistence.
- Không cố phục hồi format, `J` hoặc filler gốc của Playfair decrypt.
- Không thêm thuật toán/variant khác như autokey Vigenère hay Playfair 6×6.

## Decisions

### 1. Hai core mới là module thuần, không tạo cipher hierarchy

Mỗi thuật toán sẽ có module riêng dưới `app/core/`, nhận `text`, `key` chuỗi và operation rồi trả chuỗi. Helper Playfair cho normalize key, dựng matrix, chuẩn bị digraph và transform pair có thể là hàm nội bộ nhỏ để test các invariant khó. Core không đọc request, file, config, log hay tạo HTTP response.

Lý do: Caesar key là integer và bảo toàn toàn bộ non-ASCII; Vigenère key là ASCII string; Playfair normalize mất dữ liệu và có validation riêng. Một interface/base class chung lúc này sẽ che khác biệt thay vì làm seam sâu hơn. Module riêng giữ dependency một chiều và đáp ứng quyết định Week 1 không dựng abstraction sớm.

Phương án không chọn: đổi Caesar sang một registry/`CipherService` chung hoặc class hierarchy. Việc đó mở rộng regression surface mà không cần thiết cho contract mới.

### 2. Normalization dùng kiểm tra ASCII tường minh

Mọi kiểm tra letter sẽ dùng range ASCII rõ ràng, không dùng `str.isalpha()` hoặc Unicode normalization/transliteration. Với Playfair, “uppercase” là ánh xạ `a-z` sang `A-Z` trên từng ký tự ASCII; ký tự Unicode như `ß` không được phép case-expand thành `SS` trước khi filter. Dedup giữ insertion order, matrix fill dùng alphabet hằng số bỏ `J`.

Lý do: delta spec định nghĩa alphabet 25 ô và hành vi Unicode chính xác. API Unicode chung của Python rộng hơn contract và có case mapping một-thành-nhiều, dễ tạo ciphertext khác nhau ngoài ý muốn.

Phương án không chọn: `text.upper()` rồi `isalpha()`, loại dấu bằng Unicode normalization, hoặc transliterate.

### 3. Playfair preprocessing và decrypt là hai pipeline khác nhau

Encrypt sẽ normalize plaintext rồi duyệt bằng index: cặp khác nhau tiêu thụ hai ký tự; cặp lặp tiêu thụ một và chèn `X`, riêng ký tự `X` dùng `Q`; ký tự cuối dùng cùng lựa chọn filler. Decrypt chỉ normalize ciphertext, kiểm non-empty/even/no identical digraph rồi transform từng cặp; không chèn filler, chỉ bỏ đúng một filler cuối (`XQ → X`, `X → ""`) theo quyết định chủ sở hữu 2026-09-28.

Lý do: tách pipeline ngăn decrypt vô tình “sửa” ciphertext và làm rõ round-trip chỉ về prepared plaintext đã bỏ filler cuối. Các vector `XX → XQXQ → GWGW` và `ABX → ABXQ → PDGW` là regression anchors.

Phương án không chọn: heuristic xóa mọi `X/Q` (kể cả giữa chuỗi), luôn dùng `X` kể cả va chạm, hoặc pad ciphertext lẻ khi decrypt.

### 4. HTTP adapter chịu trách nhiệm validation và ánh xạ lỗi

Các raw request schema sẽ giữ dữ liệu chưa ép kiểu, tương tự Caesar, để validation thủ công bảo toàn precedence. Text/key presence được kiểm trước; key string/algorithm policy tiếp theo; validation normalized Playfair cuối cùng. Multipart theo cùng tầng hiện tại: framing/field presence, scalar format, file metadata/bytes/UTF-8 rồi algorithm content.

Các exception/message mới chỉ đại diện cho lỗi public đã chốt. Exception handler chung tiếp tục tạo envelope hai trường; core có thể dùng lỗi nội bộ cho invariant lập trình nhưng lỗi đó không được rò ra API.

Lý do: giao hoàn toàn cho validation mặc định của framework có thể tạo `detail`, thay đổi thứ tự lỗi hoặc dùng message tiếng Anh, trái contract.

Phương án không chọn: một schema cưỡng ép chung cho key Caesar integer và key Playfair/Vigenère string, hoặc thêm machine error code.

### 5. Route mới explicit; Caesar adapter không bị refactor bắt buộc

Router Vigenère và Playfair sẽ được đăng ký tường minh trong app assembly. Mỗi route gọi đúng core, không dispatch theo tên thuật toán lấy từ input. Code dùng chung chỉ được trích cho transport mechanics thực sự giống nhau, chẳng hạn tạo content/attachment response sau khi đã có result; không đổi route Caesar chỉ để đạt DRY.

Lý do: endpoint explicit giúp OpenAPI, type/validation và security boundary dễ audit; giữ Caesar adapter ổn định là cách chắc nhất chứng minh compatibility.

Phương án không chọn: endpoint `/api/cipher/{algorithm}`, dynamic import/registry, hoặc sửa request Caesar để thêm `algorithm`.

### 6. Tái sử dụng file primitives, giữ processing trong memory có giới hạn

Hai route file mới sẽ dùng các helper hiện tại cho extension, đọc tối đa `5 MiB + 1 byte`, UTF-8/BOM, filename và `Content-Disposition`. Core chỉ nhận chuỗi đã decode. Playfair có thể tạo output gần gấp đôi số ASCII letter trong trường hợp chèn filler dày đặc, nhưng input đã bị chặn 5 MiB và toàn bộ pipeline vẫn có cận bộ nhớ nhỏ hơn trần request 64 MiB.

Lý do: helper hiện tại đã được nghiệm thu cho boundary bytes, BOM và header safety. Streaming transform không phù hợp với Playfair vì digraph có thể phụ thuộc ký tự kế tiếp sau các ký tự bị loại.

Phương án không chọn: FE tạo download từ preview, lưu temporary file, hoặc streaming Playfair theo chunk độc lập.

### 7. Guard dùng tập route file tường minh

Request-size guard sẽ phân loại `/api/caesar/file`, `/api/vigenere/file`, `/api/playfair/file` là file routes để chọn message 413; multipart-completion guard dùng cùng tập route khi kiểm closing boundary. Bốn route text mới vẫn nhận message request generic. Việc nhận diện tiếp tục dựa trên method/path, không dựa vào `Content-Type` để tránh spoof classification.

Lý do: guard hiện hard-code một route Caesar. Một constant/helper route set là thay đổi nhỏ nhất có thể test theo bảng route, đồng thời không mở rộng guard cho endpoint không phải file.

Phương án không chọn: prefix matching rộng như `/api/*/file`, vì route chưa đăng ký có thể bị phân loại như API thật và che lỗi 404/405.

### 8. Same-origin runtime và UI hiện tại giữ nguyên

App tiếp tục chạy cổng 8000, không thêm CORS hay environment API base. Các endpoint mới xuất hiện trong `/docs`; trang `/` chưa có control gọi chúng trong change backend này. Không sửa template/static assets hoặc `repo_docs/frontend-integration.md` trong apply trừ khi một change tài liệu/UI riêng được duyệt sau.

Lý do: scope mới là backend scope và không định nghĩa state/interaction UI mới. Tự thiết kế UI trong change này sẽ vượt nguồn có thẩm quyền.

### 9. Test theo contract và ranh giới module

Unit tests sẽ khóa matrix, normalization, digraph, X/Q collision, vector canonical, case/Unicode/key-stream Vigenère và pure-core determinism. Integration tests sẽ tham số hóa endpoint/operation nơi contract giống nhau, đồng thời giữ case riêng cho khác biệt Playfair. File tests phủ 5 MiB boundary, BOM, filename, JSON-vs-attachment, precedence và guard route matrix. Suite hiện tại phải tiếp tục xanh và coverage backend toàn cục giữ tối thiểu 90%.

Lý do: lỗi có rủi ro cao nằm ở policy edge và adapter boundary hơn là happy path. Vector tests ngăn các biến thể “Playfair canonical” khác nhau cùng lọt qua.

## Risks / Trade-offs

- **[Playfair cố ý mất thông tin]** Người dùng có thể kỳ vọng decrypt phục hồi nguyên văn → API/spec giữ filler giữa chuỗi, bỏ một filler cuối và trả uppercase plaintext; plaintext chẵn kết thúc bằng `X` mất `X` cuối (`AX → A`); UI mới, nếu được làm sau, phải giải thích rõ.
- **[Unicode case mapping ngoài ý muốn]** Hàm built-in có thể biến non-ASCII thành ASCII → dùng range/mapping ASCII tường minh và test `ß`, chữ có dấu, emoji.
- **[Regression Caesar khi chia sẻ adapter]** Refactor để giảm lặp có thể đổi precedence hoặc OpenAPI → không bắt buộc refactor Caesar; thêm characterization/regression tests trước mọi extraction.
- **[Guard bỏ sót hoặc nhận nhầm route]** Hard-code phân tán dễ lệch → một route set duy nhất, test cả ba file route, bốn text route và route không tồn tại.
- **[Output Playfair lớn hơn input logic]** Filler có thể làm tăng gần 2× số letter → giữ input cap 5 MiB, xử lý tuyến tính và giải phóng buffer bytes trước transform như baseline.
- **[Không giới hạn riêng độ dài key]** Key rất dài vẫn tiêu thụ tài nguyên trong trần request → normalize/dedup tuyến tính; request cap 64 MiB là cận hạ tầng, không tự thêm business limit chưa được duyệt.
- **[Scope DOCX chưa được version trong Git]** Provenance có thể khó truy ngược → mọi quyết định quan sát được được lặp đầy đủ trong delta specs và cite các mã BE-VIG/BE-PLAY; DOCX gốc không bị sửa.

## Migration Plan

1. Thêm core và unit tests độc lập, chưa đăng ký route.
2. Thêm message/exception/validation mới và route text, chạy regression suite Caesar.
3. Thêm route file dùng helper hiện tại, sau đó mở rộng route set của hai guard.
4. Đăng ký router trong app assembly và xác minh OpenAPI `/docs` mô tả đúng sáu endpoint mới.
5. Chạy Ruff, toàn bộ pytest/coverage và các vector/contract tests mới trước khi phát hành.

Triển khai là additive, không cần data migration hoặc downtime đặc biệt. Rollback bằng cách quay lại release trước change; không có dữ liệu mới cần chuyển đổi. Nếu lỗi chỉ nằm ở route mới, có thể gỡ đăng ký router và phần route classification tương ứng mà không đổi contract Caesar.
