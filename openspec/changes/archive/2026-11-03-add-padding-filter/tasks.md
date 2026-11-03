## 1. Baseline và test thuật toán

- [x] 1.1 Chạy full test hiện có và liệt kê các test đang kỳ vọng Playfair tự bỏ filler cuối (`tests/unit/test_playfair.py`, `tests/integration/test_additional_text_endpoints.py`, `tests/integration/test_additional_file_endpoints.py`) cùng test Hill kỳ vọng đúng năm trường ở decrypt. **Xong khi:** baseline xanh và có danh sách test sẽ đổi kỳ vọng.
- [x] 1.2 Viết unit test cho bộ nhận diện filler Playfair theo `playfair-core`: `BALXLOON`, `TAXICABX`, `ABXQ`, `ABCX`, `XQXQ`, `AX`, `IXIGSAWX`, vector canonical (vị trí `19`), `BOOKKEEPER` không có filler, và chữ ở chỉ số chẵn không bao giờ bị nhận diện. **Xong khi:** test đỏ đúng chỗ, trước khi cài.
- [x] 1.3 Viết unit test cho nhận diện ký tự đệm Hill theo `hill-core`: T06 `HELLOX`, `HELLO!X`, `THUDOHANOIXX` (vị trí `10,11`), `ACN→XXX` (giới hạn `m−1`), `padChar="Q"` và mặc định, chữ thường `hellox`, cụm chữ Việt giữ nguyên nằm giữa không lệch vị trí. Kiểm thêm bất biến `count = len(positions)` và `filtered = result bỏ chữ tại positions`. **Xong khi:** test đỏ đúng chỗ, encrypt không có khóa `padding`.

## 2. Playfair Core

- [x] 2.1 Trong `app/core/playfair.py`, thêm `find_filler_positions(raw)` và `decrypt_with_padding(text, keyword) -> (raw, positions, filtered)`. Cho nhánh decrypt của `transform_text` trả bản thô và bỏ `strip_trailing_filler`. **Xong khi:** test mục 1.2 xanh, vector encrypt/decrypt canonical giữ nguyên ở dạng thô, core không import tầng API.

## 3. Hill Core

- [x] 3.1 Trong `_transform` của `app/core/hill.py`, chỉ ở nhánh decrypt: đếm tối đa `m−1` chữ cuối bằng `padChar` theo giá trị 0–25, dựng `filtered` bằng cách bỏ đúng `slots` tương ứng trong bản sao `parts`, rồi thêm khóa `padding` vào `TransformResult`. **Xong khi:** test mục 1.3 xanh, `result`/`blocks`/`warnings` của encrypt và decrypt không đổi so với baseline, round-trip 1000 khóa vẫn xanh.

## 4. Schema, Exception Handling và HTTP Adapter

- [x] 4.1 Thêm model `PaddingInfo` (`extra="forbid"`) và `PlayfairDecryptResponse`; nối `POST /api/playfair/decrypt` qua `decrypt_with_padding`. Encrypt và Vigenère giữ `TextCipherResponse`. **Xong khi:** API trả đúng body ở `additional-text-cipher-api` (`PDGW → ABXQ` + padding), encrypt/Vigenère vẫn đúng hai key.
- [x] 4.2 Thêm message `Tùy chọn lọc ký tự đệm phải là true hoặc false.` vào `app/errors/messages.py` cùng exception 422 tương ứng. Mở rộng `validate_additional_file_form_fields` để validate `strip_padding` chỉ cho Playfair, ngay sau `response_mode`. **Xong khi:** `TRUE`/`1`/`yes`/rỗng trả 422 đúng message; precedence `response_mode` sai thắng `strip_padding` sai, `strip_padding` sai thắng extension sai; Vigenère bỏ qua part này như trước.
- [x] 4.3 Cập nhật `_process_file` cho Playfair decrypt. Content mode trả `success,result,padding` (BOM không có trong `result`/`filtered`). File mode chọn body là bản thô hoặc bản lọc theo `strip_padding`, giữ filename/BOM. `output_length` lịch sử đo đúng body trả về. **Xong khi:** các scenario `additional-file-cipher-api` xanh, kể cả `strip_padding=true` ở encrypt và ở content mode không đổi kết quả.
- [x] 4.4 Tách `HillEncryptResponse` (năm trường) và `HillDecryptResponse` (sáu trường, lồng `PaddingInfo`) trong `app/api/routes_hill.py`. **Xong khi:** decrypt `DPDKKB` trả đúng sáu key và `padding` `{count:1,positions:[5],filtered:"HELLO"}`; encrypt vẫn đúng năm key; lỗi Hill không có `padding`.
- [x] 4.5 Cập nhật OpenAPI: schema `padding` cho Playfair decrypt, Hill decrypt và content mode của `/api/playfair/file` (`oneOf` hai hoặc ba trường); khai báo trường form `strip_padding`; mô tả vai trò của `padChar` lúc decrypt. **Xong khi:** test contract OpenAPI xanh và `/openapi.json` hiển thị đúng các schema trên.

## 5. Test integration và regression

- [x] 5.1 Cập nhật các test Playfair cũ từ "bỏ filler cuối" sang bản thô + `padding`, và thêm integration test cho mọi scenario mới của `padding-filter`, `additional-text-cipher-api`, `additional-file-cipher-api`, `additional-cipher-error-handling`. **Xong khi:** không còn assertion nào dựa vào quy tắc ngày 2026-09-28; body được so khớp nguyên văn.
- [x] 5.2 Thêm integration test Hill decrypt (sáu trường, `padChar` tùy chọn, dấu câu cuối) và regression cho response encrypt của mọi cipher, Vigenère, DES, lịch sử (`output_length` text/content/file). **Xong khi:** suite regression xanh và không có migration mới.

## 6. Tài liệu FE và quality gates

- [x] 6.1 Cập nhật `repo_docs/frontend-integration.md`:
  - thêm mục breaking change "0.x Lọc ký tự đệm Playfair/Hill (`2026-10-01`)", gồm bảng trước/sau `PDGW`, `GWGW`, `BMODZBXDNAGE`, `DPYRANQO` và việc FE cần làm;
  - mô tả toggle `Tự động lọc ký tự đệm (Playfair/Hill padding)`, cách dùng `positions` để đánh dấu, giới hạn lọc nhầm, `strip_padding` cho attachment;
  - mô tả phần "Lọc ký tự đệm" trong khung Phân tích Hill (padChar, số ký tự, khối/ô, bản thô/bản lọc);
  - cập nhật hoặc thay thế mục 0.3 và copy cảnh báo Playfair ở mục 11.

  **Xong khi:** tài liệu khớp runtime và không còn hướng dẫn "hiển thị nguyên result đã bỏ filler".
- [x] 6.2 Cập nhật `repo_docs/examples/cipher-api.ts`: type `PaddingInfo`; `HillTransformResponse` có `padding?` ở decrypt; helper Playfair decrypt giữ `result` và `padding` cho text/preview file; tham số `stripPadding` cho download file Playfair. **Xong khi:** `tsc --strict --noEmit` xanh và helper cũ của các cipher khác không đổi chữ ký.
- [x] 6.3 Cập nhật README nếu có chỗ nhắc hành vi filler Playfair hoặc response Hill. Chạy `uv run --frozen pytest`, `uv run --frozen ruff check .`, `uv run --frozen ruff format --check .`, kiểm coverage ≥ 90% và `openspec validate add-padding-filter --strict`. **Xong khi:** mọi gate xanh trên state cuối.
- [x] 6.4 Rà diff theo bảy delta spec và quyết định chủ sở hữu ngày 2026-10-01. **Xong khi:** không đổi thuật toán encrypt, không đổi response encrypt/Vigenère/các cipher khác, không lưu dữ liệu nhạy cảm, không commit file `.docx`/`.html` tham chiếu.
  - Gates 2026-10-02: `1318 passed, 14 skipped`, coverage `95,07%`; Ruff check/format, `tsc --strict --noEmit` cho `cipher-api.ts`, `git diff --check` và `openspec validate add-padding-filter --strict` đều xanh.
  - Đo Playfair 5 MiB (Python 3.12.3, Linux x86_64): decrypt thô `1,099s`, decrypt kèm nhận diện filler `1,449s`; Hill chỉ thêm O(m) + một lần join.
