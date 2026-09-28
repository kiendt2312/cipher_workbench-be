## Context

Xem `proposal.md` - Why. Runtime hiện có bốn core cipher độc lập, router text/file tường minh, decoder Affine strict làm precedent cho exact JSON/multipart shape, helper file dùng chung trong `app/services/file_processing.py`, và hai ASGI guard trong `app/api/request_size_guard.py`. Các delta spec của change này là contract Columnar; hành vi dùng chung tuân authority order trong handoff. HTML upload đúng SHA-256 đã duyệt chỉ cung cấp thuật toán hàng/cột và keyword ranking, không cung cấp cleaning, padding hoặc API behavior.

Điểm thiết kế riêng là một key string có hai grammar, giới hạn tính sau ASCII-only trim, Unicode JSON surrogate phải được đưa về Unicode scalar trước transform, và thuật toán phải hoạt động theo Python Unicode code point chứ không theo UTF-16 code unit hay grapheme cluster.

## Goals / Non-Goals

**Goals:**

- Cô lập parser/ranking và transform Columnar thành module thuần, stateless, không phụ thuộc HTTP và có complexity tuyến tính theo text ngoài bước sort keyword bị chặn ở 256 cột.
- Bổ sung ba adapter HTTP strict theo đúng precedence trong specs, tái sử dụng envelope, exception handler, file helper và request guards hiện có.
- Dùng một parser key domain duy nhất cho JSON và multipart sau khi transport layer đã phân loại missing/type, để text/file không lệch grammar hoặc ranking.
- Làm OpenAPI mô tả đủ hai dạng key bằng prose/examples mà không biểu diễn sai post-trim length hoặc union grammar.
- Giữ behavior và test suite của 12 route cũ nguyên vẹn.

**Non-Goals:**

- Không tạo cipher interface/factory/registry, endpoint tổng quát hoặc pipeline validation dùng chung cho mọi cipher.
- Không sửa decoder/schema route cũ chỉ để đồng nhất strict-field hoặc surrogate policy.
- Không xử lý grapheme cluster, normalize Unicode, giữ CRLF liền nhau, thêm padding hay làm sạch text.
- Không triển khai UI, copy HTML upload hoặc thêm dependency.

## Decisions

### 1. Một module core Columnar thuần chứa parser rank và transform

Thêm `app/core/columnar.py` với API nhỏ: một hàm parse key string thành tuple/list rank đã validate, một hàm keyword ranking ổn định, và transform encrypt/decrypt nhận text cùng rank. Transport layer chịu trách nhiệm phân biệt missing/type; core chỉ nhận string có mặt và báo lỗi domain thống nhất khi content sai.

Numeric parser trim bằng tập ký tự literal `" \t\r\n\f\v"`, kiểm giới hạn 2.048 trước parsing, xử lý tối đa một outer brace, rồi tokenize grammar ASCII có separator comma và/hoặc ASCII whitespace. Parser không dùng `str.strip()` mặc định, `str.isdigit()` hay `\d`, vì chúng nhận Unicode whitespace/digit ngoài contract. Token được kiểm leading zero và range nhỏ trước khi chuyển số; toàn bộ key đã bị chặn 2.048 code point nên không có integer-token DoS. Numeric parse được thử trước, sau đó mới thử full ASCII keyword. Keyword rank sort các cặp `(uppercase-letter, original-index)`, rồi ghi rank theo index, nên duplicate ổn định trái sang phải.

Encrypt không cần dựng matrix: với mỗi rank tăng dần, tìm physical column rồi lấy `text[column::m]`. Decrypt tính length từng physical column từ `divmod(len(text),m)`, cắt ciphertext theo rank, sau đó nối row-major từ các column segment. `m <= 256`, nên một rank-to-column map nhỏ tránh lặp `index()` và giữ complexity `O(n+m)` sau parsing/ranking.

Lý do: parser là domain contract dùng chung, còn missing/type là transport contract khác nhau. Module thuần phù hợp layering test hiện có và cho phép unit test mọi vector/bound độc lập HTTP.

Phương án không chọn: dựng matrix/padding theo HTML demo hoặc parse numeric key bằng split tùy tiện. Cả hai dễ làm sai hàng cuối, empty token, brace và Unicode semantics.

### 2. Python string là chuỗi Unicode scalar sau bước JSON-surrogate validation

File UTF-8 strict đã tạo Python string chỉ gồm Unicode scalar, nên đi thẳng vào core. Với JSON, thêm decoder Columnar riêng dựa trên raw-body pattern của Affine: giữ duplicate member bằng `object_pairs_hook`, yêu cầu object exact `text,key`, và đi qua một helper validate JSON string.

Khi `json.loads` nhận raw UTF-8 bytes, một escape pair high+low hợp lệ đã được decoder ghép thành đúng scalar `U+10000..U+10FFFF`, còn lone/misordered surrogate vẫn tồn tại trong Python string. Helper SHALL duyệt member name và mọi string value trước field validation, từ chối bất kỳ code point trong range surrogate còn sót lại bằng invalid-body. Việc này chỉ xác nhận JSON đã tạo Unicode scalar; không chạy NFC/NFD, không đổi case và không ghép grapheme.

Lý do: CPython `json.loads` chấp nhận lone surrogate escape dù `utf-8` response không thể encode nó an toàn; valid pair đã có đúng scalar semantics mà contract yêu cầu.

Phương án không chọn: để lỗi encode response thành 500 hoặc dùng `errors=replace`. Hai cách làm mất dữ liệu và vi phạm canonical 422/round-trip.

### 3. Schema/validator Columnar riêng giữ strict behavior cục bộ

Thêm request model strict `text,key` và decoder/validator Columnar riêng trong schema layer. Decoder thực thi media/JSON/object/duplicate/surrogate/exact-shape; validator sau đó kiểm `text`, key missing/empty bằng ASCII trim, key type, rồi gọi parser content. Multipart validator đọc `FormData.multi_items()` để chặn unknown/duplicate, phân loại file presence/type trước key, rồi action/mode. Key là upload part thay vì scalar được map vào canonical string-type error.

Lý do: decoder/model Caesar/Vigenère/Playfair vẫn cho field lạ; sửa abstraction chung sẽ tạo breaking regression. Affine chứng minh route-specific strict decoder là seam hiện hành.

Phương án không chọn: Pydantic/FastAPI binding trực tiếp. Binding không giữ duplicate JSON/form fields và có thể coercion type hoặc trả error shape ngoài contract.

### 4. Router text/file tường minh và tái sử dụng helper file nguyên trạng

Thêm router text Columnar với hai handlers chung một helper operation, và router file Columnar với một handler. File route thực hiện raw-form validation rồi gọi đúng helper hiện tại cho extension, bounded byte read, zero-byte check, strict UTF-8/BOM, filename, content-disposition và attachment body. BOM-only file được phép vì zero-byte check diễn ra trên raw bytes trước decode; core nhận empty logical text.

Router được include trực tiếp trong app assembly để inventory tăng đúng ba route. Không extract pipeline tổng quát trừ khi apply phát hiện repetition hẹp có characterization test bảo vệ và không đổi route cũ.

Lý do: cách này nhỏ nhất, giữ precedence nhìn thấy được và giảm regression surface.

Phương án không chọn: thêm Columnar vào generalized dispatcher hoặc sửa các router cũ sang một framework chung. Phạm vi và rủi ro vượt objective.

### 5. Một canonical message/exception domain mới, handler hiện tại giữ authority

Thêm đúng message invalid-content Columnar và exception tương ứng; missing key, string-key type, text/file/action/mode và infrastructure messages tái sử dụng constants/classes hiện có. Exception không giữ raw key. Unexpected errors tiếp tục qua handler hiện tại, chỉ log loại lỗi/traceback và metadata request an toàn, không đưa payload vào exception/log context.

Lý do: mọi lỗi parser content cần cùng một public message, trong khi lỗi missing/type đã là shared contract.

Phương án không chọn: message động giải thích token/rank sai. Nó làm lộ key và phá exact error contract.

### 6. Guard chỉ mở rộng file-route allowlist

Thêm đúng `/api/columnar/file` vào `FILE_ROUTE_PATHS`. Request-size guard vốn global nên hai text route tự nhận generic 64 MiB behavior; file path mới nhận file-size message và multipart-completion check. Không đổi hằng số, middleware order, header parsing hay bốn path cũ.

Lý do: cùng seam đã dùng khi thêm Affine và là thay đổi tối thiểu để đạt đúng năm file routes.

Phương án không chọn: match prefix `/api/*/file` hoặc toàn `/api/*`; match rộng có thể âm thầm thay đổi route tương lai/không thuộc cipher.

### 7. OpenAPI được dựng explicit, key schema dùng prose thay vì validation keywords sai

Hai router dùng tag `Columnar Transposition`, error schema hiện hành và explicit request bodies. Key schema chỉ có `type:string`, description và examples numeric/keyword. Không dùng `pattern` vì contract là union parser có ordering/braces/separators; không dùng `oneOf`; không dùng raw `maxLength` vì limit áp sau ASCII trim. JSON docs chỉ quảng bá `application/json` dù runtime nhận `application/*+json`, theo baseline. File 200 mô tả cả JSON và `text/plain`.

Lý do: OpenAPI phải hữu ích cho consumer nhưng không được biểu diễn constraint mạnh hơn/sai khác runtime.

Phương án không chọn: regex khổng lồ hoặc hai schema union. Chúng không thể mô tả chính xác permutation/ranking và dễ khiến generated client hiểu key là hai wire type khác nhau.

### 8. Validation theo lớp và tài liệu chỉ sau implementation gate

Unit tests khóa parser/ranking/core trước; integration tests khóa exact shapes, precedence, surrogate, vectors, text/file parity, bytes/BOM/headers; contract tests khóa OpenAPI, 15-route inventory, guards, statelessness và safe logging. Sau đó chạy full suite 12-route regression, Ruff và branch coverage. README/guide FE chỉ được cập nhật khi code gates xanh, rồi chạy lại full validation và independent code/spec audit.

Lý do: thứ tự này tách contract errors khỏi thuật toán và không cho docs tuyên bố behavior chưa được chứng minh.

## Risks / Trade-offs

- [Grammar numeric có nhiều separator/brace edge case] → Dùng lexer/parser ASCII nhỏ, test bảng valid/invalid gồm compact digits, empty token, leading zero, malformed/nested brace, sign/decimal/exponent/Unicode digit và bounds 2/256.
- [CPython JSON nhận lone surrogate escape] → Walk decoded member names/string values trước field validation, từ chối mọi surrogate còn sót, test escaped pair/lone cùng literal non-BMP parity.
- [Transposition có thể tách CRLF, combining sequence hoặc emoji display sequence] → Đặc tả và test exact code-point round-trip; không cố bảo toàn grapheme vì sẽ đổi algorithm contract.
- [Decrypt hàng không đều dễ cắt theo rank thay vì physical position] → Tính length array theo physical index trước, dùng canonical `ABCDE`, bài giảng sáu cột, `m>n` và randomized round-trip tests.
- [Strict route mới có thể vô tình siết schema route cũ] → Decoder/validator riêng, characterization tests 12 route và full suite trước/sau include.
- [OpenAPI không thể máy hóa toàn bộ key grammar nếu bỏ pattern/maxLength] → Description/examples chính xác và integration tests cấm keywords gây hiểu sai; server vẫn là validation authority.
- [Sửa allowlist/assembly là điểm cross-cutting] → Diff chỉ thêm exact path/router, test set equality cho năm file routes và exact 15 cipher POST routes.
- [Transform file 5 MiB tạo thêm string/segments trong memory] → Reuse bounded reader; thuật toán nối theo list/segments, tránh matrix/padding và không giữ raw bytes sau decode, giống memory discipline Affine.

## Migration Plan

1. Thêm unit/characterization tests và core/parser Columnar; chưa nối routes cho đến khi domain tests xanh.
2. Thêm decoder/validators, message/exception và text/file routers; include đúng ba routes và mở rộng exact file-route allowlist.
3. Chạy targeted integration/contract tests, rồi `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, branch coverage tối thiểu 90% và strict OpenSpec validation.
4. Chỉ sau bước 3, cập nhật README và `repo_docs/frontend-integration.md` từ 12 lên 15 routes, rồi chạy lại toàn bộ gates và independent code/spec audit.
5. Deploy như additive backend change; client cũ không cần thay đổi, client mới opt-in ba route Columnar.

Rollback: gỡ include hai router Columnar và entry allowlist mới cùng module/schema/message/tests/docs Columnar trong một rollback release. Không có database/data migration; 12 route cũ là baseline. OpenSpec change không được archive/commit/push nếu owner chưa yêu cầu workflow riêng.
