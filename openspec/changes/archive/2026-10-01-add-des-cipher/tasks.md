## 1. Chuẩn bị và test thuật toán

- [x] 1.1 Thêm `cryptography` vào nhóm dev bằng `uv add --dev cryptography`; viết helper test đối chiếu DES qua TripleDES khóa 8 byte (ưu tiên `hazmat.decrepit`). **Xong khi:** `uv.lock` cập nhật, test layering vẫn xanh, helper ra `85E813540F0AB405` cho T01.
- [x] 1.2 Viết unit test bảng hằng, `permute`, khóa con và từng vòng theo T01 (K1…K16, Ln/Rn, vòng 1 E ⊕ K1, S, f) và bài tập slide 21. **Xong khi:** test đỏ vì chưa có core, bao phủ toàn bộ scenario `des-core` về bảng và giá trị trung gian.
- [x] 1.3 Viết unit test mã hóa/giải mã T01–T13, T17–T19, PKCS#7, UTF-8, ECB/CBC, khóa yếu/nửa yếu, đếm khối lặp, trace chiều decrypt, 1000 lần ngẫu nhiên đối chiếu thư viện. **Xong khi:** mọi scenario `des-core` có assertion.

## 2. DES Core

- [x] 2.1 Tạo `app/core/des.py` với bảng chuẩn, `permute`, `rotate_left`, `key_schedule`, hàm f và `trace_block`. **Xong khi:** test 1.2 xanh, C16D16 = C0D0.
- [x] 2.2 Dựng bảng SP, IP/IP⁻¹ theo byte và đường mã hóa/giải mã khối nhanh; ECB, CBC, PKCS#7, chuẩn hóa khóa/IV/hex, khóa yếu/nửa yếu, đếm khối lặp, `DesError` có mã. **Xong khi:** test 1.3 xanh, trace và đường nhanh khớp trên 1000 khối ngẫu nhiên, core chỉ import thư viện chuẩn.

## 3. Exception Handling

- [x] 3.1 Thêm message DES (tĩnh và template `{n}`, `{name}`) vào `app/errors/messages.py` và `DesError(AppError)` vào `app/errors/exceptions.py`. **Xong khi:** body lỗi DES đúng hai trường; test envelope các cipher cũ và Hill không đổi.

## 4. HTTP Adapter

- [x] 4.1 Tạo `app/api/des_schemas.py`: kiểm media, parse JSON phát hiện field trùng, tập field theo route, kiểu field, E12, E10, khóa, IV, dữ liệu theo đúng thứ tự spec. **Xong khi:** test validation (trong `tests/integration/test_des_endpoints.py`) phủ mọi dòng bảng lỗi JSON và các scenario thứ tự ưu tiên, biên 5.242.880/5.242.881 byte cả ASCII lẫn đa byte.
- [x] 4.2 Tạo `app/api/routes_des.py` với `/encrypt`, `/decrypt`, response model, warnings W01→W02→W03, core chạy qua threadpool, include ở `app/main.py`. **Xong khi:** T01–T13, T16–T20 qua API ra đúng `result`/message/status; OpenAPI có tag `DES`.
- [x] 4.3 Thêm `/api/des/trace` với response model trace đầy đủ, E13, W01/W02. **Xong khi:** JSON trace cho T01 khớp mẫu scope §7; decrypt có `subkey` 16 → 1; trace không ghi lịch sử.

## 5. File Processing

- [x] 5.1 Tạo `app/api/routes_des_file.py` theo mẫu Affine: exact field set, thứ tự lỗi file, encrypt text → hex, decrypt hex nhiều dòng → text, `response_mode` content/file, BOM, tên `.encrypted.txt`/`.decrypted.txt`. **Xong khi:** mọi scenario `des-file-cipher-api` xanh, gồm biên 5 MiB, 415/413/422.
- [x] 5.2 Thêm `/api/des/file` vào `FILE_ROUTE_PATHS`. **Xong khi:** guard 64 MiB và multipart bị cắt trả đúng message cho route DES; test guard của năm route file cũ không đổi.

## 6. Database và lịch sử

- [x] 6.1 Thêm `des` vào `CIPHERS` và migration `0003_allow_des_cipher_operations.py` theo mẫu `0002`. **Xong khi:** upgrade trên DB có bản ghi cũ giữ nguyên dữ liệu, insert `des` hợp lệ, CHECK vẫn chặn tên lạ; downgrade về danh sách có `hill`.
- [x] 6.2 Cập nhật test lịch sử: ba route DES được ghi (kể cả lỗi 413/415/422), `/api/des/trace` không được ghi, filter `cipher=des`, độ dài code point/byte, không lưu khóa/IV/nội dung. **Xong khi:** test DB (khi có `TEST_DATABASE_URL`) và test không DB đều xanh.

## 7. Test tích hợp, hiệu năng và quality gates

- [x] 7.1 Integration test cho mỗi lỗi DES-E01…E13 (E11 qua các lỗi file baseline) với đúng HTTP status và message; regression route/envelope/OpenAPI của sáu cipher cũ. **Xong khi:** toàn bộ test xanh.
- [x] 7.2 Đo thủ công mã hóa và giải mã 5 MiB qua core và qua API (ECB, CBC), ghi máy, thời gian, RSS vào Evidence của task này. **Xong khi:** có số đo; không thêm performance test tự động.
  - Evidence 2026-10-01: Python 3.12.3, Linux 7.0.0-34-generic x86_64, AMD Ryzen 7 H 260. Core 5 MiB (655.360 khối): ECB mã hóa `6,05s`, giải mã `5,73s`; CBC mã hóa `6,40s`, giải mã `6,54s`.
  - API (TestClient, gồm parse/serialize): JSON encrypt 5 MiB text ECB `5,95s`, CBC `6,45s`; file encrypt 5 MiB ECB `5,67s` (file kết quả 10.485.776 byte); JSON decrypt 5 MiB hex (2,5 MiB dữ liệu) `2,98s`; file decrypt 5 MiB hex `2,82s`; peak RSS khoảng `231.000 KiB`.
  - Phát hiện: bản mã hex dài gấp đôi bản rõ, nên bản mã của văn bản lớn hơn khoảng 2,5 MiB vượt giới hạn 5 MiB ở chiều giải mã (JSON 413 `Dữ liệu vượt quá 5 MiB.`, file 413). Quyết định chủ sở hữu Q22: giữ 5 MiB cho mọi chiều, ghi rõ trong tài liệu FE.
- [x] 7.3 Chạy `uv run --frozen pytest` (coverage ≥ 90%), `uv run --frozen ruff check .`, `uv run --frozen ruff format --check .`, `openspec validate add-des-cipher --strict`. **Xong khi:** mọi gate xanh.
  - Gates 2026-10-01: `1278 passed` (gồm test PostgreSQL 17 qua `TEST_DATABASE_URL`), coverage `95,65%`; Ruff check/format, `git diff --check`, OpenSpec 1.8.0 `validate add-des-cipher --strict` và `validate --specs --strict` (28/28) đều xanh.

## 8. Docs

- [x] 8.1 Cập nhật README: 7 cipher, bốn route DES, bảng lỗi/cảnh báo, khác biệt so với scope. **Xong khi:** README khớp runtime.
- [x] 8.2 Cập nhật `repo_docs/frontend-integration.md` và `repo_docs/examples/cipher-api.ts`: request/response encrypt/decrypt/file/trace, warnings, các cặp `inputFormat`/`outputFormat`, union `Cipher` lịch sử có `des`. **Xong khi:** TypeScript strict compile (nếu có `tsc`) và hướng dẫn không nhắc `.des.txt` hay HTTP 400.
