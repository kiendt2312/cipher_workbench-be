# Handoff tích hợp Frontend — Caesar, Vigenère, Playfair, Affine và Columnar

Tài liệu này là **consumer contract duy nhất cho Frontend** khi tích hợp với backend
cipher. Nội dung độc lập framework: FE có thể dùng React, Vue, Svelte hoặc JavaScript
thuần, nhưng hành vi API và trạng thái quan sát được phải giữ đúng contract dưới đây.

- Cập nhật: `2026-09-28`. Backend có 15 route cipher, `GET /api/health`,
  `GET /api/history` (tùy chọn, cần PostgreSQL).
- **Người mới:** đọc mục **A. Bắt đầu nhanh** (khoảng 10 phút) rồi dùng file
  [`examples/cipher-api.ts`](examples/cipher-api.ts). Các mục 1–17 là tra cứu chi tiết.
- **Đã tích hợp trước đây:** đọc mục **0. Thay đổi gần đây**.
- UI tĩnh tại `/` của backend là một FE chạy được theo đúng tài liệu này; mở nó để
  xem hành vi mẫu.

## A. Bắt đầu nhanh

### A.1 Chạy backend

```bash
# Trong repo backend, cần Docker
cp .env.example .env          # lần đầu; đổi POSTGRES_PASSWORD và DATABASE_URL cho khớp
docker compose up -d --build  # PostgreSQL + migration + app
curl -s http://localhost:8080/api/health
# {"success":true,"result":{"app":"ok","database":"ok","history":"enabled"}}
```

Cấu hình dev server của FE proxy `/api` tới `http://localhost:8080` (hoặc
`http://localhost:8000` nếu chạy backend bằng `uv run uvicorn`). Code FE luôn gọi URL
tương đối `/api/...`; không ghi cứng host/port, backend không bật CORS.

```ts
// vite.config.ts
export default defineConfig({
  server: { proxy: { "/api": process.env.BACKEND_URL ?? "http://localhost:8080" } },
});
```

Swagger để thử API: <http://localhost:8080/docs>.

### A.2 Toàn bộ endpoint

| Method | Path | Body | Thành công (HTTP 200) |
|---|---|---|---|
| POST | `/api/{cipher}/encrypt` | JSON, xem A.3 | `{"success":true,"result":"<bản mã>"}` |
| POST | `/api/{cipher}/decrypt` | JSON, xem A.3 | `{"success":true,"result":"<bản rõ>"}` |
| POST | `/api/{cipher}/file` | multipart: `file`, khóa (A.3), `action`, `response_mode` | `content`: JSON như trên; `file`: file `text/plain` đính kèm |
| GET | `/api/health` | — | `{"success":true,"result":{"app","database","history"}}` (503 khi DB lỗi) |
| GET | `/api/history` | query `limit`, `cursor`, `cipher`, `operation` | `{"success":true,"result":{"items":[...],"nextCursor":...}}` |

`{cipher}` là một trong `caesar`, `vigenere`, `playfair`, `affine`, `columnar` (15 route
POST). `action` là `encrypt`/`decrypt`; `response_mode` là `content` (mặc định) hoặc
`file`.

### A.3 Khóa theo cipher

| Cipher | JSON text | Multipart | Quy tắc | Ví dụ |
|---|---|---|---|---|
| Caesar | `"key": 3` (**số**, không phải chuỗi) | `key` | Số nguyên có dấu, lớn tùy ý; file tối đa 32 ký tự | `{"text":"Hello World","key":3}` → `Khoor Zruog` |
| Vigenère | `"key": "LEMON"` | `key` | Chỉ `A-Z`/`a-z`, không khoảng trắng | `Attack at dawn!` → `Lxfopv ef rnhr!` |
| Playfair | `"key": "PLAYFAIR EXAMPLE"` | `key` | Có ít nhất một chữ cái; kết quả là văn bản chuẩn hóa (xem 4.3) | `HIDE THE GOLD` → `BMODZBXDNAGE` |
| Affine | `"a": 5, "b": 8` (**số**) | `a`, `b` | Số nguyên có dấu; `a` mod 26 nguyên tố cùng nhau với 26 | `HELLO` → `RCLLA` |
| Columnar | `"key": "3 1 4 2"` hoặc `"BALLOON"` | `key` | Hoán vị `1..m` (2–256 cột) hoặc từ khóa 2–256 chữ cái | `MEET ME AT NOON` + `BALLOON` → `EAM NETT EO NMO` |

Ba điều hay sai nhất:

1. Caesar và Affine gửi **JSON number**, nhưng giữ giá trị người dùng nhập dưới dạng
   chuỗi và ghép token bằng `BigInt` để không mất độ chính xác (có sẵn trong file mẫu).
2. Gửi `text` và chuỗi khóa **nguyên văn**: không `trim()`, không đổi hoa thường.
3. File luôn hai request: `response_mode=content` để xem trước, rồi
   `response_mode=file` để tải file chính thức với tên file từ header
   `Content-Disposition`.

### A.4 API client dùng ngay

File [`examples/cipher-api.ts`](examples/cipher-api.ts) (TypeScript, không phụ thuộc
thư viện) gồm `transformText`, `previewFile`, `downloadFile`, `saveBlob`, `getHealth`,
`canShowServerHistory`, `getHistory` và bộ hàm lịch sử trên trình duyệt. File đã được
compile với `tsc --strict` và chạy thử với backend thật.

```ts
import {
  ApiError, transformText, previewFile, downloadFile, saveBlob,
  getHealth, canShowServerHistory, getHistory, addLocalHistory,
} from "./cipher-api";

const result = await transformText({ cipher: "affine", operation: "encrypt", text: "HELLO", a: "5", b: "8" });
// "RCLLA"

const fileRequest = { cipher: "vigenere", operation: "encrypt", file, key: "LEMON" } as const;
const preview = await previewFile(fileRequest);          // hiện trong UI
const { blob, filename } = await downloadFile(fileRequest); // khi người dùng bấm tải
saveBlob(blob, filename);

if (canShowServerHistory(await getHealth())) {
  const page = await getHistory({ limit: 20, cipher: "playfair" });
  const next = page.nextCursor ? await getHistory({ limit: 20, cursor: page.nextCursor }) : null;
}

try {
  await transformText({ cipher: "vigenere", operation: "encrypt", text: "hi", key: "LE MON" });
} catch (error) {
  if (error instanceof ApiError) showError(error.message); // message tiếng Việt từ server
  else showError("Không thể gọi máy chủ. Vui lòng thử lại.");
}
```

### A.5 Lỗi

Mọi lỗi có dạng `{"success": false, "message": "<tiếng Việt>"}` với status 4xx/5xx
(kể cả khi yêu cầu file). FE hiển thị nguyên `message`; không rẽ nhánh logic theo nội
dung message. Lỗi mạng (không có response) thì tự hiện thông báo kết nối. Danh sách
status và message đầy đủ ở mục 9 và 16.3.

### A.6 UI tối thiểu phải có

- Chọn cipher, chế độ mã hóa/giải mã, nguồn văn bản/file; ô khóa theo A.3 (Affine có
  hai ô).
- Xóa kết quả cũ mỗi khi cipher, chế độ, nguồn, input hoặc khóa thay đổi.
- Khóa mọi control và chặn gửi lặp khi request đang chạy.
- Cảnh báo Playfair luôn hiện khi chọn Playfair (câu chuẩn ở mục 11).
- File: kiểm tra sơ bộ `.txt`, tối đa 5 MiB, không rỗng; xem trước rồi mới tải.
- Lịch sử (tùy chọn): lịch sử trên máy theo mục 17; lịch sử máy chủ chỉ khi
  `canShowServerHistory` trả `true` (mục 16).

Checklist nghiệm thu đầy đủ ở mục 14.

## 0. Thay đổi gần đây

### 0.0 UI static tại `/` hỗ trợ đủ 5 cipher (`2026-09-28`)

UI đi kèm backend không còn là Caesar-only: có bộ chọn 5 cipher, ô khóa theo từng
cipher (Affine có hai ô `a`/`b`), cảnh báo Playfair, lịch sử trên trình duyệt (mục 17)
và tab lịch sử máy chủ (mục 16). UI chỉ dùng API công khai trong tài liệu này, nên là
ví dụ chạy được của contract: mở `http://localhost:8080/` khi chạy docker-compose.
FE riêng không phải đổi gì vì thay đổi này.

### 0.1 Khóa lịch sử server, retention 30 ngày, lịch sử trên trình duyệt (`2026-09-28`)

Project không có đăng nhập, nên:

- `GET /api/history` **mặc định tắt**. Khi tắt, endpoint trả HTTP 404 với message
  "Lịch sử không được bật trên máy chủ này.". Môi trường dev (`.env.example`) bật
  sẵn; môi trường dùng chung hoặc public sẽ tắt.
- `GET /api/health` có thêm `result.history`: `"enabled"` hoặc `"disabled"`.
- Lịch sử server chỉ giữ 30 ngày.
- Lịch sử **cá nhân** của người dùng (xem lại input/kết quả của chính họ) do FE lưu
  trên trình duyệt, không gửi lên server (mục 17).

**FE cần làm:**

1. Chỉ hiện màn hình lịch sử server khi health trả `history: "enabled"` và
   `database: "ok"`; xử lý thêm 404 từ `/api/history` (mục 16.3).
2. Làm lịch sử cá nhân trên trình duyệt theo mục 17 nếu cần tính năng "xem lại".

### 0.2 PostgreSQL, health và lịch sử thao tác (`2026-09-28`)

**Endpoint mới:** `GET /api/health` và `GET /api/history`. 15 route cipher giữ
nguyên request, response, status và message.

**Hành vi mới:**

- Backend có thể chạy kèm PostgreSQL. Khi có DB, mỗi request cipher (kể cả request
  lỗi) được ghi lại dưới dạng metadata: cipher, operation, text/file, độ dài, status,
  thời gian xử lý. Không lưu text, key, tên file, nội dung file hay kết quả.
- Khi chạy bằng docker-compose, backend ở `http://localhost:8080`. Khi chạy bằng
  `uv run uvicorn` mặc định vẫn là `http://localhost:8000`.

**FE cần làm:**

1. Trỏ dev proxy `/api` tới đúng cổng backend đang chạy (mục 2 và 16.1).
2. Nếu làm màn hình lịch sử: gọi `GET /api/health` để biết có DB không, rồi dùng
   `GET /api/history` theo contract ở mục 16.
3. Không thay đổi gì ở luồng encrypt/decrypt.

### 0.3 Playfair decrypt bỏ filler cuối (`2026-09-28`)

**Endpoint bị ảnh hưởng:** `POST /api/playfair/decrypt` và `POST /api/playfair/file`
với `action=decrypt` (cả `response_mode=content` lẫn `file`). Encrypt, request
shape, status code, message lỗi và filename **không đổi**.

**Hành vi mới:** sau khi giải mã, backend bỏ đúng **một** filler ở cuối kết quả:

- kết quả kết thúc bằng `XQ` → bỏ `Q`;
- ngược lại, kết quả kết thúc bằng `X` → bỏ `X`;
- filler giữa chuỗi (cặp chữ lặp) vẫn giữ nguyên.

| Ciphertext (key `PLAYFAIR EXAMPLE`) | Trước | Sau |
|---|---|---|
| `PDGW` (từ `ABX`) | `ABXQ` | `ABX` |
| `BMODZBXDNAGE` (từ `HIDE THE GOLD`) | `HIDETHEGOLDX` | `HIDETHEGOLD` |
| `GWGW` (từ `XX`) | `XQXQ` | `XQX` |
| `BMODZBXDNABEKUDMUIXMMOUVIF` | `HIDETHEGOLDINTHETREXESTUMP` | không đổi |
| Encrypt + decrypt `BALLOON` | `BALXLOON` | không đổi (filler giữa chuỗi) |

**Giới hạn đã chấp nhận:** ciphertext không phân biệt được filler với chữ thật,
nên plaintext có số chữ chẵn kết thúc bằng `X` sẽ mất `X` cuối (`AX → A`).

**FE cần làm:**

1. Hiển thị nguyên `result` từ server; **không** tự strip thêm X/Q ở client.
   Nếu FE đã từng tự bỏ X/Q cuối, xóa logic đó để tránh cắt hai lần.
2. Cập nhật mock/fixture/test: `GWGW → XQX`, `PDGW → ABX`,
   `BMODZBXDNAGE → HIDETHEGOLD`.
3. Cập nhật copy cảnh báo Playfair theo mục 11 (không còn ghi "giữ filler X/Q").

## 1. Nguyên tắc tích hợp

FE bắt buộc giữ nguyên:

- endpoint, method, content type, field và kiểu key theo từng cipher;
- response JSON đúng hai trường, status và thứ tự validation;
- kết quả do server tính; FE không tự tính result dùng trong production;
- file preview/download hai request, giới hạn 5 MiB, UTF-8, BOM và filename;
- xóa stale result khi cipher/mode/source/input/key/a/b thay đổi hoặc request lỗi;
- same-origin và URL `/api/...` tương đối.

FE được tự do chọn framework, component/state store, layout, CSS và cách tổ chức
API client. FE validation chỉ hỗ trợ UX; backend luôn là authority cuối cùng.

## 2. Runtime boundary và kiến trúc

```text
Browser / FE
  │
  │  same-origin: /api/{cipher}/...
  ▼
FastAPI :8000 (compose publish ra host :8080)
  ├── history recorder: ghi metadata sau response (chỉ khi có DB)
  ├── request guards: valid Content-Length > 64 MiB + multipart framing
  ├── HTTP adapters + validation precedence
  ├── file processing: .txt / 5 MiB / UTF-8 / BOM / filename
  ├── canonical error handlers
  └── pure core theo từng thuật toán
        ├── Caesar
        ├── Vigenère
        ├── Playfair
        ├── Affine
        └── Columnar Transposition
  │
  ├── JSON preview/error hoặc text/plain attachment
  │
  └── PostgreSQL (tùy chọn): bảng cipher_operations ← /api/history, /api/health
```

Backend phục vụ UI và API cùng origin. Trong container và khi chạy bằng uv, app
nghe cổng `8000`; docker-compose publish ra máy host ở cổng `8080`
(`APP_HOST_PORT`). FE gọi đường dẫn tương đối, ví dụ `/api/vigenere/encrypt`;
không ghi cứng backend host/port trong code.

Khi chạy FE dev server riêng, cấu hình dev proxy tới cổng backend đang chạy:

| Cách chạy backend | Proxy target |
|---|---|
| `docker compose up` (có PostgreSQL) | `http://localhost:8080` |
| `uv run uvicorn app.main:app --port 8000` | `http://localhost:8000` |

```text
/api/*  ──proxy──>  http://localhost:8080/api/*   (hoặc :8000 khi chạy bằng uv)
```

Ví dụ Vite, đọc target từ biến môi trường để mỗi người tự chọn:

```ts
// vite.config.ts
export default defineConfig({
  server: {
    proxy: { "/api": process.env.BACKEND_URL ?? "http://localhost:8080" },
  },
});
```

Backend không hứa hẹn CORS cho origin tách riêng. FE dev server khác origin phải
proxy `/api`; không khôi phục `API_BASE` ghi cứng trong code, mock toggle hoặc local
cipher service từ demo cũ.

Machine-readable surfaces của backend đang chạy (thay `8080` bằng `8000` nếu chạy
bằng uv):

- Swagger UI: <http://localhost:8080/docs>
- OpenAPI JSON: <http://localhost:8080/openapi.json>

OpenAPI hiện hữu có ba giới hạn biểu diễn mà FE codegen phải overlay thay vì biến
thành validation chặt hơn runtime:

- text request chỉ advertise `application/json`, trong khi decoder runtime còn nhận
  `application/*+json`;
- pattern OpenAPI của multipart Affine không biểu diễn bước trim whitespace ngoài
  trước grammar/giới hạn 32 ký tự;
- Caesar text và một số legacy schema không liệt kê đầy đủ error response hoặc
  `additionalProperties: false`, dù runtime/spec vẫn giữ exact response envelope.

Các giới hạn trên không tạo contract mới và không thu hẹp behavior runtime đã test.

Health check nằm ở `GET /api/health` (mục 16.2), không phải `/health`.

Không copy OpenAPI thành một YAML tĩnh khác trong FE vì bản sao sẽ dễ trôi lệch.
Backend không lưu input, key, file, result hay session. Khi có PostgreSQL, backend
chỉ lưu metadata thao tác, đọc qua `GET /api/history` (mục 16).

## 3. Danh mục 15 endpoint

| Cipher | Text encrypt | Text decrypt | File |
|---|---|---|---|
| Caesar | `POST /api/caesar/encrypt` | `POST /api/caesar/decrypt` | `POST /api/caesar/file` |
| Vigenère | `POST /api/vigenere/encrypt` | `POST /api/vigenere/decrypt` | `POST /api/vigenere/file` |
| Playfair | `POST /api/playfair/encrypt` | `POST /api/playfair/decrypt` | `POST /api/playfair/file` |
| Affine | `POST /api/affine/encrypt` | `POST /api/affine/decrypt` | `POST /api/affine/file` |
| Columnar | `POST /api/columnar/encrypt` | `POST /api/columnar/decrypt` | `POST /api/columnar/file` |

Text endpoints nhận `application/json` hoặc `application/*+json`. File endpoints
nhận `multipart/form-data` và có cùng hai response mode: `content` hoặc `file`.

Ngoài 15 route cipher, backend có hai route đọc: `GET /api/health` và
`GET /api/history` (mục 16).

Contract wire riêng của ba route Columnar:

| Endpoint | Request chính xác | HTTP 200 | Status lỗi được công bố |
|---|---|---|---|
| `POST /api/columnar/encrypt` | JSON object chỉ có `text:string`, `key:string` | `application/json`: `{"success":true,"result":"<ciphertext>"}` | `413`, `422`, `500` |
| `POST /api/columnar/decrypt` | JSON object chỉ có `text:string`, `key:string` | `application/json`: `{"success":true,"result":"<plaintext>"}` | `413`, `422`, `500` |
| `POST /api/columnar/file` | Multipart chỉ có required `file,key,action`; optional `response_mode` | mode `content`: JSON `{success,result}`; mode `file`: `text/plain; charset=utf-8` attachment | `413`, `415`, `422`, `500` |

Mọi lỗi của cả ba route dùng `application/json` và đúng
`{"success":false,"message":"<tiếng Việt>"}`. JSON text runtime còn nhận media type
vendor `application/*+json` (và parameter hợp lệ), dù OpenAPI chỉ quảng bá
`application/json`.

## 4. Thuật toán FE cần hiểu

Phần này chỉ đủ để FE giải thích UX và viết test. **Server là nơi duy nhất tạo kết
quả chính thức.** Visualization phía client không được thay thế response server.

### 4.1 Caesar

Với khóa `k`, backend chuẩn hóa bằng modulo 26:

```text
k' = ((k mod 26) + 26) mod 26
Encrypt: E(x) = (x + k') mod 26
Decrypt: D(x) = (x - k') mod 26
```

Chỉ ASCII `A-Z`/`a-z` thay đổi và giữ case. Số, dấu câu, whitespace, LF/CRLF,
chữ có dấu, emoji và Unicode khác giữ nguyên đúng vị trí.

```text
Hello World + key 3  → Khoor Zruog
Khoor Zruog + key 3 → Hello World
Xin chào! Zz + key 29 → Alq fkàr! Cc
```

Trong Caesar mode, FE phải giữ shift-map hai hàng 26 chữ cái theo accepted UI;
shift-map chỉ là visualization, không phải result production. Hiển thị thêm giá trị
key đã chuẩn hóa bên cạnh là tùy chọn.

### 4.2 Vigenère repeating-key

Key là chuỗi không rỗng chỉ gồm ASCII `A-Z`/`a-z`, được backend chuyển uppercase.
Key lặp lại; chỉ chữ cái ASCII trong input tiêu thụ một vị trí key. Case input được
giữ; whitespace, CRLF, số, dấu câu và mọi Unicode ngoài ASCII giữ nguyên và không
làm key tiến lên.

```text
Plaintext:  Attack at dawn!
Key stream: LEMONL EM ONLE
Encrypt:    Lxfopv ef rnhr!
Decrypt:    Attack at dawn!
```

Ví dụ key-position: `AéA` với key `BC` mã hóa thành `BéC`; `é` không tiêu thụ `C`.

### 4.3 Playfair 5×5

Playfair là luồng **normalize có mất dữ liệu**:

1. Keyword: uppercase ASCII → chỉ giữ `A-Z` → `J` thành `I` → loại trùng, giữ lần đầu.
2. Matrix 5×5 điền keyword rồi alphabet `A-Z` bỏ `J`, theo hàng.
3. Plaintext: uppercase ASCII, loại mọi non-letter, `J` thành `I`.
4. Chia digraph. Cặp lặp hoặc ký tự cuối lẻ dùng filler `X`; nếu ký tự đang xử lý
   là `X`, dùng fallback `Q` để tránh cặp `XX`.
5. Encrypt/decrypt theo rule cùng hàng, cùng cột hoặc hình chữ nhật.

Matrix cho key `PLAYFAIR EXAMPLE`:

```text
P L A Y F
I R E X M
B C D G H
K N O Q S
T U V W Z
```

Các vector bắt buộc:

| Operation | Input | Prepared/normalized | Result |
|---|---|---|---|
| Encrypt | `HIDE THE GOLD IN THE TREE STUMP` | `HIDETHEGOLDINTHETREXESTUMP` | `BMODZBXDNABEKUDMUIXMMOUVIF` |
| Decrypt | `BMODZBXDNABEKUDMUIXMMOUVIF` | — | `HIDETHEGOLDINTHETREXESTUMP` |
| Encrypt | `XX` | `XQXQ` | `GWGW` |
| Encrypt | `ABX` | `ABXQ` | `PDGW` |
| Decrypt | `PDGW` | — | `ABX` |
| Decrypt | `GWGW` | — | `XQX` |

Playfair output luôn uppercase ASCII. Decrypt giữ filler giữa chuỗi nhưng backend
tự bỏ đúng một filler cuối (`…XQ → …X`, `…X → …`); plaintext chẵn kết thúc bằng `X`
vì vậy mất `X` cuối (`AX → A`). Backend không phục hồi `J`, case, whitespace, dấu câu
hoặc Unicode đã bị loại. FE **không được tự strip thêm filler** và **không được
cố dựng lại formatting nguyên bản**. UI phải cảnh báo rõ rằng round-trip Playfair
chỉ trả prepared plaintext (đã bỏ filler cuối), không phải input ban đầu.

### 4.4 Affine modulo 26

Affine nhận hai integer `a`, `b`, normalize thành `a'`, `b'` modulo 26 và yêu cầu
`gcd(a',26)=1`. Các residue `a'` hợp lệ là
`1,3,5,7,9,11,15,17,19,21,23,25`; `b'` nhận `0..25`, nên có đúng 312 cặp
normalized. `(5,8)` chỉ là gợi ý/canonical vector, không phải default server.

```text
a' = ((a mod 26) + 26) mod 26
b' = ((b mod 26) + 26) mod 26
Encrypt: E(x) = (a' × x + b') mod 26
Decrypt: D(y) = inverse(a', 26) × (y - b') mod 26
HELLO → RCLLA → HELLO với (5,8)
```

Chỉ ASCII letter thay đổi và giữ case; Unicode, emoji, whitespace và CRLF giữ
nguyên. Affine round-trip là lossless với khóa hợp lệ. FE không được tự sửa `a`
không khả nghịch hoặc dùng phép tính client làm result chính thức.

### 4.5 Columnar Transposition

Backend ghi text theo hàng với `m` cột vật lý và đọc cột theo rank khóa. Không có
padding/normalization; mọi Unicode code point, CR/LF, whitespace, combining mark
và emoji được hoán vị như phần tử độc lập. Với JSON text, `U+FEFF` ở bất kỳ vị trí
nào cũng là dữ liệu; chỉ prefix byte UTF-8 BOM của file upload mới là metadata.
Encrypt/decrypt lossless khi dùng cùng khóa.

Key luôn là string, trim ở hai đầu chỉ sáu ASCII whitespace `SP`, `TAB`, `CR`,
`LF`, `FF`, `VT` và dài tối đa 2.048 Unicode code point sau trim:

- numeric permutation có đúng rank `1..m`, `2 ≤ m ≤ 256`, token phân cách bằng
  một dấu phẩy có thể kèm ASCII whitespace, hoặc một hay nhiều ASCII whitespace;
  có thể có đúng một cặp `{...}` ngoài cùng. Ví dụ `3 1 4 2`, `3,1,4,2` và
  `{3, 1 4,2}`;
- keyword khớp `[A-Za-z]{2,256}`, xếp rank case-insensitive và ổn định theo vị trí
  gốc khi trùng chữ. `BALLOON → [2,1,3,4,6,7,5]`.

Không gửi compact digits, leading zero, dấu, decimal/exponent, Unicode digit hoặc
keyword có space/non-ASCII. Sáu vector canonical (ký hiệu `\r`, `\n` là code point
CR/LF thực trong string):

| Input | Key | Encrypt result |
|---|---|---|
| `khoacongnghethongtin` | `3 6 2 1 5 4` | `agnonokntioetchghghn` |
| `ABCDE` | `3 1 4 2` | `BDAEC` |
| `MEET ME AT NOON` | `BALLOON` | `EAM NETT EO NMO` |
| `A B\r\nC!` | `2 1 3` | ` \nA\r!BC` |
| `😀A𝄞é` | `2 1 3` | `A😀é𝄞` |
| `XY` | `3 1 2 4` | `YX` |

Decrypt từng result bằng cùng key phải trả đúng input, kể cả hàng cuối thiếu cột,
whitespace/CRLF, non-BMP và trường hợp số cột lớn hơn số code point.

FE phải giữ nguyên `text` và key khi serialize: không gọi `trim()`, normalize
Unicode/newline, đổi case, collapse whitespace hoặc chuyển numeric-looking key
thành number. Nếu dựng visualization, lưu ý JavaScript indexing/`.length` dùng
UTF-16 code unit; backend hoán vị Unicode code point, không phải code unit hay
grapheme cluster. Result chính thức vẫn luôn là response server.

## 5. TypeScript contract dùng trực tiếp

Các type dưới đây mô tả consumer model. Caesar text dùng một integer token,
Affine dùng hai integer token; Vigenère, Playfair và Columnar dùng string key. Multipart
truyền mọi scalar dưới dạng string nhưng Affine dùng field `a`/`b`, không dùng `key`.

```ts
export type Cipher = "caesar" | "vigenere" | "playfair" | "affine" | "columnar";
export type StringKeyCipher = "vigenere" | "playfair" | "columnar";
export type Operation = "encrypt" | "decrypt";
export type ResponseMode = "content" | "file";

export interface SuccessResponse {
  success: true;
  result: string;
}

export interface ErrorResponse {
  success: false;
  message: string;
}

/** Chỉ dùng với giá trị đã kiểm tra Number.isSafeInteger(). */
export interface CaesarTextRequest {
  text: string;
  key: number;
}

export interface StringKeyTextRequest {
  text: string;
  key: string;
}

/** Chỉ dùng khi cả a và b đã kiểm tra Number.isSafeInteger(). */
export interface AffineTextRequest {
  text: string;
  a: number;
  b: number;
}

export interface CaesarTextInput {
  cipher: "caesar";
  text: string;
  /** Chuỗi integer người dùng nhập; serializer phát JSON number token. */
  key: string;
}

export interface StringKeyTextInput {
  cipher: StringKeyCipher;
  text: string;
  key: string;
}

export interface AffineTextInput {
  cipher: "affine";
  text: string;
  /** Raw UI state; serializer phát JSON integer token, không phát JSON string. */
  a: string;
  b: string;
}

export type TextInput = CaesarTextInput | StringKeyTextInput | AffineTextInput;

export interface KeyFileInput {
  cipher: Exclude<Cipher, "affine">;
  file: File;
  key: string;
  action: Operation;
}

export interface AffineFileInput {
  cipher: "affine";
  file: File;
  a: string;
  b: string;
  action: Operation;
}

export type FileInput = KeyFileInput | AffineFileInput;

export interface AttachmentResult {
  blob: Blob;
  filename: string;
}
```

Wire request Caesar/Affine text bắt buộc là JSON integer token, không phải JSON
string. Backend chấp nhận token tùy độ lớn; đây không phải contract string thay thế.
Vì JavaScript `number` có thể làm tròn, giữ raw UI state dạng string và ghép token
đã kiểm tra vào JSON mà không parse qua `number`. Chỉ dùng `CaesarTextRequest` hoặc
`AffineTextRequest` với `Number.isSafeInteger(...)`; không gọi `JSON.stringify()`
trực tiếp trên `bigint`. `StringKeyTextRequest` có thể `JSON.stringify()` trực tiếp.

JSON integer **trên wire** có syntax `-?(0|[1-9][0-9]*)`: không có dấu `+`,
decimal, exponent, leading zero hoặc whitespace trong token. Raw state của control
numeric vẫn là string để giữ precision và accepted UI hiện tại vẫn cho phép outer
whitespace/dấu `+`. Helper bên dưới trim rồi canonicalize riêng token wire bằng
`BigInt`; nó không sửa raw state đang hiển thị và không tạo alternate string contract.

## 6. JSON response và xử lý lỗi

Mọi success dùng đúng HTTP `200`. Success JSON luôn đúng hai trường:

```json
{"success":true,"result":"Khoor Zruog"}
```

JSON error luôn đúng hai trường, kể cả request `response_mode=file`:

```json
{"success":false,"message":"Khóa phải là số nguyên."}
```

Không có machine `code`, `detail`, field errors, `normalizedInput`, matrix hoặc
metadata bổ sung. FE phải hiển thị `message` tiếng Việt hợp lệ do server trả về,
nhưng **không dùng nội dung message làm stable identifier hoặc nhánh business**.
Để quản lý UI, dùng request context (cipher/field/action) và HTTP status; message
chỉ dành cho người dùng.

Helper TypeScript framework-neutral:

```ts
class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

function isErrorResponse(value: unknown): value is ErrorResponse {
  if (typeof value !== "object" || value === null) return false;
  const body = value as Record<string, unknown>;
  const keys = Object.keys(body);
  return keys.length === 2
    && keys.includes("success")
    && keys.includes("message")
    && body.success === false
    && typeof body.message === "string";
}

async function readJsonSuccess(response: Response): Promise<SuccessResponse> {
  const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";
  if (!contentType.includes("application/json")) {
    throw new ApiError("Đã xảy ra lỗi hệ thống.", response.status);
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new ApiError("Đã xảy ra lỗi hệ thống.", response.status);
  }

  if (response.status !== 200 || isErrorResponse(body)) {
    const message = isErrorResponse(body)
      ? body.message
      : "Đã xảy ra lỗi hệ thống.";
    throw new ApiError(message, response.status);
  }

  const success = body as Record<string, unknown>;
  const keys = Object.keys(success);
  if (
    keys.length !== 2
    || !keys.includes("success")
    || !keys.includes("result")
    || success.success !== true
    || typeof success.result !== "string"
  ) {
    throw new ApiError("Đã xảy ra lỗi hệ thống.", response.status);
  }
  return { success: true, result: success.result };
}
```

## 7. Text flow

### 7.1 Request shape và key

| Cipher | JSON body | Key hợp lệ |
|---|---|---|
| Caesar | `{"text":"...","key":3}` | JSON integer thật; âm, 0, >25 và integer rất lớn đều hợp lệ |
| Vigenère | `{"text":"...","key":"LEMON"}` | String không rỗng, toàn bộ khớp `[A-Za-z]+` |
| Playfair | `{"text":"...","key":"PLAYFAIR EXAMPLE"}` | String không rỗng và còn ít nhất một ASCII letter sau normalization |
| Affine | `{"text":"...","a":5,"b":8}` | Hai JSON integer thật; `a'` khả nghịch; không có default |
| Columnar | `{"text":"...","key":"3 1 4 2"}` | String numeric permutation hoặc keyword; không coercion |

Runtime endpoint text nhận `application/json` hoặc media type `application/*+json`;
OpenAPI hiện chỉ advertise `application/json`.
`text` phải là string khác rỗng. Whitespace-only hợp lệ với Caesar/Vigenère/Affine/Columnar;
Playfair đi tiếp qua normalization rồi bị từ chối vì không còn ASCII letter.
FE gửi nguyên `text`; không trim, normalize newline hoặc thay Unicode trước request.

Caesar từ chối boolean, float, numeric string, array và object làm key. Vigenère/
Playfair từ chối key JSON có giá trị nhưng không phải string bằng message
`Khóa phải là chuỗi.` FE gửi key string nguyên trạng: Vigenère không trim; Playfair
normalization là trách nhiệm của server và không phải lý do để FE rewrite key.

Affine yêu cầu chính xác ba member `text`, `a`, `b`; member lạ/trùng bị từ chối.
Numeric string, float, boolean, array/object cho `a`/`b` dùng lỗi integer tương ứng
và không coercion; thiếu hoặc `null` dùng lỗi thiếu khóa tương ứng. `(5,8)` không
được server tự điền. JSON integer tùy độ lớn được backend giảm modulo theo token chữ số.

Khác với Affine, JSON Caesar/Vigenère/Playfair giữ legacy behavior: member bổ sung
được bỏ qua và member trùng được JSON decoder lấy lần xuất hiện cuối. FE không nên
gửi hoặc dựa vào hai behavior này; request builder chuẩn chỉ phát mỗi field một lần.

Columnar giống Affine ở exact-shape gate: object phải có đúng `text,key`, không
field lạ/trùng. Key thiếu, `null` hoặc string rỗng sau ASCII trim trả `Thiếu khóa.`;
number/bool/array/object trả `Khóa phải là chuỗi.` và không được coercion. Decoder
từ chối mọi lone hoặc misordered JSON surrogate trong member name/text/key trước
field validation; escaped surrogate pair hợp lệ có parity với ký tự non-BMP literal.

### 7.2 Native fetch

```ts
function jsonIntegerToken(raw: string, missing: string, invalid: string): string {
  const value = raw.trim();
  if (value === "") throw new Error(missing);
  if (!/^[+-]?[0-9]+$/.test(value)) {
    throw new Error(invalid);
  }
  return BigInt(value).toString();
}

function caesarJsonBody(text: string, rawKey: string): string {
  const key = jsonIntegerToken(rawKey, "Thiếu khóa.", "Khóa phải là số nguyên.");
  return `{"text":${JSON.stringify(text)},"key":${key}}`;
}

function affineJsonBody(text: string, rawA: string, rawB: string): string {
  const a = jsonIntegerToken(rawA, "Thiếu khóa a.", "Khóa a phải là số nguyên.");
  const b = jsonIntegerToken(rawB, "Thiếu khóa b.", "Khóa b phải là số nguyên.");
  return `{"text":${JSON.stringify(text)},"a":${a},"b":${b}}`;
}

async function transformText(
  operation: Operation,
  input: TextInput,
): Promise<SuccessResponse> {
  const body = input.cipher === "caesar"
    ? caesarJsonBody(input.text, input.key)
    : input.cipher === "affine"
      ? affineJsonBody(input.text, input.a, input.b)
      : JSON.stringify({ text: input.text, key: input.key });

  const response = await fetch(`/api/${input.cipher}/${operation}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
  return readJsonSuccess(response);
}

const affineEncrypted = await transformText("encrypt", {
  cipher: "affine",
  text: "HELLO",
  a: "5",
  b: "8",
}); // result === "RCLLA"

const affineDecrypted = await transformText("decrypt", {
  cipher: "affine",
  text: affineEncrypted.result,
  a: "5",
  b: "8",
}); // result === "HELLO"

const columnarEncrypted = await transformText("encrypt", {
  cipher: "columnar",
  text: "ABCDE",
  key: "3 1 4 2",
}); // result === "BDAEC"
```

FE phải xóa result/analysis cũ trước khi gọi, khóa control khi request đang chạy,
và chỉ hiển thị/copy/download `result` nhận từ server.

Với **nguồn text**, FE được tạo file UTF-8 từ chính `result` server bằng `Blob`;
tên mặc định hiện hành là `ket-qua.encrypted.txt` hoặc `ket-qua.decrypted.txt`.
Quy tắc request attachment lần hai ở phần file chỉ áp dụng cho **nguồn file upload**.

### 7.3 curl

Các lệnh dưới đây dùng cổng `8000` (backend chạy bằng uv); khi chạy bằng
docker-compose, đổi thành `8080`.

```bash
curl -sS -X POST http://localhost:8000/api/caesar/encrypt \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello World","key":3}'
# {"success":true,"result":"Khoor Zruog"}

curl -sS -X POST http://localhost:8000/api/vigenere/encrypt \
  -H 'Content-Type: application/json' \
  -d '{"text":"Attack at dawn!","key":"LEMON"}'
# {"success":true,"result":"Lxfopv ef rnhr!"}

curl -sS -X POST http://localhost:8000/api/playfair/encrypt \
  -H 'Content-Type: application/json' \
  -d '{"text":"HIDE THE GOLD IN THE TREE STUMP","key":"PLAYFAIR EXAMPLE"}'
# {"success":true,"result":"BMODZBXDNABEKUDMUIXMMOUVIF"}

curl -sS -X POST http://localhost:8000/api/affine/encrypt \
  -H 'Content-Type: application/json' \
  -d '{"text":"HELLO","a":5,"b":8}'
# {"success":true,"result":"RCLLA"}

curl -sS -X POST http://localhost:8000/api/affine/decrypt \
  -H 'Content-Type: application/json' \
  -d '{"text":"RCLLA","a":5,"b":8}'
# {"success":true,"result":"HELLO"}

curl -sS -X POST http://localhost:8000/api/columnar/encrypt \
  -H 'Content-Type: application/json' \
  -d '{"text":"ABCDE","key":"3 1 4 2"}'
# {"success":true,"result":"BDAEC"}

# Representative text error: Vigenère key có khoảng trắng
curl -sS -i -X POST http://localhost:8000/api/vigenere/encrypt \
  -H 'Content-Type: application/json' \
  -d '{"text":"Attack","key":"LE MON"}'
# HTTP 422; {"success":false,"message":"Khóa Vigenère chỉ được chứa chữ cái A-Z hoặc a-z."}
```

Đổi `encrypt` thành `decrypt` và truyền ciphertext tương ứng để gọi năm endpoint
decrypt. Ví dụ Playfair decrypt trả normalized/prepared plaintext, không phục hồi input.

## 8. File flow

### 8.1 Multipart contract

Ba route Caesar/Vigenère/Playfair dùng:

| Field | Bắt buộc | Giá trị |
|---|---:|---|
| `file` | Có | File có filename kết thúc bằng `.txt`, không phân biệt hoa thường |
| `key` | Có | String trong multipart; policy phụ thuộc cipher |
| `action` | Có | Chính xác `encrypt` hoặc `decrypt` |
| `response_mode` | Không | `content` hoặc `file`; mặc định `content` |

Không tự đặt `Content-Type` khi gửi `FormData`; browser phải thêm multipart boundary.
`action` và `response_mode` phân biệt hoa thường.

Caesar multipart key được trim, phải khớp `[+-]?[0-9]+` và dài tối đa 32 ký tự.
Vigenère key phải khớp `[A-Za-z]+` mà không tự trim/sửa. Playfair key lọc ký tự
không phải ASCII letter và hợp lệ nếu normalization còn ít nhất một chữ cái.
FE vẫn append raw control value; không trim/rewrite text hoặc key trước khi gửi.

Ba route legacy không có exact-field gate: field bổ sung bị bỏ qua và nếu một field
single-value xuất hiện nhiều lần, binding hiện tại lấy lần xuất hiện cuối. Đây là
behavior tương thích cũ, không phải cơ chế override cho FE; request builder phải chỉ
gửi các field trong bảng và mỗi tên đúng một lần.

Route Affine dùng exact field set riêng:

| Field | Bắt buộc | Giá trị |
|---|---:|---|
| `file` | Có | File `.txt` UTF-8 theo contract chung |
| `a` | Có | Signed-decimal string sau trim, tối đa 32 ký tự, không default |
| `b` | Có | Signed-decimal string sau trim, tối đa 32 ký tự, không default |
| `action` | Có | Chính xác `encrypt` hoặc `decrypt` |
| `response_mode` | Không | `content` hoặc `file`; mặc định `content` |

Affine từ chối field lạ/trùng trước field validation. `a`/`b` phải khớp toàn bộ
`[+-]?[0-9]+`; độ dài 32 tính cả dấu sau trim. `a'` còn phải thỏa `gcd(a',26)=1`.
FE append nguyên raw `a`/`b`; việc trim để validate multipart là trách nhiệm server.
OpenAPI pattern nhìn như áp trực tiếp lên raw value và vì vậy không mô tả outer
whitespace đã được runtime chấp nhận; contract runtime/spec ở đoạn này là authority.

Route Columnar cũng dùng exact field set, gồm required `file,key,action` và optional
`response_mode`. `file` phải là upload part có filename; scalar `file` là invalid
body, còn upload part với `filename=""` đi đến lỗi extension `415`. MIME khai báo
không quyết định validity. `key` phải là scalar string theo §4.5; key upload part,
field lạ hoặc duplicate đều bị từ chối. OpenAPI mô tả key bằng prose cùng examples
`3 1 4 2`, `BALLOON`, không dùng `pattern`, `oneOf` hoặc raw `maxLength` gây hiểu sai.

### 8.2 Hai request bắt buộc

1. Preview: gửi file gốc với `response_mode=content`; nhận HTTP `200`,
   `application/json` và đúng JSON `{success,result}`.
2. Download: khi người dùng bấm tải, gửi lại file gốc bằng request thứ hai với
   `response_mode=file`; nhận HTTP `200`, `text/plain; charset=utf-8`, raw bytes và
   `Content-Disposition: attachment` server-owned.

FE không được đóng preview result vào Blob để giả làm official file download.
Preview không mang trạng thái BOM đầu vào và không phải authority cho filename.
Nếu request file lỗi ở bất kỳ mode nào, response vẫn là JSON `{success,message}`
và không có attachment.

### 8.3 Native fetch

```ts
function createFileForm(
  input: FileInput,
  responseMode: ResponseMode,
): FormData {
  const data = new FormData();
  data.append("file", input.file);
  if (input.cipher === "affine") {
    data.append("a", input.a);
    data.append("b", input.b);
  } else {
    data.append("key", input.key);
  }
  data.append("action", input.action);
  data.append("response_mode", responseMode);
  return data;
}

async function previewFile(input: FileInput): Promise<SuccessResponse> {
  const response = await fetch(`/api/${input.cipher}/file`, {
    method: "POST",
    body: createFileForm(input, "content"),
  });
  return readJsonSuccess(response);
}

function attachmentFilename(disposition: string): string | null {
  const utf8 = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8) return decodeURIComponent(utf8[1]);

  const quoted = disposition.match(/filename="((?:\\.|[^"])*)"/i);
  return quoted ? quoted[1].replace(/\\([\\"])/g, "$1") : null;
}

async function downloadFile(input: FileInput): Promise<AttachmentResult> {
  const response = await fetch(`/api/${input.cipher}/file`, {
    method: "POST",
    body: createFileForm(input, "file"),
  });
  const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";

  if (response.status !== 200 || contentType.includes("application/json")) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      // Dùng fallback bên dưới.
    }
    throw new ApiError(
      isErrorResponse(body) ? body.message : "Không thể tải kết quả. Vui lòng thử lại.",
      response.status,
    );
  }

  if (!contentType.startsWith("text/plain")) {
    throw new ApiError("Đã xảy ra lỗi hệ thống.", response.status);
  }
  const filename = attachmentFilename(
    response.headers.get("content-disposition") ?? "",
  );
  if (!filename) throw new ApiError("Đã xảy ra lỗi hệ thống.", response.status);

  return { blob: await response.blob(), filename };
}

const selected = document.querySelector<HTMLInputElement>("#file")?.files?.[0];
if (!selected) throw new Error("Thiếu file.");

const affineFileInput: AffineFileInput = {
  cipher: "affine",
  file: selected,
  a: "5",
  b: "8",
  action: "encrypt",
};

const preview = await previewFile(affineFileInput); // JSON result từ server
const attachment = await downloadFile(affineFileInput); // request server thứ hai
const objectUrl = URL.createObjectURL(attachment.blob);
const link = Object.assign(document.createElement("a"), {
  href: objectUrl,
  download: attachment.filename,
});
document.body.append(link);
link.click();
link.remove();
setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
```

Sau khi nhận `AttachmentResult`, FE tạo object URL, kích hoạt download bằng
`filename` từ server và gọi `URL.revokeObjectURL()` sau khi dùng.

### 8.4 curl

Các lệnh dưới đây dùng cổng `8000` (backend chạy bằng uv); khi chạy bằng
docker-compose, đổi thành `8080`.

```bash
# Caesar preview
curl -sS -X POST http://localhost:8000/api/caesar/file \
  -F 'file=@input.txt;type=text/plain' -F 'key=3' \
  -F 'action=encrypt' -F 'response_mode=content'

# Vigenère preview
curl -sS -X POST http://localhost:8000/api/vigenere/file \
  -F 'file=@input.txt;type=text/plain' -F 'key=LEMON' \
  -F 'action=encrypt' -F 'response_mode=content'

# Playfair preview
curl -sS -X POST http://localhost:8000/api/playfair/file \
  -F 'file=@input.txt;type=text/plain' -F 'key=PLAYFAIR EXAMPLE' \
  -F 'action=encrypt' -F 'response_mode=content'

# Affine preview
curl -sS -X POST http://localhost:8000/api/affine/file \
  -F 'file=@input.txt;type=text/plain' -F 'a=5' -F 'b=8' \
  -F 'action=encrypt' -F 'response_mode=content'

# Affine official attachment: request thứ hai, server quyết định filename
curl -sS -OJ -X POST http://localhost:8000/api/affine/file \
  -F 'file=@input.txt;type=text/plain' -F 'a=5' -F 'b=8' \
  -F 'action=encrypt' -F 'response_mode=file'

# Columnar preview
curl -sS -X POST http://localhost:8000/api/columnar/file \
  -F 'file=@input.txt;type=text/plain' -F 'key=BALLOON' \
  -F 'action=encrypt' -F 'response_mode=content'

# Columnar official attachment: gửi lại file gốc, dùng filename/BOM từ server
curl -sS -OJ -X POST http://localhost:8000/api/columnar/file \
  -F 'file=@input.txt;type=application/octet-stream' -F 'key=BALLOON' \
  -F 'action=encrypt' -F 'response_mode=file'

# Representative file error: lỗi vẫn là JSON dù yêu cầu attachment
curl -sS -i -X POST http://localhost:8000/api/caesar/file \
  -F 'file=@input.md;type=text/plain' -F 'key=3' \
  -F 'action=encrypt' -F 'response_mode=file'
# HTTP 415; {"success":false,"message":"Chỉ chấp nhận file .txt."}
```

### 8.5 Byte, encoding, BOM và filename

- Giới hạn chính xác: `5 MiB = 5 * 1024 * 1024 = 5.242.880 byte` raw content,
  tính cả ba byte BOM nếu có.
- Đúng `5.242.880` byte qua bước size; `5.242.881` byte trả HTTP `413`.
- Message cố ý dùng `File vượt quá dung lượng tối đa 5 MB.` dù phép đo là MiB.
- Chỉ chấp nhận UTF-8 thường hoặc UTF-8 có BOM. Invalid UTF-8 trả HTTP `415`.
- Content preview không chứa `U+FEFF` ở đầu result.
- Attachment giữ BOM nếu và chỉ nếu input có BOM.
- Backend không normalize newline; cipher lossless giữ nguyên LF/CRLF, còn Playfair
  chủ động loại format theo thuật toán.
- File `0` byte bị từ chối nhưng file BOM-only hợp lệ. Whitespace-only hợp lệ với
  Caesar/Vigenère/Affine/Columnar
  nhưng không hợp lệ với Playfair sau normalization.
- `.txt` kiểm tra không phân biệt hoa thường; `a.txt.exe` bị từ chối.

Filename do server tạo:

```text
note.txt       + encrypt → note.encrypted.txt
note.txt       + decrypt → note.decrypted.txt
bao.cao.TXT    + encrypt → bao.cao.encrypted.txt
```

Server bỏ path component, chỉ bỏ phần `.txt` cuối cùng, giữ các dấu chấm trước đó,
không thêm tên thuật toán và luôn dùng `.txt` thường cho output. FE lấy filename
từ `Content-Disposition` (`filename*` UTF-8 được ưu tiên), không tự dựng lại tên.

### 8.6 Nội dung file theo cipher

| Cipher | LF/CRLF, whitespace, số, dấu câu | Unicode ngoài ASCII | Case/output |
|---|---|---|---|
| Caesar | Giữ nguyên | Giữ nguyên | Chỉ ASCII letter đổi, giữ case |
| Vigenère | Giữ nguyên; không làm key tiến | Giữ nguyên; không làm key tiến | Chỉ ASCII letter đổi, giữ case |
| Playfair | Bị loại khi normalize | Bị loại | Uppercase ASCII, `J→I`, có thể có filler `X/Q` |
| Affine | Giữ nguyên | Giữ nguyên | Chỉ ASCII letter đổi, giữ case; round-trip lossless |
| Columnar | Hoán vị nguyên trạng | Hoán vị theo code point | Không đổi code point; round-trip lossless |

## 9. Validation, status và message

| Status | Trường hợp | Message chính xác |
|---:|---|---|
| `200` | Text/content mode thành công hoặc file mode trả attachment | Không có error message |
| `413` | File vượt 5 MiB hoặc file-route request có một `Content-Length` hợp lệ lớn hơn 64 MiB | `File vượt quá dung lượng tối đa 5 MB.` |
| `413` | Request text có một `Content-Length` decimal hợp lệ lớn hơn 64 MiB | `Yêu cầu vượt quá dung lượng cho phép.` |
| `415` | Filename không kết thúc `.txt` | `Chỉ chấp nhận file .txt.` |
| `415` | File không phải UTF-8 | `File phải sử dụng UTF-8.` |
| `422` | Sai media type, JSON/multipart không đọc được, body không phải object | `Dữ liệu gửi lên không hợp lệ.` |
| `422` | Text thiếu, null, rỗng hoặc sai kiểu | `Văn bản không được để trống.` |
| `422` | Key thiếu, null hoặc chuỗi rỗng | `Thiếu khóa.` |
| `422` | Caesar key có giá trị nhưng không phải integer | `Khóa phải là số nguyên.` |
| `422` | Affine JSON thiếu/null `a`; multipart thiếu/null/trim-rỗng `a` | `Thiếu khóa a.` |
| `422` | Affine JSON `a` sai kiểu; multipart `a` sai grammar/length | `Khóa a phải là số nguyên.` |
| `422` | Affine `a'` không khả nghịch | `Khóa a phải nguyên tố cùng nhau với 26.` |
| `422` | Affine JSON thiếu/null `b`; multipart thiếu/null/trim-rỗng `b` | `Thiếu khóa b.` |
| `422` | Affine JSON `b` sai kiểu; multipart `b` sai grammar/length | `Khóa b phải là số nguyên.` |
| `422` | Vigenère/Playfair/Columnar key có giá trị nhưng không phải string | `Khóa phải là chuỗi.` |
| `422` | Vigenère key có ký tự ngoài ASCII letter | `Khóa Vigenère chỉ được chứa chữ cái A-Z hoặc a-z.` |
| `422` | Playfair key normalize không còn ASCII letter | `Khóa Playfair phải chứa ít nhất một chữ cái A-Z hoặc a-z.` |
| `422` | Playfair text normalize không còn ASCII letter | `Văn bản Playfair phải chứa ít nhất một chữ cái A-Z hoặc a-z.` |
| `422` | Playfair ciphertext có số letter lẻ | `Bản mã Playfair phải chứa số lượng chữ cái chẵn.` |
| `422` | Playfair ciphertext có digraph hai letter giống nhau | `Bản mã Playfair không được chứa cặp hai chữ cái giống nhau.` |
| `422` | Columnar key string sai length/grammar/permutation/bounds | `Khóa Columnar phải là hoán vị 1..m hoặc từ khóa gồm 2 đến 256 chữ cái A-Z.` |
| `422` | Thiếu file | `Thiếu file.` |
| `422` | File 0 byte | `File không được để trống.` |
| `422` | Action thiếu/sai | `Action phải là encrypt hoặc decrypt.` |
| `422` | Response mode sai | `Response mode phải là content hoặc file.` |
| `500` | Lỗi đọc file | `Không thể đọc file.` |
| `500` | Lỗi hệ thống khác | `Đã xảy ra lỗi hệ thống.` |

Thứ tự lỗi text Caesar/Vigenère/Playfair sau request-size guard:

```text
JSON object đọc được
→ text presence/type/non-empty
→ key presence
→ key type
→ key policy của cipher
→ Playfair normalized text/ciphertext validation
```

Thứ tự lỗi text Affine:

```text
media type / JSON syntax / object / exact member set
→ text presence/type/non-empty
→ a presence/type/normalize/gcd
→ b presence/type/normalize
→ transform
```

Thứ tự lỗi text Columnar:

```text
media type / JSON syntax / object / exact member set / duplicate / surrogate
→ text presence/type/non-empty
→ key missing/ASCII-empty → key wire type → key content
→ transform
```

Thứ tự lỗi file Caesar/Vigenère/Playfair sau request-size/multipart guard:

```text
multipart đọc được
→ file presence
→ key presence
→ action presence
→ key format/policy
→ action value
→ response_mode
→ extension
→ 5 MiB
→ 0 byte
→ UTF-8
→ Playfair normalized content/ciphertext validation
```

Thứ tự lỗi file Affine:

```text
multipart framing / exact field set / duplicate
→ file presence/type
→ a presence/grammar/length/normalize/gcd
→ b presence/grammar/length/normalize
→ action
→ response_mode
→ extension → 5 MiB → 0 byte → UTF-8 → transform
```

Thứ tự lỗi file Columnar:

```text
multipart framing / exact field set / duplicate
→ file presence/type
→ key missing/ASCII-empty → key wire type → key content
→ action → response_mode
→ extension → 5 MiB → 0 byte → UTF-8 → transform
```

Backend dừng ở lỗi đầu tiên. FE không nên tự suy diễn rằng lỗi file/encoding đã
qua chỉ vì request bị từ chối sớm ở key.

Trần hạ tầng 64 MiB chỉ từ chối sớm khi request có **đúng một** header
`Content-Length` decimal hợp lệ và giá trị vượt trần. Header thiếu, trùng hoặc sai
định dạng được chuyển tiếp để tầng sau xử lý; điều này không thay đổi giới hạn file
nghiệp vụ 5 MiB được đếm từ bytes nội dung upload.

## 10. FE validation và phân chia trách nhiệm

| FE chịu trách nhiệm | Backend chịu trách nhiệm |
|---|---|
| Kiểm tra sơ bộ để bật/tắt action | Kiểm tra wire type, policy và precedence thật |
| Giữ raw key/a/b phù hợp cipher và tránh mất precision | Normalize/validate khóa và chạy core |
| Hiển thị cảnh báo Playfair lossy | Quyết định prepared plaintext và filler |
| Kiểm tra sơ bộ extension, `File.size`, 0 byte | Đếm byte, UTF-8, BOM và filename attachment |
| Loading, stale-result clearing, focus, live region | Status và exact response envelope/message |
| Visualization minh họa | Result production-authoritative |
| Dùng attachment/filename server trả | Quyết định bytes, BOM và official filename |

FE không được:

- coi client validation là bằng chứng request chắc chắn hợp lệ;
- tính Caesar/Vigenère/Playfair/Affine/Columnar client-side để thay result server;
- ép `a`/`b` Affine ngoài safe range qua JavaScript `number`;
- trim/sửa `text`, string key hoặc raw multipart key rồi gửi giá trị khác người dùng
  nhập; riêng numeric JSON control giữ raw state nhưng được canonicalize thành true
  JSON integer token ở bước serialize;
- tự xóa thêm filler Playfair hoặc phục hồi formatting bằng heuristic;
- dùng preview Blob làm official download cho nguồn file;
- branch business logic theo chuỗi message tiếng Việt.

## 11. UI state và transition

State tối thiểu:

```text
cipher     = caesar | vigenere | playfair | affine | columnar
mode       = encrypt | decrypt
source     = text | file
text/file  = input hiện tại
key/a/b    = raw input theo cipher
result     = null | server result
loading    = boolean
error      = null | user-facing message
view       = result | analysis
```

| Event | State bắt buộc | UX |
|---|---|---|
| Mở trang | `cipher=caesar`, `mode=encrypt`, `source=text`, `result=null`, `loading=false` | Action disabled tới khi hợp lệ |
| Đổi cipher | Xóa result/analysis/error; validate lại key/input | Đổi key hint và Playfair warning |
| Đổi encrypt/decrypt | Giữ input/key/a/b nếu phù hợp; xóa stale result/error | Đổi label plaintext/ciphertext |
| Đổi text/file | Bắt buộc giữ draft riêng của text và file; xóa result/error | Hiện panel nguồn mới |
| Sửa text, file, key, `a` hoặc `b` | Xóa result/analysis/error | Validate lại ngay |
| Submit preview/text | Xóa result; `loading=true` | Khóa control và chặn submit lặp |
| Success | Lưu đúng server result; xóa error | Mở copy/download |
| API/network failure | `result=null`, xóa analysis; lưu fallback/message | Mở khóa để retry |
| Download click | Request file mode lần hai | Không dùng preview Blob |
| Download failure | Xóa trạng thái success cũ | Hiện lỗi, không kích hoạt download |
| Clear output | Chỉ xóa result/analysis | Giữ input/key/a/b |
| Reset | Xóa toàn bộ state/draft/result/error; đưa status về neutral và view về result | Quay lại `caesar` + `encrypt` + `text` |

Playfair phải có cảnh báo luôn nhìn thấy trước submit hoặc cạnh result:

> Playfair chuẩn hóa thành chữ hoa ASCII, gộp J/I, loại định dạng; khi giải mã giữ
> filler X/Q giữa chuỗi và bỏ filler cuối; kết quả không khôi phục nguyên văn đầu vào.

Trong loading, khóa mọi đường thay đổi/gửi lặp: click, keyboard shortcut,
Enter/Space trên drop zone và file drop. Status/error/result thay đổi phải được công
bố qua live region; lỗi không chỉ biểu diễn bằng màu; mọi control dùng được bằng
bàn phím và có focus indicator.

Các invariant UI Week 1 tiếp tục bắt buộc khi mở rộng thêm cipher:

- Có ba nhóm status độc lập cho input, key (`key` hoặc cặp `a`/`b`) và output;
  mỗi status có neutral/valid/error bằng text và dấu hiệu không chỉ dựa vào màu.
- Result read-only có hai tab **Văn bản** và **Phân tích**; mặc định là Văn bản.
  Analysis chỉ diễn giải server result/input, không tự tạo ciphertext/plaintext.
- Copy/Clear output và Download bị vô hiệu khi chưa có result. Clear output giữ
  input/key/a/b; Reset toàn trang có semantics riêng như bảng trên.
- Notice success/error đóng được và tự ẩn khi cipher/mode/source/input/key/a/b thay đổi.
- File panel hỗ trợ picker lẫn drag/drop, hiển thị tên, kích thước nhị phân, preview,
  **Đổi file** và **Gỡ file**.
- Caesar mode giữ **Tạo ví dụ** (`Hello World`, key `3`) và shift-map hai hàng 26
  chữ cái. Shift-map chỉ là visualization client-side; production result vẫn từ server.
- Tabs/selectors/drop zone có semantics/ARIA phù hợp; copy failure có thông báo
  tiếng Việt và không làm UI kẹt.

UI thuộc phạm vi FE; BE không giữ OpenSpec cho UI. Các invariant trên chỉ là
khuyến nghị để FE bám theo contract API.

## 12. Migration checklist từ 12 lên 15 route (chỉ cho FE cũ)

- [ ] Mở endpoint allowlist từ 12 lên đúng 15 route trong bảng; thêm selector
  `columnar`, không tạo route generalized/versioned.
- [ ] Route text/file dựa trên cipher đang chọn và luôn là URL `/api/...` tương đối.
- [ ] Mở discriminated request types/builders: Caesar integer key,
  Vigenère/Playfair/Columnar string key, Affine hai key `a`/`b`.
- [ ] Thêm state/hint/validation riêng cho raw `a` và `b`; cả hai bắt buộc, `(5,8)`
  chỉ là gợi ý, và FE không tự sửa `a` không khả nghịch.
- [ ] Giữ input key dạng raw string trong UI; serialize Caesar text thành JSON integer token.
- [ ] Serialize Affine text thành hai JSON integer token không mất precision, không
  đổi sang numeric string và không đi qua JavaScript `number` khi ngoài safe range.
- [ ] Affine multipart gửi exact field `file,a,b,action,response_mode`; không gửi `key`.
- [ ] Dùng string key nguyên trạng cho Vigenère/Playfair/Columnar; hint Columnar
  phải giải thích numeric permutation/keyword, ASCII-only trim và bounds 2..256.
- [ ] Columnar text gửi exact JSON `text,key`; Columnar multipart gửi exact
  `file,key,action,response_mode`; không gửi key kiểu number hoặc upload part.
- [ ] Thêm cảnh báo Playfair lossy, uppercase, `J→I` và filler `X`/`Q` giữa chuỗi.
- [ ] Xóa stale result khi cipher/mode/source/input/key/a/b thay đổi hoặc request thất bại.
- [ ] Preview file dùng `response_mode=content`; download dùng request thứ hai mode `file`.
- [ ] Dùng server attachment và filename; không tạo official file từ preview.
- [ ] Error parser chỉ nhận `{success:false,message}`; không chờ `code`, `details`
  hoặc metadata và không branch theo nội dung message.
- [ ] Cập nhật OpenAPI snapshot/generated types nếu FE thực sự dùng chúng; thêm
  contract test đếm đúng 15 route và test Columnar text/preview/download/error.
- [ ] Gỡ mock, `USE_MOCK`, local cipher result và `API_BASE` ghi cứng trong code.
- [ ] Dev server proxy `/api` tới backend (`8080` khi chạy compose, `8000` khi chạy uv);
  không yêu cầu CORS.
- [ ] Health check dùng `GET /api/health`, không dùng `/health`.

Checklist này mô tả công việc của FE riêng. UI static đi kèm backend đã làm theo
checklist này trong change `update-static-ui-all-ciphers`.

## 13. Hành vi demo cũ không được sao chép

[`Caesar_Cipher_Tool_Demo.html`](../Caesar_Cipher_Tool_Demo.html) chỉ là reference UI cũ.
Không sao chép:

- giới hạn `1 MB` thay vì 5 MiB;
- `_encrypted.txt`/`_decrypted.txt` thay vì `.encrypted.txt`/`.decrypted.txt`;
- mock API, `USE_MOCK` hoặc local Caesar service;
- `API_BASE=http://localhost:8080` hay backend URL hard-coded;
- CORS như một yêu cầu mặc định cho dev;
- bỏ `response_mode` hoặc tải file từ preview Blob;
- message/label tiếng Anh hoặc error shape có `code`;
- bất kỳ client-generated production result nào.

`affine-cipher.html` là reference ngoài repository chỉ xác nhận công thức, residue hợp lệ
và vector `HELLO → RCLLA`. Các điểm cố ý khác production là default UI `(5,8)`,
input `type=number`/JavaScript `Number`, validation message động và kết quả tính
client-side: không điểm nào là wire contract hay result authority. Runtime/OpenSpec
hiện tại luôn thắng demo.

## 14. Acceptance checklist

- [ ] Cả 15 endpoint được chọn đúng theo cipher/source/operation.
- [ ] Caesar vector `Hello World`, key `3` cho `Khoor Zruog` và decrypt đúng chiều ngược lại.
- [ ] Vigenère vector `Attack at dawn!`/`LEMON` cho `Lxfopv ef rnhr!` và decrypt đúng.
- [ ] Playfair canonical vector cho `BMODZBXDNABEKUDMUIXMMOUVIF` và decrypt trả prepared text đã bỏ filler cuối.
- [ ] Playfair `XX→XQXQ→GWGW`, `ABX→ABXQ→PDGW`, `PDGW→ABX`, `GWGW→XQX` đều đúng.
- [ ] Affine `HELLO→RCLLA→HELLO` với `(5,8)` và mixed/Unicode/CRLF giữ đúng contract.
- [ ] Affine có đúng 12 residue `a'`, 26 residue `b'` và 312 cặp normalized hợp lệ.
- [ ] Columnar `ABCDE → BDAEC → ABCDE` với `3 1 4 2`, keyword `BALLOON` và
  Unicode/CRLF/uneven/`m>n` round-trip đúng contract, không padding/normalize.
- [ ] FE không tự strip thêm filler và hiển thị cảnh báo Playfair không lossless.
- [ ] Caesar text gửi một JSON integer; Affine gửi hai integer `a,b`;
  Vigenère/Playfair/Columnar gửi string key.
- [ ] Affine integer ngoài JS safe range không bị chuyển qua `number` hoặc làm tròn.
- [ ] FE không trim/rewrite text, string key hoặc multipart key trước khi gửi; raw
  numeric JSON state chỉ được canonicalize thành number token ở serializer.
- [ ] Whitespace-only: Caesar/Vigenère/Affine/Columnar thành công, Playfair trả normalized-empty 422.
- [ ] Vigenère giữ Unicode/CRLF và không làm key tiến; Caesar giữ non-ASCII/CRLF.
- [ ] Playfair loại Unicode/CRLF/format và trả uppercase ASCII.
- [ ] Validation hiển thị server message nhưng không dùng message làm identifier.
- [ ] Error envelope chỉ có `success,message`; success JSON chỉ có `success,result`.
- [ ] Preview và download file là hai request; lỗi file mode vẫn được đọc như JSON.
- [ ] File đúng `5.242.880` byte qua size; thêm một byte trả 413.
- [ ] Invalid UTF-8 trả 415; `.TXT` hợp lệ; `.txt.exe` bị từ chối.
- [ ] Content preview bỏ BOM; attachment giữ BOM đúng theo input.
- [ ] Filename dùng `.encrypted.txt`/`.decrypted.txt`, kể cả tên nhiều dấu chấm.
- [ ] Affine multipart `a`/`b` được server trim/validate grammar/32 ký tự; exact
  fields, duplicate/additional-field rejection và precedence đúng.
- [ ] Columnar exact JSON/multipart, string-key grammar/2.048 limit, surrogate
  handling, key precedence và canonical invalid-key message đều đúng.
- [ ] Legacy request builder không dựa vào behavior bỏ qua field lạ/lấy duplicate cuối.
- [ ] Cipher/mode/source/input/key/a/b thay đổi hoặc request lỗi đều xóa stale result.
- [ ] Loading chặn submit/drop lặp; UI có keyboard, focus và live-region behavior.
- [ ] Caesar regression: ba endpoint và integer-key contract cũ vẫn hoạt động như trước.
- [ ] FE dùng same-origin `/api`; local dev dùng proxy, không mock/CORS/API base cũ.
- [ ] `/docs` và `/openapi.json` được dùng để đối chiếu runtime contract; health check
  dùng `GET /api/health`.
- [ ] Nếu có màn hình lịch sử server: chỉ hiện khi health có `history: "enabled"` và
  `database: "ok"`; phân trang bằng `nextCursor`; xử lý lỗi 404/422/503 theo mục 16.3.
- [ ] Lịch sử cá nhân (nếu có) lưu trên trình duyệt theo mục 17: tối đa 50 mục, có nút
  xóa, có công tắc tắt lưu, mọi truy cập storage bọc `try/catch`.

## 15. Source precedence và bảo trì

Thứ tự áp dụng:

1. Primary authority, theo thứ tự nội bộ: accepted requirements trong
   [OpenSpec UI năm cipher](../openspec/changes/archive/2026-09-28-update-static-ui-all-ciphers/),
   [OpenSpec khóa lịch sử và retention](../openspec/changes/archive/2026-09-28-add-history-access-retention/),
   [OpenSpec PostgreSQL và lịch sử](../openspec/changes/archive/2026-09-28-add-postgres-persistence/),
   [OpenSpec Columnar](../openspec/changes/archive/2026-09-28-add-columnar-transposition-cipher/),
   [OpenSpec Affine](../openspec/changes/archive/2026-09-28-add-affine-cipher/),
   [completed OpenSpec Playfair/Vigenère](../openspec/changes/archive/2026-09-28-add-playfair-vigenere-ciphers/)
   và [completed OpenSpec Caesar Week 1](../openspec/changes/archive/2026-09-28-caesar-cipher-week1-mvp/);
   sau đó current implementation/tests cho observed behavior; cuối cùng runtime
   `/openapi.json` là machine-readable projection. Known OpenAPI under-description
   ở §2 không được dùng để thu hẹp behavior đã được spec/runtime test chấp nhận.
2. [README hiện tại](../README.md) và consumer guide này; nếu lệch mục 1 thì guide
   phải được sửa, không được biến wording cũ thành contract mới.
3. `affine-cipher.html` (reference ngoài repository) và demo/mock cũ chỉ để tham khảo,
   không có quyền ghi đè production behavior. Source DOCX và
   [bản scope Caesar bảo tồn](../docs/reference/be-scope-v1.0.md) chỉ dùng truy vết.

Nếu các nguồn trong primary tier mâu thuẫn ngoài các under-description đã ghi rõ,
đó là defect cần reconcile với owner/spec, không phải quyền để FE tự chọn behavior
hoặc để guide âm thầm redesign contract.

Các implementation link chính để audit contract là
[`schemas.py`](../app/api/schemas.py),
[`messages.py`](../app/errors/messages.py),
[`file_processing.py`](../app/services/file_processing.py),
[`routes_affine_text.py`](../app/api/routes_affine_text.py) và
[`routes_affine_file.py`](../app/api/routes_affine_file.py),
[`routes_columnar_text.py`](../app/api/routes_columnar_text.py) và
[`routes_columnar_file.py`](../app/api/routes_columnar_file.py),
[`routes_health.py`](../app/api/routes_health.py) và
[`routes_history.py`](../app/api/routes_history.py). File mẫu
[`examples/cipher-api.ts`](examples/cipher-api.ts) phải được cập nhật cùng tài liệu
khi contract đổi.

Guide không lặp toàn bộ ma trận scenario hoặc decision history của OpenSpec. Khi
API/behavior thay đổi, cập nhật OpenSpec trước, rồi cập nhật guide này trong cùng
change. Không thêm `/v1`, endpoint, field hoặc behavior mới chỉ bằng cách sửa tài liệu.

## 16. Health và lịch sử thao tác

Backend có thể chạy kèm PostgreSQL. Khi bật, mỗi request tới 15 route cipher được
ghi lại dưới dạng **metadata**. Backend không lưu text, key, tên file, nội dung file
hay kết quả. Contract của 15 route cipher không đổi: FE không phải sửa gì ở luồng
encrypt/decrypt.

### 16.1 Chạy backend có PostgreSQL khi dev FE

Cần Docker. Trong thư mục repo backend:

```bash
cp .env.example .env          # lần đầu; đổi POSTGRES_PASSWORD và DATABASE_URL cho khớp
docker compose up -d --build  # db + migrate + app
curl -s http://localhost:8080/api/health
# {"success":true,"result":{"app":"ok","database":"ok"}}
```

- Backend ở `http://localhost:8080`; proxy `/api` của FE dev server về đây.
- Dữ liệu lịch sử được giữ qua các lần khởi động lại. `docker compose down -v` xóa sạch
  dữ liệu khi cần làm lại từ đầu.
- Muốn thử màn hình lịch sử khi không có DB: chạy backend bằng
  `uv run uvicorn app.main:app --port 8000` mà không đặt `DATABASE_URL`; khi đó
  `database` là `disabled` và `/api/history` trả 503.
- Tạo dữ liệu mẫu: gọi vài request encrypt/decrypt bất kỳ qua UI hoặc `curl`, mỗi
  request sinh một dòng lịch sử.

### 16.2 `GET /api/health`

```json
{"success": true, "result": {"app": "ok", "database": "ok", "history": "enabled"}}
```

| `database` | HTTP | Ý nghĩa |
|---|---|---|
| `ok` | 200 | DB trả lời `SELECT 1` trong 1 giây |
| `disabled` | 200 | Backend chạy không có DB; không ghi lịch sử |
| `unavailable` | 503 | Đã cấu hình DB nhưng không kết nối được |

| `history` | Ý nghĩa |
|---|---|
| `enabled` | `GET /api/history` được phép gọi |
| `disabled` | `GET /api/history` trả 404; đây là mặc định trên môi trường dùng chung |

`history` không ảnh hưởng HTTP status của health. Chỉ hiện màn hình lịch sử server
khi `history` là `enabled` và `database` là `ok`. Cipher vẫn hoạt động trong mọi
trạng thái.

### 16.3 `GET /api/history`

Query (tất cả tùy chọn):

| Tham số | Giá trị | Mặc định |
|---|---|---|
| `limit` | số nguyên `1`–`100` | `20` |
| `cursor` | chuỗi opaque lấy từ `nextCursor` của trang trước | trang đầu |
| `cipher` | `caesar`, `vigenere`, `playfair`, `affine`, `columnar` | tất cả |
| `operation` | `encrypt`, `decrypt` | tất cả |

Kết quả sắp mới nhất trước. `nextCursor` là `null` ở trang cuối. FE phải coi cursor
là chuỗi opaque, gửi lại nguyên văn và không tự dựng.

```json
{
  "success": true,
  "result": {
    "items": [
      {
        "id": 2,
        "createdAt": "2026-09-28T03:20:02.741246Z",
        "cipher": "playfair",
        "operation": "decrypt",
        "source": "text",
        "responseMode": null,
        "inputLength": 4,
        "outputLength": 3,
        "httpStatus": 200,
        "succeeded": true,
        "durationMs": 4
      }
    ],
    "nextCursor": null
  }
}
```

Ý nghĩa các trường:

- `source`: `text` cho route JSON, `file` cho route multipart.
- `operation`: `null` khi request lỗi trước lúc backend đọc được `action` của file.
- `responseMode`: `content` hoặc `file` cho route file; luôn `null` cho route text.
- `inputLength`/`outputLength`: số Unicode code point với text, số byte UTF-8 với
  file; `null` khi request lỗi trước lúc đo được.
- `httpStatus`/`succeeded`: status backend đã trả; `succeeded` đúng khi status 2xx.
  Request lỗi (413/415/422/500) cũng có trong lịch sử.

```ts
type HistoryItem = {
  id: number;
  createdAt: string; // ISO 8601
  cipher: "caesar" | "vigenere" | "playfair" | "affine" | "columnar";
  operation: "encrypt" | "decrypt" | null;
  source: "text" | "file";
  responseMode: "content" | "file" | null;
  inputLength: number | null;
  outputLength: number | null;
  httpStatus: number;
  succeeded: boolean;
  durationMs: number;
};

async function fetchHistory(params: {
  limit?: number;
  cursor?: string;
  cipher?: HistoryItem["cipher"];
  operation?: "encrypt" | "decrypt";
}) {
  const query = new URLSearchParams();
  for (const [name, value] of Object.entries(params)) {
    if (value !== undefined) query.set(name, String(value));
  }
  const response = await fetch(`/api/history?${query}`);
  const body = await response.json();
  if (!body.success) throw new Error(body.message);
  return body.result as { items: HistoryItem[]; nextCursor: string | null };
}
```

```bash
curl -s 'http://localhost:8080/api/history?limit=5&cipher=playfair'
```

Lỗi dùng envelope chung `{"success": false, "message": …}`:

| HTTP | `message` | Khi nào |
|---|---|---|
| 422 | `Giới hạn phải là số nguyên từ 1 đến 100.` | `limit` sai |
| 422 | `Con trỏ phân trang không hợp lệ.` | `cursor` hỏng hoặc bị sửa |
| 422 | `Bộ lọc lịch sử không hợp lệ.` | `cipher`/`operation` ngoài tập cho phép |
| 404 | `Lịch sử không được bật trên máy chủ này.` | Server tắt `HISTORY_API_ENABLED`; kiểm tra trước mọi query |
| 503 | `Lịch sử tạm thời không khả dụng.` | Backend không có DB hoặc DB lỗi |

Lưu ý cho FE:

- Lịch sử là best-effort: nếu DB lỗi đúng lúc, request đó có thể không xuất hiện.
- Endpoint không có xác thực và trả lịch sử chung của cả instance, không theo user.
  Vì vậy nó mặc định tắt; chỉ bật ở môi trường dev hoặc nội bộ.
- Server chỉ giữ 30 ngày gần nhất (có thể lệch tối đa 6 giờ). Không có API xóa.

### 16.4 Gợi ý UI cho màn hình lịch sử

- Gọi `GET /api/health` khi mở màn hình. `history: "disabled"` hoặc
  `database: "disabled"` thì ẩn màn hình lịch sử server; `database: "unavailable"` thì
  hiện lỗi và nút thử lại; còn lại thì tải lịch sử. Vẫn xử lý 404 phòng khi cấu hình
  server đổi giữa chừng.
- Phân trang kiểu "Tải thêm": giữ `nextCursor` của trang cuối, gọi lại với
  `cursor=<nextCursor>`, nối thêm vào danh sách; ẩn nút khi `nextCursor` là `null`.
- Khi đổi bộ lọc `cipher`/`operation`, bỏ cursor cũ và tải lại từ trang đầu.
- `createdAt` là UTC; đổi sang giờ địa phương khi hiển thị.
- Hiển thị `httpStatus`/`succeeded` để phân biệt request lỗi; không có message lỗi
  gốc trong lịch sử.
- Danh sách trống (`items: []`, `nextCursor: null`) là trạng thái hợp lệ, cần có
  empty state riêng.

## 17. Lịch sử cá nhân trên trình duyệt

Project không có đăng nhập, nên server không thể biết request nào của ai. Tính năng
"xem lại thao tác của tôi" (kèm input và kết quả) do FE lưu trong `localStorage` của
trình duyệt. Dữ liệu này **không gửi lên server** và không liên quan tới
`/api/history`.

### 17.1 Quy tắc

- Chỉ lưu request **thành công** (`success: true`).
- Tối đa **50 mục**, mới nhất trước; thêm mục thứ 51 thì bỏ mục cũ nhất.
- Mỗi mục gồm thời điểm, cipher, operation, input, key và kết quả.
- Với file: chỉ lưu tên file, không lưu nội dung file tải lên hay file kết quả.
- Mọi lệnh đọc/ghi `localStorage` bọc `try/catch`. Trình duyệt chặn storage (chế độ
  riêng tư, bị đầy) thì bỏ qua lịch sử, encrypt/decrypt vẫn chạy bình thường.
- Có nút **"Xóa lịch sử trên máy này"** và công tắc **"Lưu lịch sử trên máy này"**.
- Hiện cảnh báo ngắn: lịch sử chứa cả key, chỉ nên bật trên máy cá nhân.

### 17.2 Mẫu code

```ts
const STORAGE_KEY = "cipher-workbench.history.v1";
const ENABLED_KEY = "cipher-workbench.history.enabled";
const MAX_ENTRIES = 50;

type LocalHistoryEntry = {
  at: string; // new Date().toISOString()
  cipher: "caesar" | "vigenere" | "playfair" | "affine" | "columnar";
  operation: "encrypt" | "decrypt";
  source: "text" | "file";
  input: string;          // text nhập, hoặc tên file với source "file"
  key: Record<string, string | number>; // { key } hoặc { a, b } với Affine
  result: string | null;  // null với file tải về
};

function readLocalHistory(): LocalHistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function isLocalHistoryEnabled(): boolean {
  try {
    return localStorage.getItem(ENABLED_KEY) !== "false";
  } catch {
    return false;
  }
}

function addLocalHistory(entry: LocalHistoryEntry): void {
  if (!isLocalHistoryEnabled()) return;
  try {
    const next = [entry, ...readLocalHistory()].slice(0, MAX_ENTRIES);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Storage blocked or full: skip history, never break the cipher flow.
  }
}

function clearLocalHistory(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to clear.
  }
}
```

Gọi `addLocalHistory` ngay sau khi nhận response thành công. Khi người dùng tắt
công tắc "Lưu lịch sử trên máy này", đặt `ENABLED_KEY` là `"false"` và hỏi có muốn
xóa lịch sử đã lưu không.

### 17.3 Khác nhau giữa hai loại lịch sử

| | Lịch sử cá nhân (mục 17) | Lịch sử server (mục 16) |
|---|---|---|
| Nơi lưu | `localStorage` trên máy người dùng | PostgreSQL trên server |
| Ai xem được | Người dùng trên đúng trình duyệt đó | Ai gọi được `/api/history` khi cờ bật |
| Nội dung | Input, key, kết quả | Chỉ metadata, không có nội dung |
| Thời hạn | Đến khi người dùng xóa (tối đa 50 mục) | 30 ngày |
| Mục đích | Xem lại thao tác của mình | Thống kê và theo dõi vận hành |
