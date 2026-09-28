## 1. Baseline và characterization tests

- [x] 1.1 Ghi nhận bằng test hiện có rằng baseline có đúng 12 cipher POST routes và chụp contract route/schema/status/guard của Caesar, Vigenère, Playfair, Affine trước khi include Columnar. **Xong khi:** test characterization xanh trên commit baseline và không sửa behavior/runtime cũ.
- [x] 1.2 Thêm unit tests thất bại cho ASCII-only trim, post-trim length 2.048/2.049, numeric grammar/separators/braces, compact digits, leading zero, empty token, sign/decimal/exponent/Unicode digit, exact permutation và bounds `m=2/256`. **Xong khi:** bảng valid/invalid khóa phủ mọi rule của `columnar-core` và lỗi test chỉ do implementation chưa có.
- [x] 1.3 Thêm unit tests thất bại cho keyword ASCII, case-insensitive stable ranking, `BALLOON → [2,1,3,4,6,7,5]`, duplicate tie-break và non-ASCII/length bounds. **Xong khi:** ranking/grammar keyword có test trực tiếp, tách khỏi HTTP.
- [x] 1.4 Thêm unit tests thất bại cho sáu canonical vector, decrypt-back, randomized round-trip, uneven rows, empty core input, `m>n`, whitespace/CRLF, combining mark, non-leading BOM và non-BMP code point. **Xong khi:** test chứng minh exact code-point round-trip, không padding/normalization.

## 2. Columnar Core

- [x] 2.1 Tạo `app/core/columnar.py` với constants ASCII trim/bounds và parser numeric nhỏ không dùng Unicode `strip`/`isdigit`/`\d`; numeric grammar được thử trước keyword. **Xong khi:** toàn bộ test parser mục 1.2 xanh, parser trả rank exact và mọi invalid content dùng một domain failure không chứa raw key.
- [x] 2.2 Cài keyword ranking ổn định bằng letter case-insensitive cùng original index, không normalize Unicode. **Xong khi:** test mục 1.3 xanh cho case variants, duplicate và bounds 2/256.
- [x] 2.3 Cài encrypt bằng physical-column strides và decrypt bằng physical-column lengths/rank map, không dựng padding matrix. **Xong khi:** mọi canonical/randomized/Unicode/uneven/`m>n` test mục 1.4 xanh và output length luôn bằng input length.
- [x] 2.4 Mở rộng layering test hiện có cho module Columnar. **Xong khi:** core chỉ dùng standard library, không import FastAPI/Starlette/Pydantic hoặc layer `app.api`, `app.services`, `app.errors`.

## 3. Schema, surrogate và Exception Handling

- [x] 3.1 Thêm request model/decoder JSON Columnar riêng với media rule hiện hành, duplicate detection, exact `text,key` shape và không coercion. **Xong khi:** malformed/non-object/unknown/duplicate đều trả canonical invalid-body, `application/*+json` được nhận và schema text cũ không đổi.
- [x] 3.2 Thêm helper validate JSON surrogate sau decode: xác nhận pair hợp lệ đã thành scalar và từ chối mọi surrogate còn sót trong member names/string values trước field validation. **Xong khi:** escaped pair có parity với literal non-BMP, mọi lone/misordered surrogate trả invalid-body 422 và không có response encode 500.
- [x] 3.3 Thêm validator text theo đúng `text → key missing/empty → key type → key content`, dùng ASCII-only trim và parser core chung. **Xong khi:** tests nhiều lỗi đồng thời chỉ trả lỗi ưu tiên cao nhất, whitespace-only text hợp lệ và JSON number/bool/object key không được coercion.
- [x] 3.4 Thêm validator multipart exact `file,key,action,response_mode` dựa trên `multi_items()`, phân loại upload/scalar và validation theo thứ tự contract. **Xong khi:** unknown/duplicate, missing/scalar file, key upload part, missing/type/content key, action/mode đều map đúng lỗi/precedence.
- [x] 3.5 Thêm canonical message và exception invalid-key Columnar tối thiểu, tái sử dụng message/exception shared cho các lỗi còn lại. **Xong khi:** mọi error body có đúng hai field, message nguyên văn, exception không lưu raw key và mapping 12 route cũ không đổi.

## 4. HTTP Adapter text và OpenAPI

- [x] 4.1 Thêm router `POST /api/columnar/encrypt` và `POST /api/columnar/decrypt` gọi decoder/validator strict rồi core theo operation. **Xong khi:** canonical numeric/keyword vectors, Unicode, whitespace, uneven rows, `m>n` và decrypt-back trả exact success envelope.
- [x] 4.2 Khai báo OpenAPI text tag `Columnar Transposition`, exact request `text:string,key:string`, response 200/413/422/500 và key prose cùng examples `3 1 4 2`, `BALLOON` không `pattern`/`oneOf`/`maxLength`. **Xong khi:** contract test kiểm schema/media/status/examples và runtime vẫn nhận vendor `+json` dù docs chỉ quảng bá `application/json`.
- [x] 4.3 Include router text trong app assembly mà không thêm generalized/versioned route. **Xong khi:** inventory tạm có đúng 14 cipher POST routes và tám text route cũ giữ nguyên behavior/schema.

## 5. File Processing, HTTP Adapter file và guards

- [x] 5.1 Thêm `POST /api/columnar/file` dùng raw-form validator rồi tái sử dụng helper extension/read-limit/UTF-8/BOM/filename/attachment hiện tại; giải phóng raw bytes sau decode. **Xong khi:** text/file cùng key/input tạo cùng logical result, zero-byte bị từ chối nhưng BOM-only hợp lệ và không có file pipeline song song.
- [x] 5.2 Cài `response_mode=content|file` cho encrypt/decrypt, giữ preview/download là hai request stateless. **Xong khi:** content trả exact JSON không BOM/header attachment; file trả exact UTF-8 bytes, conditional BOM, `text/plain; charset=utf-8` và server-owned filename.
- [x] 5.3 Khai báo OpenAPI file exact `file,key,action,response_mode`, tag Columnar, key prose cùng examples `3 1 4 2`, `BALLOON` không keywords gây hiểu sai, response 200 có JSON/text và error 413/415/422/500 có JSON. **Xong khi:** contract test đối chiếu exact required/optional fields, examples, enum/default, media và statuses.
- [x] 5.4 Thêm đúng `/api/columnar/file` vào `FILE_ROUTE_PATHS`, không đổi middleware/constants/header behavior. **Xong khi:** set equality có đúng năm file routes, >64 MiB text/file dùng đúng message và truncated multipart Columnar trả invalid-body trước field validation.
- [x] 5.5 Include router file trong app assembly. **Xong khi:** app có chính xác 15 cipher POST routes gồm đúng ba Columnar paths và không có path ngoài scope.

## 6. Integration và contract tests

- [x] 6.1 Phủ text integration matrix cho exact/duplicate/unknown fields, malformed/non-object/media, empty-vs-whitespace, key missing/type/content, 2/256 bounds, 2.048/2.049 length và full precedence. **Xong khi:** từng case khớp exact status/message/body và chỉ một lỗi được trả.
- [x] 6.2 Phủ surrogate integration matrix cho lone high/low/misordered ở member name/text/key, valid escaped pair, literal emoji và pair qua encrypt/decrypt. **Xong khi:** lone luôn là invalid-body 422 trước field errors và valid pair được tính là một code point.
- [x] 6.3 Phủ multipart shape/precedence cho unknown/duplicate, missing file, file scalar, `filename=""`, key upload/string errors, action/mode và extension. **Xong khi:** thứ tự `framing/shape → file → key → action → mode → extension` được khóa bằng multi-error cases.
- [x] 6.4 Phủ file bytes cho MIME ignored, `.TXT`/double extension, đúng 5.242.880 và 5.242.881 byte kể cả BOM, zero/BOM-only, strict UTF-8, CRLF, combining/non-BMP và non-leading `U+FEFF`. **Xong khi:** mọi status/message/result khớp specs, không commit fixture lớn.
- [x] 6.5 Phủ attachment headers/bytes/filename cho encrypt/decrypt, BOM có/không, nhiều dấu chấm, path component và Unicode; phủ file-mode error vẫn JSON. **Xong khi:** body/header exact và client không cần tự dựng authoritative filename/BOM.
- [x] 6.6 Phủ contract cho canonical vectors, text/file parity, exact 15 routes, OpenAPI tags/schemas/examples/media/status, năm-route guards, stateless preview/download và safe 500 logging. **Xong khi:** test phát hiện mọi metadata thừa hoặc raw text/key/file/result marker trong log.

## 7. Hồi quy và quality gates trước tài liệu

- [x] 7.1 Chạy targeted Columnar unit/integration/contract tests và sửa mọi failure trong phạm vi change. **Xong khi:** toàn bộ test Columnar xanh, không skip/xfailed để né contract.
- [x] 7.2 Chạy `uv run pytest` gồm regression của 12 route cũ. **Xong khi:** full suite xanh và backend branch coverage tối thiểu 90% không thêm exclusion che code mới.
- [x] 7.3 Chạy `uv run ruff check .`, `uv run ruff format --check .` và `openspec validate add-columnar-transposition-cipher --strict`. **Xong khi:** cả ba command exit 0 trên cùng worktree state.
- [x] 7.4 Rà diff dependency/layering/scope. **Xong khi:** không có dependency mới, generalized API/factory/registry, UI runtime change, auth/database/CORS/deployment, padding/normalization hoặc chỉnh completed OpenSpec changes.

## 8. README, Frontend guide, Web UI và Docker scope

- [x] 8.1 Chỉ sau mục 7 xanh, cập nhật mọi section stale trong `README.md` từ 4 cipher/12 routes lên 5 cipher/15 routes, gồm paths, key grammar/examples, vectors, Unicode/surrogate, file/error/guard và migration notes. **Xong khi:** README phản ánh verified runtime, không coi HTML/client là authority và không còn claim inventory cũ.
- [x] 8.2 Cập nhật `repo_docs/frontend-integration.md` cho selector/route/schema Columnar, exact JSON/multipart fields, key parsing guidance, preview/download, OpenAPI/error precedence và migration 12→15. **Xong khi:** guide không yêu cầu FE implementation trong backend change và không hướng client gửi key kiểu number.
- [x] 8.3 Xác minh Web UI/static/templates, Docker/deployment files, dependency manifests và HTML upload không bị sửa/copy/import. **Xong khi:** diff chỉ có runtime/test/docs cần thiết; không có visual matrix, animation, client-side cipher, Docker hay dependency change.

## 9. Final validation và independent audit

- [x] 9.1 Sau cập nhật docs, chạy lại `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` và strict OpenSpec validation. **Xong khi:** mọi gate exit 0, branch coverage vẫn ≥90% và kết quả được ghi nhận từ state cuối.
- [x] 9.2 Thực hiện independent code/spec audit đối chiếu owner contract, bốn delta specs và fixed baseline `c55278f207e84811cf26e3a748df612cd6a9915e`. **Xong khi:** mọi finding material được sửa hoặc ghi rõ decision/risk; auditor xác nhận không reuse evidence từ worktree đã xóa.
- [x] 9.3 Kiểm tra integrity cuối. **Xong khi:** completed OpenSpec changes không đổi/không archive, không commit/push, HTML reference không vào repo và `git diff` chỉ chứa artifact/implementation/test/docs thuộc change.
