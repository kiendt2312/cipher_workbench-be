# Thiết kế kỹ thuật — Caesar Cipher Week 1 MVP

Tài liệu này trả lời câu hỏi **LÀM THẾ NÀO**. Động cơ (TẠI SAO) và phạm vi (CÁI GÌ) đã nằm ở
[`proposal.md`](./proposal.md); hành vi quan sát được đã nằm ở các spec trong [`specs/`](./specs/).
Ở đây chỉ bàn cách hiện thực hóa chúng và lý do chọn cách đó.

## Context

- **Repo trống về mặt code.** Chỉ có `BE Scope – Week 1 Caesar Cipher MVP.docx` v1.0 (source of truth,
  đã trích sang `docs/reference/be-scope-v1.0.md` để grep), mockup `Caesar_Cipher_Tool_Demo.html`
  (540 dòng, HTML + CSS + JS nhét chung một file, chạy backend giả lập `USE_MOCK = true`) và thư mục
  `openspec/`. Không có legacy code, không có database, không có migration — mọi quyết định dưới đây
  là greenfield, chi phí đổi ý ở Tuần 1 gần bằng 0.
- **`uv` chưa được cài trên máy dev** (`which uv` → không tìm thấy), trong khi stack đã chốt dùng
  `uv` + `pyproject.toml`. Đây là việc phải làm đầu tiên, trước cả dòng code đầu tiên.
- **Python 3.12.3 và Docker 29.7.1 đã có sẵn** — không cần nâng cấp runtime, không cần cài Docker.
- **Ràng buộc định hình thiết kế:** ứng dụng stateless; một tiến trình phục vụ cả UI lẫn API
  (same-origin, không CORS); 13 thông báo lỗi tiếng Việt phải đúng nguyên văn từng chữ; ngưỡng
  dung lượng phải phân biệt chính xác 5242880 byte (nhận) với 5242881 byte (từ chối); coverage
  backend ≥ 90%.
- **Ràng buộc từ docx §6:** KHÔNG tạo abstract cipher interface hay repository pattern ở Tuần 1.

## Goals / Non-Goals

### Goals (ở tầng thiết kế)

- Ánh xạ 5 module trong docx §6 thành 5 ranh giới rõ ràng trong source tree, để task chia theo module
  không giẫm chân nhau.
- Đặt mọi hằng số và chuỗi thông báo hướng người dùng ở **đúng một nơi duy nhất**, để "5 MiB" và 13 chuỗi
  lỗi không bao giờ bị lệch giữa Python, template và JavaScript.
- Chọn cách hiện thực cho phép xử lý file 5 MiB trong thời gian người dùng không cảm nhận được, mà không
  mở cửa cho việc đẩy RAM.
- Làm cho thứ tự kiểm tra lỗi **xác định** (deterministic): một request cho trước luôn cho ra đúng một
  thông báo, không phụ thuộc thứ tự field trong form hay chi tiết nội bộ của framework.
- Giữ Caesar Core hoàn toàn độc lập với HTTP, để cùng một hàm phục vụ cả luồng bàn phím lẫn luồng file
  như docx §2.1 yêu cầu, và để test nó không cần dựng server.

### Non-Goals (ở tầng thiết kế)

- Không thiết kế lớp trừu tượng cho thuật toán thứ hai (Vigenère, ROT13…) — docx §6 cấm.
- Không thiết kế tầng persistence, cache, hàng đợi hay background task — app stateless.
- Không thiết kế cơ chế i18n/đa ngôn ngữ — toàn bộ text hướng người dùng là tiếng Việt cứng.
- Không thiết kế build pipeline cho frontend (bundler, transpiler, npm) — UI là HTML/CSS/JS thuần.
- Không thiết kế CI/CD, observability stack hay chiến lược triển khai cloud — ngoài phạm vi docx §8.
- Không tối ưu cho file lớn hơn 5 MiB (streaming transform, xử lý theo dòng) — ngưỡng cứng 5 MiB làm
  cho cách "đọc trọn vào bộ nhớ rồi biến đổi một lần" là đủ và đơn giản hơn nhiều.

## Decisions

### 1. Cấu trúc thư mục ánh xạ 1-1 với 5 module trong docx §6

**Quyết định.** Dùng layout `app/core/`, `app/services/`, `app/api/`, `app/errors/`, `app/templates/`,
`app/static/`, `tests/unit/`, `tests/integration/`. Chi tiết đầy đủ ở mục
[Project Structure](#project-structure) bên dưới.

**Lý do.** docx §6 đã chia sẵn 5 module với trách nhiệm tách bạch, và `openspec/config.yaml` yêu cầu
chia task theo đúng 5 module đó. Nếu thư mục ánh xạ 1-1 với module thì: (a) mỗi task chạm một thư mục,
hai người làm song song hiếm khi conflict; (b) khi review, câu hỏi "code này thuộc module nào" có câu
trả lời cơ học thay vì phải tranh luận; (c) mỗi capability spec soi chiếu được vào đúng một thư mục,
nên truy vết spec → code → test là thẳng hàng.

| docx §6 | Thư mục |
|---|---|
| Caesar Core | `app/core/` |
| File Processing | `app/services/` |
| HTTP Adapter | `app/api/` |
| Web UI | `app/templates/` + `app/static/` |
| Exception Handling | `app/errors/` |

**Phương án đã cân nhắc rồi loại.**
- *Layout phẳng (`app/caesar.py`, `app/api.py`, `app/errors.py`…).* Ngắn hơn, nhưng xóa mất ranh giới
  module ngay khi file thứ hai xuất hiện trong cùng một mối quan tâm, và làm quy tắc phụ thuộc
  (mục [Project Structure](#project-structure) §3) không thể diễn đạt bằng đường dẫn.
- *Layout theo feature-slice (`app/text_cipher/`, `app/file_cipher/`).* Sẽ nhân đôi Caesar Core hoặc
  đẻ ra một thư mục `shared/` — đi ngược yêu cầu "cùng một module Caesar Core phải được tái sử dụng
  cho cả input bàn phím và file" (docx §2.1).
- *Tách `src/` layout.* Có lợi khi đóng gói thành library phân phối qua PyPI; ở đây ứng dụng chạy trực
  tiếp, thêm một tầng thư mục chỉ làm import dài hơn mà không đổi gì.

### 2. Caesar Core là hàm thuần, không phải class hierarchy

**Quyết định.** `app/core/caesar.py` chỉ export một hàm thuần — **`transform_text(text, key, operation)`**:

```python
Operation = Literal["encrypt", "decrypt"]

def transform_text(text: str, key: int, operation: Operation) -> str: ...
```

**Đây là chữ ký chính thức của module Caesar Core, truy vết docx §2.1 ("Cung cấp một interface chính:
`transform_text(text, key, operation)`") và docx §6 (bảng module, dòng Caesar Core).** `operation` có
**đúng hai giá trị hợp lệ: `"encrypt"` và `"decrypt"`**, viết thường, phân biệt hoa thường.

> **Lưu ý về nơi lưu giữ hợp đồng này.** Các spec trong `specs/` là hợp đồng **hành vi quan sát được**
> nên không được nêu tên hàm nội bộ; chữ ký `transform_text(text, key, operation)` vì vậy đã được gỡ
> khỏi `specs/caesar-core/spec.md`. **`design.md` là nơi duy nhất còn giữ chữ ký này trong bộ artifact**,
> và nó là hợp đồng bắt buộc vì docx §2.1/§6 đã chốt — implement phải dùng đúng tên hàm và đúng bộ ba
> tham số này, không đổi thành `caesar(text, shift)`, `encrypt/decrypt` tách đôi hay biến thể khác.

Không `CipherBase`, không `CaesarCipher(Cipher)`, không factory, không registry, không repository.
`Operation` là `Literal["encrypt", "decrypt"]` (hoặc `StrEnum`) chứ không phải hệ thống lớp. Hàm không
có state, không đọc config, không log, không ném exception nghiệp vụ — key bao nhiêu cũng hợp lệ vì đã
chuẩn hóa modulo 26; việc *key có phải số nguyên hay không* là chuyện của tầng API.

**Lý do.** docx §6 nói thẳng: "Không tạo abstract cipher interface hoặc repository pattern trong Tuần 1.
Chỉ thêm seam dùng chung khi một feature tương lai thực sự cần implementation thứ hai." Một interface
trừu tượng dựng từ **một** implementation duy nhất gần như luôn sai hình dạng: nó được suy ra từ chi
tiết của Caesar (một tham số `key` kiểu int, dịch vòng 26 chữ cái) chứ không từ nhu cầu chung thật sự,
nên khi thuật toán thứ hai xuất hiện ta vẫn phải sửa interface — mất công hai lần mà không được gì.

**Trade-off YAGNI vs khả năng mở rộng tuần sau.** Rủi ro thật là: Tuần 2 thêm thuật toán thứ hai và phải
refactor. Điều làm cho rủi ro này **rẻ và an toàn** là:

1. `transform_text` là hàm thuần, không state, không I/O → refactor nó là thao tác cơ học, công cụ IDE
   làm được, và không có gì để "migrate".
2. Toàn bộ tầng trên chỉ phụ thuộc vào *chữ ký* của nó, và chữ ký này (text vào, text ra) chính là hình
   dạng chung của mọi cipher đối xứng — đó đã là một seam, chỉ là seam ở mức hàm thay vì mức class.
3. Có test unit phủ 100% core, nên khi refactor, test sẽ bắt mọi hồi quy ngay lập tức. docx §8 đã yêu
   cầu "các task của tuần tiếp theo phải có regression test cho chức năng Tuần 1".
4. Điểm phải sửa khi thêm cipher thứ hai đếm được: một tham số mới ở tầng API và một nhánh dispatch.
   Chi phí đó nhỏ hơn chi phí nuôi một lớp trừu tượng sai suốt cả tuần.

**Phương án đã cân nhắc rồi loại.** Protocol/ABC `Cipher` với `CaesarCipher` là implementation đầu tiên —
loại vì docx cấm và vì lý do (1)–(4) ở trên. Class `CaesarCipher` giữ `key` trong `__init__` — loại vì
biến một phép biến đổi không state thành một object có vòng đời, khiến việc tái sử dụng giữa hai luồng
(text/file) phải bàn thêm chuyện tạo/tái dùng instance mà không đổi lại được lợi ích gì.

### 3. Dịch ký tự bằng `str.translate()` với 26 bảng dựng sẵn

**Quyết định.** Dựng sẵn 26 bảng dịch (một bảng cho mỗi khóa đã chuẩn hóa 0–25) ở thời điểm import
module, rồi biến đổi cả chuỗi bằng một lời gọi `str.translate()`:

```python
_UP, _LO = string.ascii_uppercase, string.ascii_lowercase
_TABLES = [
    str.maketrans(_UP + _LO, _UP[k:] + _UP[:k] + _LO[k:] + _LO[:k])
    for k in range(26)
]
# encrypt: text.translate(_TABLES[key % 26])
# decrypt: text.translate(_TABLES[(-key) % 26])
```

Giải mã **không** cần bảng riêng: giải mã với khóa `k` bằng mã hóa với khóa `-k`, sau chuẩn hóa modulo 26
vẫn rơi vào cùng 26 bảng đó.

**Lý do — số đo thực tế trên máy dev (Python 3.12.3, file 5 MiB):**

| Cách làm | Văn bản ASCII 5 MiB | Văn bản tiếng Việt ~5 MiB |
|---|---|---|
| `str.translate()` + bảng dựng sẵn | **≈ 4,4 ms** | **≈ 136 ms** |
| Vòng lặp từng ký tự (gom list rồi `join`) | ≈ 371 ms (**~85×** chậm hơn) | ≈ 315 ms |
| Vòng lặp từng ký tự (nối chuỗi `out += ch`) | ≈ 388 ms (**~88×** chậm hơn) | — |

Chi phí dựng cả 26 bảng: **≈ 72 µs, một lần duy nhất** lúc import — nhỏ đến mức không cần lazy-init.
Chi phí `bytes.decode("utf-8")` cho 5 MiB: **≈ 8 ms**.

**Ước lượng độ trễ cho file 5 MiB (phần CPU của server):** decode ≈ 8 ms + transform ≈ 5–140 ms +
encode ≈ 10 ms → **khoảng 25–160 ms**, tùy tỉ lệ ký tự non-ASCII. Trường hợp xấu nhất vẫn dưới ngưỡng
200 ms mà người dùng bắt đầu cảm nhận là "chậm", và bị lấn át bởi thời gian upload 5 MiB qua mạng.
Với vòng lặp, riêng phần transform đã ~0,4 s và tăng tuyến tính theo số request đồng thời — đủ để một
người dùng bình thường cũng làm tắc worker.

**Lợi ích phụ, quan trọng ngang hiệu năng:** `str.translate` ánh xạ theo code point và **để nguyên mọi
ký tự không có trong bảng**. Vì bảng chỉ chứa 52 chữ cái ASCII, nên chữ số, khoảng trắng, `\n`, `\r`,
`\t`, tiếng Việt có dấu, emoji, ký tự đặc biệt và cả `U+FEFF` nằm giữa nội dung đều đi qua nguyên vẹn
**một cách tự nhiên, không cần một nhánh `else` nào**. Yêu cầu "giữ nguyên mọi ký tự khác" (docx §2.1)
trở thành thuộc tính cấu trúc của giải pháp chứ không phải một điều kiện do lập trình viên nhớ viết —
nghĩa là không thể quên, và cũng chính là thứ bảo toàn `\r\n` nguyên trạng (xem Quyết định 5).

**Phương án đã cân nhắc rồi loại.**
- *Vòng lặp `for ch in text` với số học `ord`/`chr`.* Trực quan, giống mockup JS, dễ đọc với người mới —
  nhưng chậm ~85× và phải tự viết nhánh giữ nguyên ký tự (nơi dễ sinh bug nhất). Vẫn giữ nó lại **trong
  test** như một implementation tham chiếu độc lập để đối chiếu kết quả (xem Quyết định 11).
- *Dựng bảng theo yêu cầu mỗi request (`str.maketrans` mỗi lần gọi).* Chỉ tốn vài µs, nhưng dựng sẵn 26
  bảng rẻ hơn nữa, bất biến và loại bỏ hẳn câu hỏi có nên cache hay không.
- *`bytes.translate` trên dữ liệu chưa decode.* Nhanh nhất về lý thuyết, nhưng phá vỡ yêu cầu encoding:
  ta vẫn **phải** decode UTF-8 để phát hiện file không phải UTF-8 (docx §5 → 415). Bỏ decode nghĩa là
  bỏ luôn một yêu cầu nghiệm thu, nên "nhanh hơn" ở đây là nhanh sai.
- *Dịch bằng regex `re.sub` với callback.* Chậm hơn cả vòng lặp thuần, không xét tiếp.

### 4. Cưỡng chế giới hạn 5 MiB: đọc theo chunk trên **bytes**, dừng ở byte thứ 5242881

**Vấn đề.** Gọi `await file.read()` không tham số rồi mới đo `len()` nghĩa là đã nạp toàn bộ payload vào
bộ nhớ *trước khi* biết nó có hợp lệ hay không — một client gửi 2 GiB sẽ được phục vụ đầy đủ cho tới
lúc bị từ chối.

**Quyết định — phòng thủ hai tầng.**

*Tầng 0 — ngoại lệ hạ tầng chống cạn tài nguyên, được chủ sở hữu phê duyệt (KHÔNG phải nguồn chân lý
nghiệp vụ).* Một dependency/middleware đọc header `Content-Length`; nếu có, parse được và vượt
`MAX_REQUEST_BYTES = 64 MiB` thì trả 413 ngay, không đọc body. Phân loại phản hồi **theo tuyến**, không
theo `Content-Type`: request tới `/api/caesar/file` dùng 413 + chuỗi nghiệp vụ file hiện có
`"File vượt quá dung lượng tối đa 5 MB."`; mọi tuyến khác dùng 413 + chuỗi hạ tầng
`"Yêu cầu vượt quá dung lượng cho phép."`. Cả hai dùng đúng envelope `success`/`message`, không thêm
machine-readable code; chuỗi generic cố ý không công khai con số 64 MiB. Chuỗi hạ tầng này không phải
thông báo nghiệp vụ thứ 14 của docx §5, và chỉ được định nghĩa trong OpenSpec/code thực thi — không sửa
hay diễn giải lại docx hoặc bản trích của nó.

Đặt trần cao hơn hẳn 5 MiB là có chủ ý: mọi payload ở quy mô thực tế (kể cả file 10 MiB trong ví dụ ở
Quyết định 9) vẫn đi tới handler để nhận đúng thông báo theo thứ tự đã chốt; chỉ payload ở quy mô rõ
ràng lạm dụng mới bị chặn sớm. `Content-Length` do client khai và có thể vắng mặt hoặc sai định dạng
(ví dụ chunked transfer-encoding), nên request như vậy đi tiếp; tầng này **không bao giờ** được dùng để
quyết định ranh giới file 5 MiB. Ngưỡng đúng 64 MiB cũng đi tiếp, chỉ `>` mới bị chặn. Hành vi và phản
hồi của tầng này phải giống nhau giữa local và container.

*Tầng 1 — nguồn chân lý.* Trong handler, đọc `UploadFile` theo chunk 64 KiB, cộng dồn vào `bytearray`,
và dừng ngay khi tổng vượt ngưỡng:

```python
LIMIT = 5 * 1024 * 1024  # 5242880
buf = bytearray()
while chunk := await upload.read(64 * 1024):
    buf.extend(chunk)
    if len(buf) > LIMIT:          # đúng 5242880 -> đi tiếp; 5242881 -> dừng
        raise FileTooLargeError()
```

Điều kiện là `>` chứ không phải `>=`, nên **5242880 byte được nhận, 5242881 byte bị từ chối** — đúng
tiêu chí nghiệm thu docx §7 — và đây là phép đếm byte thật do chính ta thực hiện, không phải con số do
ai khác khai báo. Vòng lặp thoát ngay khi vượt ngưỡng, nên lượng byte giữ trong bộ nhớ bị chặn ở
`LIMIT + 64 KiB` bất kể client gửi bao nhiêu.

**Toàn bộ thao tác ở chế độ BYTES, không bao giờ ở chế độ text.** Không dùng `open(..., "r")`,
không `io.TextIOWrapper`, không `file.read().decode()` trên từng chunk. Hai lý do:

1. **Universal newlines.** Chế độ text của Python âm thầm chuyển `\r\n` → `\n`. Spec `file-cipher-api`
   và `caesar-core` yêu cầu bảo toàn nguyên trạng ký tự kết thúc dòng: file CRLF tải xuống phải vẫn là
   CRLF, file chỉ có `\n` không được tự mọc thêm `\r`. Đọc bytes là cách duy nhất đảm bảo điều đó.
2. **Decode không được cắt ngang.** Một ký tự UTF-8 nhiều byte có thể nằm vắt qua ranh giới chunk; decode
   từng chunk sẽ sinh `UnicodeDecodeError` giả và trả 415 cho file hoàn toàn hợp lệ. Vì thế **gom đủ
   bytes trước, decode một lần duy nhất ở cuối** (chi phí chỉ ≈ 8 ms cho 5 MiB).

**Phương án đã cân nhắc rồi loại.**
- *Tin `UploadFile.size`.* Starlette có điền thuộc tính này, nhưng nó phản ánh trạng thái **sau khi**
  multipart parser đã ghi xong toàn bộ file — dùng nó làm lá chắn tài nguyên là tự lừa mình. Có thể
  dùng như đường tắt tối ưu, nhưng khi ấy lại có *hai* nguồn sự thật cho cùng một ranh giới; một nguồn
  duy nhất (phép đếm của ta) đơn giản và dễ test hơn.
- *Chỉ dựa vào `Content-Length`.* Client tự khai, có thể nói dối hoặc không gửi; ngoài ra nó đo cả phong
  bì multipart (boundary, header của part, tên file) nên **không** so sánh trực tiếp được với 5242880 —
  một file đúng 5 MiB sẽ có `Content-Length` lớn hơn 5242880 vài trăm byte và bị từ chối oan. Vì vậy nó
  chỉ đóng được vai trò trần thô ở Tầng 0.
- *Cấu hình `max_part_size` của multipart parser.* Chặn được sớm, nhưng lỗi ném ra từ tầng parser khó
  ánh xạ về đúng chuỗi `"File vượt quá dung lượng tối đa 5 MB."` với đúng mã 413, và làm ranh giới
  nghiệp vụ trôi vào cấu hình thư viện — nơi không ai đọc khi review.

**Giới hạn còn lại, ghi nhận thành thật.** FastAPI hoàn tất việc phân tích multipart *trước khi* handler
chạy, nên với payload dưới trần Tầng 0 thì body đã được nạp (Starlette tràn ra đĩa khi vượt ~1 MiB, nên
RAM mỗi request vẫn bị chặn). Phép đọc theo chunk vì thế bảo vệ **bộ nhớ của tiến trình ta** và quyết
định ranh giới chính xác, còn Tầng 0 mới là thứ bảo vệ khỏi payload khổng lồ. Với một app học tập chạy
same-origin, mức phòng thủ này là tương xứng; xem thêm mục Risks.

### 5. UTF-8 BOM: phát hiện trên bytes thô, bỏ khi biến đổi, gắn lại đúng theo đầu vào

**Quyết định — ba bước, tách bạch.**

1. **Phát hiện trên bytes thô**, trước mọi thao tác decode:
   `had_bom = raw.startswith(b"\xef\xbb\xbf")`. Cờ này là dữ liệu đi kèm nội dung suốt quá trình xử lý.
2. **Bỏ BOM khi biến đổi:** decode bằng codec `utf-8-sig`, codec này bỏ BOM nếu có và hoạt động bình
   thường nếu không có. Văn bản đưa vào `transform_text` vì vậy **không bao giờ** chứa `U+FEFF` mở đầu,
   nên BOM không bị đếm như một ký tự nội dung và không lọt vào preview. Bytes không hợp lệ UTF-8 vẫn
   làm codec ném `UnicodeDecodeError` → ánh xạ thành 415 `"File phải sử dụng UTF-8."`
   Lưu ý: cờ `had_bom` lấy từ bytes thô chứ **không** suy ra từ hành vi của codec — tách bạch "phát
   hiện" khỏi "decode" khiến mỗi phần test được độc lập.
3. **Gắn lại ở mode `file`:** `body = (b"\xef\xbb\xbf" if had_bom else b"") + result.encode("utf-8")`.
   Đầu vào có BOM → đầu ra bắt đầu bằng `EF BB BF`; đầu vào không BOM → **không tự thêm** BOM.

**Hành vi ở mode `content`.** `result` trong JSON **không bao giờ** chứa BOM, kể cả khi file đầu vào có.
Lý do: BOM là dấu hiệu encoding của một file, không phải ký tự nội dung; JSON đã tự khai báo UTF-8 nên
BOM ở đó vô nghĩa, và nếu lọt vào sẽ hiện thành một ký tự vô hình ở đầu preview trên UI. Cờ `had_bom`
vẫn được tính ở mode `content` (chi phí bằng 0) nhưng không được dùng — nhờ vậy hai mode dùng chung
đúng một đường xử lý, chỉ khác nhau ở bước đóng gói response cuối cùng.

**Chỉ BOM mở đầu mới bị bỏ.** Một `U+FEFF` nằm giữa nội dung là ký tự thật, không phải chữ cái ASCII,
nên `str.translate` giữ nguyên nó và nó được encode trở lại y hệt. Không cần code đặc biệt.

**Nhất quán với Quyết định 4.** Cả hai đều thao tác trên `bytes` rồi mới decode thủ công đúng một lần.
Nếu dùng chế độ text, universal newlines sẽ biến `\r\n` thành `\n` và file tải xuống khác file gốc —
lỗi âm thầm, không test nào ở tầng API bắt được nếu không cố ý kiểm tra byte.

**Phương án đã cân nhắc rồi loại.**
- *`decode("utf-8")` rồi `lstrip("﻿")`.* Cho kết quả tương tự nhưng gộp hai ý niệm vào một dòng và
  `lstrip` sẽ bóc **nhiều** `U+FEFF` liên tiếp — làm mất dữ liệu trong trường hợp biên hiếm gặp.
- *Luôn ghi BOM ở đầu ra.* Đơn giản hơn một nhánh, nhưng vi phạm thẳng spec "không tự thêm BOM" và làm
  bẩn file của người dùng dùng Linux.
- *Không bao giờ ghi BOM.* Vi phạm docx §2.4 và làm hỏng trải nghiệm mở file bằng Notepad/Excel trên
  Windows — chính là lý do quy tắc giữ BOM tồn tại.

### 6. Cưỡng chế khuôn dạng error response: exception nghiệp vụ + bộ exception handler ở tầng app

**Vấn đề.** FastAPI mặc định trả `{"detail": [...]}` kèm 422 cho lỗi validation của Pydantic, và
`{"detail": "..."}` cho `HTTPException`. Cả hai đều **sai khuôn dạng** so với hợp đồng
`{"success": false, "message": "..."}`, và thông báo của Pydantic bằng tiếng Anh, lộ tên field cùng chi
tiết kỹ thuật — vi phạm docx §1 ("không để lỗi kỹ thuật hoặc stack trace xuất hiện trên giao diện").

**Quyết định — ba thành phần.**

*(a) Một lớp exception nghiệp vụ duy nhất.* `app/errors/exceptions.py`:

```python
class CaesarError(Exception):
    status_code: int
    message: str      # lấy từ app/errors/messages.py, nguyên văn docx §5
```

kèm các lớp con mỏng (`MissingKeyError`, `InvalidKeyError`, `FileTooLargeError`,
`UnsupportedEncodingError`, …), mỗi lớp chỉ cố định sẵn cặp `(status_code, message)`. Mọi tầng dưới
HTTP ném `CaesarError`; chúng **không** import `HTTPException` và không biết gì về FastAPI.

*(b) Validate nghiệp vụ nằm trong code của ta, không ủy cho Pydantic.* Model request khai báo **lỏng**
(`text: Any`, `key: Any` với sentinel cho "vắng mặt") để Pydantic gần như không bao giờ tự từ chối;
toàn bộ quy tắc nằm trong một hàm validate viết tay chạy theo đúng thứ tự ở Quyết định 9. Đây là điểm
then chốt: nó biến "đè lại thông báo của framework" (mong manh, phụ thuộc phiên bản) thành "framework
không bao giờ tạo ra thông báo cần đè" (xác định, tự kiểm soát). Nhờ vậy ta kiểm soát được cả thứ tự
kiểm tra lẫn chuỗi thông báo — hai thứ Pydantic không cho phép điều khiển tới mức docx §5 đòi hỏi.

*(c) Bốn exception handler đăng ký ở `app/errors/handlers.py`, tất cả trả `JSONResponse`:*

| Handler | Khi nào kích hoạt | Phản hồi |
|---|---|---|
| `CaesarError` | Mọi lỗi nghiệp vụ đã biết | `exc.status_code` + `{"success": false, "message": exc.message}` |
| `RequestValidationError` | Body JSON hỏng, không phải object, sai Content-Type | 422 + `"Dữ liệu gửi lên không hợp lệ."` |
| `HTTPException` | 404/405… do Starlette sinh | Giữ status, bọc lại thành khuôn dạng chuẩn |
| `Exception` | Bug ngoài dự kiến | 500 + `"Đã xảy ra lỗi hệ thống."`, log traceback nội bộ |

Handler `RequestValidationError` **phải** được đăng ký tường minh — đây chính là chỗ FastAPI cài sẵn
handler mặc định của nó, không đăng ký đè thì `{"detail": ...}` sẽ lọt ra ngoài.

**Chuỗi `"Dữ liệu gửi lên không hợp lệ."` là dòng thứ 13 đã được duyệt và đã được bổ sung vào bảng
docx §5.** Trường hợp body không đọc được (ví dụ `{"text": "a", "key":`, body không phải JSON object
hoặc multipart méo) chắc chắn xảy ra trong thực tế và không thể im lặng. Chuỗi cũng là requirement
"Ánh xạ lỗi HTTP 422 cho thân yêu cầu không đọc được" trong `specs/error-handling/`. Về mặt code, nó
nằm trong `app/errors/messages.py` để giữ đúng một nguồn sự thật cho toàn bộ 13 thông báo.

**Chuỗi `"Yêu cầu vượt quá dung lượng cho phép."` là ngoại lệ hạ tầng, không phải dòng thứ 14 của
docx §5.** `app/errors/messages.py` giữ chuỗi này bên cạnh 13 chuỗi nghiệp vụ để code vẫn có một nguồn
sự thật, nhưng test và tài liệu phải phân biệt rõ hai tập. Request-size guard chọn giữa chuỗi file và
chuỗi generic theo tuyến như Quyết định 4, rồi trả cùng envelope hai trường; không sửa primary DOCX
hay `docs/reference/be-scope-v1.0.md` để hợp thức hóa quyết định hạ tầng này.

**Đảm bảo lỗi vẫn là JSON ngay cả khi `response_mode=file`.** Hai cơ chế cộng lại:

1. Exception handler được đăng ký ở **tầng ứng dụng**, nên nó chặn bất kể endpoint nào ném lỗi và bất kể
   `response_mode` là gì. Endpoint không có quyền tự chọn khuôn dạng lỗi.
2. **Không dùng `StreamingResponse` cho mode `file`.** Toàn bộ bytes kết quả được dựng xong trong bộ nhớ
   rồi mới trả bằng một `Response(content=..., media_type="text/plain; charset=utf-8")` kèm header
   `Content-Disposition`. Nhờ vậy, tại thời điểm response bắt đầu được ghi ra, mọi kiểm tra đã xong và
   không còn khả năng thất bại — không bao giờ có tình huống "đã gửi nửa file attachment rồi mới gặp
   lỗi", tình huống mà về mặt HTTP là không thể sửa được. Với trần 5 MiB, dựng trọn trong bộ nhớ là hoàn
   toàn chấp nhận được (xem Quyết định 3).

**Ghi log.** Handler `Exception` và mọi `CaesarError`/`HTTPException` có status từ 500 trở lên log
traceback đầy đủ ở mức `ERROR` kèm loại lỗi, endpoint và thời điểm, nhưng **không log nội dung văn bản
hay nội dung file** của người dùng (app stateless, docx §8). Các `CaesarError` 4xx là lỗi người dùng;
việc log chúng chỉ là tùy chọn và không kèm traceback.

**Lưu ý khi test.** `TestClient` mặc định để exception ngoài dự kiến nổi lên thay vì đi qua handler;
muốn khẳng định hành vi 500, phải dựng client với `raise_server_exceptions=False`.

**Phương án đã cân nhắc rồi loại.**
- *Ném `HTTPException(status_code, detail=...)` từ khắp nơi rồi đè `http_exception_handler`.* Hoạt động
  được, nhưng kéo FastAPI vào tầng service/core, phá quy tắc phụ thuộc và khiến test core phải import
  framework.
- *Middleware bọc mọi response rồi viết lại thân.* Phải parse rồi serialize lại JSON cho **cả** đường
  thành công, tốn kém và dễ làm hỏng response attachment ở mode `file`.
- *Dịch thông báo của Pydantic sang tiếng Việt bằng một bảng ánh xạ.* Cực kỳ mong manh: thông báo của
  Pydantic là chi tiết nội bộ, đổi theo phiên bản, và không bao giờ ánh xạ 1-1 vào 13 dòng của docx §5.

### 7. Giữ nguyên kiểu JSON của key và nhận mọi JSON integer mà không dựng số nguyên khổng lồ

**Vấn đề — hai cạm bẫy chồng lên nhau.**
1. **`bool` là lớp con của `int` trong Python.** `isinstance(True, int)` là `True`, và `True + 2 == 3`.
   Một kiểm tra `isinstance(key, int)` sẽ **chấp nhận** `{"key": true}` rồi mã hóa với khóa 1 — sai âm
   thầm, không lỗi, không log, kết quả trông vẫn "hợp lý".
2. **Pydantic ép kiểu lỏng ở chế độ mặc định:** `"3"` → `3`, `3.0` → `3`. Spec `text-cipher-api` yêu cầu
   từ chối cả hai bằng 422 `"Khóa phải là số nguyên."`

3. **Parser chuẩn của Python giới hạn chuyển chuỗi thập phân sang `int`.** Từ Python 3.11, một JSON
   integer dài hơn mặc định 4.300 chữ số làm `json.loads` ném `ValueError`, trong khi spec
   `text-cipher-api` yêu cầu nhận mọi JSON integer và trần request hạ tầng đã giới hạn tổng body ở
   64 MiB.

**Quyết định.** Hai route text đọc body JSON bằng `json.loads(..., parse_int=JsonIntegerToken)`. Hook
`parse_int` chỉ được JSON decoder gọi cho token số nguyên đúng cú pháp; vì vậy numeric string vẫn là
`str`, boolean vẫn là `bool`, float vẫn là `float`, còn JSON integer được giữ bằng một subtype `str`
riêng thay vì bị đổi ngay thành Python `int`. `parse_key` chỉ nhận **chính xác** `JsonIntegerToken`
(hoặc `int` khi model được gọi trực tiếp trong code/test), rồi tính modulo 26 theo từng chữ số. Cách
này tuyến tính theo kích thước body, không tắt giới hạn an toàn toàn tiến trình và không dựng số nguyên
khổng lồ chỉ để Caesar Core chuẩn hóa lại:

```python
if key is MISSING or key is None:
    raise MissingKeyError()            # 422 "Thiếu khóa."
if type(key) is JsonIntegerToken:
    return decimal_modulo_26(key)       # giữ dấu; không gọi int(key)
if type(key) is not int:               # bool/float/str/list/dict đều rớt ở đây
    raise InvalidKeyError()            # 422 "Khóa phải là số nguyên."
```

`type(True) is bool`, không phải token hay `int`, nên kiểm tra vẫn loại sạch boolean; float, string,
list và dict cũng đều rớt. Route parse thủ công vẫn bắt buộc media type JSON, body đọc được và top-level
object trước khi chạy thứ tự validate field; OpenAPI request schema được khai báo tường minh để `/docs`
không mất hợp đồng.

**Quy tắc "thiếu" và "sai kiểu" (đã chốt, áp dụng cho cả hai endpoint).** `key` vắng mặt, `key: null`,
hoặc (ở multipart) `key` là chuỗi rỗng → 422 `"Thiếu khóa."`; chỉ khi **có giá trị thực mà không parse
được thành số nguyên** mới trả `"Khóa phải là số nguyên."` (căn cứ: mockup dòng 319–323). Ranh giới này
là lý do bắt buộc phải có sentinel `MISSING` — nếu dùng `None` làm giá trị mặc định thì không phân biệt
được "client không gửi key" với "client gửi `key: null`", dù ở đây cả hai cùng cho một thông báo, việc
tách bạch vẫn giữ cho logic đọc đúng ý định.

**Phương án đã cân nhắc rồi loại.**
- *`key: StrictInt` của Pydantic.* Về mặt kiểu thì đúng (strict mode từ chối cả bool, str và float),
  nhưng lỗi phát ra dưới dạng `RequestValidationError` với khuôn dạng riêng của Pydantic; để tách
  "thiếu key" khỏi "key sai kiểu" thành hai thông báo khác nhau, ta phải đi bới `exc.errors()[0]["type"]`
  bên trong handler — tức là phụ thuộc vào chi tiết nội bộ của thư viện để quyết định một chuỗi mà docx
  quy định nguyên văn. Đổi phiên bản Pydantic có thể làm hỏng lặng lẽ.
- *`isinstance(key, int) and not isinstance(key, bool)`.* Đúng về hành vi, nhưng diễn đạt quy tắc theo
  kiểu "trừ hao" và mọi người đọc đều phải dừng lại nghĩ một nhịp. `type(v) is int` nói thẳng điều ta muốn.
- *Dùng parser mặc định rồi tắt toàn cục `sys.set_int_max_str_digits(0)`.* Đáp ứng ca hơn 4.300 chữ số
  nhưng gỡ biện pháp chống DoS cho toàn tiến trình và vẫn dựng một `int` khổng lồ không cần thiết.
- *Tự viết parser JSON hoàn chỉnh.* Không cần thiết; hook chuẩn `parse_int` đã giữ đúng ranh giới kiểu
  JSON mà không phải tự hiện thực grammar JSON.

### 8. Validate `key` ở endpoint multipart: quy tắc parse chuỗi tường minh (QUYẾT ĐỊNH THIẾT KẾ)

**Vấn đề.** Trong `multipart/form-data`, **mọi** trường đều tới dưới dạng chuỗi — không có kiểu JSON để
dựa vào, nên quy tắc "phải là JSON integer" ở Quyết định 7 không áp dụng được. docx §4.3 chỉ nói `key` là
"số nguyên có dấu" mà không định nghĩa chuỗi nào được coi là hợp lệ. **Đây là điểm docx chưa nói rõ; các
quy tắc dưới đây là quyết định thiết kế của team, không phải trích dẫn docx.**

**Quyết định — thuật toán parse.**

1. Trường vắng mặt → `"Thiếu khóa."`
2. `strip()` khoảng trắng hai đầu; nếu kết quả rỗng → `"Thiếu khóa."`
3. Nếu chuỗi dài hơn 32 ký tự → `"Khóa phải là số nguyên."` (chặn trước, xem ghi chú bên dưới)
4. Khớp với regex **`^[+-]?[0-9]+$`**; không khớp → `"Khóa phải là số nguyên."`
5. Khớp → `int(chuỗi)`, sau đó chuẩn hóa modulo 26 ở core.

| Đầu vào | Kết quả | Vì sao |
|---|---|---|
| `"3"`, `"-3"`, `"0"`, `"9999"` | Nhận | Trường hợp thông thường; docx yêu cầu hỗ trợ khóa âm và khóa > 25 |
| `" 3 "` | Nhận (= 3) | Khoảng trắng thừa gần như luôn là artifact của copy-paste hoặc autofill, không phải ý định người dùng |
| `"+3"` | Nhận (= 3) | Là số nguyên có dấu không mơ hồ; docx nói "số nguyên **có dấu**" |
| `"03"` | Nhận (= 3) | Số 0 đứng đầu không gây mơ hồ trong hệ thập phân; từ chối chỉ gây khó chịu vô ích |
| `"-0"` | Nhận (= 0) | Chuẩn hóa modulo 26 cho ra 0, giống hệt `"0"` |
| `"3.0"`, `"3."` | **Từ chối** | **Nhất quán với endpoint JSON**, nơi `3.0` bị từ chối tường minh. Hai endpoint cùng một nghiệp vụ mà đối xử khác nhau với cùng một giá trị sẽ làm người dùng và người viết test bối rối |
| `"1e3"`, `"0x1F"`, `"1_000"` | **Từ chối** | Là literal của ngôn ngữ lập trình, không phải thứ người dùng gõ vào ô "Khóa". `int("1_000")` trả về 1000 trong Python — cạm bẫy thật, regex chặn nó |
| `"٣"` (chữ số Ả Rập-Ấn) | **Từ chối** | **Cạm bẫy:** `\d` trong regex Python và cả `int()` đều chấp nhận chữ số Unicode. Vì vậy regex dùng `[0-9]` tường minh chứ **không** dùng `\d` |
| `"abc"`, `"3abc"`, `"true"`, `"--3"` | Từ chối | Không phải số nguyên |

**Vì sao chặn độ dài ở bước 3.** Từ Python 3.11, `int()` ném `ValueError` với chuỗi số quá 4300 chữ số
(biện pháp chống DoS của chính CPython). Nếu không tự chặn trước, một client gửi 10.000 chữ số sẽ làm
`int()` ném lỗi ở chỗ ta không lường, rơi vào handler `Exception` và trả **500 `"Đã xảy ra lỗi hệ
thống."`** thay vì **422 `"Khóa phải là số nguyên."`** — sai mã, sai thông báo, và có vẻ như lỗi của
server. Trần 32 ký tự là rộng rãi hơn mọi nhu cầu thật (khóa có ý nghĩa nằm trong 0–25) mà vẫn đóng chặt
khe hở này.

**Nguyên tắc dẫn đường.** Khoan dung với thứ chắc chắn là nhiễu (khoảng trắng, `+`, số 0 đứng đầu), tuyệt
đối nghiêm khắc với thứ mơ hồ hoặc lệch chuẩn giữa hai endpoint (số thực, ký pháp lập trình, chữ số
Unicode). Quy tắc sống trong **một** hàm `parse_key(raw: str) -> int` dùng chung, và bảng trên trở thành
bảng tham số cho test.

**Phương án đã cân nhắc rồi loại.**
- *Gọi thẳng `int(raw)` và bắt `ValueError`.* Ngắn nhất, nhưng thầm lặng chấp nhận `"1_000"`, `"٣"` và
  khoảng trắng đủ loại (kể cả khoảng trắng Unicode) — hành vi do CPython định nghĩa chứ không do ta,
  và không ai đọc code đoán ra được.
- *Để Pydantic ép `key: int` từ form.* Chấp nhận `"3.0"` trong một số cấu hình và trả về khuôn dạng lỗi
  của riêng nó — cùng vấn đề đã nêu ở Quyết định 7.
- *Từ chối `" 3 "` và `"+3"` cho "chặt chẽ".* Chặt chẽ nhưng không bảo vệ được gì; chỉ làm người dùng
  gặp lỗi khó hiểu sau khi dán số từ nơi khác.

### 9. Thứ tự ưu tiên khi nhiều lỗi xảy ra cùng lúc (QUYẾT ĐỊNH THIẾT KẾ — ĐÃ CHỐT)

**Vấn đề.** docx §5 liệt kê từng trường hợp lỗi riêng lẻ nhưng **không** quy định điều gì xảy ra khi
nhiều điều kiện cùng sai. Một file `.pdf` nặng 10 MiB gửi kèm mà thiếu `key` thỏa mãn *ba* dòng của
bảng cùng lúc (415, 413, 422). Nếu không chốt thứ tự, thông báo trả về sẽ phụ thuộc vào thứ tự viết
code — nghĩa là test sẽ giòn và hành vi sẽ đổi sau mỗi lần refactor.

**Quyết định — tầng 0 trước, rồi thứ tự validation cố định và dừng ở lỗi ĐẦU TIÊN gặp phải.** Đây là
thứ tự đã chốt cho toàn dự án (và đã được ghi thành requirement "Thứ tự kiểm tra xác định khi nhiều
lỗi xảy ra cùng lúc" trong `specs/error-handling/`); mọi endpoint phải tuân theo:

**Ngoại lệ hạ tầng — bước âm 1.** Nếu `Content-Length > 64 MiB`, tầng 0 từ chối trước khi đọc body.
Thông báo được chọn theo **tuyến**: API file dùng `"File vượt quá dung lượng tối đa 5 MB."`, tuyến khác
dùng `"Yêu cầu vượt quá dung lượng cho phép."`. Đây là trường hợp duy nhất được phép thắng lỗi body
hoặc field; nó bảo vệ tài nguyên trước khi có thể áp dụng hợp đồng validation. Nếu header bằng hoặc
nhỏ hơn ngưỡng, vắng mặt hay không parse được, request đi tiếp và tầng 0 không ảnh hưởng thứ tự dưới.

**Tiền đề — bước 0: với request đã qua tầng 0, thân yêu cầu phải đọc được trước đã.** Sáu bước dưới đây
chỉ có nghĩa khi body đã được phân tích thành công. Nếu body không đọc được — JSON hỏng cú pháp, body
không phải JSON object, `Content-Type` sai, multipart méo — thì **không** trường nào tồn tại để kiểm
tra, nên hệ thống trả ngay 422 `"Dữ liệu gửi lên không hợp lệ."` và **không** đi vào thứ tự này. Đây là
điều kiện tiên quyết, không phải một mục trong danh sách ưu tiên.

| # | Bước | Ví dụ thông báo | Chi phí |
|---|---|---|---|
| 1 | **Sự hiện diện của trường bắt buộc:** `text`/`file` → `key` → `action` | `"Văn bản không được để trống."` / `"Thiếu file."` / `"Thiếu khóa."` | Chỉ đọc metadata, không I/O |
| 2 | **Định dạng trường vô hướng:** `key` → `action` → `response_mode` | `"Khóa phải là số nguyên."` / `"Action phải là encrypt hoặc decrypt."` / `"Response mode phải là content hoặc file."` | Vài phép so sánh chuỗi |
| 3 | **Đuôi file `.txt`** (415) | `"Chỉ chấp nhận file .txt."` | Chỉ đọc tên file |
| 4 | **Dung lượng 5 MiB** (413) | `"File vượt quá dung lượng tối đa 5 MB."` | Đọc bytes theo chunk |
| 5 | **File 0 byte** (422) | `"File không được để trống."` | Đã biết sau bước 4 |
| 6 | **Decode UTF-8** (415) | `"File phải sử dụng UTF-8."` | Đắt nhất: duyệt toàn bộ bytes |

**Trả lời ví dụ trong đề bài.** File `.pdf` 10 MiB thiếu luôn `key` → **422 `"Thiếu khóa."`** Bước 1
(sự hiện diện của trường) đứng trước bước 3 (đuôi file) và bước 4 (dung lượng), nên chặn ngay tại đó.
Một request 10 MiB vẫn nằm dưới trần lạm dụng 64 MiB ở Quyết định 4, nên nó đi tới handler và nhận đúng
thông báo này thay vì bị Tầng 0 chặn sớm. Ngược lại, request 65 MiB thiếu `key` bị tầng 0 chặn trước;
API file nhận chuỗi file, còn API text nhận chuỗi generic — hai quyết định khớp nhau đúng như thiết kế.

**Lý do — rẻ trước, đắt sau.** Bước 1–3 chỉ nhìn metadata (tên trường, tên file) và không chạm một byte
nội dung nào; bước 6 phải quét toàn bộ 5 MiB. Kiểm tra theo thứ tự chi phí tăng dần nghĩa là request
sai rõ ràng nhất bị loại sớm nhất, và cũng cho ra thông báo **hữu ích nhất cho người dùng**: khi thiếu
key, nói "Thiếu khóa." đưa họ tới hành động đúng tiếp theo; nói "File phải sử dụng UTF-8." thì không.

**Hệ quả kiến trúc — bước 2 đứng TRƯỚC bước 4.** `key` phải được validate xong **trước khi** đọc hết
file. Vì thế luồng xử lý trong `routes_file.py` bắt buộc là: nhận tham chiếu `UploadFile` (chưa đọc nội
dung) → chạy bước 1–3 trên metadata → **chỉ khi đó** mới gọi vòng đọc theo chunk ở Quyết định 4 → chạy
bước 5–6. Hệ quả cụ thể: **không** được viết handler kiểu gọi `await file.read()` ngay dòng đầu rồi mới
validate, dù đó là cách viết tự nhiên nhất. Một comment ở đầu handler phải ghi rõ ràng buộc này, và có
test khẳng định một request thiếu `key` kèm file 6 MiB vẫn trả `"Thiếu khóa."` (chứ không phải 413).

**Cặp quy tắc phân biệt hoa thường — tương phản có chủ ý.** `action` và `response_mode` **phân biệt hoa
thường**: `"ENCRYPT"` bị từ chối với `"Action phải là encrypt hoặc decrypt."` Ngược lại, đuôi file
`.txt` **không** phân biệt hoa thường: `BaoCao.TXT` được chấp nhận. Lý do cho sự tương phản: `action` và
`response_mode` là **giá trị của giao thức**, do code của client sinh ra, nên chuẩn hóa chặt giữ hợp
đồng API sắc nét và bắt lỗi tích hợp sớm; còn đuôi file là **dữ liệu do con người và hệ điều hành tạo
ra** — Windows sinh `.TXT` một cách bình thường và người dùng không kiểm soát được điều đó, nên nghiêm
khắc ở đây chỉ là trừng phạt người dùng vì thứ không phải lỗi của họ.

**Tên file kết quả.** Bỏ đuôi `.txt` **CUỐI CÙNG** (không phải phần sau dấu chấm đầu tiên), rồi nối
`.encrypted.txt` / `.decrypted.txt` bằng dấu **chấm**: `bao.cao.v2.txt` → `bao.cao.v2.encrypted.txt`.
Đuôi kết quả **luôn viết thường** kể cả khi gốc viết hoa: `BaoCao.TXT` → `BaoCao.encrypted.txt`. Quy
tắc này nằm trong một hàm thuần `build_result_filename(original, action)` ở `app/services/` để test
được mà không cần HTTP.

**Phương án đã cân nhắc rồi loại.**
- *Gom tất cả lỗi rồi trả về một mảng.* Thông tin phong phú hơn, nhưng phá vỡ hợp đồng
  `{"success": false, "message": "..."}` (một chuỗi, số ít) mà docx §5 quy định, và buộc UI phải quyết
  định hiển thị cái nào.
- *Kiểm tra dung lượng trước sự hiện diện của trường (ưu tiên "phòng thủ tài nguyên").* Nghe hợp lý,
  nhưng khiến hành vi phụ thuộc vào kích thước file: cùng một lỗi thiếu `key` lại cho hai thông báo
  khác nhau tùy file to hay nhỏ. Vai trò phòng thủ tài nguyên đã được Tầng 0 ở Quyết định 4 đảm nhiệm.
- *Để thứ tự tự nhiên theo code.* Chính là thứ đang tránh: không xác định, không test được.

### 10. Port mockup HTML: tách thành template + `static/app.js` + `static/styles.css`

**Quyết định.** Tách file mockup 540 dòng thành ba file theo đúng ranh giới ngôn ngữ:

- `app/templates/index.html` — chỉ cấu trúc và nội dung, phục vụ qua Jinja2.
- `app/static/styles.css` — toàn bộ khối `<style>` (dòng 7–151 của mockup).
- `app/static/app.js` — toàn bộ khối `<script>` (dòng 294–538), trừ phần backend giả lập bị xóa.

**Lý do.**
- Ba ngôn ngữ trong một file làm diff vô nghĩa: sửa một chuỗi thông báo hiện ra như thay đổi ở "file
  HTML", không nói được là chạm vào logic hay vào trình bày.
- CSS/JS tách rời được trình duyệt cache riêng, còn trang HTML thì không — có ý nghĩa thật với một
  ứng dụng mà người dùng tải lại nhiều lần trong lúc thử nghiệm.
- **6 điểm sửa bắt buộc chạm cả ba tầng**, nên nếu để chung một file thì mỗi lần sửa lại phải cuộn qua
  500 dòng không liên quan, và review khó khẳng định đã sửa đủ.
- Chia tách cho phép **test riêng từng tài sản** (`GET /static/app.js` trả 200) và cho phép viết test
  guard bằng cách đọc thẳng `app.js` (xem Quyết định 11).

**Vì sao là Jinja2 template chứ không phải file HTML tĩnh thuần.** Chỉ để giải quyết đúng một vấn đề
thật: **ngưỡng 5 MiB không được phép tồn tại ở hai nơi.** Server render trang và tiêm hằng số từ Python
vào DOM (ví dụ `<body data-max-bytes="{{ max_file_bytes }}">`), `app.js` đọc lại từ đó. Nhờ vậy
`MAX_FILE_BYTES = 5 * 1024 * 1024` ở `app/config.py` là nguồn sự thật duy nhất, và lỗi kiểu "JS vẫn còn
1 MB trong khi server đã 5 MiB" — chính là bug đang nằm trong mockup — trở thành **không thể xảy ra về
mặt cấu trúc**. Đây là lý do cụ thể, không phải "để sau này linh hoạt".

**Áp 6 điểm sửa bắt buộc.**

| # | Điểm sửa | Chỗ trong mockup | Cách áp |
|---|---|---|---|
| 1 | 1 MB → **5 MiB** | `MAX_FILE_BYTES = 1024 * 1024` (dòng 298); kiểm tra ở dòng 336 và 414; nhãn "tối đa 1 MB" (dòng 218) | Xóa hằng số cứng, đọc từ `data-max-bytes` do server tiêm; nhãn đổi thành "tối đa 5 MB" đúng chữ của docx, kèm chú thích phụ `5 MiB = 5.242.880 byte` |
| 2 | `_encrypted` → **`.encrypted`** | Dòng 518: `download:` `${base}_${...}.txt` | Ở luồng file, **để server quyết định tên** qua `Content-Disposition` (mode `file`); chỉ luồng nhập tay mới sinh tên ở client, và dùng dấu chấm |
| 3 | Thông báo lỗi đúng docx §5 | `mockApi` (dòng 324–351) tự sinh chuỗi rút gọn: `"File rỗng."`, `"Chỉ hỗ trợ file .txt."`, `"File vượt dung lượng cho phép (1 MB)."` | Xóa sạch `mockApi`; UI **luôn hiển thị nguyên văn `message` do server trả về**, không bao giờ tự soạn chuỗi lỗi. Quy tắc này cũng chặn trước mọi sai lệch chưa phát hiện |
| 4 | Bổ sung `response_mode` | `realApi.file` (dòng 349–351) không gửi trường này | Preview → `response_mode=content`; nhấn "Tải kết quả" → gửi lại với `response_mode=file` và để trình duyệt nhận attachment |
| 5 | Same-origin, không CORS | `USE_MOCK = true` (296), `API_BASE = "http://localhost:8080"` (297) | Xóa cả hai hằng số và toàn bộ nhánh mock; `fetch("/api/caesar/…")` bằng đường dẫn tương đối |
| 6 | Giữ UTF-8 BOM | Dòng 517 dựng `new Blob([state.result])` ở client | File tải xuống **phải đến từ server** ở mode `file`, vì bản preview trong JS đã mất BOM (Quyết định 5) và client không có cách nào biết file gốc có BOM hay không |

**Giữ lại có chủ ý:** hàm `CaesarService.shift` **không** bị xóa hoàn toàn — bảng dịch chuyển bảng chữ
cái và phần tô màu chỉ cần ánh xạ 26 chữ cái để **hiển thị**, không phải để tính kết quả. Giữ lại một
hàm nhỏ `shiftAlphabet(k)` phục vụ riêng phần hiển thị bảng, đồng thời xóa hẳn đường mock để kết quả
thật luôn luôn đến từ server. Ranh giới này cần một comment trong `app.js`, vì nó dễ bị hiểu nhầm thành
"vẫn còn code mock".

**Kỷ luật state của output.** `state.result` phải giữ đúng chuỗi server trả về; lớp tô màu dựng DOM mà
không thêm newline, và copy/download cũng dùng nguyên chuỗi đó. Mọi thất bại của request xử lý hoặc
request tải file phải xóa result/analysis thành công cũ, vô hiệu action phụ thuộc result và đặt status
kết quả sang lỗi. `clearResult()` luôn đặt `state.view = "result"`, render placeholder của tab
"Văn bản", ẩn/xóa "Phân tích" và đồng bộ `aria-selected`. Khi `state.loading` là true, guard dùng chung
phải chặn cả phím tắt lẫn click/Enter/Space/file-drop của custom drop zone; thuộc tính `disabled` trên
`div` không được xem là đủ.

**Phục vụ qua FastAPI.** `app.mount("/static", StaticFiles(directory="app/static"), name="static")` cho
tài sản tĩnh; `GET /` trả `TemplateResponse("index.html", {...})` qua `Jinja2Templates`. Cùng một
tiến trình, cùng origin, nên `/docs` của FastAPI vẫn giữ mặc định và không cần CORS (docx §8).

**Phương án đã cân nhắc rồi loại.**
- *Giữ nguyên một file HTML rồi vá tại chỗ.* Nhanh nhất hôm nay, đắt nhất ở mọi lần sửa sau, và không
  giải quyết được vấn đề nhân bản hằng số 5 MiB.
- *Phục vụ `index.html` tĩnh, không Jinja2.* Bớt một dependency, nhưng lại phải viết `5242880` vào JS
  — đúng loại lỗi mà điểm sửa #1 tồn tại để diệt.
- *Thêm bundler/framework.* Ngoài phạm vi rõ ràng (docx §8: không React).

### 11. Chiến lược test đạt coverage ≥ 90%

**Phân tầng.**

*Unit (`tests/unit/`) — nhanh, không chạm HTTP.*
- `test_caesar.py`: bảng tham số cho khóa 0/1/3/25/26/-3/-27/1000; giữ nguyên chữ hoa/thường, chữ số,
  tiếng Việt, emoji, ký tự đặc biệt; **round-trip** `decrypt(encrypt(t, k), k) == t` trên một tập văn
  bản đa dạng; tiêu chí nghiệm thu `"Hello World"` + khóa 3 → `"Khoor Zruog"` (docx §7); và một test
  **đối chiếu** kết quả của `str.translate` với một implementation tham chiếu viết bằng vòng lặp
  `ord`/`chr` ngay trong file test — hai cách làm độc lập cùng ra một kết quả là bằng chứng mạnh rằng
  bảng dịch được dựng đúng.
- `test_key_parsing.py`: toàn bộ bảng ở Quyết định 8 dưới dạng `pytest.mark.parametrize`, cộng các cạm
  bẫy `True`/`3.0`/`"3"`/`"١"`/`"1_000"`/chuỗi 5000 chữ số.
- `test_file_rules.py`: các hàm thuần của File Processing — `build_result_filename` (gồm
  `bao.cao.v2.txt` và `BaoCao.TXT`), phát hiện BOM, kiểm tra đuôi không phân biệt hoa thường.
- `test_layering.py`: phân tích AST các file trong `app/core/` và khẳng định không có import nào tới
  `fastapi`, `starlette`, `pydantic` — biến quy tắc phụ thuộc ở mục Project Structure §3 thành một điều
  kiện tự động thay vì một thỏa thuận miệng.

*Integration (`tests/integration/`) — qua `TestClient` (httpx), chạm HTTP thật nhưng không cần server rời.*
- `test_text_endpoints.py`: đường thành công của `/encrypt` và `/decrypt`, khóa âm/lớn, Unicode nguyên vẹn.
- `test_file_endpoint.py`: cả hai `response_mode`; `Content-Disposition` và tên file kết quả; byte BOM
  `EF BB BF` ở đầu response; **bảo toàn CRLF** (gửi file chứa `\r\n`, khẳng định bytes trả về vẫn có
  `\r\n`) — test này chính là lưới an toàn cho quyết định "đọc ở chế độ bytes" ở Quyết định 4.
- `test_error_contract.py`: **một test cho mỗi dòng của bảng docx §5**, khẳng định đồng thời HTTP status
  và chuỗi `message` **nguyên văn**; cộng thêm test cho thứ tự ưu tiên ở Quyết định 9 (đặc biệt: file
  6 MiB + thiếu key → `"Thiếu khóa."`), test body JSON hỏng → `"Dữ liệu gửi lên không hợp lệ."`, và
  test khẳng định **không** response lỗi nào chứa khóa `"detail"` — lưới an toàn chống việc khuôn dạng
  mặc định của FastAPI lọt ra ngoài.
- Test request-size guard: phủ ranh `64 MiB`/`64 MiB + 1`, header vắng/sai định dạng, route file so với
  route không phải file, envelope không có code, thông báo generic không lộ `64 MiB`, và xác nhận tầng
  0 thắng body/field validation chỉ khi vượt trần. Chạy cùng tập kỳ vọng với app local và container.
- `test_app_runtime.py`: `GET /` trả 200 HTML; `GET /docs` trả 200; `GET /static/app.js` trả 200; hành vi
  tầng 0 giống nhau giữa local và container.

*UI — test guard tự động cộng nghiệm thu native Browser ngoài image.* Không đưa Playwright/Selenium vào
dependency hay image Tuần 1. Dùng test guard rẻ cho hồi quy tĩnh, rồi chạy native Browser trên app thật
trước khi chấp nhận remediation:
1. Test HTTP khẳng định trang `/` render và có chứa giá trị `5242880` do server tiêm.
2. **Test guard đọc thẳng nội dung `app/static/app.js`** và khẳng định nó **không** chứa `USE_MOCK`,
   `http://localhost:8080`, `_encrypted`, `1024 * 1024`, và **có** chứa `response_mode`. Đây là 5 trong
   6 điểm sửa bắt buộc, được khóa lại bằng năm dòng assert. Thô sơ, nhưng bắt đúng loại hồi quy có xác
   suất cao nhất (ai đó copy lại đoạn mockup cũ) với chi phí gần bằng 0.
3. Native Browser phải chứng minh kết quả hiển thị/copy/download đúng từng ký tự, không thêm newline;
   lỗi tải file xóa success cũ và chuyển trạng thái lỗi; Analysis → Xóa đặt lại view, nội dung hiển thị
   và ARIA tab selection; trong request cố ý trì hoãn, phím tắt, click/Enter/Space vùng thả và file drop
   thực tế đều bị khóa. Sau đó chạy lại hai luồng docx §3.1/§3.2 và kiểm console sạch.

**Tạo file 5 MiB trong test mà không commit file lớn.** Sinh trong bộ nhớ ngay tại thời điểm chạy, không
bao giờ để lên đĩa hay vào git:

```python
LIMIT = 5 * 1024 * 1024
exact   = io.BytesIO(b"A" * LIMIT)        # 5242880 -> phải được nhận
too_big = io.BytesIO(b"A" * (LIMIT + 1))  # 5242881 -> phải bị từ chối
```

`b"A" * 5242880` mất chưa tới một mili giây và tốn ~5 MB RAM trong chốc lát. Hai fixture ở
`tests/conftest.py` gói hai giá trị này để cả hai test biên dùng chung **đúng một hằng số** — nếu ngưỡng
đổi, chỉ có một nơi phải sửa. `tmp_path` của pytest nằm ngoài repo nên test không cần và không được dựa
vào quy tắc ignore `*.txt`. Ứng dụng xử lý upload/download trong bộ nhớ hoặc response HTTP, không tạo
file `.txt` trong repo lúc chạy. `.gitignore` chỉ chặn hai dạng output người dùng có thể vô tình tải
vào root repo: `/*.encrypted.txt` và `/*.decrypted.txt`; không thêm runtime directory.

**Mục tiêu và phạm vi đo coverage.** `--cov=app --cov-fail-under=90 --cov-report=term-missing`. Coverage
đo **chỉ mã Python trong `app/`**. `app/static/*.js` và `app/templates/*.html` **không** được tính vào
con số coverage — coverage.py chỉ instrument `.py`, và Tuần 1 không có test runner cho JavaScript. Nói
rõ điều này để không ai hiểu nhầm rằng "90%" bao gồm cả UI.

**Chống test hình thức:** mỗi scenario trong `specs/` phải có một test tương ứng và test đặt tên theo
hành vi được khẳng định. Coverage là **sàn để phát hiện nhánh bị bỏ quên**, không phải mục tiêu tự thân;
`term-missing` được dùng để nhìn ra dòng nào chưa chạy, và các nhánh lỗi được ưu tiên trước các nhánh
thành công vì chính chúng là nơi docx §5 đặt yêu cầu nghiệm thu.

### 12. Dockerfile multi-stage, dùng `uv` khi build, chạy bằng user không phải root

**Quyết định — hai stage.**

*Stage `builder` (`python:3.12-slim`).*
- Lấy `uv` bằng cách copy binary từ image chính thức đã **ghim phiên bản cụ thể**
  (`COPY --from=ghcr.io/astral-sh/uv:<phiên-bản> /uv /usr/local/bin/uv`) — nhanh và tất định hơn hẳn
  `curl | sh` trong lúc build, và không phụ thuộc mạng ngoài registry. Không dùng tag `latest`: build
  phải lặp lại được.
- Copy **chỉ** `pyproject.toml` + `uv.lock` trước, chạy `uv sync --frozen --no-dev` để dựng `/app/.venv`,
  rồi mới copy mã nguồn. Nhờ vậy lớp cài dependency chỉ bị dựng lại khi lock file đổi, không phải mỗi
  lần sửa code.
- `--frozen` bắt buộc khớp `uv.lock` (build thất bại thay vì âm thầm resolve lại — chính là điều ta muốn
  ở một image sản phẩm). `--no-dev` loại pytest/ruff khỏi image chạy.
- `UV_COMPILE_BYTECODE=1` (khởi động nhanh hơn) và `UV_LINK_MODE=copy` (tránh cảnh báo hardlink khi cache
  và đích khác filesystem).

*Stage `runtime` (`python:3.12-slim`).*
- Tạo user không đặc quyền: `useradd --create-home --uid 10001 appuser`.
- Copy `/app/.venv` và thư mục `app/` từ builder bằng `COPY --from=builder --chown=appuser:appuser`.
- `ENV PATH="/app/.venv/bin:$PATH"` — không cần `uv` ở runtime, nên **`uv` không có mặt trong image
  cuối**: image nhỏ hơn và bề mặt tấn công hẹp hơn.
- `USER appuser` đặt **trước** `CMD`, nên tiến trình không bao giờ chạy bằng root. Cổng 8000 không phải
  cổng đặc quyền (<1024) nên không cần quyền gì thêm.
- `EXPOSE 8000` và `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`.
  `--host 0.0.0.0` là bắt buộc trong container (mặc định `127.0.0.1` chỉ nghe trong namespace mạng của
  container và sẽ làm `-p 8000:8000` trông như bị hỏng). Cổng 8000 giống hệt khi chạy local, đúng docx §7.
- `.dockerignore` loại `.git/`, `.venv/`, `tests/`, `openspec/`, `*.docx`, `__pycache__/`,
  `Caesar_Cipher_Tool_Demo.html` — image chỉ chứa thứ cần để chạy.

**Kiểm chứng:** `docker run --rm <image> id -u` phải in một số khác `0`; `curl localhost:8000/` và
`curl localhost:8000/docs` phải trả 200.

**Phương án đã cân nhắc rồi loại.**
- *Single-stage với `uv` cài trong image cuối.* Đơn giản hơn, nhưng đưa trình quản lý gói và cache build
  vào image sản phẩm.
- *`pip install -r requirements.txt`.* Mâu thuẫn với stack đã chốt (`uv` + `pyproject.toml`) và làm mất
  tính tất định mà `uv.lock` mang lại.
- *Image `python:3.12-alpine`.* Nhỏ hơn, nhưng dùng musl nên nhiều wheel phải biên dịch lại — build chậm
  và dễ vỡ, đổi lại vài chục MB không đáng cho một app Tuần 1.

## Project Structure

### 1. Cây thư mục đầy đủ khi hoàn thành Tuần 1

Chú thích: `[có]` = đã tồn tại trong repo · `[mới]` = tạo mới trong change này · `[sinh]` = do công cụ
sinh ra, có commit nhưng không viết tay.

```
caesar_cipher-be/
├── BE Scope – Week 1 Caesar Cipher MVP.docx            [có]  bản gốc v1.0 — SOURCE OF TRUTH
├── BE Scope – ….before-ui-update.docx                  [có]  ĐÃ BỊ THAY THẾ — không dùng làm căn cứ
├── Caesar_Cipher_Tool_Demo.html                        [có]  mockup, giữ nguyên làm tài sản tham chiếu
├── paseo.json                                          [có]
├── README.md                                           [mới] cách chạy local/Docker, chạy test, lint
├── pyproject.toml                                      [mới] deps + cấu hình Ruff + pytest + coverage
├── uv.lock                                             [sinh] uv sinh; PHẢI commit để build tất định
├── .gitignore                                          [mới] cache/tooling + /*.encrypted.txt, /*.decrypted.txt
├── .dockerignore                                       [mới] .git/, .venv/, tests/, openspec/, *.docx, mockup
├── Dockerfile                                          [mới] multi-stage; xem Quyết định 12
│
├── docs/
│   └── reference/
│       └── be-scope-v1.0.md                            [có]  bản trích docx để đọc/grep
│
├── openspec/
│   ├── config.yaml                                     [có]
│   └── changes/caesar-cipher-week1-mvp/
│       ├── README.md                                   [có]
│       ├── .openspec.yaml                              [có]
│       ├── proposal.md                                 [có]
│       ├── design.md                                   [mới] tài liệu này
│       ├── tasks.md                                    [mới] do người phụ trách task viết
│       └── specs/{caesar-core,text-cipher-api,file-cipher-api,
│                  error-handling,web-ui,app-runtime}/spec.md   [có]
│
├── app/
│   ├── __init__.py                                     [mới]
│   ├── main.py                                         [mới] tạo app, mount /static, route GET /, đăng ký handler
│   ├── config.py                                       [mới] MAX_FILE_BYTES=5242880, MAX_REQUEST_BYTES,
│   │                                                         ALLOWED_EXTENSION=".txt", CHUNK_SIZE, PORT=8000
│   ├── core/
│   │   ├── __init__.py                                 [mới]
│   │   └── caesar.py                                   [mới] transform_text + 26 bảng dịch dựng sẵn
│   ├── services/
│   │   ├── __init__.py                                 [mới]
│   │   └── file_processing.py                          [mới] đọc theo chunk + giới hạn, BOM, decode UTF-8,
│   │                                                         build_result_filename, dựng bytes kết quả
│   ├── api/
│   │   ├── __init__.py                                 [mới]
│   │   ├── schemas.py                                  [mới] model request/response + parse_key + validate theo thứ tự
│   │   ├── routes_text.py                              [mới] POST /api/caesar/encrypt, /api/caesar/decrypt
│   │   └── routes_file.py                              [mới] POST /api/caesar/file
│   ├── errors/
│   │   ├── __init__.py                                 [mới]
│   │   ├── messages.py                                 [mới] 13 chuỗi docx §5 + 1 chuỗi ngoại lệ hạ tầng OpenSpec
│   │   ├── exceptions.py                               [mới] CaesarError và các lớp con
│   │   └── handlers.py                                 [mới] 4 exception handler (tầng duy nhất biết HTTP)
│   ├── templates/
│   │   └── index.html                                  [mới] port từ mockup; nhận max_file_bytes từ server
│   └── static/
│       ├── styles.css                                  [mới] tách từ <style> của mockup
│       ├── app.js                                      [mới] tách từ <script>; đã xóa mock + API_BASE
│       └── favicon.ico                                 [mới] tùy chọn, tránh 404 nhiễu log
│
└── tests/
    ├── __init__.py                                     [mới]
    ├── conftest.py                                     [mới] fixture client, fixture bytes 5 MiB / 5 MiB+1, fixture BOM/CRLF
    ├── unit/
    │   ├── __init__.py                                 [mới]
    │   ├── test_caesar.py                              [mới] ↔ app/core/caesar.py
    │   ├── test_key_parsing.py                         [mới] ↔ app/api/schemas.py (hàm parse_key)
    │   ├── test_file_rules.py                          [mới] ↔ app/services/file_processing.py (hàm thuần)
    │   └── test_layering.py                            [mới] kiểm tra AST: core không import framework
    └── integration/
        ├── __init__.py                                 [mới]
        ├── test_text_endpoints.py                      [mới] ↔ app/api/routes_text.py
        ├── test_file_endpoint.py                       [mới] ↔ app/api/routes_file.py
        ├── test_error_contract.py                      [mới] ↔ app/errors/ — một test cho mỗi dòng docx §5
        ├── test_app_runtime.py                         [mới] ↔ app/main.py — /, /docs, /static
        └── test_ui_assets.py                           [mới] ↔ app/static/app.js — guard 6 điểm sửa
```

**Không có file cấu hình rời cho lint/test.** Ruff, pytest và coverage đều cấu hình trong
`pyproject.toml`; không tạo `ruff.toml`, `pytest.ini`, `setup.cfg` hay `.coveragerc` — một file cấu hình
duy nhất thì không có chuyện hai nơi nói hai điều khác nhau.

### 2. Bảng ánh xạ thư mục → trách nhiệm → module docx §6 → capability spec

| Đường dẫn | Trách nhiệm (một câu) | Module docx §6 | Capability spec |
|---|---|---|---|
| `app/core/caesar.py` | Export **`transform_text(text, key, operation)`** với `operation` ∈ {`encrypt`, `decrypt`} (docx §2.1, §6): dịch chữ cái ASCII và chuẩn hóa khóa về 0–25, không biết gì ngoài `str` vào và `str` ra. | Caesar Core | `caesar-core` |
| `app/services/file_processing.py` | Đọc bytes có giới hạn, xử lý BOM/UTF-8, đặt tên file kết quả và dựng bytes tải xuống. | File Processing | `file-cipher-api` |
| `app/api/routes_text.py` | Chuyển request JSON thành lời gọi core và trả success response. | HTTP Adapter | `text-cipher-api` |
| `app/api/routes_file.py` | Chuyển request multipart thành lời gọi service+core, trả JSON hoặc attachment theo `response_mode`. | HTTP Adapter | `file-cipher-api` |
| `app/api/schemas.py` | Định nghĩa hợp đồng request/response và áp thứ tự validate ở Quyết định 9. | HTTP Adapter | `text-cipher-api`, `file-cipher-api` |
| `app/errors/messages.py` | Giữ nguyên văn 13 chuỗi nghiệp vụ docx §5 và chuỗi generic của ngoại lệ hạ tầng OpenSpec ở một nơi, phân biệt rõ hai tập. | Exception Handling | `error-handling` |
| `app/errors/exceptions.py` | Định nghĩa `CaesarError` mang cặp `(status_code, message)` cho tầng dưới ném lên. | Exception Handling | `error-handling` |
| `app/errors/handlers.py` | Chuyển mọi exception thành error response chuẩn và ghi log nội bộ. | Exception Handling | `error-handling` |
| `app/templates/index.html` | Khung giao diện, nhận hằng số cấu hình do server tiêm. | Web UI | `web-ui` |
| `app/static/app.js` | Thu thập input, gọi API bằng đường dẫn tương đối, hiển thị kết quả/thông báo/preview/download. | Web UI | `web-ui` |
| `app/static/styles.css` | Trình bày, responsive. | Web UI | `web-ui` |
| `app/main.py` | Lắp ráp: tạo app, mount `/static`, route `/`, đăng ký router và exception handler. | HTTP Adapter (lắp ráp) | `app-runtime` |
| `app/config.py` | Hằng số cấu hình dùng chung (ngưỡng dung lượng, đuôi cho phép, cổng). | — (dùng chung) | `app-runtime`, `file-cipher-api` |
| `Dockerfile`, `.dockerignore` | Đóng gói chạy được bằng Docker, user không phải root, cổng 8000. | — (hạ tầng) | `app-runtime` |
| `tests/unit/` | Kiểm chứng các hàm thuần, không cần HTTP. | Test | tất cả |
| `tests/integration/` | Kiểm chứng hợp đồng quan sát được qua HTTP. | Test | tất cả |

### 3. Quy tắc phụ thuộc giữa các tầng

```
main.py  ──►  api/  ──►  services/  ──►  core/
   │           │            │             │
   └───────────┴────────────┴────────► errors/{messages,exceptions}
               │
               └──► errors/handlers  (tầng DUY NHẤT ngoài api/main được biết HTTP)
```

**Được phép import:**
- `app/core/` → **chỉ thư viện chuẩn Python** (`string`, `typing`). Không gì khác.
- `app/services/` → `app.core`, `app.config`, `app.errors.exceptions`, `app.errors.messages`, stdlib.
- `app/api/` → mọi thứ bên dưới (`core`, `services`, `config`, `errors`) + FastAPI/Pydantic.
- `app/errors/handlers.py` → FastAPI/Starlette + `exceptions`/`messages`.
- `app/main.py` → tất cả. Không module nào khác được import `main` (tránh vòng lặp import).

**KHÔNG được import:**
- `app/core/` **không được** import `fastapi`, `starlette`, `pydantic`, `app.api`, `app.services`,
  `app.config`, kể cả `app.errors`.
- `app/services/` **không được** import `fastapi`/`starlette` hay `app.api`. Để đọc `UploadFile` mà
  không import FastAPI, service nhận vào một đối tượng **duck-typed** có `async def read(size) -> bytes`
  (`UploadFile` thỏa mãn cấu trúc này). Nhờ vậy test service chỉ cần một `BytesIO` bọc mỏng.
- `app/errors/exceptions.py` và `messages.py` **không được** import framework — chúng là dữ liệu và kiểu
  thuần, để mọi tầng dùng được.

**Vì sao đây là điều then chốt.** docx §2.1 yêu cầu "cùng một module Caesar Core phải được tái sử dụng
cho cả input bàn phím và file". Yêu cầu đó chỉ đứng vững khi core **không thể** biết request đến từ đâu.
Ngay khi core import `fastapi` hay nhận vào một `Request`, nó không còn dùng lại được cho luồng kia mà
không kéo theo cả một stack HTTP — và test unit của nó lập tức cần dựng client. Quy tắc một chiều này
cũng là thứ khiến Quyết định 2 (hàm thuần, không interface trừu tượng) an toàn: core có ít phụ thuộc
tới mức thay đổi nó là chuyện cục bộ.

**Cưỡng chế bằng máy, không bằng lời hứa:** `tests/unit/test_layering.py` phân tích AST mọi file trong
`app/core/` và fail nếu thấy import bị cấm.

### 4. Quy ước đặt tên và tổ chức test

- `tests/unit/` **soi gương** source tree: `test_<tên module>.py` cho module Python tương ứng
  (`test_caesar.py` ↔ `app/core/caesar.py`). Mở một file source là biết ngay file test của nó ở đâu.
- `tests/integration/` **soi gương theo endpoint/khía cạnh** chứ không theo module, vì một request chạm
  nhiều module: `test_<nhóm endpoint>.py` (`test_file_endpoint.py` ↔ `POST /api/caesar/file`).
- Hàm test đặt tên mô tả hành vi, không mô tả cách hiện thực:
  `test_file_dung_5_mib_duoc_chap_nhan`, `test_thieu_key_thang_the_loi_dung_luong`. Đọc tên test phải
  hiểu được quy tắc nghiệp vụ mà không cần đọc thân hàm.
- Test soi chiếu bảng docx §5 đặt tập trung ở `test_error_contract.py` để "13 dòng của docx ↔ 13 test"
  kiểm được bằng mắt trong một file.
- Fixture dùng chung nằm ở `tests/conftest.py`; **không** có fixture nào ghi file vào repo — dữ liệu lớn
  sinh trong bộ nhớ, dữ liệu cần đường dẫn thật dùng `tmp_path` của pytest.
- Không có thư mục `tests/fixtures/` chứa file `.txt` mẫu: mọi payload (BOM, CRLF, latin-1, 5 MiB) đều
  dựng bằng literal bytes ngay trong test, nên nhìn test là thấy chính xác các byte đang được kiểm tra.

### 5. Nội dung chính của `pyproject.toml`

**`[project]`** — `requires-python = ">=3.12,<3.13"` (khớp Python 3.12.3 trên máy dev và
`python:3.12-slim` trong Docker).

**Dependency runtime:**

| Gói | Vì sao cần |
|---|---|
| `fastapi` | Framework web, cung cấp luôn `/docs` |
| `uvicorn[standard]` | ASGI server, cổng 8000 |
| `python-multipart` | **Bắt buộc** để FastAPI phân tích `multipart/form-data`; thiếu nó `/api/caesar/file` lỗi lúc khởi động |
| `jinja2` | Render `index.html` và tiêm hằng số `MAX_FILE_BYTES` (Quyết định 10) |

**Dependency dev** (nhóm `dev`, bị `uv sync --no-dev` loại khỏi image):

| Gói | Vì sao cần |
|---|---|
| `pytest` | Test runner |
| `pytest-cov` | Đo coverage và cưỡng chế ngưỡng |
| `httpx` | `TestClient` của Starlette phụ thuộc vào nó |
| `ruff` | Lint + format |

**`[tool.ruff]`** — `line-length = 100`, `target-version = "py312"`.
**`[tool.ruff.lint]`** — `select = ["E", "F", "I", "UP", "B", "SIM", "N", "RUF"]`
(pycodestyle, pyflakes, isort, pyupgrade, bugbear, simplify, naming, quy tắc riêng của Ruff).
`per-file-ignores` nới lỏng cho `tests/**` (ví dụ cho phép assert dài và tên test dài).
**`[tool.ruff.format]`** — dùng mặc định (nháy kép, thụt 4 khoảng trắng) để không phải tranh luận.

**`[tool.pytest.ini_options]`** —
`testpaths = ["tests"]`,
`addopts = "--cov=app --cov-report=term-missing --cov-fail-under=90 -q"`.
Ngưỡng nằm trong `addopts` nên **chạy `pytest` trần cũng fail khi tụt dưới 90%** — không cần nhớ thêm cờ,
và CI tương lai kế thừa miễn phí.

**`[tool.coverage.run]`** — `source = ["app"]`, `branch = true` (đo cả nhánh, quan trọng vì phần lớn logic
Tuần 1 là các nhánh validate).
**`[tool.coverage.report]`** — `omit` bỏ `app/**/__init__.py`.

**Phạm vi đo coverage — nói rõ một lần:** con số 90% **chỉ tính mã Python trong `app/`**.
`app/static/*.js`, `app/static/*.css` và `app/templates/*.html` **KHÔNG** nằm trong phép đo — coverage.py
không instrument chúng và Tuần 1 không có test runner JavaScript. Chất lượng UI được bảo vệ bằng test
guard ở `tests/integration/test_ui_assets.py` (Quyết định 11) chứ không bằng coverage.

## Risks / Trade-offs

**[`uv` chưa được cài trên máy dev, trong khi toàn bộ quy trình phụ thuộc vào nó]** → Biến việc cài `uv`
thành **task đầu tiên và là điều kiện chặn** của change, có tiêu chí hoàn thành đo được (`uv --version`
in ra phiên bản) và ghi phiên bản đó vào `README.md`. Commit `uv.lock` để mọi máy và image Docker dựng
ra cùng một tập dependency. Nếu việc cài thất bại trên máy của ai đó, có đường lui tạm thời
`python -m venv .venv && pip install -e .` để không ai bị chặn — nhưng Dockerfile và tài liệu vẫn chỉ
mô tả đường `uv`, để đường lui không âm thầm trở thành đường chính.

**[Thông báo "5 MB" trong khi giới hạn thực thi là 5 MiB — người dùng có thể bối rối]** → **Đã được
người dùng duyệt: giữ nguyên văn chuỗi `"File vượt quá dung lượng tối đa 5 MB."` dù ngưỡng thực thi là
5 MiB.** Đây là quyết định đã chốt, không còn là câu hỏi mở — tuyệt đối **không** sửa chuỗi lỗi cho
"đúng đơn vị". Phần còn lại chỉ là giảm nhẹ sự bối rối ở ba chỗ khác: (a) đúng một hằng
số `MAX_FILE_BYTES = 5 * 1024 * 1024` trong `app/config.py`, có comment ghi rõ `= 5242880 byte = 5 MiB`;
(b) UI hiển thị nhãn phụ `5 MiB = 5.242.880 byte` ở khu vực chọn file — thông tin thêm này không thay
đổi chuỗi lỗi mà docx quy định; (c) test khẳng định chuỗi lỗi **đúng từng ký tự** để không ai "sửa cho
đúng" rồi phá hợp đồng — test này chính là thứ bảo vệ quyết định đã duyệt khỏi bị vô hiệu hóa bởi một
lần refactor thiện chí.

**[Chuỗi `"Dữ liệu gửi lên không hợp lệ."` từng thiếu trong bảng docx §5]** → Đã giải quyết: chuỗi được
người dùng duyệt, có requirement riêng trong `specs/error-handling/`, và docx §5 hiện đã có đủ dòng thứ
13. `app/errors/messages.py` là nguồn sự thật thực thi và test hợp đồng phủ cả 13 chuỗi.

**[Nhiều request file lớn đồng thời làm phình RAM]** → Ước lượng xấu nhất cho **một** request: 5 MiB
bytes thô + bản `str` đã decode + bản `str` kết quả + bytes đầu ra. Chuỗi Python chọn độ rộng theo ký tự
"rộng" nhất, nên một file 5 MiB toàn ASCII mà lẫn **một** emoji sẽ khiến cả chuỗi dùng 4 byte/ký tự
→ ~21 MiB cho mỗi bản, tổng đỉnh có thể tới ~45 MiB cho một request. Giảm thiểu: trần
`MAX_REQUEST_BYTES` ở Tầng 0 (Quyết định 4); vòng đọc dừng ngay khi vượt ngưỡng; giải phóng buffer bytes
thô ngay sau khi decode xong thay vì giữ tới cuối handler; Starlette tự tràn phần body vượt ~1 MiB ra
đĩa nên RAM của tầng parser bị chặn; Tuần 1 chạy `uvicorn` với số worker mặc định và **ghi rõ trong
README rằng ứng dụng không có rate limit** — nó là công cụ học tập chạy same-origin, không phải dịch vụ
công khai. Nếu tuần sau cần mở ra Internet, cần thêm rate limit và reverse proxy giới hạn body size.

**[Mockup HTML có thể còn lệch docx ở chỗ chưa phát hiện]** → 6 điểm đã biết được khóa lại bằng test
guard, nhưng 540 dòng mockup còn có thể chứa sai lệch khác (chuỗi trạng thái, nhãn, hành vi biên). Giảm
thiểu bằng một quyết định kiến trúc thay vì một lần rà soát: **UI không bao giờ tự soạn thông báo lỗi
nghiệp vụ, luôn hiển thị nguyên văn `message` do server trả về** — nhờ vậy mọi chuỗi lệch còn sót trong
JS đều là code chết, không thể tới mắt người dùng. Bổ sung một lượt đối chiếu thủ công `index.html` với
danh mục UI ở docx §2.2 khi làm bước UI, và xóa hẳn `mockApi` để không còn đường nào cho kết quả giả
xuất hiện.

**[Mục tiêu coverage 90% có thể đẩy team viết test hình thức]** → Rủi ro thật: test gọi hàm rồi không
assert gì, hoặc assert lại chính hằng số vừa import, chỉ để kéo số lên. Giảm thiểu: (a) tiêu chí nghiệm
thu thật của change là **các scenario trong `specs/`**, coverage chỉ là sàn để phát hiện nhánh bị bỏ
quên; (b) yêu cầu truy vết — mỗi scenario trong spec có ít nhất một test tương ứng, review đối chiếu
theo danh sách này chứ không theo phần trăm; (c) `branch = true` khiến các nhánh lỗi (phần lớn logic
Tuần 1) phải được chạm thật, khó "ăn gian" bằng vài test happy path; (d) quy ước review: test không có
assert về **hành vi quan sát được** thì bị từ chối, kể cả khi coverage đã đạt.

**[Hai đường validate `key` — JSON token và parse chuỗi — có thể trôi lệch nhau]** → Endpoint JSON dùng
hook `parse_int` để nhận đúng token số nguyên và chuẩn hóa theo từng chữ số; endpoint multipart dùng
regex cùng trần 32 ký tự. Hai quy tắc khác nhau về bản chất nên dễ phân kỳ theo thời gian (ví dụ một bên
chấp nhận `"3.0"`, bên kia không). Giảm thiểu: cả hai đi qua **một** module `app/api/schemas.py`; test
khẳng định `3.0` bị từ chối ở cả hai nơi, numeric string không biến thành token, và JSON integer dài
hơn 4.300 chữ số vẫn trả kết quả Caesar đúng mà không thay đổi giới hạn chuyển đổi `int` toàn tiến trình.

**[Trần lạm dụng 64 MiB ở Tầng 0 là con số chọn tay và nằm ngoài DOCX]** → Đây là ngoại lệ hạ tầng
OpenSpec đã được chủ sở hữu phê duyệt, không phải giới hạn nghiệp vụ mới: primary DOCX và bản trích giữ
nguyên. Đặt cao để thứ tự kiểm tra ở Quyết định 9 chi phối mọi trường hợp thực tế, đổi lại một payload
60 MiB vẫn được nạp (tràn ra đĩa) trước khi bị từ chối. Giảm thiểu: trần là hằng số ở `app/config.py`
chứ không rải rác trong code; route-aware guard trả chuỗi file cho API file và chuỗi generic không lộ
ngưỡng cho tuyến khác; test local/container khóa hành vi này. Nếu triển khai ra ngoài môi trường học
tập thì reverse proxy phía trước mới là nơi đúng để chặn body quá khổ.

**[Output tải xuống có thể bị lưu nhầm vào root repo]** → Ứng dụng không tạo `.txt` trong repo lúc
runtime và pytest dùng `tmp_path` ngoài repo, nên ignore toàn cục `*.txt` vừa sai lý do vừa có thể che
fixture/tài liệu hợp lệ. Chỉ ignore hai pattern root-level do công cụ này sinh ra:
`/*.encrypted.txt` và `/*.decrypted.txt`; không tạo runtime directory mới.

## Deferred technical debt

Ba smell sau được ghi nhận bền vững nhưng được chủ sở hữu chấp thuận **defer, không chặn remediation**:

1. Logic lọc/đọc header bị lặp giữa `_content_length` và `_header` trong request-size guard.
2. Các phép gán trạng thái disabled bị lặp quanh vòng khóa control tổng quát trong `app.js`.
3. Nhánh `state.mode === "encrypt"` lặp lại ở render, analysis, dispatch API và đặt tên file.

Chỉ refactor các điểm này trong một change riêng khi có lợi ích đo được; remediation hiện tại không mở
rộng phạm vi sang cleanup không bắt buộc.

## Migration Plan

Repo chưa có code và ứng dụng stateless, **không có dữ liệu để migrate và không có schema để đổi**. Phần
này vì vậy mô tả **thứ tự triển khai** — chọn sao cho mỗi bước tự kiểm chứng được và không bước nào phải
chờ bước sau mới biết mình đúng.

| # | Bước | Nội dung | Cách xác minh |
|---|---|---|---|
| 0 | **Bootstrap** | Cài `uv`; `pyproject.toml` với deps + cấu hình Ruff/pytest/coverage; `.gitignore`; khung thư mục `app/`, `tests/` với `__init__.py` | `uv --version` in ra phiên bản; `uv sync` tạo `.venv` và `uv.lock`; `uv run ruff check .` sạch; `uv run pytest` chạy được (0 test, coverage tạm tắt) |
| 1 | **Caesar Core** | `app/core/caesar.py` + `tests/unit/test_caesar.py` + `test_layering.py` | `"Hello World"` khóa 3 → `"Khoor Zruog"`; giải mã ngược lại đúng; khóa âm/>25 đúng; Unicode & `\r\n` nguyên vẹn; coverage của `app/core/` = 100%; test layering xanh |
| 2 | **Exception Handling + khung app** | `errors/{messages,exceptions,handlers}.py`, `main.py` tối thiểu, `config.py` | `GET /docs` trả 200; một route thử nghiệm ném `CaesarError` trả đúng `{"success": false, "message": ...}`; route không tồn tại trả 404 **đúng khuôn dạng chuẩn**, không có khóa `"detail"` |
| 3 | **Text API** | `schemas.py` (gồm `parse_key`), `routes_text.py` + test integration | Toàn bộ scenario của `text-cipher-api` xanh, gồm `key: true`, `key: 3.0`, `key: "3"`, `key: null`, thiếu `key`, và thứ tự ưu tiên text-trước-key |
| 4 | **File Processing + File API** | `file_processing.py`, `routes_file.py` + test integration | 5242880 byte → 200, 5242881 byte → 413; tên `bao.cao.v2.encrypted.txt` và `BaoCao.encrypted.txt`; BOM giữ ở mode `file`, bị loại ở mode `content`; CRLF nguyên vẹn; file latin-1 → 415; thiếu `key` + file 6 MiB → `"Thiếu khóa."` |
| 5 | **Web UI** | Tách mockup thành `index.html` + `styles.css` + `app.js`; áp 6 điểm sửa; mount `/static`, route `/` | `GET /` trả 200 và chứa `5242880`; test guard `test_ui_assets.py` xanh; chạy tay đủ hai luồng ở docx §3.1 và §3.2 trên trình duyệt, gồm kéo-thả, bảng dịch chuyển, tab Phân tích, copy/clear, download |
| 6 | **Docker** | `Dockerfile` multi-stage + `.dockerignore` + README | `docker build` thành công; `docker run -p 8000:8000` rồi `curl localhost:8000/` và `/docs` đều 200; `docker run --rm <image> id -u` khác `0`; `uv` không có trong image cuối |
| 7 | **Chốt** | Bật `--cov-fail-under=90`, chạy toàn bộ suite, đối chiếu docx §7 | `uv run pytest` xanh với coverage ≥ 90%; `uv run ruff check .` và `ruff format --check .` sạch; đi hết 8 gạch đầu dòng của docx §7 |

**Vì sao thứ tự này.** Nó đi **xuôi theo chiều phụ thuộc** ở mục Project Structure §3: mỗi bước chỉ dùng
những thứ đã được kiểm chứng ở bước trước, nên khi một test đỏ thì nguyên nhân gần như chắc chắn nằm
trong bước vừa làm. Exception Handling được đặt **trước** các endpoint (bước 2 trước 3) một cách có chủ
ý: khuôn dạng lỗi là thứ mọi endpoint phải tuân theo, dựng nó sau nghĩa là phải quay lại sửa từng
endpoint đã viết. UI đặt sau API vì nó cần một backend thật để chạy đối chiếu; Docker đặt cuối vì nó chỉ
đóng gói thứ đã chạy được.

**Chiến lược quay lui.** Mỗi bước là một commit (hoặc PR nhỏ) độc lập, và vì phụ thuộc là **một chiều**
nên các bước sau có thể `git revert` mà không làm hỏng bước trước: bỏ Docker (bước 6) không ảnh hưởng
app; bỏ UI (bước 5) vẫn còn API chạy được và test xanh; bỏ File API (bước 4) vẫn còn Text API. Chiều
ngược lại thì không — revert bước 1 hay 2 sẽ làm gãy mọi thứ phía trên, nên hai bước đó phải có test
xanh trước khi đi tiếp, và đó chính là lý do chúng đứng đầu. Bước 0 hỏng thì cách quay lui là xóa
`.venv/` và `uv.lock` rồi `uv sync` lại — không có gì ngoài repo bị ảnh hưởng. Không có dữ liệu người
dùng ở bất kỳ bước nào, nên mọi lần quay lui đều không gây mất mát.

## Open Questions

Chỉ liệt kê những ẩn số **trả lời sau được mà không làm đổi spec, cách tiếp cận hay việc chia task**.

1. **Số worker `uvicorn` trong container** — chạy 1 worker (mặc định) hay nhiều? Ảnh hưởng thông lượng và
   RAM đỉnh khi có nhiều upload 5 MiB đồng thời, nhưng chỉ là một tham số ở `CMD`, không đổi hành vi quan
   sát được, không đổi spec và không đổi task nào. Tuần 1 mặc định 1 worker; đo rồi chỉnh sau nếu cần.
2. **Có thêm `favicon.ico` và nhãn thương hiệu cho UI không** — thuần thẩm mỹ; docx §2.2 không yêu cầu.
   Thiếu nó chỉ gây vài dòng 404 trong log.
3. **Định dạng log ở môi trường chạy thật (text người đọc được hay JSON có cấu trúc)** — Tuần 1 dùng
   logger mặc định ghi ra stdout, đủ cho chạy local và `docker logs`. Đổi sang JSON có cấu trúc là việc
   của lúc có nơi thu thập log, và chỉ chạm cấu hình logger.
