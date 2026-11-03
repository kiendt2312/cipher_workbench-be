# Design

## Context

Xem `proposal.md` cho động cơ và phạm vi. Backend là Python 3.12/FastAPI, đã có Caesar core/file helpers, strict RSA schemas/error envelope, request-size guard và best-effort operation history. Runtime history hiệu lực đang chuyển sang SQLite qua active change `migrate-history-to-sqlite`, có migration root và continuity registries riêng. RSA có `mod_pow`, trial division tới `10^12` và deterministic Miller–Rabin chỉ dưới `2^64`; DH cần q tới 128 bit và public trace trái→phải nên không thể reuse nguyên trạng.

Hai nguồn nghiệp vụ bắt buộc:

- `/home/hieu-anh/Documents/Cipher/cipher_workbench-be/Trao đổi khóa Diffie-Hellman_ thuật toán và logic.md` (Tài liệu thuật toán DH), 263 dòng, §§3–6, 10–12.
- `/home/hieu-anh/Documents/Cipher/cipher_workbench-be/Scope Backend Diffie-Hellman – Caesar_Cipher.md` (Scope DH), 104 dòng, BE-01–BE-08, §API, §Bắt lỗi, TC-01–TC-13.

Các quyết định chủ sở hữu sau grilling có quyền cao hơn khi hai nguồn hoặc repository mâu thuẫn; từng deviation đã được ghi ở proposal/specs.

## Goals / Non-Goals

**Goals:**

- Tách core số học thuần khỏi HTTP adapter; mọi CPU-heavy primality/factorization/generation chạy ngoài event loop.
- Giữ exact six-route contract, strict schemas, deterministic error precedence và full educational traces.
- Cung cấp DH standalone với dữ liệu số học được tính thật: parameters, private/public keys, shared secrets, match và full traces.
- Reuse Caesar transform/file semantics trong một integration riêng mà không thay đổi public Caesar routes hoặc hạ DH thành Caesar mode; standalone chỉ thêm compatibility input decimal string canonical từ `sharedKey` DH.
- Thêm history DH theo migration SQLite tuyến tính, bảo toàn dữ liệu và tương thích active change SQLite/RSA.

**Non-Goals:**

- Không trừu tượng hóa mọi cipher, không production crypto, không giữ session/cache/provenance cho q.
- Không đổi thuật toán/trace RSA, Caesar response, file download contract hay các migration đã áp dụng.

## Decisions

### 1. Module DH riêng và reuse có chọn lọc

Tạo core DH riêng cho primality, factorization, left-to-right `mod_pow`, primitive-root, keypair/shared secret và safe-prime generation. Reuse Caesar `transform_text` và file byte helpers; có thể extract helper số học nội bộ chỉ khi test chứng minh RSA output/trace không đổi.

Alternative reuse trực tiếp RSA `mod_pow` bị loại vì RSA trace đi right-to-left với schema/sequence khác TC-04. Alternative gọi built-in `pow` cho mọi path bị loại vì không tạo được educational rows; built-in `pow` vẫn có thể dùng làm oracle test và fast path không trace nếu kết quả parity được bảo đảm.

### 2. Chính sách primality và factorization 128 bit

- Manual `/params` dùng trial division trong miền `<=10^12`, giữ behavior dễ giải thích.
- Trên `10^12` tới `2^128-1`, dùng Miller–Rabin nhiều witness cùng small-prime prefilter; generation dùng witness lấy từ CSPRNG và số rounds cố định được ghi/test để xác suất false-positive tối đa `4^-rounds` theo giả định chuẩn của Miller–Rabin.
- Factor `q-1` tổng quát bằng trial division small primes rồi Pollard–Brent/Rho đệ quy, xác nhận mỗi factor bằng cùng primality policy và deduplicate trước primitive-root checks. Với safe prime sinh nội bộ, vẫn xác minh độc lập `p=(q-1)/2` thay vì tin provenance.
- CPU work chạy threadpool với concurrency limiter; không cache tham số/khóa giữa requests. Benchmark 16/32/64/128-bit và adversarial composites là implementation gate.

Alternative deterministic RSA witnesses bị loại vì chỉ có chứng minh cho `<2^64`. Alternative đánh dấu q đã sinh bằng token/state bị loại theo quyết định owner. Không tuyên bố primality 128-bit là chứng minh toán học tuyệt đối; đây là probable-prime educational contract.

### 3. CSPRNG và random generation có test seam

Dùng nguồn random mật mã của Python cho p/q/private keys. Core nhận callable injectable chỉ trong internal API để unit test deterministic; HTTP không cho client seed. Candidate đặt high bit + odd bit, q phải đúng bit length; alpha được tìm từ giá trị nhỏ nhất thỏa checks để output dễ học và reproducible sau khi q cố định.

### 4. Strict transport và serialization

DH có decoder/schema riêng theo RSA precedent: phát hiện malformed JSON, duplicate/unknown/inapplicable fields trước domain work; cryptographic numbers chỉ nhận ASCII canonical decimal strings không dấu/space/leading zero ngoại trừ `"0"`. Control `bits` và trace row `index/bit` là JSON integer thật. Output crypto strings được canonicalize.

Success responses thêm `success:true`; error luôn bốn field. `/params` thiếu alpha dùng `alpha:null`, checks rỗng, suggestion string; supplied invalid alpha không trả success body. Warning là object `{code,message}` để máy và UI cùng dùng; exchange warning dùng code `EDUCATIONAL_PRIVATE_KEYS`. Message không mô tả response là dữ liệu mẫu: nó nói rõ private/public/shared keys và traces là kết quả số học thật, đồng thời cảnh báo private key không rời bên sở hữu và public key phải được xác thực để chống MITM trong hệ thống thực tế.

### 5. Trace schema DH

Mỗi row gồm đúng `index`, `bit`, `exponentPrefix`, `squared`, `multiplied`, `result`; `index/bit` native integer, `multiplied` null khi bit 0, các giá trị còn lại decimal strings. Trace đầy đủ, không truncate/paginate; exponent tối đa 128 bit nên tối đa 128 rows. Primitive-root check gồm `factor`, `exponent`, `result`, `passes`.

Exchange group steps theo `publicKeyA`, `publicKeyB`, `sharedKeyA`, `sharedKeyB`; keypair/shared-secret dùng array `steps`. Điều này khóa TC-04 nhưng không động tới RSA trace.

### 6. `/caesar` JSON và multipart cùng một response

Dispatch chỉ theo exact media type. JSON nhận `data`; multipart nhận file và scalar fields, không nhận `response_mode`. Cả hai decode thành text rồi gọi cùng shared-secret + Caesar flow và trả JSON. Multipart dùng existing `.txt`, case-insensitive extension, exact 5 MiB reader và strict UTF-8; UTF-8 BOM được bỏ khỏi visible content như Caesar content mode, nhưng history byte lengths tính cả BOM.

Validation multipart theo metadata → extension → bounded read → empty → UTF-8 để tránh CPU/file work khi crypto fields đã sai.

### 7. History SQLite và migration tuyến tính

Route matcher thêm exact special-case `/api/dh/caesar`, đổi source theo media type; không đưa `dh` vào generic `{encrypt,decrypt,file}` route generator và năm route DH còn lại không match. Notes chỉ nhận operation và lengths. SQLite CHECK, runtime model/filter, continuity `CIPHERS` và staging schema cùng thêm `dh`. Migration nằm trong `alembic_sqlite` root và nối actual SQLite head của active `migrate-history-to-sqlite`; revision PostgreSQL chỉ là source/rollback reference và MUST không chạy trên SQLite. Downgrade không xóa row DH.

JSON input/output length là Unicode code points. Multipart input là raw byte count; output là UTF-8 byte count cộng BOM length nếu input có BOM, dù response JSON không chứa BOM. `response_mode` luôn null.

### 8. Source precedence và traceability

Mỗi requirement/scenario dẫn chiếu Tài liệu thuật toán DH, Scope DH, accepted owner decision hoặc existing capability. Khi conflict: accepted owner decisions > hai nguồn DH > existing feature precedent cho phần không được nguồn DH định nghĩa; không sửa nguồn gốc.

Decision record được owner xác nhận ngày 2026-10-08: D1 generated q composable; D2 missing alpha suggestion-only; D3 exchange trả private keys; D4 manual cap chỉ `/params`, downstream 128 bit stateless; D5 exact 5 MiB + Caesar UTF-8/BOM; D6 status/envelope theo RSA/repo; D7 crypto strings, controls native; D8 history chỉ DH Caesar. Cùng confirmation giữ trace trái→phải, JSON-only Caesar và sáu endpoint/exclusions. Follow-up cùng ngày xác nhận DH là feature standalone ngang cấp Caesar, còn `/api/dh/caesar` là integration; không thay đổi D1–D8 hay thêm compatibility route.

| TC | Requirement/scenario chính | Nguồn |
| --- | --- | --- |
| TC-01 | Core “Tham số giáo trình hợp lệ” | Cả hai tài liệu §§3/TC-01 |
| TC-02 | Core “Exchange mẫu q 23” | Thuật toán §§4–5; Scope TC-02 |
| TC-03 | Core “Hai bên ra cùng K” | Thuật toán §7; Scope TC-03 |
| TC-04 | Core “TC-04 chính xác” | Thuật toán §6; Scope TC-04 |
| TC-05 | Error “q composite” | Thuật toán §10; Scope TC-05 |
| TC-06 | Error “Alpha không nguyên căn có suggestion” | Thuật toán §§3,10; Scope TC-06 |
| TC-07 | Error “Alpha ngoài miền” | Thuật toán §3; Scope TC-07 |
| TC-08 | Core/API random 32-bit | Thuật toán §3; Scope TC-08 |
| TC-09 | Core/Error private boundary | Thuật toán §§4,10; Scope TC-09 |
| TC-10 | Core/Error peer public boundary | Thuật toán §§10,12; Scope TC-10 |
| TC-11 | API “Encrypt JSON TC-11” | Thuật toán §11; Scope TC-11 |
| TC-12 | Core “Shift zero không chặn” | Thuật toán §10; Scope TC-12 |
| TC-13 | Core/Error manual q cap | Scope TC-13; owner D4 giải quyết conflict generated q |

## Risks / Trade-offs

- **[128-bit factorization có latency không ổn định]** → Pollard–Brent, small-prime prefilter, threadpool/concurrency limit và benchmark adversarial; ghi rõ phạm vi educational. Không trình bày benchmark tốt là chứng minh worst-case.
- **[Miller–Rabin 128-bit là xác suất]** → rounds cố định, CSPRNG witnesses, pseudoprime corpus và công khai limitation; không reuse claim deterministic 64-bit của RSA.
- **[Full traces tăng response/CPU]** → exponent tối đa 128 bit, tối đa 128 rows mỗi modPow; exchange có đúng bốn traces, không endpoint trace tùy ý.
- **[Active SQLite change và DH cùng sửa history contract]** → base revision on actual `alembic_sqlite` head, cập nhật runtime/continuity registries đồng bộ và chạy upgrade/downgrade/data-preservation; không thêm PostgreSQL runtime migration.
- **[API trả private keys]** → warning bắt buộc và docs nhấn mạnh educational; không persist/log/history.
- **[Strict schema có thể khác source table tối giản]** → OpenAPI examples + exact integration snapshots; đây là detail đã chốt theo repository precedent.

## Migration Plan

1. Implement/test core và six routes mà chưa bật history DH.
2. Reconcile actual `alembic_sqlite` head, thêm SQLite migration CHECK `dh`, cập nhật continuity/runtime registries và verify preservation/downgrade trên disposable SQLite; không chạy PostgreSQL revisions.
3. Bật route matcher/history notes sau migration; deployment chạy migration trước app.
4. Rollback app trước; downgrade schema chỉ sau khi operator xử lý row `dh`, không tự xóa.

## Open Questions

Không còn câu hỏi sản phẩm. Số Miller–Rabin rounds, Pollard–Brent retry/concurrency constants và benchmark thresholds được chốt trong implementation dựa trên đo đạc nhưng MUST không thay đổi contract/spec ở trên.
