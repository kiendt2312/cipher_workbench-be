## Context

Xem `proposal.md` - Why. Runtime hiện tách lõi từng thuật toán trong `app/core/`, tự giải mã JSON để giữ integer token không giới hạn độ lớn, dùng router text/file riêng, helper file dùng chung trong `app/services/file_processing.py`, và hai guard request trong `app/api/request_size_guard.py`. Các spec của change này là contract Affine; hành vi kế thừa tuân thứ tự completed OpenSpec/runtime trước, rồi README/guide FE hiện tại. `affine-cipher.html` đứng cuối, chỉ là tham chiếu công thức/vector và không tham gia runtime.

Điểm cần thiết kế riêng là Affine có hai khóa với hai wire representation khác nhau: JSON integer không giới hạn JS safe integer và multipart signed-decimal string tối đa 32 ký tự. Schema Affine còn phải từ chối member lạ mà không siết lại schema của 6 endpoint text hiện hữu.

## Goals / Non-Goals

**Goals:**

- Cô lập thuật toán Affine thành một module thuần, stateless, dễ kiểm thử và không phụ thuộc HTTP.
- Bổ sung ba adapter HTTP theo đúng thứ tự validation trong các delta spec, tái sử dụng envelope, exception handler, file helper và guard hiện có.
- Giữ integer JSON chính xác ở mọi độ lớn và chuẩn hóa theo modulo 26 trước khi kiểm tra/nghịch đảo, không phụ thuộc giới hạn số của JavaScript.
- Mô tả OpenAPI đủ rõ cho JSON hai khóa và multipart hai khóa mà không tạo thêm một abstraction cipher tổng quát.
- Cho phép kiểm chứng hồi quy rằng 9 endpoint cũ không đổi cả success, error lẫn guard behavior.

**Non-Goals:**

- Không gom Caesar/Vigenère/Playfair/Affine vào factory, registry, base class hoặc endpoint tổng quát.
- Không sửa schema cũ để đồng nhất việc từ chối field lạ; strict member set chỉ thuộc hai endpoint Affine mới.
- Không đưa demo hoặc phép tính phía client vào đường xử lý production; không triển khai FE trong change này.
- Không tối ưu bằng bảng tra cứu/cache toàn cục vì miền modulo 26 nhỏ và mỗi request độc lập.

## Decisions

### 1. Module lõi Affine độc lập và API hàm nhỏ

Thêm `app/core/affine.py` với các hàm thuần để chuẩn hóa khóa, kiểm tra/tính nghịch đảo modulo và transform text theo operation. Module chỉ duyệt code point của chuỗi, biến đổi ASCII `A-Z`/`a-z` bằng offset 0..25, và nối nguyên trạng mọi code point khác. Decrypt dùng positive modulo sau phép trừ.

Lý do: cấu trúc này khớp ba core module hiện có, giữ thuật toán tách khỏi transport và cho phép unit test trực tiếp các invariant. Nghịch đảo có thể tính bằng extended Euclid hoặc tìm residue trong miền 0..25; implementation chọn cách ngắn, rõ và kiểm thử được, không thêm dependency.

Phương án không chọn: một `Cipher` interface/registry dùng chung. Nó mở rộng phạm vi và che giấu khác biệt thật giữa key integer, string key và Playfair preprocessing mà không đem lại tái sử dụng cần thiết cho ba route mới.

### 2. Decoder/schema Affine riêng, tái sử dụng cơ chế giữ integer token

Thêm model request Affine có ba field `text`, `a`, `b`, OpenAPI type tương ứng `string`, `integer`, `integer`, và cấu hình từ chối field lạ. Decoder Affine đọc raw body, áp dụng cùng media-type/JSON framing policy hiện tại, dùng `json.loads(..., parse_int=JsonIntegerToken, parse_constant=...)` để giữ nguyên integer token. Decoder kiểm tra object, member lạ và tên trùng trước validation field; member thiếu được giữ bằng sentinel để validator trả message theo thứ tự `text → a → b`. Các decoder/model cũ giữ nguyên.

`a` và `b` được parse theo thứ tự bằng helper Affine mới. Với `JsonIntegerToken`, residue được tính trực tiếp từng chữ số để không materialize một integer khổng lồ; với Python `int`, dùng modulo thông thường. `bool`, float, string, null và missing không đi qua nhánh integer. `a` được chuẩn hóa rồi kiểm tra `gcd(a',26)==1`; chỉ sau khi `a` hợp lệ mới parse `b`.

Lý do: runtime đã có kỹ thuật bảo toàn integer JSON và Python/Pydantic không được phép coercion làm numeric string hoặc boolean thành integer. Decoder riêng bảo vệ contract strict mới mà không tạo breaking change cho endpoint cũ.

Phương án không chọn: dùng trực tiếp `int` field Pydantic hoặc giới hạn 64-bit. Coercion/giới hạn đó trái contract true JSON integer và có thể làm mất chính xác hay nhận sai kiểu. Cũng không chuyển qua float/JavaScript Number.

### 3. Router Affine tường minh, chỉ extract helper khi có lặp thật

Thêm router text Affine với hai handler encrypt/decrypt dùng chung một helper request nội bộ, và router file Affine với một handler. Các router được include trực tiếp trong `app/main.py` để tổng route cipher là 12. Chúng dùng response model/envelope và error handler hiện có; chỉ thêm exception/message Affine tối thiểu cho missing/type/invertibility của `a` và missing/type của `b`.

Nếu implementation cho thấy khối response file hoặc OpenAPI schema giống hệt đã lặp, có thể extract helper hẹp mà không đổi signature/hành vi route cũ. Mặc định không sửa luồng cũ chỉ để đạt vẻ đồng nhất.

Lý do: route tường minh làm thứ tự validation, OpenAPI và regression boundary dễ đọc. Phương án một endpoint nhận tên thuật toán hoặc registry bị loại vì trái phạm vi đã chốt.

### 4. Multipart Affine được kiểm tra từ raw form theo exact field set

Endpoint file nhận khai báo `file`, `a`, `b`, `action`, `response_mode`, nhưng sau multipart-completion guard sẽ đọc `request.form()` để kiểm tra tập tên, duplicate và lấy giá trị theo thứ tự contract. Validator giữ đúng phân loại parser hiện tại: part có `filename=""` vẫn là `UploadFile` rồi thất bại extension với 415, còn part tên `file` không có tham số `filename` là scalar và thất bại body framing với 422; không tạo policy override riêng cho Affine. `a` và `b` dùng grammar `^[+-]?[0-9]+$` sau trim, giới hạn 32 ký tự sau trim, rồi chuẩn hóa modulo 26; không dùng default server. `response_mode` duy nhất được phép vắng và khi đó là `content`.

Sau validation scalar, endpoint chuyển sang helper file hiện tại theo thứ tự extension, đọc có giới hạn 5 MiB, non-empty, UTF-8/BOM, transform, rồi content hoặc attachment. Preview/download vẫn là hai request độc lập; filename/BOM/body builder hiện hữu là nguồn duy nhất.

Lý do: binding tham số FastAPI không đủ để phân biệt/chặn field lạ hay duplicate một cách xác định, trong khi raw form cho phép giữ đúng precedence. Phương án thêm một pipeline file tổng quát cho mọi cipher bị loại vì có nguy cơ đổi 3 endpoint file cũ.

### 5. Mở rộng guard theo route allowlist, không đổi threshold

Thêm đúng `/api/affine/file` vào `FILE_ROUTE_PATHS`: request-size guard dùng tập này để chọn file-size message, còn multipart-completion guard dùng nó để bật kiểm tra closing boundary. Request-size guard vẫn áp dụng global như hiện tại nên hai route text Affine tự nhận generic >64 MiB message mà không cần allowlist mới. Không đổi hằng số, thứ tự middleware, mapping lỗi hay route cũ.

Lý do: đây là cách nhỏ nhất để kế thừa hardening hiện có. Test sẽ đặc tả request đúng/ngay trên/vượt ngưỡng liên quan và multipart thiếu completion cho route mới, đồng thời chạy test guard của route cũ.

Phương án không chọn: guard toàn bộ `/api/*` hoặc thay limit theo cipher; cả hai đều mở rộng contract ngoài yêu cầu.

### 6. OpenAPI và error contract được đặc tả cùng adapter

OpenAPI Affine khai báo chính xác required members, không additional properties, integer keys ở JSON, string keys ở multipart, enum action/response mode, hai kiểu success file và error envelopes hiện có. Runtime chỉ phát `{success:false,message}` và dừng ở lỗi đầu tiên theo precedence trong `affine-error-handling/spec.md`; log server không chứa text/file bytes/key raw.

Lý do: router hiện dùng explicit `openapi_extra`, nên tiếp tục cùng pattern giảm khác biệt giữa docs và runtime. Không thêm `code`, `details`, normalized key hoặc metadata dù chúng có thể tiện debug, vì đó là thay đổi contract.

### 7. Verification theo lớp và cập nhật tài liệu sau code

Unit test khóa/transform/inverse và acceptance vectors; integration test text, file, error precedence, guard, OpenAPI và route count; cuối cùng chạy toàn bộ suite để chứng minh 9 endpoint cũ không đổi. README và `repo_docs/frontend-integration.md` chỉ cập nhật sau khi implementation vượt các test, với migration note từ 9 lên 12 route và cảnh báo FE không dùng JavaScript Number cho integer ngoài safe range.

Lý do: thứ tự này giữ docs phản ánh runtime đã kiểm chứng. `affine-cipher.html` không được copy, sửa, import hoặc stage trong bất kỳ bước nào.

## Risks / Trade-offs

- [Kiểm tra duplicate JSON/multipart cần đọc cấu trúc raw thay vì chỉ dựa vào model binding] → Cô lập logic trong decoder/form validator Affine, test duplicate/lạ/malformed và không chạm decoder cũ.
- [Integer JSON tùy ý có thể rất dài và gây tốn CPU/bộ nhớ trước khi modulo] → Giữ request-size guard hiện tại, parse token dạng chuỗi và tính residue tuyến tính không tạo big integer; test token ngoài JS safe range. Không đặt giới hạn mới trái contract.
- [Thêm hai khóa có thể làm lệch error precedence giữa text và file] → Dùng validator tuần tự `text/file → a → b → action/response_mode → content`, mỗi test nhiều lỗi đồng thời khẳng định chỉ lỗi ưu tiên cao nhất.
- [Tái sử dụng file helper nhưng chỉnh code dùng chung có thể gây regression] → Ưu tiên gọi helper ổn định; nếu buộc extract thì thêm characterization test trước và chạy full suite 9 endpoint.
- [OpenAPI có thể mô tả integer tùy ý nhưng FE JavaScript vẫn mất chính xác] → Guide sau implementation yêu cầu gửi nguyên JSON integer token bằng serializer không làm tròn hoặc từ chối input ngoài safe range ở FE; server không hạ contract xuống safe integer.
- [Tên/mime/CRLF/BOM dễ bị thay đổi qua encode/decode] → Dùng nguyên helper filename/BOM hiện tại, không normalize newline, và phủ test exact bytes cho content lẫn attachment.

## Migration Plan

1. Thêm core, validation, exception/message và router Affine sau các test đặc tả; include ba route và mở rộng đúng allowlist guard.
2. Chạy test Affine theo lớp, kiểm tra OpenAPI có 12 route cipher, rồi chạy toàn bộ lint/format/test/coverage của repository.
3. Chỉ khi bước 2 đạt, cập nhật README và guide FE về ba route, hai khóa, vectors, file/error flow và migration 9 → 12; không đưa demo vào source.
4. Deploy như bản backend tương thích ngược: client cũ không cần thay đổi, client mới opt-in ba route Affine.

Rollback: gỡ include router Affine và entry guard mới cùng module/test/docs Affine trong một rollback release; không có dữ liệu/database migration và 9 endpoint cũ vẫn là baseline. OpenSpec change chỉ archive bằng workflow riêng sau khi implementation được nghiệm thu, không archive trong planning/apply tự động.
