## Context

Repo có sáu cipher với core tách khỏi HTTP (`app/core` chỉ dùng thư viện chuẩn, được kiểm bằng `tests/unit/test_layering.py`), router/schema tường minh cho từng feature, handler lỗi chung hai trường, guard 64 MiB và multipart completion guard theo `FILE_ROUTE_PATHS`, lịch sử metadata ghi bằng middleware theo bảng route trong `app/history/routes.py`. Hill là ngoại lệ có envelope lỗi riêng và không có file route; Affine/Columnar là mẫu cho decoder JSON strict và file route có exact field set. Xem `proposal.md` cho động cơ, quyết định Q1–Q21 và bảng khác biệt nguồn; xem bảy delta spec cho contract chính xác.

## Goals / Non-Goals

**Goals:**

- Một lõi DES đọc được, đối chiếu được với bài giảng, ra đúng T01–T20 và giá trị trung gian T01; nhanh vừa đủ cho 5 MiB trong vài giây.
- Bốn route DES dùng lại tối đa hạ tầng sẵn có: handler lỗi hai trường, pipeline file, guard, middleware lịch sử.
- Không đổi status, body, route hoặc OpenAPI của sáu cipher hiện có.

**Non-Goals:**

- Bản cài thứ hai tối ưu (bitslice, numpy), thư viện mật mã runtime, 3DES/AES, chế độ ngoài ECB/CBC.
- Performance test tự động; UI.

## Decisions

### 1. Một module core với bảng chuẩn và bảng tra dẫn xuất

Thêm `app/core/des.py` chứa nguyên văn bảng PC-1, PC-2, LS, IP, IP⁻¹, E, P, S1–S8 (đánh số từ 1 như tài liệu) và hàm `permute` tổng quát trên số nguyên. Từ các bảng này, lúc import, module dựng bảng tra: 8 bảng SP (S-box kết hợp P, 64 phần tử mỗi bảng), bảng IP/IP⁻¹ theo byte, và E bằng dịch bit. Đường mã hóa hàng loạt dùng bảng tra; đường trace dùng `permute` và S-box gốc để lộ từng bước. Cả hai được test chéo trên cùng vector và dữ liệu ngẫu nhiên. Đây vẫn là "một bản cài" theo Q20: một nguồn bảng duy nhất, không engine song song kiểu bitslice/numpy.

Phương án đã loại: bitslice đạt khoảng 0,12 giây cho ECB nhưng S-box thành mạch logic hàng trăm phép toán, không đối chiếu được với bài giảng; numpy phá luật layering và vẫn không nhanh hơn cho mã hóa CBC.

### 2. API core trên bytes, lỗi core có mã

Core cung cấp: chuẩn hóa/parse khóa, IV và hex; `key_schedule`; mã hóa/giải mã bytes theo ECB/CBC; PKCS#7 pad/unpad; nhận diện khóa yếu/nửa yếu; đếm khối lặp; `trace_block`. Lỗi miền (hex sai ký tự, sai độ dài, padding, UTF-8) là `DesError` mang mã (`E03`…`E08`, `E13`) và số liệu cần cho message, không mang dữ liệu người dùng. Message tiếng Việt nằm ở `app/errors/messages.py`, adapter chuyển mã thành exception HTTP. Core không biết HTTP status.

### 3. Lỗi DES dùng `AppError` hai trường

Thêm một exception `DesError(AppError)` ở `app/errors/exceptions.py` nhận status và message đã format, đi qua handler chung nên body đúng `{success:false,message}`. Không mở rộng handler Hill. Message có tham số (`{n}`, `{name}`) dùng template trong `messages.py`; message tĩnh được thêm vào `CANONICAL_MESSAGES` chỉ khi cần cho `HTTPException` (không cần ở change này).

### 4. Decoder JSON strict theo mẫu Hill/Affine

Thêm `app/api/des_schemas.py`: kiểm media type như route hiện hành, parse raw JSON với phát hiện field trùng, yêu cầu object, kiểm tập field cho từng route (`encrypt`, `decrypt`, `trace`). Kiểu: `text`/`key`/`block` là string hoặc null; `iv` string hoặc null; enum nhận mọi kiểu rồi mới phân loại E10. Sau parse, validator thực thi thứ tự lỗi của `des-error-handling`: body → E12 (đếm `len(s.encode("utf-8"))`) → E10 → khóa → IV → dữ liệu. Hex hợp lệ được kiểm bằng tập ký tự tường minh, không dùng `int(x, 16)` (vốn chấp nhận `0x`, `_` và chữ số Unicode).

### 5. Router DES và chạy core ngoài event loop

Thêm `app/api/routes_des.py` (encrypt, decrypt, trace) và `app/api/routes_des_file.py` (file), include ở `app/main.py` với tag `DES`. Response model pydantic `extra="forbid"` cho success, warning và trace để OpenAPI mô tả chính xác. Vì 5 MiB tốn khoảng 6 giây CPU, route gọi core qua `starlette.concurrency.run_in_threadpool` để không chặn các request khác; core thuần nên an toàn khi chạy trong thread.

### 6. File route dùng lại pipeline hiện hành

`routes_des_file.py` theo cấu trúc `routes_affine_file.py`: parse multipart với exact field set và phát hiện field trùng, rồi theo thứ tự trong `des-error-handling`; đọc file bằng `read_limited_bytes`, decode bằng helper hiện hành (giữ cờ BOM), tạo tên bằng `build_result_filename` và header bằng `build_content_disposition`. Thêm `/api/des/file` vào `FILE_ROUTE_PATHS` để guard 64 MiB và multipart completion guard nhận diện. Ghi chú history (`note_history`) theo cách các file route khác làm: chỉ độ dài byte.

### 7. Lịch sử và migration

Thêm `des` vào `CIPHERS` trong `app/db/models.py`. `_routes_for` đã sinh `/encrypt`, `/decrypt`, `/file` cho mỗi cipher nên DES tự có đúng ba route ghi lịch sử; `/api/des/trace` không nằm trong bảng nên không được ghi. Thêm `alembic/versions/0003_allow_des_cipher_operations.py` theo mẫu `0002`: drop rồi tạo lại CHECK `ck_cipher_operations_cipher` với `des`; downgrade về danh sách có `hill`.

### 8. Test và đối chiếu

`cryptography` vào nhóm dev (`uv add --dev cryptography`); test đối chiếu dùng DES qua `TripleDES` (`cryptography.hazmat.decrepit`) với khóa 8 byte lặp ba lần để tránh cảnh báo deprecation. Test layering không đổi vì chỉ `tests/` import thư viện này. Bố cục: `tests/unit/test_des.py` (bảng, khóa con, vòng, T01–T13, T17–T19, PKCS#7, CBC, khóa yếu, trace, 1000 lần ngẫu nhiên), `tests/integration/test_des_endpoints.py` (toàn bộ route, decoder, thứ tự lỗi, biên 5 MiB, mỗi lỗi một test, OpenAPI, guard, log 500, regression envelope cũ), bổ sung test lịch sử hiện có.

## Risks / Trade-offs

- **5 MiB mất khoảng 6 giây** → ghi đè tiêu chí 2 giây (Q20), chạy core trong threadpool, đo và ghi Evidence; FE nên hiển thị trạng thái đang xử lý cho file lớn.
- **Hai đường tính (bảng tra và trace) có thể lệch** → test chéo trace với đường nhanh trên T01–T05 và 1000 khối ngẫu nhiên.
- **Bảng S-box chép sai một ô** chỉ làm lệch giữa chừng → test mỗi hàng là hoán vị 0–15, test giá trị trung gian từng vòng T01 và đối chiếu thư viện chuẩn.
- **`cryptography` cảnh báo deprecation cho TripleDES** → import từ `decrepit` khi có; pytest không bật warnings-as-errors.
- **Sửa `CIPHERS` mà chưa migrate** làm ghi DES thất bại âm thầm (best-effort) → test migration trên DB có bản ghi cũ trước khi công bố.
- **Message E08 nhắc `outputFormat`** trong khi file route không có tham số này → chấp nhận theo scope; tài liệu FE nêu rõ.

## Migration Plan

1. Core và unit test (T01–T20 phần core, giá trị trung gian, ngẫu nhiên).
2. Decoder, exception, router JSON, trace; integration test lỗi và thứ tự.
3. File route, guard, regression file của các cipher khác.
4. `CIPHERS`, migration `0003`, test lịch sử với DB bật/tắt.
5. Full gates (pytest coverage ≥ 90%, Ruff), đo 5 MiB, cập nhật tài liệu FE.
6. Triển khai: chạy migration trước khi bật backend mới. Rollback ứng dụng chỉ cần gỡ router; downgrade CHECK chỉ an toàn khi không còn bản ghi `des`.
