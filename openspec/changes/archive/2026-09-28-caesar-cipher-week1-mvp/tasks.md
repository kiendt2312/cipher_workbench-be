## 1. Bootstrap dự án

- [x] 1.1 Cài `uv` trên máy dev (`curl -LsSf https://astral.sh/uv/install.sh | sh`). **Xong khi:** `uv --version` in ra phiên bản. *(Task chặn — `uv` hiện chưa có trên máy.)*
- [x] 1.2 Viết `pyproject.toml` theo design §Project Structure.5: `requires-python = ">=3.12,<3.13"`, 4 dep runtime, 4 dep dev, cấu hình Ruff (line-length 100, rule set `E,F,I,UP,B,SIM,N,RUF`), cấu hình pytest + coverage (`--cov=app`, `branch = true`, **chưa bật** `--cov-fail-under`). **Xong khi:** `uv sync` tạo `.venv` và `uv.lock`; `uv run ruff check .` sạch.
- [x] 1.3 Tạo khung thư mục `app/{core,services,api,errors,templates,static}` và `tests/{unit,integration}` với đủ `__init__.py`; viết `.gitignore`. **Xong khi:** `uv run pytest` chạy được (0 test, không lỗi import).
- [x] 1.4 Viết `app/config.py`: `MAX_FILE_BYTES = 5242880`, `MAX_REQUEST_BYTES`, `ALLOWED_EXTENSION = ".txt"`, `CHUNK_SIZE`, `PORT = 8000`. **Xong khi:** ngưỡng 5 MiB chỉ tồn tại ở đúng một nơi trong toàn repo.

## 2. Caesar Core

- [x] 2.1 Viết `app/core/caesar.py`: `transform_text(text, key, operation)` với `operation` ∈ {`encrypt`, `decrypt`}, dùng `str.translate()` với 26 bảng dịch dựng sẵn (design §Decisions.3). Chuẩn hóa khóa về 0–25 bằng modulo cho kết quả không âm. **Xong khi:** module chỉ import thư viện chuẩn, không import gì thuộc `app`.
- [x] 2.2 Viết `tests/unit/test_caesar.py` phủ toàn bộ 23 scenario của spec `caesar-core`: `"Hello World"`+3 → `"Khoor Zruog"` và chiều ngược lại; khóa `-3`/`29`/`26`/`0`; wrap `Z→A`, `z→a`; giữ nguyên số, dấu câu, tiếng Việt có dấu, emoji, tab, LF, **CRLF**; chuỗi rỗng và whitespace-only; round-trip encrypt→decrypt. **Xong khi:** coverage của `app/core/` đạt 100%.
- [x] 2.3 Viết `tests/unit/test_layering.py`: phân tích AST mọi file trong `app/core/`, fail nếu thấy import `fastapi`, `starlette`, `pydantic`, `app.api`, `app.services`, `app.config`, `app.errors`. **Xong khi:** test xanh và cố tình thêm một import cấm thì test đỏ.
- [x] 2.4 Viết test đối chiếu: so kết quả `str.translate` với một implementation vòng lặp tham chiếu trên tập đầu vào đa dạng. **Xong khi:** hai cách cho kết quả giống hệt trên mọi ca kiểm thử.

## 3. Exception Handling và khung ứng dụng

- [x] 3.1 Viết `app/errors/messages.py`: 12 chuỗi nguyên văn docx §5 **cộng** `"Dữ liệu gửi lên không hợp lệ."` (dòng 13 đã được duyệt). **Xong khi:** đây là nơi duy nhất trong repo chứa các chuỗi này, không có chuỗi nào lặp lại hard-code chỗ khác.
- [x] 3.2 Viết `app/errors/exceptions.py`: `CaesarError(status_code, message)` và các lớp con cho từng nhóm lỗi. **Xong khi:** module không import framework nào.
- [x] 3.3 Viết `app/errors/handlers.py`: 4 handler cho `CaesarError`, `RequestValidationError`, `HTTPException`, `Exception`. Lỗi 500 ghi log nội bộ kèm ngữ cảnh nhưng **không** log nội dung văn bản/file của người dùng. **Xong khi:** mọi lỗi trả đúng `{"success": false, "message": "..."}`, không bao giờ có khóa `"detail"`, không lộ stack trace.
- [x] 3.4 Viết `app/main.py` tối thiểu: tạo app, đăng ký 4 exception handler. **Xong khi:** `GET /docs` trả 200; route không tồn tại trả 404 đúng khuôn dạng chuẩn; một route thử ném `CaesarError` trả đúng cặp status/message.
- [x] 3.5 Viết `tests/integration/test_error_contract.py`: một test cho mỗi dòng bảng docx §5 (13 dòng), đối chiếu đúng HTTP status và chuỗi nguyên văn. **Xong khi:** đọc file thấy ngay "13 dòng docx ↔ 13 test".

## 4. HTTP Adapter — Text API

- [x] 4.1 Viết `parse_key` và model request/response trong `app/api/schemas.py`. JSON: giữ token integer bằng hook `parse_int`, chấp nhận đúng loại token đó (hoặc exact `int` khi gọi nội bộ), tính modulo theo chữ số để không dựng số nguyên khổng lồ, đồng thời chặn `bool`, `float` và numeric string (design §Decisions.7). **Xong khi:** `true`, `3.0`, `"3"` đều bị từ chối; `3`, `-3`, `29` và JSON integer dài hơn 4.300 chữ số được nhận mà không tắt giới hạn an toàn toàn tiến trình.
- [x] 4.2 Cài quy tắc key vắng mặt / `null` / chuỗi rỗng → `"Thiếu khóa."`; có giá trị thực nhưng không phải số nguyên → `"Khóa phải là số nguyên."`. **Xong khi:** 4 trường hợp trên trả đúng chuỗi tương ứng.
- [x] 4.3 Cài thứ tự validate của design §Decisions.9 cho luồng JSON: body đọc được → `text` → hiện diện `key` → định dạng `key`. **Xong khi:** `{}` → `"Văn bản không được để trống."`; `{"text": "", "key": "3"}` → lỗi text chứ không phải lỗi key.
- [x] 4.4 Viết `app/api/routes_text.py`: `POST /api/caesar/encrypt` và `POST /api/caesar/decrypt`, gọi `transform_text`. **Xong khi:** hai endpoint hiện trong `/docs` và trả `{"success": true, "result": "..."}`.
- [x] 4.5 Viết `tests/integration/test_text_endpoints.py` phủ 45 scenario của spec `text-cipher-api`. **Xong khi:** toàn bộ xanh, gồm body không phải JSON → 422 `"Dữ liệu gửi lên không hợp lệ."`, whitespace-only → 200, Unicode/CRLF đi qua API nguyên vẹn.

## 5. File Processing

- [x] 5.1 Viết hàm đọc theo chunk 64 KiB trên **bytes** trong `app/services/file_processing.py`, dừng khi vượt 5242880 byte (design §Decisions.4). Nhận đối tượng duck-typed có `async read(size)` để không phải import FastAPI. **Xong khi:** 5242880 byte được nhận, 5242881 byte bị từ chối, và service test được bằng `BytesIO` bọc mỏng.
- [x] 5.2 Cài xử lý BOM: phát hiện `b"\xef\xbb\xbf"` trên bytes thô, decode `utf-8-sig`, gắn lại BOM ở mode `file` đúng theo đầu vào, mode `content` không bao giờ có BOM (design §Decisions.5). **Xong khi:** file có BOM tải xuống giữ BOM; file không BOM không bị thêm BOM; `result` ở mode content không chứa BOM.
- [x] 5.3 Cài decode UTF-8 **một lần ở cuối** trên toàn bộ bytes, tuyệt đối không dùng chế độ text có universal newlines. **Xong khi:** file CRLF giữ nguyên CRLF byte-for-byte; file LF không bị thêm `\r`; file latin-1 → `"File phải sử dụng UTF-8."`
- [x] 5.4 Viết `build_result_filename`: bỏ đuôi `.txt` **cuối cùng**, thêm `.encrypted.txt` / `.decrypted.txt`, đuôi kết quả luôn viết thường. **Xong khi:** `bao.cao.v2.txt` → `bao.cao.v2.encrypted.txt`; `BaoCao.TXT` → `BaoCao.encrypted.txt`.
- [x] 5.5 Viết `tests/unit/test_file_rules.py` cho các hàm thuần trên. **Xong khi:** phủ hết ranh giới kích thước, 4 biến thể BOM/newline, và các ca đặt tên file.

## 6. HTTP Adapter — File API

- [x] 6.1 Viết `parse_key` cho multipart: strip → regex `^[+-]?[0-9]+$` (dùng `[0-9]` chứ không `\d` để loại chữ số Unicode) → chặn chuỗi dài quá 32 ký tự (design §Decisions.8). **Xong khi:** nhận ` 3 `, `+3`, `03`, `-0`; từ chối `3.0`, `1e3`, `1_000`, `٣`, và chuỗi 5000 chữ số không gây 500.
- [x] 6.2 Viết `app/api/routes_file.py`: `POST /api/caesar/file` với `file`, `key`, `action`, `response_mode` (mặc định `content`). `action` và `response_mode` **phân biệt hoa thường**; đuôi `.txt` **không** phân biệt. **Xong khi:** `ENCRYPT` → 422; `a.TXT` → được nhận.
- [x] 6.3 Cài thứ tự validate 6 bước: hiện diện trường → định dạng trường vô hướng → đuôi `.txt` (415) → dung lượng (413) → 0 byte (422) → UTF-8 (415). **Không** được `await file.read()` ở dòng đầu handler. **Xong khi:** file `.pdf` 10 MiB thiếu key → `"Thiếu khóa."`; `.md` 6 MiB với key hợp lệ → 415.
- [x] 6.4 Cài hai chế độ phản hồi: `content` trả JSON; `file` trả attachment `text/plain; charset=utf-8` kèm `Content-Disposition`. Dựng trọn bytes rồi mới trả, **không** dùng `StreamingResponse`, để lỗi luôn ra được JSON. **Xong khi:** lỗi ở mode `file` vẫn trả JSON chuẩn, không bao giờ trả attachment lỗi.
- [x] 6.5 Viết `tests/integration/test_file_endpoint.py` phủ 47 scenario của spec `file-cipher-api`. Dữ liệu 5 MiB sinh bằng `b"A" * LIMIT` trong bộ nhớ, **không commit file lớn vào repo**. **Xong khi:** toàn bộ xanh và `git status` sạch sau khi chạy test.

## 7. Web UI

- [x] 7.1 Tách `Caesar_Cipher_Tool_Demo.html` thành `app/templates/index.html` + `app/static/styles.css` + `app/static/app.js`; xóa hẳn `mockApi` và `USE_MOCK`. **Xong khi:** không còn dòng nào tính Caesar trong trình duyệt ngoài `shiftAlphabet(k)` phục vụ bảng dịch chuyển hiển thị.
- [x] 7.2 Áp 6 điểm sửa bắt buộc: giới hạn 5 MiB (tiêm `max_file_bytes` từ server qua Jinja2), tên file `.encrypted.txt`/`.decrypted.txt`, chuỗi lỗi theo docx §5, gửi `response_mode`, đường dẫn tương đối cùng origin, giữ BOM khi tải xuống. **Xong khi:** không còn `API_BASE` hay cổng 8080 ghi cứng, và ngưỡng 5 MiB không xuất hiện dưới dạng số literal trong JS.
- [x] 7.3 Việt hóa toàn bộ nhãn và giá trị hiển thị: Sao chép / Xóa / Đổi file / Gỡ file / Tải kết quả / Tạo ví dụ / Làm mới; tab Phân tích hiện "Mã hóa"/"Giải mã" và "Văn bản"/"File · <tên>"; tiêu đề thông báo tiếng Việt. **Xong khi:** không còn chuỗi `encrypt`, `decrypt`, `Network error`, `Server error` nào hiển thị ra giao diện.
- [x] 7.4 Bổ sung nút "Làm mới" toàn cục (reset đầu vào, file, khóa, kết quả, thông báo, 3 thanh trạng thái, đưa chế độ về Mã hóa và nguồn về Văn bản), giữ song song các nút "Xóa" từng panel. **Xong khi:** hai cơ chế cùng tồn tại và không ảnh hưởng nhau.
- [x] 7.5 Sửa các lệch còn lại: whitespace-only là **hợp lệ** (không phải lỗi); nút tải kết quả khả dụng ở **cả hai** nguồn đầu vào (nguồn bàn phím dùng tên `ket-qua.encrypted.txt`/`ket-qua.decrypted.txt`); nhãn đơn vị dung lượng là MiB; khóa **cả cụm** điều khiển trong lúc gửi request; ô khóa nhận dấu `+`. **Xong khi:** đủ 5 điểm, kiểm bằng tay trên trình duyệt.
- [x] 7.6 Dọn khung trang ngoài phạm vi: bỏ banner "backend giả lập", nav giả `CAESAR.IO` với link chết, footer "Share feedback / Report issue", chú thích `USE_MOCK`/`API_BASE`. **Xong khi:** không còn liên kết chết hay điều hướng tới trang chưa tồn tại.
- [x] 7.7 Sửa `realApi`: đọc HTTP status và content-type, hiển thị đúng `message` của server; chỉ báo lỗi kết nối khi thực sự không gọi được; bỏ `catch {}` rỗng. **Xong khi:** phản hồi lỗi 4xx/5xx hiện đúng thông báo tiếng Việt thay vì "không kết nối được máy chủ".
- [x] 7.8 Mount `/static` và route `GET /` trong `app/main.py`. **Xong khi:** `GET /` trả 200 và HTML chứa `5242880`.
- [x] 7.9 Viết `tests/integration/test_ui_assets.py` guard 6 điểm sửa bằng cách đọc thẳng `app.js`. **Xong khi:** test đỏ nếu ai đó vô tình đưa `API_BASE` hoặc ngưỡng 1 MB trở lại.
- [x] 7.10 Chạy tay đủ hai luồng docx §3.1 và §3.2 trên trình duyệt: nhập bàn phím và tải file, gồm kéo-thả, bảng dịch chuyển, tab Phân tích, copy, clear, download. **Xong khi:** cả hai luồng thông suốt, không lỗi console.

## 8. Docker và hoàn tất

- [x] 8.1 Viết `Dockerfile` multi-stage: copy `uv` từ image ghim phiên bản, `uv sync --frozen --no-dev`, copy lock trước source để tận dụng cache; runtime `USER appuser` (uid 10001), `EXPOSE 8000`, chạy `--host 0.0.0.0`. Viết `.dockerignore`. **Xong khi:** `docker build` thành công; `docker run --rm <image> id -u` khác `0`; `uv` không có trong image cuối.
- [x] 8.2 Xác minh container: `docker run -p 8000:8000` rồi `curl localhost:8000/` và `/docs` đều 200, hành vi giống hệt chạy local. **Xong khi:** `tests/integration/test_app_runtime.py` xanh và kiểm tay trên container đạt.
- [x] 8.3 Viết `README.md`: cách chạy local, chạy Docker, chạy test, chạy lint. **Xong khi:** người mới clone repo làm theo README chạy được ứng dụng mà không cần hỏi thêm.
- [x] 8.4 Bật `--cov-fail-under=90` trong `pyproject.toml` và chạy toàn bộ suite. Coverage **chỉ đo Python trong `app/`**, không tính JS/CSS/HTML. **Xong khi:** `uv run pytest` xanh với coverage ≥ 90%.
- [x] 8.5 Chạy `uv run ruff check .` và `uv run ruff format --check .`. **Xong khi:** cả hai sạch.
- [x] 8.6 Đối chiếu từng gạch đầu dòng của docx §7 (8 tiêu chí nghiệm thu) và tick từng cái. **Xong khi:** đủ 8/8, gồm file đúng 5 MiB được nhận và 5 MiB + 1 byte bị từ chối.

## 9. Đồng bộ ngược tài liệu

- [x] 9.1 Cập nhật `BE Scope – Week 1 Caesar Cipher MVP.docx` §5: thêm dòng thứ 13 `Body JSON không hợp lệ | 422 | Dữ liệu gửi lên không hợp lệ.` **Xong khi:** bảng §5 có đủ 13 dòng khớp `app/errors/messages.py`.
- [x] 9.2 Cập nhật docx §5: bổ sung quy tắc thứ tự kiểm tra 6 bước khi nhiều lỗi xảy ra cùng lúc. **Xong khi:** docx nêu đúng thứ tự đã cài trong `app/api/schemas.py`.
- [x] 9.3 Sửa docx §4.2: ví dụ hiện đặt nhầm cặp mã hóa dưới tiêu đề "Giải mã văn bản". **Xong khi:** §4.2 dùng `"Khoor Zruog"` + khóa 3 → `"Hello World"`.
- [x] 9.4 Cập nhật docx §2.2: nhãn nút hành động đổi động theo chế độ ("Mã hóa"/"Giải mã"), không phải "Thực hiện"; bổ sung các nút thực tế của giao diện. **Xong khi:** danh sách nút trong docx khớp `app/templates/index.html`.
- [x] 9.5 Xóa hoặc chuyển vào thư mục lưu trữ file `BE Scope – Week 1 Caesar Cipher MVP.before-ui-update.docx`. **Xong khi:** thư mục gốc chỉ còn đúng một bản scope, không ai nhầm bản cũ.

## 10. Remediation sau review hai trục

- [x] 10.1 Đồng bộ chính sách OpenSpec cho ngoại lệ hạ tầng 64 MiB vào `openspec/config.yaml` và đối chiếu lại toàn bộ spec/design đã sửa: primary DOCX cùng `docs/reference/be-scope-v1.0.md` giữ nguyên, 13 thông báo nghiệp vụ vẫn tách biệt với thông báo hạ tầng, change không bị archive. **Xong khi:** `openspec validate caesar-cipher-week1-mvp --strict` xanh và diff không chạm DOCX/bản trích. *(Việc sửa `openspec/config.yaml` được defer sang apply vì file nằm ngoài `artifactPaths.*.existingOutputPaths` của skill update-change.)*
- [x] 10.2 Bổ sung `REQUEST_TOO_LARGE = "Yêu cầu vượt quá dung lượng cho phép."`, cài request-size guard phân loại theo tuyến và test ranh 64 MiB: API file dùng `FILE_TOO_LARGE`, tuyến khác dùng generic 413, không có machine code và không lộ `64 MiB` trong message; giữ nguyên handler file 5 MiB. **Xong khi:** test phủ `64 MiB`, `64 MiB + 1`, header vắng/sai, body/field cũng lỗi, route file/non-file và local/container parity đều xanh.
- [x] 10.3 Sửa render kết quả UI để chuỗi hiển thị, sao chép và tải xuống đúng từng ký tự với `result` của server, không tự thêm newline. **Xong khi:** test hồi quy chuỗi có/không có newline cuối xanh và native Browser xác nhận DOM/copy/download khớp.
- [x] 10.4 Sửa lỗi tải file thất bại sau một lượt thành công: xóa result/analysis cũ, vô hiệu action phụ thuộc result, hiện placeholder và đặt status lỗi với `message` server. **Xong khi:** test tự động và native Browser chứng minh không còn success stale.
- [x] 10.5 Giải phóng buffer bytes thô ngay sau khi decode file, trước transform/dựng response. **Xong khi:** review đường dữ liệu xác nhận handler không giữ đồng thời biến `raw` qua phần transform và toàn bộ test file/BOM/newline vẫn xanh.
- [x] 10.6 Sửa runtime stage của Dockerfile dùng `useradd --create-home` và mọi `COPY` runtime cần thiết có `--chown=appuser:appuser`. **Xong khi:** image build được, app chạy uid khác 0, file runtime thuộc đúng user và `/`, `/docs`, API hoạt động.
- [x] 10.7 Bổ sung các giải thích bắt buộc: comment `MAX_FILE_BYTES` ghi `5242880 byte = 5 MiB`, UI hiện `5 MiB = 5.242.880 byte`, và comment cạnh `shiftAlphabet` nói rõ chỉ phục vụ hiển thị. **Xong khi:** test asset/config khóa đủ ba nội dung và giao diện browser hiển thị đúng clarification.
- [x] 10.8 Mở rộng guard `tests/integration/test_ui_assets.py` để cấm cả token `_encrypted`. **Xong khi:** test xanh trên code đúng và đỏ khi chèn lại token cấm.
- [x] 10.9 Bổ sung README nêu rõ ứng dụng Tuần 1 không có rate limit và không nên phơi trực tiếp ra Internet. **Xong khi:** README ghi rõ giới hạn và hướng giảm thiểu bằng reverse proxy/rate limit cho triển khai công khai.
- [x] 10.10 Thay ignore `.txt` toàn cục bằng đúng `/*.encrypted.txt` và `/*.decrypted.txt`; không tạo runtime directory. **Xong khi:** file output root-level được ignore, còn `.txt` ở thư mục khác vẫn hiện trong `git status`, phù hợp design.
- [x] 10.11 Chạy validation repository đầy đủ: toàn bộ `uv run pytest` với branch coverage ≥ 90%, `uv run ruff check .`, `uv run ruff format --check .`, OpenSpec strict validation và Docker build/runtime smoke. **Xong khi:** lưu lại command cùng kết quả xanh; không bỏ qua test hay hạ ngưỡng.
- [x] 10.12 Chạy genuine native Browser regression trên app local và container: hai luồng docx §3.1/§3.2, exact result, failed-download cleanup, Analysis → Xóa reset `state.view`/visible content/ARIA, và trong request cố ý trì hoãn khóa phím tắt cùng drop-zone click/Enter/Space/file-drop thực tế; kiểm console. **Xong khi:** có evidence quan sát cụ thể cho từng ca và không có console error ngoài lỗi được chủ động tạo.
- [x] 10.13 Chạy lại full two-axis code review từ fixed point `dbc8d285c73756de58429be23f1af88abaaa7a89` tới accepted HEAD; Standards và Spec độc lập. Ba smell đã ghi ở `Deferred technical debt` là non-blocking. **Xong khi:** không còn hard Standards violation hay Spec finding chưa xử lý và báo cáo giữ hai axis riêng.
- [x] 10.14 Sau khi toàn bộ evidence được chấp nhận, commit remediation trên isolated branch rồi push accepted HEAD tới remote `main` bằng refspec tường minh, chỉ khi quan hệ remote chứng minh fast-forward; tuyệt đối không force push và không archive OpenSpec. **Xong khi:** báo commit SHA, remote pre/post SHA và kết quả push chính xác; nếu remote đã tiến thì dừng để reconcile thay vì overwrite.
