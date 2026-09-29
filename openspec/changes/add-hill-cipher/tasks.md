## 1. Baseline và test thuật toán

- [x] 1.1 Chụp bằng test inventory 15 POST route hiện có, exact success/error envelope của năm cipher, history filter và guard/file limit trước khi thêm Hill. **Xong khi:** test baseline xanh và cho thấy không có `/api/hill/*`.
- [x] 1.2 Viết unit test cho mod/gcd/inverse, đủ 12 cặp nghịch đảo, determinant/adjugate/inverse, K·K⁻¹ và các khóa E04 cấp 2–4. **Xong khi:** T01–T04, T08–T09 và vector 4×4 `TEST→FNMP` được kiểm trực tiếp ở core.
- [x] 1.3 Viết unit test cho keyword HILL, normalization số âm/lớn, ma trận sai, padding/case/dấu câu và T05–T07, T10–T12. **Xong khi:** toàn bộ T01–T12 có assertion result, blocks hoặc warning phù hợp.
- [x] 1.4 Viết unit test NFC/NFD tiếng Việt, `đ/Đ`, strip bật/tắt, chữ Unicode khác, padChar tùy chọn và random 1000 khóa mỗi cấp. **Xong khi:** các trường hợp ở `hill-core` đều có test trước khi nối HTTP.

## 2. Hill Core

- [x] 2.1 Cài số học mod 26, determinant/minor/adjugate/inverse và nhân vector hàng trong `app/core/hill.py`. **Xong khi:** test mục 1.2 xanh, K·K⁻¹ ≡ I và T03 là `QRT`.
- [x] 2.2 Cài chuẩn hóa ma trận, chuyển keyword hàng-major, phân tích khóa, phát hiện W03 và sinh khóa ngẫu nhiên. **Xong khi:** T05/T12 và 1000 lần sinh mỗi cấp thỏa điều kiện; core không import tầng API/DB.
- [x] 2.3 Cài tách/dựng text theo cụm Việt NFC/NFD, stripDiacritics, case và ký tự giữ nguyên. **Xong khi:** test Unicode và `Help, me!→Dple, se!` xanh, không mất code point khi strip tắt.
- [x] 2.4 Cài encrypt/decrypt, padding và danh sách blocks đầy đủ. **Xong khi:** T01–T12, `HELLO→DPDKKB→HELLOX`, W01 và vector 4×4 xanh.

## 3. Schema, Exception Handling và HTTP Adapter

- [x] 3.1 Thêm decoder JSON Hill strict với media hiện hành, duplicate/unknown field, surrogate và hai request variant khóa. **Xong khi:** malformed/non-object/lone surrogate/field lạ-trùng trả E11; các route cũ không đổi.
- [x] 3.2 Thêm validator Hill cho text, 1 MiB UTF-8, matrix/keyword/m, options và precedence E01–E11 trừ E07. **Xong khi:** mỗi mã có test API riêng; nhiều lỗi đồng thời theo đúng thứ tự spec.
- [x] 3.3 Thêm Hill-specific exception/response mapping và warning serialization. **Xong khi:** lỗi nghiệp vụ Hill có đúng `success,message,code,details`, lỗi 500/guard chung và các cipher cũ giữ format hiện hành.
- [x] 3.4 Thêm `POST /api/hill/encrypt` và `/decrypt` cùng response models, history notes và OpenAPI. **Xong khi:** T01/T05/T06/T07 chạy qua API có result, toàn bộ blocks/key/warnings, tag và status đúng; không có file route Hill.
- [x] 3.5 Thêm `POST /api/hill/key/analyze` và `GET /api/hill/key/random?m=` cùng OpenAPI. **Xong khi:** analyze T01 trả đủ ma trận/det/inverse, random m=2–4 hợp lệ, thiếu/trùng/sai m trả E08.

## 4. Database và lịch sử

- [x] 4.1 Thêm Alembic revision nới CHECK cipher cho `hill`, giữ migration `0001` nguyên trạng; cập nhật model. **Xong khi:** upgrade trên DB có row cũ bảo toàn row, insert Hill hợp lệ và CHECK vẫn chặn tên lạ.
- [x] 4.2 Sửa route mapping lịch sử để nhận đúng hai POST Hill transform, không tạo `/hill/file` giả và không ghi hai key endpoints. **Xong khi:** DB bật ghi một row/request transform gồm cả 422/413, `source=text`; key endpoints ghi zero row.
- [x] 4.3 Mở filter `cipher=hill` và cập nhật test DB bật/tắt/best-effort/privacy. **Xong khi:** `/api/history?cipher=hill` chỉ trả row Hill; không lưu text/key/result/blocks/warnings; response cipher không đổi khi DB lỗi.

## 5. Integration, contract và hiệu năng

- [x] 5.1 Phủ API E01–E06, E08–E11 với HTTP status, code và details; xác nhận E07 chỉ là FE handoff. **Xong khi:** mọi case lỗi khả dĩ của bốn Hill API có test, gồm precedence, option sai, keyword sai và E04 det/gcd.
- [x] 5.2 Phủ exact response/OpenAPI, 18 POST cipher route và một GET Hill random, JSON media, 1 MiB boundary, 64 MiB guard exception và regression 15 route cũ. **Xong khi:** schema/body/status đúng, test cũ giữ nguyên.
- [x] 5.3 Chạy round-trip ngẫu nhiên với 1000 khóa hợp lệ và text ngẫu nhiên; benchmark core trên ASCII 1 MiB với m=2 và m=4, ghi máy và kết quả. **Xong khi:** inverse/round-trip đúng; mỗi phép xử lý core dưới 1 giây trên môi trường benchmark đã ghi, không tính JSON/network.
  - Evidence 2026-09-29: Python 3.12.3, Linux 7.0.0-34-generic x86_64; năm mẫu m=2 `0.969248–0.979766s`, m=4 `0.704462–0.713211s`, gồm đầy đủ 524.288/262.144 blocks.

## 6. Tài liệu FE và quality gates

- [x] 6.1 Sau khi test implementation xanh, cập nhật README và `repo_docs/frontend-integration.md` cho 6 cipher, 18 POST route, 4 Hill API, FE `.txt` 1 MiB/E07 và response Hill riêng. **Xong khi:** hướng dẫn không gợi ý `/api/hill/file` hoặc áp limit 5 MiB cho Hill.
- [x] 6.2 Cập nhật `repo_docs/examples/cipher-api.ts` với helper/type Hill riêng và history union, giữ helpers năm cipher cũ. **Xong khi:** TypeScript strict compile và helper Hill bảo toàn blocks/key/warnings.
- [x] 6.3 Chạy full `uv run --frozen pytest`, `uv run --frozen ruff check .`, `uv run --frozen ruff format --check .`, coverage ≥90% và OpenSpec strict validate trên môi trường có CLI tương thích. **Xong khi:** mọi gate xanh trên state cuối, không thêm dependency runtime và không sửa HTML nguồn.
- [x] 6.4 Rà diff và nghiệm thu theo sáu delta spec cùng quyết định Q1–Q19. **Xong khi:** không có thay đổi thuật toán/contract năm cipher cũ, không lưu dữ liệu nhạy cảm, migration và tài liệu FE khớp runtime.
