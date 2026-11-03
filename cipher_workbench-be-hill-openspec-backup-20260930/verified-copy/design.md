## Context

Repo hiện có năm core cipher tách khỏi HTTP, router/schema tường minh cho từng feature, handler lỗi chung hai trường, request guard 64 MiB và lịch sử metadata tùy chọn. `Scope Backend_ Hệ mã hóa Hill.html` định nghĩa toán Hill vector hàng, bốn API và test vector; các quyết định Q1–Q19 ngày 2026-09-29 chốt các chỗ khác biệt với baseline. Xem `proposal.md` và sáu delta spec của change này để biết contract chính xác. Đây là planning artifact; chưa sửa runtime.

## Goals / Non-Goals

**Goals:**

- Cài Hill vector hàng, m=2–4, ra đúng T01–T12 và vector cấp bốn; không thêm dependency runtime.
- Có đúng bốn Hill API và dữ liệu phân tích/blocks/warnings đủ cho FE.
- Giữ response/lỗi và giới hạn file của năm cipher cũ nguyên vẹn.
- Ghi metadata của đúng hai route biến đổi Hill, migration giữ dữ liệu cũ.

**Non-Goals:**

- Không có UI, file upload endpoint Hill, xác thực, lưu plaintext/key/result, generalized cipher interface, Affine-Hill hoặc phân tích mã.
- Không sửa migration `0001` đã áp dụng, không archive change cũ và không triển khai trong workflow planning này.

## Decisions

### 1. Core Hill thuần, ma trận nhỏ và vector hàng

Thêm `app/core/hill.py` chứa số học modulo 26, `det`, `minor`, `adjugate`, inverse, nhân vector hàng, chuẩn hóa khóa, phân tích và random key. Dùng số nguyên Python để không tràn; mod 26 ở biên ma trận/output, định thức Laplace đủ cho m≤4. Inverse được kiểm qua `K·K⁻¹ ≡ I` cho vector cố định và khóa ngẫu nhiên. Không tái dùng hàm Affine `modular_inverse` nếu điều đó kéo theo rule validate multiplier không thuộc Hill; một helper số học nhỏ có thể tách riêng khi tests chứng minh không đổi Affine.

### 2. Chuẩn bị văn bản theo cụm chữ Việt có dấu

Đi qua text một lần để nhận diện ASCII letter, Unicode Việt có dấu dạng composed/decomposed, và ký tự khác. Dùng Unicode normalization cho việc nhận diện hoặc bỏ dấu từng cụm, không tự normalize toàn bộ kết quả mặc định. `đ/Đ` xử lý tường minh. Với strip tắt, cụm Việt có dấu giữ nguyên mọi code point và không tham gia khối; với strip bật, cụm chuyển thành ASCII và có một vị trí đầu ra. Ký tự Unicode không phải chữ Việt có dấu luôn giữ nguyên. Việc dựng lại dùng layout để chèn chữ đã biến đổi đúng chỗ/case; padding được nối sau toàn bộ ký tự gốc. Không dùng regex `[A-Za-z]` trực tiếp trên code point đầu của cụm NFD, vì như vậy sẽ mã hóa chữ `e` và để dấu kết hợp lại phía sau.

### 3. Một đường phân tích khóa cho ba nơi dùng

Một hàm domain nhận ma trận chuẩn hóa và trả `matrix,m,det,gcd,detInverse,adjugate,inverse`; encrypt/decrypt/analyze/random đều dùng cùng kết quả. Keyword chuyển thành ma trận sau khi API đã xác nhận `m`. Random lặp cho tới khi khóa khả nghịch và khác I; khóa tự nghịch đảo vẫn hợp lệ với W03. Không đưa thông tin khóa vào history hoặc log. Response chỉ có ma trận chuẩn hóa 0–25, không echo raw key.

### 4. Hill JSON decoder và validator riêng

Thêm schema/decoder riêng theo seam Affine/Columnar: parse raw JSON với duplicate detection, từ chối non-object/lone surrogate/top-level field lạ trước field validation, không coerce số thành string hoặc ngược lại. Decoder nhận `key` và `keyword` là các tên field đã biết để validator phân loại trường hợp cùng xuất hiện thành E03; `m` đi với matrix đơn thuần là field thừa E11. Với matrix, từng ô phải là JSON integer token thật (bool/float/string không hợp lệ); xử lý integer token lớn bằng tính residue từ chữ số thay vì chuyển thành `int` không giới hạn. `m` chỉ là số nguyên 2–4. Options có đúng hai field tùy chọn và được validate dù operation là decrypt. Thứ tự lỗi ở `hill-error-handling` được thực thi tại adapter, không thay decoder/schema cũ. Limit 1 MiB đo trên UTF-8 của string trước normalization; handler có thể bỏ qua tính byte khi decoder đã gặp lỗi E11.

### 5. Router Hill tường minh và response cục bộ

Thêm một router `/api/hill` có hai POST text, một POST analyze và một GET random; include tại `app/main.py`. Encrypt/decrypt trả response model Hill riêng, key endpoints trả `result` object và `warnings`. Các lỗi nghiệp vụ Hill được chuyển bằng exception/handler cục bộ hoặc handler chung chỉ mở rộng khi exception là Hill; mọi `AppError` cũ giữ body hai trường. OpenAPI khai báo union hai request key variant, exact success/error schema, 413/422/500 và tag Hill. Không thêm Hill vào `FILE_ROUTE_PATHS`, không tạo route file giả.

### 6. Lịch sử dùng danh sách route thực và migration mới

Thêm `hill` vào `CIPHERS` ở model và migration mới để thay CHECK `ck_cipher_operations_cipher` mà giữ các row cũ. `app/history/routes.py` hiện tự sinh ba route cho mỗi cipher; sửa ánh xạ để Hill chỉ có `/encrypt` và `/decrypt`, không suy ra `/file` hoặc `/key/analyze`. Middleware ghi `source=text`, `response_mode=null`, độ dài input/result theo Unicode code point giống text route hiện tại, cả khi result có padding. Khi DB tắt/lỗi, response Hill không đổi. History filter dùng danh sách CIPHERS mới.

### 7. Handoff FE khác đường file hiện tại

`repo_docs/frontend-integration.md` mô tả Hill là ngoại lệ có bốn API và file được đọc tại FE; kiểm `.txt`, 1 MiB byte gốc, decode UTF-8 nghiêm ngặt, E07 ở FE, sau đó gửi JSON `text`. `repo_docs/examples/cipher-api.ts` thêm kiểu/helper Hill riêng để không bỏ `blocks`, `key`, `warnings`; union `Cipher` lịch sử có `hill`. Không đổi helper `previewFile`/`downloadFile` của năm cipher cũ để tránh gửi tới `/api/hill/file` không tồn tại. Docs chỉ cập nhật sau khi implementation tests xanh.

## Risks / Trade-offs

- **Response lớn:** 1 MiB ASCII với m=2 có thể tạo khoảng 524.288 block JSON; giữ đủ blocks theo quyết định Q7, vì vậy đo core dưới 1 giây tách khỏi serialize/network, kiểm tra memory và kích thước response trong integration test. FE cần hiển thị phân trang/virtualized list, nhưng đó thuộc repo FE.
- **Unicode tách dấu:** xử lý theo cụm thay vì từng code point phức tạp hơn JS mẫu. Test NFC/NFD parity, `đ/Đ`, chữ ngoại ngữ và các dấu kết hợp để không mất ký tự.
- **Lỗi chung 64 MiB:** guard hiện tại chạy trước Hill decoder, có thể trả 413 hai trường khi request khổng lồ. Đây là ngoại lệ hạ tầng đã có; tài liệu Hill phải nêu rõ thay vì hứa mọi 413 đều E06.
- **Migration CHECK:** sửa `CIPHERS` trong model mà không migrate DB sẽ làm ghi Hill thất bại âm thầm. Test migration trên DB có row cũ và thử ghi Hill trước khi công bố feature.
- **Hình dạng lỗi riêng:** global handler hiện trả hai trường; route-scoped Hill error không được làm thay response của 15 route cũ. Test hồi quy exact body.
- **Mốc 1 giây phụ thuộc máy:** benchmark dùng text ASCII 1 MiB, ghi cấu hình máy và đo core, không đặt một performance gate CI dễ nhiễu khi chưa có máy chuẩn.

## Migration Plan

1. Khi được yêu cầu apply: thêm unit tests và core Hill, kiểm T01–T12, vector 4×4, inverse/round-trip, Unicode và random.
2. Thêm decoder/validators/route/error models và contract tests; giữ route cũ nguyên dạng. Kiểm giới hạn 1 MiB, 64 MiB guard và OpenAPI.
3. Tạo Alembic revision nới CHECK, cập nhật history route mapping/filter, kiểm migration với row cũ và hành vi DB bật/tắt.
4. Chạy full pytest với coverage ≥90%, Ruff check/format và benchmark có ghi môi trường; sau đó cập nhật README, FE guide/client và chạy lại gates.
5. Triển khai migration trước khi backend mới ghi history Hill; FE bật lựa chọn Hill sau khi bốn API sẵn sàng. Rollback ứng dụng có thể ngừng expose Hill; downgrade CHECK chỉ an toàn khi không còn row Hill, nên phải có bước xử lý dữ liệu riêng trước downgrade.
