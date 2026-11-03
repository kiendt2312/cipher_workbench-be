## Why

Khi giải mã, Hill hiện trả nguyên ký tự đệm (`HQKRJYDPDONU` → `THUDOHANOIXX`). Playfair thì tự cắt đúng một filler cuối nhưng vẫn giữ X chèn giữa cặp chữ lặp (`BALXLOON`). Ngày 2026-10-01, chủ sở hữu yêu cầu bỏ XX cuối của Hill "giống Playfair" và đồng bộ hai hệ mã theo chuẩn chung của các web crypto: luôn có bản giải mã thô toán học, kèm toggle "Tự động lọc ký tự đệm (Playfair/Hill padding)". Lọc mù mọi chữ X là sai (`TAXICAB` → `TACAB`), nên backend phải chỉ rõ ký tự nào là đệm thay vì xóa ngầm.

## What Changes

- Response **decrypt** của Playfair (text, file `response_mode=content`) và Hill có thêm object `padding` gồm `count`, `positions` (vị trí 0-based trong chuỗi chữ cái tham gia biến đổi) và `filtered` (bản đã lọc). Nhờ đó FE bật/tắt toggle ngay mà không gọi lại API. Response encrypt của hai hệ mã không đổi.
- `result` của decrypt luôn là **bản thô toán học**, không xóa ký tự nào.
  - **BREAKING (Playfair):** `result` decrypt không còn tự bỏ một filler cuối như quy tắc ngày 2026-09-28. Ví dụ `PDGW` → `ABXQ` (trước là `ABX`); bản đã lọc nằm ở `padding.filtered`.
  - Hill: `result` giữ như hiện tại (`HELLOX`), chỉ thêm `padding`.
- Bộ lọc Playfair nhận diện filler theo cấu trúc digraph: chữ thứ hai của một cặp là `X` (hoặc `Q` khi chữ đầu là `X`) **và** (cặp kế tiếp bắt đầu bằng đúng chữ đầu của cặp đó **hoặc** cặp này là cặp cuối). Kết quả: `BALXLOON` → `BALLOON`, `TAXICABX` → `TAXICAB`, `XQXQ` → `XX`. X thật nằm giữa chữ khác nhau được giữ.
- Bộ lọc Hill nhận diện tối đa `m − 1` chữ cuối có giá trị bằng `options.padChar` (mặc định `X`, không phân biệt hoa thường). Lúc decrypt, `padChar` giờ có tác dụng cho việc nhận diện; phép giải mã ma trận không đổi. `blocks` vẫn chứa đủ khối có đệm.
- `POST /api/playfair/file` nhận thêm trường multipart tùy chọn `strip_padding` = `true|false` (mặc định `false`), để attachment ở `response_mode=file` khớp với trạng thái toggle. Giá trị sai trả HTTP 422 với message tiếng Việt mới.
- Cập nhật OpenAPI và hướng dẫn FE: mục breaking change mới, toggle lọc ký tự đệm, phần "Lọc ký tự đệm" trong khung Phân tích của Hill, helper client mẫu giữ `padding`.

## Capabilities

### New Capabilities

- `padding-filter`: hợp đồng chung của object `padding` trên response decrypt Playfair/Hill (cấu trúc, bất biến giữa `result`/`positions`/`filtered`, ranh giới với encrypt) và cách FE dùng nó cho toggle.

### Modified Capabilities

- `playfair-core`: decrypt trả bản thô; thêm quy tắc nhận diện filler giữa cặp trùng và filler cuối; cập nhật vector `GWGW`.
- `additional-text-cipher-api`: response decrypt Playfair có ba trường `success`, `result`, `padding`; response Vigenère và encrypt Playfair giữ hai trường.
- `additional-file-cipher-api`: content mode decrypt Playfair có `padding`; thêm trường `strip_padding` cho attachment; cập nhật hành vi nội dung file và precedence.
- `additional-cipher-error-handling`: thêm message cho `strip_padding` sai và vị trí của nó trong thứ tự lỗi.
- `hill-core`: decrypt nhận diện ký tự đệm cuối theo `padChar`, nhưng không xóa khỏi `result`.
- `hill-text-cipher-api`: response decrypt Hill có sáu trường top-level (thêm `padding`); OpenAPI và hướng dẫn FE mô tả toggle và phần lọc trong khung Phân tích.

## Impact

- Code: `app/core/playfair.py`, `app/core/hill.py`, schema/route Playfair text/file (`app/api/schemas.py`, `routes_additional_text.py`, `routes_additional_file.py`), `app/api/routes_hill.py`, `app/errors/messages.py`/`exceptions.py`.
- Contract: Playfair decrypt đổi giá trị `result` (breaking với FE đang dựa vào việc tự cắt filler cuối). Hill decrypt thêm một field. Không thêm route, không đổi status code hay message cũ, không đổi lịch sử, DB hay migration.
- Kích thước response decrypt tăng vì có thêm chuỗi `filtered` (tối đa khoảng gấp đôi phần `result`). Hill vốn đã có `blocks` lớn hơn nhiều.
- Tài liệu: `repo_docs/frontend-integration.md`, `repo_docs/examples/cipher-api.ts`, README (bảng endpoint/contract nếu nhắc đến hành vi filler).
- Test: unit cho hai bộ lọc, integration cho text/file/Hill, cập nhật các test đang kỳ vọng Playfair tự cắt filler cuối.

## Ngoài phạm vi

- FE implementation (toggle, highlight ký tự đệm, phần "Lọc ký tự đệm" trong khung Phân tích); backend chỉ cung cấp dữ liệu và hướng dẫn. Mặc định bật hay tắt toggle do FE quyết định.
- Thay đổi thuật toán mã hóa/giải mã, quy tắc chèn filler của Playfair, quy tắc đệm của Hill, encrypt response, DES (PKCS#7 đã bỏ đệm xác định), Vigenère, Caesar, Affine, Columnar.
- Khôi phục lossless chữ thật trùng hình dạng với ký tự đệm (ví dụ Hill `MAX`, Playfair `AX`): ciphertext không mang thông tin này. Toggle tắt sẽ cho người dùng xem bản thô.
- Lưu số ký tự đệm từ encrypt để dùng lúc decrypt; tham số `strip_padding` cho endpoint text hoặc cho Vigenère.

## Nguồn và quyết định ưu tiên

1. Yêu cầu của chủ sở hữu ngày 2026-10-01 (nhóm Cipher workbench): bỏ ký tự đệm cuối khi giải mã Hill "giống Playfair"; đồng bộ Playfair/Hill theo hướng luôn có bản giải mã thô và toggle lọc ký tự đệm; thêm phần lọc vào khung Phân tích của Hill.
2. Quyết định chủ sở hữu ngày 2026-10-01 trong change này: (a) backend trả cả bản thô (`result`) lẫn bản lọc (`padding.filtered`) thay vì option trong request; (b) bộ lọc Playfair bỏ cả filler giữa cặp chữ lặp lẫn filler cuối.
3. Mâu thuẫn với các quyết định cũ được giải quyết như sau: quy tắc "padding không tự bị xóa khi decrypt" của Hill (Q5, Q7, Q16 ngày 2026-09-29) **được giữ** cho `result` và mở rộng bằng `padding`. Quy tắc "decrypt Playfair bỏ đúng một filler cuối" (2026-09-28) **bị thay thế**: `result` trở về bản thô, việc lọc chuyển sang `padding.filtered`. Giới hạn "plaintext chẵn kết thúc bằng X mất X cuối" chỉ còn áp dụng cho `filtered`.
4. Các main spec hiện hành tiếp tục là nguồn cho mọi contract không nêu ở trên: validation, error envelope, giới hạn kích thước, lịch sử, file pipeline.
