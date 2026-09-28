# Backend Caesar, Vigenère, Playfair, Affine và Columnar Transposition

Backend FastAPI cung cấp API mã hóa/giải mã cho năm thuật toán cổ điển:
**Caesar**, **Vigenère**, **Playfair**, **Affine** và **Columnar Transposition**.
API nhận văn bản JSON hoặc file `.txt`, trả kết quả xem trước dạng JSON hoặc file
đính kèm do server tạo.

Đây là dự án học tập, không phải công cụ bảo vệ dữ liệu nhạy cảm. Server là nguồn
có thẩm quyền cho validation và kết quả cipher. Với nguồn file upload, server còn
quyết định bytes/BOM và tên attachment; với nguồn text, client có thể tạo file từ
chính `result` server trả về. Client chỉ nên kiểm tra sơ bộ để hỗ trợ trải nghiệm.

Đội Frontend nên bắt đầu từ
[`repo_docs/frontend-integration.md`](repo_docs/frontend-integration.md), tài liệu
consumer contract chi tiết cho cả 15 endpoint.

## 1. Tổng quan hành vi

Ứng dụng chạy trong một tiến trình FastAPI trên cổng `8000`. Runtime phục vụ API,
OpenAPI và UI static cùng origin; không có authentication hay session, và không lưu
input, key, tên file, nội dung file hay kết quả sau request. Khi đặt `DATABASE_URL`,
app ghi thêm **metadata** của mỗi request cipher vào PostgreSQL (xem mục 9.1).

```text
JSON text hoặc multipart .txt
              │
              ▼
 request guards + validation xác định
              │
              ▼
 Caesar | Vigenère | Playfair | Affine | Columnar core
              │
              ▼
 JSON hai trường hoặc attachment UTF-8
```

UI static đi kèm tại `/` hỗ trợ đủ năm thuật toán (text và file .txt), lịch sử
trên trình duyệt và tab lịch sử máy chủ (hiện khi `/api/health` báo
`history: "enabled"`). Nó là HTML/CSS/JS thuần, không có build step; Frontend riêng
vẫn có thể tích hợp theo `repo_docs/frontend-integration.md`.

## 2. Năm thuật toán

### 2.1 Caesar

Caesar dùng key số nguyên. Server chuẩn hóa key bằng modulo 26:

```text
k' = ((k mod 26) + 26) mod 26
Encrypt: E(x) = (x + k') mod 26
Decrypt: D(x) = (x - k') mod 26
```

Chỉ ASCII `A-Z`/`a-z` bị dịch vòng và vẫn giữ case. Số, dấu câu, whitespace,
LF/CRLF, chữ có dấu, emoji và Unicode ngoài ASCII được giữ nguyên.

```text
Hello World + key 3  → Khoor Zruog
Khoor Zruog + key 3 → Hello World
Xin chào! Zz + key 29 → Alq fkàr! Cc
```

Key text phải là JSON integer thực sự; boolean, float và chuỗi số đều bị từ chối.
Key âm, `0`, lớn hơn `25` và integer rất lớn vẫn hợp lệ.

### 2.2 Vigenère repeating-key

Vigenère dùng key chuỗi không rỗng, khớp toàn bộ `[A-Za-z]+`. Server chuẩn hóa
key sang uppercase rồi lặp key trên các chữ cái ASCII của input.

- Chỉ `A-Z`/`a-z` bị biến đổi và tiêu thụ một vị trí key.
- Case của input được giữ nguyên.
- Whitespace, CRLF, số, dấu câu và Unicode ngoài ASCII được giữ nguyên và không
  làm key tiến lên.

```text
Attack at dawn! + LEMON → Lxfopv ef rnhr!
Lxfopv ef rnhr! + LEMON → Attack at dawn!
AéA + BC → BéC
```

### 2.3 Playfair canonical 5×5

Playfair dùng biến thể 5×5 xác định của dự án:

1. Keyword được uppercase theo ASCII, chỉ giữ `A-Z`, đổi `J → I`, rồi loại ký tự
   trùng nhưng giữ lần xuất hiện đầu tiên.
2. Matrix được điền theo hàng bằng keyword đã chuẩn hóa, sau đó bằng alphabet
   `A-Z` bỏ `J`.
3. Plaintext được uppercase theo ASCII, bỏ mọi ký tự ngoài ASCII letter và đổi
   `J → I`.
4. Plaintext được chia thành digraph. Cặp lặp hoặc ký tự cuối lẻ nhận filler `X`;
   nếu ký tự đang xử lý là `X`, filler fallback là `Q` để tránh cặp `XX`.
5. Từng digraph áp dụng quy tắc cùng hàng, cùng cột hoặc hình chữ nhật, có wrap.

Matrix cho key `PLAYFAIR EXAMPLE`:

```text
P L A Y F
I R E X M
B C D G H
K N O Q S
T U V W Z
```

Các vector chuẩn:

| Thao tác | Input | Prepared/normalized | Result |
|---|---|---|---|
| Encrypt | `HIDE THE GOLD IN THE TREE STUMP` | `HIDETHEGOLDINTHETREXESTUMP` | `BMODZBXDNABEKUDMUIXMMOUVIF` |
| Decrypt | `BMODZBXDNABEKUDMUIXMMOUVIF` | — | `HIDETHEGOLDINTHETREXESTUMP` |
| Encrypt | `XX` | `XQXQ` | `GWGW` |
| Encrypt | `ABX` | `ABXQ` | `PDGW` |
| Decrypt | `PDGW` | — | `ABX` |
| Decrypt | `GWGW` | — | `XQX` |

Playfair cố ý mất thông tin. Decrypt trả uppercase prepared plaintext, giữ filler
`X` giữa chuỗi (ví dụ `BALXLOON`) nhưng **bỏ đúng một filler cuối chuỗi**: nếu kết
quả kết thúc bằng `XQ` thì bỏ `Q`, ngược lại nếu kết thúc bằng `X` thì bỏ `X`.
Vì ciphertext không phân biệt được filler với chữ thật, plaintext chẵn kết thúc
bằng `X` sẽ mất `X` cuối (ví dụ `AX → A`). Server không phục hồi `J`, case,
whitespace, dấu câu hay Unicode đã bị loại, nên round-trip không nhất thiết bằng
input gốc.

### 2.4 Affine modulo 26

Affine dùng hai khóa integer `a`, `b`, được chuẩn hóa về `a'`, `b'` theo modulo 26.
`a'` phải nguyên tố cùng nhau với 26; tập hợp lệ chính xác là
`1,3,5,7,9,11,15,17,19,21,23,25`, còn `b'` nhận mọi residue `0..25`. Vì vậy có
đúng `12 × 26 = 312` cặp khóa normalized hợp lệ. `(5,8)` chỉ là cặp gợi ý/canonical,
không phải default server.

```text
Encrypt: E(x) = (a' × x + b') mod 26
Decrypt: D(y) = inverse(a', 26) × (y - b') mod 26

HELLO + (5,8) → RCLLA
RCLLA + (5,8) → HELLO
```

Chỉ ASCII `A-Z`/`a-z` bị biến đổi và vẫn giữ case. Mọi ký tự khác, gồm Unicode,
emoji, whitespace và CRLF, được giữ nguyên. Với khóa hợp lệ, round-trip Affine là
lossless. Khóa âm/lớn được normalize; ví dụ `(-21,-18)` và `(57,60)` tương đương
`(5,8)`. Server từ chối `a'` không khả nghịch thay vì tự sửa sang khóa khác.

### 2.5 Columnar Transposition

Columnar ghi text theo hàng với `m` cột vật lý rồi đọc cột theo rank khóa. Không
padding, không normalize và không bỏ ký tự; mọi Unicode code point, whitespace,
CR/LF và combining mark đều tham gia hoán vị như nhau. Với JSON text, `U+FEFF`
kể cả ở đầu là dữ liệu; chỉ leading UTF-8 BOM của file upload là metadata.

Key là JSON/multipart string, trim **chỉ ASCII whitespace**, tối đa 2.048 Unicode
code point sau trim và tạo từ 2 đến 256 cột. Hai dạng được nhận:

- Numeric permutation: các rank `1..m` xuất hiện đúng một lần. Separator là một
  dấu phẩy có thể kèm ASCII whitespace, hoặc một hay nhiều ASCII whitespace; có
  thể trộn hai dạng và bọc đúng một cặp `{...}` ngoài cùng. Ví dụ `3 1 4 2`,
  `3,1,4,2` hoặc `{3, 1 4,2}`. Compact digits `312`, leading zero, dấu, decimal,
  exponent, empty token và Unicode digit đều không hợp lệ.
- Keyword: đúng `[A-Za-z]{2,256}`. Rank được tạo case-insensitive, ổn định theo vị
  trí gốc khi trùng chữ; `BALLOON` cho `[2,1,3,4,6,7,5]`.

Các vector chuẩn:

```text
ABCDE + 3 1 4 2 → BDAEC → ABCDE
MEET ME AT NOON + BALLOON → EAM NETT EO NMO → MEET ME AT NOON
😀A𝄞é + 2 1 3 → A😀é𝄞 → 😀A𝄞é
```

## 3. API: 15 endpoint

| Cipher | Method và path | Request | Vai trò |
|---|---|---|---|
| Caesar | `POST /api/caesar/encrypt` | JSON | Mã hóa text |
| Caesar | `POST /api/caesar/decrypt` | JSON | Giải mã text |
| Caesar | `POST /api/caesar/file` | Multipart | Mã hóa/giải mã file |
| Vigenère | `POST /api/vigenere/encrypt` | JSON | Mã hóa text |
| Vigenère | `POST /api/vigenere/decrypt` | JSON | Giải mã text |
| Vigenère | `POST /api/vigenere/file` | Multipart | Mã hóa/giải mã file |
| Playfair | `POST /api/playfair/encrypt` | JSON | Mã hóa text |
| Playfair | `POST /api/playfair/decrypt` | JSON | Giải mã text |
| Playfair | `POST /api/playfair/file` | Multipart | Mã hóa/giải mã file |
| Affine | `POST /api/affine/encrypt` | JSON | Mã hóa text |
| Affine | `POST /api/affine/decrypt` | JSON | Giải mã text |
| Affine | `POST /api/affine/file` | Multipart | Mã hóa/giải mã file |
| Columnar | `POST /api/columnar/encrypt` | JSON | Mã hóa text |
| Columnar | `POST /api/columnar/decrypt` | JSON | Giải mã text |
| Columnar | `POST /api/columnar/file` | Multipart | Mã hóa/giải mã file |

Consumer đang dùng allowlist 12 route phải mở lên đúng ba path Columnar trên để
thành 15 route; không có route generalized hoặc versioned mới. OpenAPI gắn cả ba
operation vào tag `Columnar Transposition` và là projection machine-readable của
contract request/response đã test.

### 3.1 Text JSON

OpenAPI quảng bá `Content-Type: application/json` cho các endpoint text; runtime
cũng nhận `application/*+json` và media type parameter hợp lệ:

| Cipher | Body | Kiểu key |
|---|---|---|
| Caesar | `{"text":"Hello World","key":3}` | JSON integer |
| Vigenère | `{"text":"Attack at dawn!","key":"LEMON"}` | String `[A-Za-z]+` |
| Playfair | `{"text":"HIDE THE GOLD","key":"PLAYFAIR EXAMPLE"}` | String còn ít nhất một ASCII letter sau normalize |
| Affine | `{"text":"HELLO","a":5,"b":8}` | Hai JSON integer thật; không có default |
| Columnar | `{"text":"ABCDE","key":"3 1 4 2"}` | String numeric permutation hoặc keyword |

`text` phải là string khác rỗng. Chuỗi chỉ có whitespace hợp lệ với Caesar,
Vigenère, Affine và Columnar; Playfair từ chối nếu normalization không còn ASCII
letter. Riêng hai route Affine yêu cầu object có
chính xác `text`, `a`, `b`: field lạ hoặc trùng bị từ chối. `a`/`b` phải là JSON
integer token thật, không coercion string/float/bool/null và không bị giới hạn bởi
JavaScript safe integer; client phải serialize mà không làm tròn. Hai route
Columnar cũng yêu cầu exact object `text,key`, từ chối field lạ/trùng và không
coerce key. Lone/misordered JSON surrogate ở member name hoặc string value là
invalid body; escaped surrogate pair hợp lệ được tính như một Unicode code point.

Ví dụ:

```bash
curl -sS -X POST http://localhost:8000/api/caesar/encrypt \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello World","key":3}'

curl -sS -X POST http://localhost:8000/api/vigenere/encrypt \
  -H 'Content-Type: application/json' \
  -d '{"text":"Attack at dawn!","key":"LEMON"}'

curl -sS -X POST http://localhost:8000/api/playfair/encrypt \
  -H 'Content-Type: application/json' \
  -d '{"text":"HIDE THE GOLD IN THE TREE STUMP","key":"PLAYFAIR EXAMPLE"}'

curl -sS -X POST http://localhost:8000/api/affine/encrypt \
  -H 'Content-Type: application/json' \
  -d '{"text":"HELLO","a":5,"b":8}'

curl -sS -X POST http://localhost:8000/api/columnar/encrypt \
  -H 'Content-Type: application/json' \
  -d '{"text":"ABCDE","key":"3 1 4 2"}'
```

### 3.2 File multipart

Ba endpoint Caesar/Vigenère/Playfair `/file` nhận `multipart/form-data` với các field:

| Field | Bắt buộc | Giá trị |
|---|---:|---|
| `file` | Có | File có filename kết thúc bằng `.txt`, không phân biệt hoa thường |
| `key` | Có | Chuỗi multipart; Caesar dùng signed integer, hai cipher còn lại dùng string key |
| `action` | Có | Chính xác `encrypt` hoặc `decrypt` |
| `response_mode` | Không | `content` hoặc `file`; mặc định `content` |

`action` và `response_mode` phân biệt hoa thường. Với Caesar, key multipart được
trim, phải khớp `[+-]?[0-9]+` và dài tối đa 32 ký tự. Vigenère không trim hay tự
sửa key; Playfair normalize key theo quy tắc thuật toán.

`POST /api/affine/file` có exact field set riêng:

| Field | Bắt buộc | Giá trị |
|---|---:|---|
| `file` | Có | File `.txt` UTF-8 theo contract chung |
| `a` | Có | Signed-decimal string, trim ngoài, tối đa 32 ký tự, không có default |
| `b` | Có | Signed-decimal string, trim ngoài, tối đa 32 ký tự, không có default |
| `action` | Có | Chính xác `encrypt` hoặc `decrypt` |
| `response_mode` | Không | `content` hoặc `file`; mặc định `content` |

Field lạ hoặc trùng bị từ chối trước validation field/content. `a` và `b` phải khớp
`[+-]?[0-9]+` sau trim; `a'` còn phải nguyên tố cùng nhau với 26.

`POST /api/columnar/file` cũng là exact multipart object, nhưng dùng field
`file,key,action` và optional `response_mode`. `key` luôn là scalar string theo
grammar Columnar ở §2.5; upload part cho key, field lạ hoặc field trùng bị từ chối.

```bash
curl -sS -X POST http://localhost:8000/api/vigenere/file \
  -F 'file=@input.txt;type=text/plain' \
  -F 'key=LEMON' \
  -F 'action=encrypt' \
  -F 'response_mode=content'

curl -sS -X POST http://localhost:8000/api/affine/file \
  -F 'file=@input.txt;type=text/plain' \
  -F 'a=5' -F 'b=8' -F 'action=encrypt' -F 'response_mode=content'

curl -sS -X POST http://localhost:8000/api/columnar/file \
  -F 'file=@input.txt;type=text/plain' \
  -F 'key=BALLOON' -F 'action=encrypt' -F 'response_mode=content'
```

## 4. Response và lỗi

Text thành công và file `response_mode=content` trả HTTP `200` với đúng hai field:

```json
{"success":true,"result":"Khoor Zruog"}
```

Mọi lỗi trả JSON đúng hai field, kể cả request dùng `response_mode=file`:

```json
{"success":false,"message":"Khóa phải là số nguyên."}
```

Contract không có machine error `code`, `detail`, field errors,
`normalizedInput`, matrix, prepared text hoặc metadata bổ sung. Client nên dùng
HTTP status và request context cho logic, còn `message` tiếng Việt để hiển thị.

File `response_mode=file` thành công là ngoại lệ không dùng JSON: server trả body
bytes UTF-8 với `Content-Type: text/plain; charset=utf-8` và
`Content-Disposition: attachment`.

Các nhóm status chính:

| Status | Ý nghĩa |
|---:|---|
| `200` | Thành công; JSON preview hoặc attachment |
| `413` | File vượt 5 MiB hoặc request rõ ràng vượt trần hạ tầng |
| `415` | Sai đuôi `.txt` hoặc file không phải UTF-8 |
| `422` | Body/field/key/action/content không hợp lệ |
| `500` | Lỗi đọc file hoặc lỗi hệ thống đã được che chi tiết kỹ thuật |

Backend dừng ở lỗi đầu tiên theo validation precedence đã chốt. Ma trận message
và thứ tự đầy đủ nằm trong OpenSpec và
[`repo_docs/frontend-integration.md`](repo_docs/frontend-integration.md).

Riêng Affine, text dùng thứ tự `body → text → a → b`; file dùng
`multipart framing/exact fields → file → a → b → action → response_mode →
extension → size → empty → UTF-8 → transform`. Các message khóa mới là
`Thiếu khóa a.`, `Khóa a phải là số nguyên.`,
`Khóa a phải nguyên tố cùng nhau với 26.`, `Thiếu khóa b.` và
`Khóa b phải là số nguyên.`. Mỗi response lỗi vẫn chỉ chứa `success,message`.

Columnar text dùng `body/exact shape/surrogate → text → key missing/empty → key
type → key content → transform`; file dùng `multipart framing/exact fields → file
→ key → action → response_mode → extension → size → empty → UTF-8 → transform`.
Key sai wire type dùng `Khóa phải là chuỗi.`; content sai dùng
`Khóa Columnar phải là hoán vị 1..m hoặc từ khóa gồm 2 đến 256 chữ cái A-Z.`.

## 5. Contract file

- Chỉ nhận filename kết thúc bằng `.txt`, không phân biệt hoa thường; ví dụ
  `.TXT` hợp lệ nhưng `.txt.exe` không hợp lệ. MIME upload không quyết định tính
  hợp lệ; filename và bytes là authority.
- File phải là UTF-8 thường hoặc UTF-8 có BOM.
- Giới hạn chính xác là `5 MiB = 5 * 1024 * 1024 = 5.242.880 byte` nội dung file.
  Đúng giới hạn được chấp nhận; `5.242.881` byte trả HTTP `413`. Message public
  vẫn ghi “5 MB” để giữ contract đã chấp nhận.
- File `0` byte bị từ chối, nhưng file chỉ có UTF-8 BOM hợp lệ. Whitespace-only
  hợp lệ với Caesar/Vigenère/Affine/Columnar,
  nhưng Playfair từ chối sau normalization.
- `response_mode=content` trả JSON preview và loại BOM khỏi chuỗi `result`.
- `response_mode=file` trả attachment do server tạo; attachment giữ BOM nếu và
  chỉ nếu input có BOM.
- Filename chỉ bỏ đuôi `.txt` cuối cùng, giữ các dấu chấm trước đó và luôn dùng
  `.txt` thường:

```text
note.txt       + encrypt → note.encrypted.txt
note.txt       + decrypt → note.decrypted.txt
bao.cao.TXT    + encrypt → bao.cao.encrypted.txt
```

Với nguồn file upload, preview và download là hai request riêng. Client phải dùng
attachment và filename của server cho bản tải chính thức, không đóng gói lại
preview thành file thay thế.

## 6. Runtime boundary

- Cổng ứng dụng: `8000` cho cả local và container.
- UI và API cùng origin; app không bật CORS. FE dev server riêng nên proxy `/api`
  tới `http://localhost:8000` và giữ URL API tương đối.
- Swagger UI: <http://localhost:8000/docs>
- OpenAPI JSON: <http://localhost:8000/openapi.json>
- Trang static đi kèm: <http://localhost:8000/>
- Health: `GET /api/health` trả `{"success":true,"result":{"app":"ok","database":…}}`
  với `database` là `ok`, `unavailable` (HTTP 503) hoặc `disabled` (không có
  `DATABASE_URL`).
- Lịch sử: `GET /api/history?limit=&cursor=&cipher=&operation=` trả metadata thao
  tác, mới nhất trước; contract chi tiết nằm trong `repo_docs/frontend-integration.md`.
- Request guard có trần hạ tầng `64 MiB` cho một `Content-Length` decimal hợp lệ;
  trần này không thay đổi giới hạn nghiệp vụ file 5 MiB. Cả năm route file được
  phân loại bằng file-size message và multipart-completion guard; các route text
  Affine/Columnar dùng message request generic giống các route text khác.

## 7. Cài đặt và chạy local

### Yêu cầu

| Thành phần | Yêu cầu từ repository |
|---|---|
| Python | `>=3.12,<3.13` theo `pyproject.toml` |
| uv | `0.12.15`, cùng bản được pin trong `Dockerfile` |
| Docker | Tùy chọn cho luồng container; repository không pin phiên bản Docker CLI |

### Cài uv 0.12.15

Theo [hướng dẫn cài đặt chính thức của uv](https://docs.astral.sh/uv/getting-started/installation/),
URL installer có thể chứa phiên bản cụ thể:

```bash
curl -LsSf https://astral.sh/uv/0.12.15/install.sh | sh
uv --version
```

Nếu installer yêu cầu cập nhật `PATH`, hãy làm theo hướng dẫn nó in ra hoặc mở
terminal mới trước khi chạy lệnh kiểm tra. Kết quả phải báo `uv 0.12.15` trước khi
đồng bộ dependency.

### Chuẩn bị môi trường khóa dependency

```bash
git clone git@github.com:kiendt2312/cipher_workbench-be.git
cd cipher_workbench-be
uv sync --frozen
```

`uv sync --frozen` dùng đúng `uv.lock` và mặc định cài nhóm dev. Nếu chỉ cần chạy
ứng dụng, dùng `uv sync --frozen --no-dev`.

### Chạy server

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Không đặt `DATABASE_URL` thì app chạy không có database: 15 route cipher hoạt
động bình thường, `/api/health` báo `database: "disabled"` và `/api/history` trả
503. Muốn chạy app bằng uv (có `--reload`) nhưng dùng PostgreSQL của
docker-compose, chỉ bật service `db`; nó mở cổng `127.0.0.1:${DB_HOST_PORT}`
(mặc định `5433`):

```bash
docker compose up -d db
set -a && . ./.env && set +a
export DATABASE_URL="postgresql+asyncpg://$POSTGRES_USER:$POSTGRES_PASSWORD@127.0.0.1:${DB_HOST_PORT:-5433}/$POSTGRES_DB"
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Nếu service `app` của compose cũng đang chạy thì dừng nó trước
(`docker compose stop app`) để giải phóng cổng `8000`.

Sau khi server khởi động, đối chiếu runtime tại `/docs` hoặc `/openapi.json` thay
vì duy trì một bản OpenAPI sao chép trong README.

## 8. Test, lint và format

```bash
uv run pytest
uv run pytest --no-cov tests/integration/test_app_runtime.py
uv run ruff check .
uv run ruff format --check .
```

Test đánh dấu `db` cần PostgreSQL thật và tự bỏ qua khi không có
`TEST_DATABASE_URL`. Chạy đầy đủ với một container tạm:

```bash
docker run -d --name cipher-test-db -e POSTGRES_USER=cipher -e POSTGRES_PASSWORD=cipher \
  -e POSTGRES_DB=cipher_test -p 127.0.0.1:55432:5432 postgres:17
export TEST_DATABASE_URL=postgresql+asyncpg://cipher:cipher@127.0.0.1:55432/cipher_test
uv run pytest
docker rm -f cipher-test-db
```

Fixture tự chạy `alembic upgrade head` và xóa sạch bảng giữa các test, nên chỉ dùng
một database dành riêng cho test.

`pyproject.toml` cấu hình coverage cho `app/`, bật branch coverage và chặn dưới
`90%`. Các phiên bản package cụ thể được khóa trong `uv.lock`; không cần nâng cấp
dependency để chạy các lệnh trên.

## 9. Docker

`Dockerfile` dùng multi-stage build, Python `3.12-slim`, uv `0.12.15`, dependency
runtime từ `uv.lock`, user không phải root `appuser` (uid `10001`) và cổng `8000`.

```bash
docker build -t caesar-cipher-be .
docker run --rm -p 8000:8000 caesar-cipher-be
```

Kiểm tra từ terminal khác:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:8000/
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:8000/docs
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:8000/openapi.json
```

### 9.1 docker-compose với PostgreSQL

`docker-compose.yml` dựng ba service:

- `db`: PostgreSQL 17, dữ liệu nằm trong volume `pgdata`, có healthcheck;
- `migrate`: chạy `alembic upgrade head` một lần sau khi `db` healthy;
- `app`: chạy sau khi `migrate` thành công; trong container vẫn là cổng `8000`,
  máy host truy cập qua `http://localhost:${APP_HOST_PORT}` (mặc định `8080`).

```bash
cp .env.example .env   # đổi POSTGRES_PASSWORD và DATABASE_URL cho khớp
docker compose up --build
curl -s http://localhost:8080/api/health
# {"success":true,"result":{"app":"ok","database":"ok"}}
curl -s 'http://localhost:8080/api/history?limit=5'
docker compose down        # giữ dữ liệu
docker compose down -v     # xóa luôn volume dữ liệu
```

`.env` bị gitignore và dockerignore. App không tự tạo bảng khi khởi động; schema
chỉ thay đổi qua migration Alembic trong `alembic/versions/`.

Bảng `cipher_operations` chỉ lưu metadata: cipher, operation, nguồn text/file,
response mode, độ dài input/output (code point cho text, byte UTF-8 cho file),
HTTP status, thành công hay lỗi và thời gian xử lý. Không lưu plaintext,
ciphertext, key, tên file, nội dung file, IP hay user agent. Ghi lịch sử là
best-effort: DB lỗi hoặc chậm quá 500 ms thì bản ghi bị bỏ qua, response cipher
không đổi.

Project không có authentication, nên việc đọc lịch sử được khóa bằng cấu hình:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `HISTORY_API_ENABLED` | tắt | `true`/`1`/`yes`/`on` mới bật `GET /api/history`; khi tắt endpoint trả 404, việc ghi lịch sử vẫn chạy |
| `HISTORY_RETENTION_DAYS` | `30` | Bản ghi cũ hơn số ngày này bị xóa (1 đến 3650; giá trị sai làm app không khởi động) |

`.env.example` bật `HISTORY_API_ENABLED=true` cho môi trường dev. **Trên mọi môi
trường dùng chung hoặc public, để biến này tắt** (không đặt hoặc `false`).
`/api/health` trả thêm `history: "enabled" | "disabled"`.

App tự xóa bản ghi quá hạn lúc khởi động và mỗi 6 giờ, nên một bản ghi có thể tồn
tại tối đa 30 ngày + 6 giờ. Chạy xóa ngay bằng tay:

```bash
docker compose exec app python -m app.history.retention
# Deleted 0 history rows older than 30 days
```

Container chạy trực tiếp Uvicorn; repository không cấu hình production reverse
proxy, TLS, rate limiting, cloud deployment hoặc orchestration.

Không phơi trực tiếp app này ra Internet. Nếu cần public service, hãy đặt một
reverse proxy/gateway bên ngoài repository để kết thúc TLS, giới hạn request và
thêm rate limiting; cấu hình và triển khai lớp đó nằm ngoài phạm vi dự án này.

## 10. Kiến trúc và cấu trúc dự án

```text
app/
├── main.py                         # assembly, router, middleware, UI static
├── config.py                       # giới hạn file/request, cổng, DATABASE_URL
├── core/
│   ├── caesar.py                   # Caesar thuần
│   ├── vigenere.py                 # Vigenère repeating-key thuần
│   ├── playfair.py                 # Playfair 5×5 thuần
│   ├── affine.py                   # Affine modulo 26 thuần
│   └── columnar.py                 # Columnar Transposition thuần
├── api/
│   ├── routes_text.py              # Caesar JSON
│   ├── routes_file.py              # Caesar multipart
│   ├── routes_additional_text.py   # Vigenère/Playfair JSON
│   ├── routes_additional_file.py   # Vigenère/Playfair multipart
│   ├── routes_affine_text.py       # Affine JSON strict
│   ├── routes_affine_file.py       # Affine multipart strict
│   ├── routes_columnar_text.py     # Columnar JSON strict
│   ├── routes_columnar_file.py     # Columnar multipart strict
│   ├── routes_health.py            # GET /api/health
│   ├── routes_history.py           # GET /api/history
│   ├── history_recorder.py         # middleware ghi metadata sau response
│   ├── schemas.py                  # parse/validation và response schema
│   └── request_size_guard.py       # 64 MiB + multipart completion guards
├── services/
│   └── file_processing.py          # size, UTF-8/BOM và filename helpers
├── db/
│   ├── engine.py                   # async engine, session factory, ping
│   └── models.py                   # bảng cipher_operations
├── history/
│   ├── routes.py                   # 15 route cipher được ghi lịch sử
│   ├── cursor.py                   # cursor phân trang opaque
│   └── store.py                    # ghi/đọc cipher_operations
├── errors/
│   ├── messages.py                 # message public canonical
│   ├── exceptions.py               # lỗi ứng dụng có status
│   └── handlers.py                 # JSON envelope và log an toàn
├── templates/                      # UI static năm thuật toán + lịch sử
└── static/

alembic/                            # migration schema (alembic upgrade head)
docker-compose.yml                  # db + migrate + app

tests/
├── unit/                            # core, validation, file helpers, layering
└── integration/                     # HTTP/OpenAPI, guards, UI assets, lịch sử/PostgreSQL
```

Các core là module thuần, không phụ thuộc FastAPI/file transport. HTTP adapters
chịu trách nhiệm validation và gọi đúng core; helper file dùng chung kiểm soát
bytes, encoding, BOM và attachment; error handlers dùng một envelope thống nhất.

## 11. Phạm vi và ngoài phạm vi

Repository này là backend cipher service cho Caesar, Vigenère, Playfair, Affine
và Columnar Transposition.
Nó có UI static năm thuật toán phục vụ cùng app; Frontend riêng (nếu có) là
consumer tách biệt, tích hợp theo `repo_docs/frontend-integration.md`.

Ngoài phạm vi hiện tại:

- authentication, authorization, session, lịch sử theo từng user và retention/xóa lịch sử tự động;
- lưu nội dung người dùng (input, key, file, kết quả) vào database;
- cipher khác ngoài năm cipher này, autokey Vigenère, Playfair 6×6 hoặc Playfair Unicode/lossless;
- phục hồi format, `J` hoặc filler giữa chuỗi khi decrypt Playfair;
- CORS cho frontend khác origin;
- production reverse proxy, TLS, rate limiting, cloud deployment và CI/CD;
- streaming file lớn hơn giới hạn nghiệp vụ.

Dockerfile chỉ đóng gói app hiện có; nó không phải cấu hình production deployment
hoàn chỉnh.

## 12. Nguồn đặc tả và thứ tự áp dụng

README là bản nhập môn, không thay thế đặc tả hoặc OpenAPI. Khi có khác biệt, dùng
thứ tự sau:

1. [OpenSpec Columnar đã hoàn tất implementation và đang active](openspec/changes/add-columnar-transposition-cipher/)
   cho Columnar, [OpenSpec Affine](openspec/changes/add-affine-cipher/) cho Affine,
   [OpenSpec Playfair/Vigenère đã hoàn thành](openspec/changes/add-playfair-vigenere-ciphers/)
   cho hai cipher đó, cùng
   [OpenSpec Caesar Week 1 đã hoàn thành](openspec/changes/caesar-cipher-week1-mvp/)
   cho Caesar và contract dùng chung.
2. Runtime trong `app/`, các test contract và `/openapi.json` xác nhận cách đặc tả
   được hiện thực ở revision đang chạy.
3. [Frontend integration guide](repo_docs/frontend-integration.md) diễn giải
   consumer contract chi tiết và phải được đồng bộ nếu lệch hai nguồn trên.
4. [Bản scope Caesar bảo tồn](docs/reference/be-scope-v1.0.md) và các source DOCX
   dùng để truy vết yêu cầu gốc.
5. `Caesar_Cipher_Tool_Demo.html` và `affine-cipher.html` chỉ là UI/algorithm
   reference; mock, client-side result/default, giới hạn 1 MB,
   filename dấu gạch dưới, host/cổng hard-code hoặc local cipher trong demo không
   ghi đè accepted behavior.

README cố ý không sao chép toàn bộ OpenAPI, bảng message hay validation matrix.
Khi contract thay đổi, cập nhật OpenSpec/runtime trước rồi đồng bộ các tài liệu
consumer tương ứng.
