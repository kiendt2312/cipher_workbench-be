## Context

Động lực của change xem `proposal.md` mục Why. Hiện trạng code liên quan:

- `app/core/playfair.py`: `transform_text(text, key, operation)` trả một chuỗi; nhánh decrypt gọi `strip_trailing_filler`. Cả route text (`routes_additional_text.py`) và route file (`routes_additional_file.py`) dùng hàm này như một `transformer(text, key, action) -> str` chung với Vigenère.
- `app/core/hill.py`: `_transform` trả `TransformResult` gồm `result`, `blocks`, `key`, `warnings`. Lúc decrypt, `padChar` đã được validate nhưng chưa được dùng. Dãy chữ tham gia biến đổi được giữ trong `prepared.values`/`prepared.slots`, trong đó `slots[i]` là vị trí của chữ thứ `i` trong `prepared.parts`.
- `app/api/routes_hill.py`: hai route dùng chung `HillTransformResponse` (năm trường, `extra="forbid"`).
- Các response Playfair là `TextCipherResponse`/`FileCipherResponse` hai trường. Lịch sử ghi `output_length` theo `result` (text) hoặc theo byte của attachment/result (file).

## Goals / Non-Goals

**Goals:**
- Chỉ có một nguồn sự thật cho quy tắc nhận diện ký tự đệm, nằm ở core backend. FE không phải tái hiện quy tắc nào.
- Response encrypt của mọi cipher và response của Vigenère giữ nguyên byte-for-byte.
- Không thêm route, không đổi DB/migration, không thêm dependency.

**Non-Goals:**
- Không tạo abstraction "padding strategy" dùng chung giữa các cipher (quy ước repo: không có abstract cipher interface). Mỗi core tự có hàm nhận diện riêng; điểm chung chỉ là hình dạng object `padding` ở tầng API.
- Không đổi thuật toán chèn filler/đệm khi encrypt.

## Decisions

### D1. `result` thô + object `padding` thay vì option trong request

Chủ sở hữu đã chốt (proposal mục Nguồn, 2a). Lý do kỹ thuật: toggle đổi trạng thái tức thì mà không cần round-trip, khung Phân tích Hill có đủ dữ liệu từ một response, và `result` mang cùng một ý nghĩa (bản thô) cho mọi decrypt. Phương án `options.stripPadding` bị loại: mỗi lần bật/tắt phải gọi lại API, FE phải tự giữ hai kết quả nếu muốn so sánh, và `result` đổi nghĩa theo request.

### D2. `padding` chỉ có ở decrypt

Encrypt Hill đã có W01 mô tả số chữ đệm; encrypt Playfair không có khái niệm "bản lọc". Thêm `padding` vào encrypt sẽ làm đổi contract đang ổn định mà không đem lại dữ liệu mới. Trong code, Hill dùng hai response model riêng (`HillEncryptResponse` năm trường, `HillDecryptResponse` sáu trường, đều `extra="forbid"`) để OpenAPI mô tả đúng từng route, thay vì một model có `padding` optional.

### D3. `positions` là chỉ số trong dãy chữ cái, không phải chỉ số ký tự của chuỗi

- Với Playfair, `result` chỉ gồm chữ A–Z nên hai cách đánh chỉ số trùng nhau.
- Với Hill, `result` có thể chứa Unicode ngoài BMP. Python đếm theo code point còn JS đếm theo UTF-16 code unit, nên chỉ số ký tự trong chuỗi sẽ lệch khi có emoji. Chỉ số trong dãy chữ ánh xạ thẳng sang `blocks` (khối `⌊p/m⌋`, ô `p mod m`), vừa đủ để khung Phân tích hiện "khối 4, ô 2–3" và đánh dấu ô trong "Xem từng bước".
- Để đánh dấu trên chuỗi, FE chỉ cần duyệt các chữ `[A-Za-z]` của `result` theo thứ tự.
- Phương án đánh chỉ số theo ký tự của chuỗi bị loại vì lệch giữa hai ngôn ngữ.

### D4. Trả sẵn `filtered` thay vì để FE tự tính từ `positions`

Ở Hill, việc tính bản lọc cần ánh xạ chữ sang vị trí trong chuỗi (bỏ qua dấu câu, cụm chữ Việt giữ nguyên, ký tự đệm nằm sau dấu câu cuối). Đưa việc này sang FE là nhân đôi logic dễ lệch. Đổi lại response decrypt lớn thêm khoảng bằng `result` (xem Risks).

### D5. Quy tắc nhận diện filler Playfair dựa trên cấu trúc digraph

- Lúc encrypt, filler chỉ xuất hiện ở hai chỗ: chữ thứ hai của một cặp, khi cặp kế tiếp bắt đầu bằng cùng chữ (`BA LX LO`); hoặc ở cặp cuối. Filler là `X`, hoặc `Q` khi chữ lặp là `X`.
- Ciphertext đã được validate là độ dài chẵn, nên ranh giới digraph lúc decrypt khớp chính xác ranh giới lúc encrypt.
- Bộ lọc chỉ xét chỉ số lẻ, so với chữ đứng trước và chữ đứng sau (định nghĩa chính xác ở `playfair-core`).
- Các phương án bị loại: xóa mọi `X` (`TAXICAB` → `TACAB`), và chỉ bỏ filler cuối (để lại `BALXLOON`, đúng chỗ khó chịu mà chủ sở hữu nêu).

Cài đặt: `find_filler_positions(raw: str) -> list[int]` là hàm thuần trong `playfair.py`. `transform_text` vẫn giữ chữ ký cũ nhưng nhánh decrypt trả bản thô. Thêm `decrypt_with_padding(text, keyword)` trả `(raw, positions, filtered)` cho các route. Bỏ `strip_trailing_filler` vì không còn caller.

### D6. Quy tắc Hill: tối đa `m − 1` chữ cuối bằng `padChar`, không phân biệt hoa thường

- Encrypt không bao giờ đệm quá `m − 1` chữ, nên mọi chữ trùng `padChar` vượt mức đó chắc chắn là chữ thật.
- So khớp theo giá trị 0–25 thay vì theo ký tự, vì Hill coi case là thuộc tính trình bày. Người dùng chép bản mã ở dạng chữ thường vẫn lọc được.
- Lúc decrypt, `padChar` lấy từ `options` của request. FE phải gửi lại đúng `padChar` đã dùng khi encrypt.

Cài đặt trong `_transform` của Hill, chỉ ở nhánh decrypt:
1. Đếm từ cuối `prepared.values` sau khi giải mã.
2. Bản lọc: tạo bản sao `prepared.parts`, gán chuỗi rỗng tại `slots[p]` của từng vị trí, rồi join.
3. `TransformResult` thêm khóa `padding`.

Chi phí thêm là O(m) cho bước đếm và O(n) cho một lần join.

### D7. Trường multipart `strip_padding` chỉ cho `/api/playfair/file`

- Spec hiện hành bắt buộc FE tải file upload qua attachment, không được tự tạo từ preview. Vì vậy attachment phải khớp với toggle, và cần một tham số trong request.
- Tên `strip_padding` theo quy ước snake_case của multipart (`response_mode`). Giá trị phân biệt hoa thường như `action`/`response_mode`.
- Validate bằng hàm riêng `validate_strip_padding`, gọi ngay sau `validate_additional_file_form_fields` (tức sau `response_mode`, trước extension) và chỉ khi `cipher == "playfair"`. Cách này giữ nguyên chữ ký hàm cũ. Vigenère không đọc part này, nên hành vi với part lạ giữ nguyên.
- Ở content mode, trường này được validate nhưng không đổi JSON: JSON đã chứa cả hai bản.
- Phương án bị loại: attachment luôn là bản thô (lệch với toggle), và attachment luôn là bản lọc (trái nguyên tắc "bản thô là kết quả chuẩn").

### D8. Hình dạng model API

`PaddingInfo` (pydantic, `extra="forbid"`) có các trường `count: int ≥ 0`, `positions: list[int]` và `filtered: str`. Các model dùng nó:
- `PlayfairDecryptResponse(success, result, padding)` cho `POST /api/playfair/decrypt`. Route encrypt giữ `TextCipherResponse`.
- `_process_file` của Playfair decrypt: content mode trả `{"success","result","padding"}`, file mode chọn body theo `strip_padding`. Schema OpenAPI của route file mô tả content-mode JSON dạng `oneOf` (hai trường hoặc ba trường).
- `HillDecryptResponse` lồng chính `PaddingInfo`, để FE dùng chung một type.

### D9. Lịch sử thao tác không đổi schema

`output_length` tiếp tục đo trên đầu ra chính thực sự trả về:
- text và content mode: `result` (bản thô);
- file mode: body attachment (bản lọc khi `strip_padding=true`), vẫn tính BOM như hiện hành.

Không ghi `padding`, `positions` hay `strip_padding` vào lịch sử, vì đây không phải metadata đã được phép lưu.

## Risks / Trade-offs

- [FE Playfair đang hiển thị `result` sẽ thấy thêm filler sau khi deploy] → Hướng dẫn FE thêm mục breaking change "0.x" kèm bảng trước/sau và việc cần làm. Nên deploy BE cùng lúc FE dùng `padding.filtered`/toggle. Cho tới lúc đó, hành vi "đúng toán" của `result` vẫn đọc được.
- [Lọc nhầm chữ thật trùng mẫu ký tự đệm (Hill `MAX` → `MA`, Playfair `AX` → `A`, chuỗi `aXa` ở ranh giới digraph)] → `result` luôn giữ bản thô, toggle cho phép tắt, hướng dẫn FE yêu cầu luôn xem được bản thô và có thể đánh dấu vị trí lọc bằng `positions`.
- [Response decrypt lớn hơn: file Playfair 5 MiB ở content mode có thể sinh JSON khoảng 10 MiB] → Vẫn dưới trần hạ tầng 64 MiB (trần này chỉ áp cho request). Hill vốn đã có `blocks` lớn hơn nhiều. Ghi chú trong hướng dẫn FE. Không thêm gate hiệu năng mới.
- [Người dùng decrypt Hill với `padChar` khác lúc encrypt nên không lọc được] → Hướng dẫn FE nêu rõ cần gửi lại cùng `padChar`. Khung Phân tích hiển thị `padChar` đang dùng.
- [Bỏ `strip_trailing_filler` làm vỡ test/import cũ] → Cập nhật test trong cùng change. Không có caller nào ngoài `playfair.py`.

## Migration Plan

1. Merge và deploy backend. Không có migration DB.
2. Gửi FE mục breaking change trong `repo_docs/frontend-integration.md` và helper mẫu mới trong `repo_docs/examples/cipher-api.ts`.
3. Rollback: revert commit của change. Contract quay về quy tắc Playfair ngày 2026-09-28 và Hill năm trường. Không có dữ liệu cần dọn.

## Open Questions

- Mặc định bật hay tắt toggle trên giao diện: FE/chủ sở hữu quyết định khi làm UI. Backend trung lập vì luôn trả cả hai bản.
