# Tasks

## 1. DH Arithmetic Core

- [x] 1.1 Tạo domain errors/constants và canonical decimal parsing/serialization cho q/alpha/X/Y/K/factors; verify unit tests phủ signs, whitespace, Unicode digits, leading zero, bool/number/null và 128-bit boundary.
- [x] 1.2 Implement left-to-right square-and-multiply với exact trace `index/bit/exponentPrefix/squared/multiplied/result`; verify TC-04 cho sequence `3,27,23,176,265,331,40`, parity với `pow` và tối đa 128 rows.
- [x] 1.3 Implement manual primality `<=10^12` và Miller–Rabin 128-bit theo rounds/witness policy được tài liệu hóa; verify prime/composite boundaries, Carmichael/pseudoprime corpus và chứng minh test không reuse claim deterministic `<2^64` ngoài miền RSA.
- [x] 1.4 Implement factorization `q-1` bằng small-prime division + Pollard–Brent/Rho; **xong khi** unit tests tái dựng đúng tích factors và retry deterministic qua injected RNG.
- [x] 1.5 Implement primitive-root checks/suggestion trên distinct factors; **xong khi** TC-01/TC-06 và 128-bit fixtures trả exact checks/suggestion.
- [x] 1.6 Benchmark factorization 16/32/64/128-bit và adversarial composites ngoài event loop; **xong khi** lưu evidence latency/concurrency và threshold, không tuyên bố worst-case guarantee.
- [x] 1.7 Implement safe-prime generation 16/32/64/128 bit và alpha nhỏ nhất hợp lệ bằng CSPRNG/test seam; **xong khi** exact bit length, `q=2p+1`, primality và injected-random tests xanh.
- [x] 1.8 Implement keypair với resample/reject khi derived Y là `1|q-1`; **xong khi** random key luôn downstream-composable và manual `q=23,alpha=5,X=11` trả exact `PRIVATE_KEY_WEAK`.
- [x] 1.9 Implement shared-secret/exchange core, grouped traces và educational warning; **xong khi** TC-02/03/09/10 và generated exchange `match=true` xanh.

## 2. Strict Schema và Exception Handling

- [x] 2.1 Tạo strict DH JSON decoder phát hiện malformed/non-object/duplicate/unknown/inapplicable fields và exact media dispatch; verify precedence tests không phụ thuộc member order ngoài duplicate/unknown.
- [x] 2.2 Tạo exact request/response/trace/check/warning schemas cho sáu endpoints với crypto decimal strings, native controls/booleans và `extra="forbid"`; verify model/OpenAPI snapshots, gồm missing-alpha `alpha:null` + suggestion-only.
- [x] 2.3 Tạo DH error adapter exact `{success:false,code,message,field}` và message table tiếng Việt; verify từng code/status/message/field trong spec, 500 redaction và các handler cipher hiện hữu không đổi.
- [x] 2.4 Implement deterministic validation ordering cho JSON/multipart; verify multi-error tests cho q→alpha→private→public→action/data và metadata→extension→size→empty→encoding.

## 3. Parameter và Key HTTP Adapters

- [x] 3.1 Implement `/api/dh/params` manual cap, valid-alpha path, omitted-alpha suggestion-only và invalid-alpha error suggestion; verify TC-01, TC-05–TC-07, TC-13 và exact success/error bodies.
- [x] 3.2 Implement `/api/dh/params/random` qua threadpool/concurrency limiter; verify bốn bit sizes, TC-08 invariants, invalid bits và response composability.
- [x] 3.3 Implement `/api/dh/keypair` và `/shared-secret`, mỗi request tự kiểm tra q tới 128 bit không provenance/state; verify manual/generated flows, TC-02/03/09/10 và exact traces.
- [x] 3.4 Implement `/api/dh/exchange` với optional private keys, full grouped steps, exposed privateKeyA/B và educational warning; verify TC-02/03, random exchange `match=true`, exact schema và không history.
- [x] 3.5 Thêm OpenAPI descriptions/examples cho năm endpoint parameter/key, nêu probable-prime/educational/private-key warning; verify route/schema inventory và không có endpoint DH ngoài sáu route đã duyệt.

## 4. Caesar Core Reuse và File Processing

- [x] 4.1 Nối shared key `K mod 26` vào Caesar core hiện hữu mà không đổi Caesar contract; verify TC-11 encrypt/decrypt, Unicode/non-ASCII preservation và SHIFT_ZERO TC-12.
- [x] 4.2 Implement `/api/dh/caesar` JSON exact fields/JSON-only response; verify encrypt/decrypt, empty input, action errors, no attachment/response_mode và exact success/warning schemas.
- [x] 4.3 Implement multipart `/api/dh/caesar` dùng existing `.txt`, strict UTF-8, BOM/content semantics và bounded reader exact 5 MiB; verify 5 MiB/5 MiB+1, `.TXT`, invalid extension/encoding, empty, BOM, CR/LF/CRLF và response luôn JSON.
- [x] 4.4 Verify request-size/multipart completion guards trả DH four-field envelope cho exact `/api/dh/*` mà không đổi old route bodies; phủ 64 MiB guard, malformed multipart và near-match paths.

## 5. Operation History và Migration

- [x] 5.1 Reconcile actual `alembic_sqlite` head của active `migrate-history-to-sqlite`; **xong khi** DH revision có đúng SQLite predecessor và không tạo/chạy PostgreSQL revision.
- [x] 5.2 Thêm SQLite migration chỉ nới cipher CHECK cho `dh`; **xong khi** upgrade giữ mọi row/index/cột/sequence và insert `rsa`/`dh` đều hợp lệ.
- [x] 5.3 Implement SQLite downgrade không xóa/sửa row DH; **xong khi** downgrade thành công khi không có DH row và fail an toàn khi row còn tồn tại.
- [x] 5.4 Cập nhật runtime model/filter cùng continuity `CIPHERS`/staging schema cho `dh`; **xong khi** transfer/verify round-trip row DH và cipher lạ vẫn bị chặn.
- [x] 5.5 Đăng ký exact matcher chỉ `/api/dh/caesar`, không qua generic route generator; **xong khi** JSON/file success/error được ghi và năm DH route khác cùng `/api/dh/encrypt|decrypt|file` không match.
- [x] 5.6 Gắn operation/length/BOM metadata cho JSON/multipart; **xong khi** source/operation/response_mode/length assertions khớp delta spec.
- [x] 5.7 Thêm privacy/best-effort assertions; **xong khi** không row/log chứa q/alpha/X/Y/K/shift/data/result/file/name/trace/warning và SQLite lỗi/schema cũ không đổi DH response.

## 6. Source Traceability và Tài liệu

- [x] 6.1 Cập nhật README và frontend integration guide với sáu endpoints, decimal-string/native-control rules, exact examples, warnings, limits và educational exclusions; verify examples parse được và không quảng bá production DH/download/history ngoài `/caesar`.
- [x] 6.2 Ghi matrix TC-01..TC-13 tới automated tests và requirement, cùng owner-approved deviations 5 MiB/status/downstream q/missing alpha/private keys/trace/history; verify không TC hoặc deviation nào thiếu reference.
- [x] 6.3 Ghi rõ primality 128-bit là Miller–Rabin probabilistic và factorization risk/benchmark evidence, phân biệt với deterministic RSA `<2^64`; verify docs không tuyên bố bảo đảm toán học hay reuse RSA nguyên trạng.

## 7. Integration Gates

- [x] 7.1 Chạy targeted DH unit/integration/OpenAPI/error/history/migration suites; verify TC-01..TC-13, strict schemas, exact status/messages và no-regression snapshots đều xanh.
- [x] 7.2 Chạy full `uv run --frozen pytest`, coverage backend >=90%, `uv run --frozen ruff check .` và `uv run --frozen ruff format --check .`; ghi exact pass/skip và không thêm exclusion che DH code.
- [x] 7.3 Chạy disposable SQLite migration/continuity rehearsal qua RSA/DH upgrade+downgrade/data preservation; **xong khi** evidence xác nhận SQLite head/registries đồng bộ và không revision PostgreSQL nào chạy trên SQLite.
- [x] 7.4 Chạy `npx -y @fission-ai/openspec@1.14.1 validate add-diffie-hellman --strict` (hoặc installed compatible CLI đã pin/verify) và `git diff --check`; verify cả hai exit 0 trên final implementation state.

## Workflow follow-up

- Sau khi implementation/review được chủ sở hữu chấp nhận ở lượt riêng, archive change bằng workflow `openspec-archive-change` và verify main specs đã nhận đầy đủ delta.
