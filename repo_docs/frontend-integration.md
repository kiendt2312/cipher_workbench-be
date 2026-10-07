# Handoff tích hợp Frontend — tám hệ mã

Tài liệu này là **điểm vào consumer contract cho Frontend** khi tích hợp với backend
cipher. Nội dung độc lập framework: FE có thể dùng React, Vue, Svelte hoặc JavaScript
thuần, nhưng hành vi API và trạng thái quan sát được phải giữ đúng contract dưới đây.
Phần RSA có contract triển khai chi tiết tại
[`rsa-frontend-contract.md`](rsa-frontend-contract.md); mục A.9 chỉ là quick start.

- Cập nhật: `2026-10-06`. Backend có 26 POST route cipher (gồm bốn route RSA), một GET sinh khóa Hill,
  `GET /api/health`,
  `GET /api/history` (tùy chọn, dùng SQLite cục bộ trên backend).
- **Người mới:** đọc mục **A. Bắt đầu nhanh** (khoảng 10 phút) rồi dùng file
  [`examples/cipher-api.ts`](examples/cipher-api.ts). Các mục 1–17 là tra cứu chi tiết.
- **Đã tích hợp trước đây:** đọc mục **0. Thay đổi gần đây**.
- Backend **không có UI**: giao diện thuộc project FE. Thử API tại `/docs`
  (<http://localhost:8080/docs> khi chạy docker-compose).

## A. Bắt đầu nhanh

### A.1 Chạy backend

```bash
# Trong repo backend, cần Docker
cp .env.example .env
docker compose up -d --build  # SQLite migration + one-process app
curl -s http://localhost:8080/api/health
# {"success":true,"result":{"app":"ok","database":"ok","history":"enabled"}}
```

Cấu hình dev server của FE proxy `/api` tới `http://localhost:8080` (hoặc
`http://localhost:8000` nếu chạy backend bằng `uv run uvicorn`). Code FE luôn gọi URL
tương đối `/api/...`; không ghi cứng host/port. Backend mặc định không bật CORS
(xem mục 0.0a nếu FE buộc phải gọi khác origin).

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
| POST | `/api/{legacy}/encrypt` | JSON, xem A.3 | `{"success":true,"result":"<bản mã>"}` |
| POST | `/api/{legacy}/decrypt` | JSON, xem A.3 | `{"success":true,"result":"<bản rõ>"}`; riêng Playfair thêm `padding` (A.10) |
| POST | `/api/{legacy}/file` | multipart: `file`, khóa (A.3), `action`, `response_mode`; Playfair thêm `strip_padding` | `content`: JSON như trên; `file`: file `text/plain` đính kèm |
| POST | `/api/hill/encrypt` | JSON Hill, xem A.7 | `{success,result,blocks,key,warnings}` |
| POST | `/api/hill/decrypt` | JSON Hill, xem A.7 | `{success,result,blocks,key,warnings,padding}` |
| GET | `/api/health` | — | `{"success":true,"result":{"app","database","history"}}` (503 khi DB lỗi) |
| GET | `/api/history` | query `limit`, `cursor`, `cipher`, `operation` | `{"success":true,"result":{"items":[...],"nextCursor":...}}` |
| POST | `/api/hill/key/analyze` | JSON `key` hoặc `keyword,m` | Phân tích ma trận khóa |
| GET | `/api/hill/key/random?m=3` | query `m=2|3|4` | Khóa Hill hợp lệ ngẫu nhiên |
| POST | `/api/des/encrypt` | JSON DES, xem A.8 | `{success,result,warnings}` |
| POST | `/api/des/decrypt` | JSON DES, xem A.8 | `{success,result,warnings}` |
| POST | `/api/des/file` | multipart: `file`, `key`, `action`, `mode`, `iv`, `response_mode` | `content`: `{success,result,warnings}`; `file`: file `text/plain` đính kèm |
| POST | `/api/des/trace` | JSON `block`, `key`, `operation` | `{success,result,trace,warnings}` |
| POST | `/api/rsa/keys` | JSON `p,q,e` dạng decimal string | Key material + full `egcdSteps` |
| POST | `/api/rsa/keys/random` | JSON integer `bits=16|32|64|128` | Key material gồm `p,q` |
| POST | `/api/rsa/encrypt` | JSON number/text hoặc multipart plaintext | Full blocks/cipher + optional selected trace |
| POST | `/api/rsa/decrypt` | JSON cipher package | Full blocks/plaintext + optional selected trace |

`{legacy}` là một trong `caesar`, `vigenere`, `playfair`, `affine`, `columnar`.
Năm cipher này có đủ text/file (15 POST route); Hill chỉ có hai POST transform và một
POST analyze, không có `/api/hill/file`. DES có đủ encrypt/decrypt/file và thêm
`/api/des/trace`. `action` là `encrypt`/`decrypt`; `response_mode` là `content`
(mặc định) hoặc `file` và dùng cho năm cipher cũ và DES.

RSA chỉ dùng bốn route exact ở bảng, không có route file/trace/history riêng. Hai
transform xuất hiện trong `GET /api/history` chung; keygen không xuất hiện. File RSA
chỉ là plaintext `.txt` gửi thẳng tới `/api/rsa/encrypt`; response luôn JSON.

### A.3 Khóa theo cipher

| Cipher | JSON text | Multipart | Quy tắc | Ví dụ |
|---|---|---|---|---|
| Caesar | `"key": 3` (**số**, không phải chuỗi) | `key` | Số nguyên có dấu, lớn tùy ý; file tối đa 32 ký tự | `{"text":"Hello World","key":3}` → `Khoor Zruog` |
| Vigenère | `"key": "LEMON"` | `key` | Chỉ `A-Z`/`a-z`, không khoảng trắng | `Attack at dawn!` → `Lxfopv ef rnhr!` |
| Playfair | `"key": "PLAYFAIR EXAMPLE"` | `key` | Có ít nhất một chữ cái; kết quả là văn bản chuẩn hóa (xem 4.3) | `HIDE THE GOLD` → `BMODZBXDNAGE` |
| Affine | `"a": 5, "b": 8` (**số**) | `a`, `b` | Số nguyên có dấu; `a` mod 26 nguyên tố cùng nhau với 26 | `HELLO` → `RCLLA` |
| Columnar | `"key": "3 1 4 2"` hoặc `"BALLOON"` | `key` | Hoán vị `1..m` (2–256 cột) hoặc từ khóa 2–256 chữ cái | `MEET ME AT NOON` + `BALLOON` → `EAM NETT EO NMO` |
| Hill | `"key":[[3,3],[2,5]]` hoặc `"keyword":"HILL","m":2` | Không có file route | Ma trận vuông cấp 2–4 khả nghịch mod 26 | `HELP` → `DPLE` |
| DES | `"key":"133457799BBCDFF1"` (string) | `key`, thêm `mode`, `iv` | Đúng 16 hex sau khi bỏ khoảng trắng; không kiểm bit chẵn lẻ | `Hello World` → `B1CA74BB3514268701A9ACC3E4E69FAA` |
| RSA | Encrypt `"e":"7","n":"187"`; decrypt `"d":"23","n":"187"` | `e`, `n` trên encrypt plaintext | Mọi crypto integer là decimal string; không qua JS `Number` | Number `88` → `11` → `88` |

Bốn điều hay sai nhất:

1. Caesar và Affine gửi **JSON number**, nhưng giữ giá trị người dùng nhập dưới dạng
   chuỗi và ghép token bằng `BigInt` để không mất độ chính xác (có sẵn trong file mẫu).
2. Gửi `text` và chuỗi khóa **nguyên văn**: không `trim()`, không đổi hoa thường.
3. File của năm cipher cũ và DES luôn hai request: `response_mode=content` để xem
   trước, rồi `response_mode=file` để tải file chính thức với tên file từ header
   `Content-Disposition`.
4. RSA là ngoại lệ file/number: crypto integer luôn giữ dưới dạng decimal string;
   multipart chỉ encrypt plaintext và luôn trả JSON, không có `response_mode`.

### A.4 API client dùng ngay

File [`examples/cipher-api.ts`](examples/cipher-api.ts) (TypeScript, không phụ thuộc
thư viện) gồm `transformText`, `previewFile`, `downloadFile`, `saveBlob`, `getHealth`,
`canShowServerHistory`, `getHistory`, các helper Hill/DES và bộ hàm lịch sử trên
trình duyệt. File đã được compile với
`tsc --strict --noEmit --target es2022 --lib es2022,dom`.

```ts
import {
  ApiError, transformText, previewFile, downloadFile, saveBlob,
  playfairDecrypt, playfairPreviewDecryptFile, displayedResult,
  transformHill, analyzeHillKey, randomHillKey, readHillTextFile,
  desEncrypt, desDecrypt, desTrace, desPreviewFile, desDownloadFile,
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

const playfair = await playfairDecrypt({ text: "PDGW", key: "PLAYFAIR EXAMPLE" });
// playfair.result === "ABXQ" (bản thô); playfair.padding.filtered === "ABX"
const shown = displayedResult(playfair, filterPadding); // theo toggle lọc ký tự đệm (A.10)

const hill = await transformHill({
  operation: "encrypt", text: "HELP", key: [[3, 3], [2, 5]],
}); // hill.result === "DPLE"; blocks/key/warnings vẫn còn nguyên
const analyzed = await analyzeHillKey({ keyword: "HILL", m: 2 });
const generated = await randomHillKey(3);

// Nếu nguồn là file Hill: không gọi /api/hill/file.
const upload = await readHillTextFile(file); // kiểm .txt, 5 MiB raw bytes, UTF-8 fatal
const fromFile = await transformHill({
  operation: "encrypt", text: upload.text, key: generated.result.matrix,
});

const des = await desEncrypt({ text: "Hello World", key: "133457799BBCDFF1" });
// des.result === "B1CA74BB3514268701A9ACC3E4E69FAA"; des.warnings === []
const desFile = { operation: "encrypt", file, key: "133457799BBCDFF1", mode: "CBC", iv: "0000000000000000" } as const;
const desPreview = await desPreviewFile(desFile);          // {success,result,warnings}
const desAttachment = await desDownloadFile(desFile);      // tên .encrypted.txt từ server
```

### A.5 Lỗi

Lỗi của năm cipher cũ có dạng `{"success": false, "message": "<tiếng Việt>"}`.
Lỗi nghiệp vụ Hill thêm `code` và `details`; FE vẫn hiển thị nguyên `message`, chỉ dùng
`code/details` để gắn lỗi vào control phù hợp. E07 do FE phát sinh khi đọc file UTF-8,
không phải response backend. Lỗi DES giữ envelope hai trường như năm cipher cũ (không
có `code`), status 422/413/415/500; bảng message ở mục 9.2. Lỗi mạng thì FE tự hiện
thông báo kết nối.

Lỗi RSA có contract riêng chính xác
`{success:false,code,message,field}`; `field` có thể là `null`, tên field hoặc path như
`cipher[3]`. Status là 413 (size), 415 (media/extension/UTF-8), 422 (validation/domain)
hoặc 500. Không áp contract RSA cho route cũ.

### A.6 UI tối thiểu phải có

- Chọn cipher, chế độ mã hóa/giải mã, nguồn văn bản/file; ô khóa theo A.3 (Affine có
  hai ô).
- Xóa kết quả cũ mỗi khi cipher, chế độ, nguồn, input hoặc khóa thay đổi.
- Khóa mọi control và chặn gửi lặp khi request đang chạy.
- Cảnh báo Playfair luôn hiện khi chọn Playfair (câu chuẩn ở mục 11).
- Playfair/Hill giải mã: toggle `Tự động lọc ký tự đệm (Playfair/Hill padding)` và
  luôn cho xem được bản thô (A.10).
- File của năm cipher cũ: kiểm tra sơ bộ `.txt`, tối đa 5 MiB, không rỗng; xem trước
  rồi mới tải. Hill: FE tự đọc `.txt` bằng UTF-8 fatal decode, kiểm tối đa 5 MiB theo
  byte gốc và gọi JSON; không gọi `/api/hill/file`. DES: dùng `/api/des/file` như năm
  cipher cũ (preview rồi tải).
- DES: hiển thị `warnings` (W01/W02/W03) cạnh kết quả; hiện trạng thái đang xử lý vì
  5 MiB mất khoảng 6 giây; cảnh báo trước khi mã hóa văn bản/file lớn hơn
  2.621.439 byte UTF-8 vì bản mã sẽ không giải mã lại được qua API (mục 4.7).
- Lịch sử (tùy chọn): lịch sử trên máy theo mục 17; lịch sử máy chủ chỉ khi
  `canShowServerHistory` trả `true` (mục 16).

Checklist nghiệm thu đầy đủ ở mục 14.

### A.7 Hill nhanh

```ts
const response = await transformHill({
  operation: "encrypt",
  text: "HELP",
  key: [[3, 3], [2, 5]],
});
// response.result === "DPLE"; giữ response.blocks/key/warnings để hiển thị giải thích
```

Request Hill dùng đúng một trong `key` hoặc cặp `keyword,m`. Không gửi `m` với
matrix `key`; `m` của keyword từ 2 đến 4.
`options` tùy chọn gồm `stripDiacritics:boolean` và `padChar` là một chữ hoa A-Z.
Khi giải mã, gửi lại đúng `padChar` đã dùng lúc mã hóa để backend nhận diện ký tự đệm.
Encrypt trả đúng `success,result,blocks,key,warnings`; decrypt trả thêm `padding`
(A.10). Analyze/random có `success,result,warnings`. FE đọc file bằng `TextDecoder("utf-8", {fatal:true})`;
decode lỗi thì hiển thị E07 và không gửi request.

### A.8 DES nhanh

```ts
const encrypted = await desEncrypt({ text: "Hello World", key: "133457799BBCDFF1" });
// encrypted.result === "B1CA74BB3514268701A9ACC3E4E69FAA" (ECB, PKCS#7)
const decrypted = await desDecrypt({ text: encrypted.result, key: "133457799BBCDFF1" });
// decrypted.result === "Hello World"

const slide = await desEncrypt({
  text: "0123456789ABCDEF", key: "133457799BBCDFF1", inputFormat: "hex",
}); // slide.result === "85E813540F0AB405" (không đệm)
const back = await desDecrypt({
  text: slide.result, key: "133457799BBCDFF1", outputFormat: "hex",
}); // back.result === "0123456789ABCDEF"

const cbc = await desEncrypt({
  text: "Hello World", key: "133457799BBCDFF1", mode: "CBC", iv: "0000000000000000",
}); // cbc.result === "B1CA74BB351426875F9A5BCA734D9EF4"; giải mã cần đúng iv này

const traced = await desTrace({ block: "0123456789ABCDEF", key: "133457799BBCDFF1" });
// traced.trace.subkeys[0].k === "1B02EFFC7072"; traced.trace.rounds.length === 16
```

Field JSON là camelCase và strict: encrypt chỉ nhận `text,key,inputFormat,mode,iv`;
decrypt chỉ nhận `text,key,outputFormat,mode,iv`; trace chỉ nhận `block,key,operation`.
Giữ cặp định dạng: mã hóa `inputFormat=text` ↔ giải mã `outputFormat=text`; mã hóa
`inputFormat=hex` ↔ giải mã `outputFormat=hex`. Chi tiết ở mục 4.7 và 9.2.

### A.9 RSA nhanh và lossless package

> Cảnh báo bắt buộc: textbook RSA chỉ minh họa thuật toán; random keygen hỗ trợ
> modulus 16/32/64/128 bit, còn manual key có giới hạn riêng và có thể nhỏ hơn. Không
> bảo vệ dữ liệu thật, không có OAEP/authenticity và không chứng minh được
> key/metadata đúng.

Đọc [`rsa-frontend-contract.md`](rsa-frontend-contract.md) trước khi implement. File đó
là nguồn chi tiết cho exact union types, bốn endpoint, errors, limits, multipart,
trace, lossless package và history RSA; phần dưới chỉ giúp thử nhanh một block flow.

```ts
const encrypted = await postJson("/api/rsa/encrypt", {
  e: "3", n: "67591", inputType: "text", mode: "block", data: "Hi!",
  traceBlockIndex: 0,
});
// encrypted.blockSize === 2; encrypted.originalUtf8ByteLength === 3
// encrypted.cipher === ["37222", "6468"]
const decrypted = await postJson("/api/rsa/decrypt", {
  d: "44715", n: "67591", inputType: "text", mode: "block",
  cipher: encrypted.cipher,
  originalUtf8ByteLength: encrypted.originalUtf8ByteLength,
});
```

- Crypto integers luôn là decimal string; không hex/base64. Output được canonicalize.
- `mode=char` tạo một block/code point; `mode=block` đóng gói UTF-8 lossless. FE phải
  lưu và gửi lại `originalUtf8ByteLength`, kể cả khi plaintext có BOM hoặc trailing NUL.
- Không trim/normalize/đổi newline. BOM đầu vào là ký tự `U+FEFF`, không phải metadata.
- Text tối đa 10.000 code point; cipher number/char/block tối đa 1/10.000/40.000 item;
  file tối đa 1.000.000 raw byte decimal.
- Mặc định `trace:null`. Gửi một `traceBlockIndex` zero-based để lấy full steps của đúng
  block đó. Không có pagination/truncation và không có trace route thứ năm.
- Multipart fields exact: `file,e,n,mode,traceBlockIndex?`; `.txt` case-insensitive,
  UTF-8 strict, plaintext encrypt only. Không có attachment hoặc ciphertext upload.
- Block decrypt thiếu hoặc gửi sai `originalUtf8ByteLength` trả 422
  `INVALID_LENGTH_METADATA`; plaintext chứa lone surrogate trả 422 `DECODE_FAILED`
  với `field=data`. Exact envelope và ví dụ ở contract chuyên biệt mục 11.1.
- `postJson` trong snippet là pseudo-helper cục bộ, không phải export hiện có của
  `examples/cipher-api.ts`; contract chi tiết có helper copyable.

### A.10 Lọc ký tự đệm Playfair/Hill

Khi **giải mã** Playfair hoặc Hill, `result` luôn là **bản thô toán học** (giữ cả ký tự
đệm). Response có thêm `padding` cho biết ký tự nào là đệm:

```json
{
  "success": true,
  "result": "THUDOHANOIXX",
  "padding": { "count": 2, "positions": [10, 11], "filtered": "THUDOHANOI" }
}
```

| Trường | Ý nghĩa |
|---|---|
| `count` | Số ký tự đệm nhận diện được (bằng `positions.length`). |
| `positions` | Vị trí 0-based trong **dãy chữ cái A–Z/a–z** của `result`, tăng dần. Playfair: trùng chỉ số ký tự của `result`. Hill: vị trí `p` nằm ở khối `⌊p/m⌋`, ô `p mod m` của `blocks`. |
| `filtered` | `result` bỏ đúng các chữ tại `positions`; mọi ký tự khác giữ nguyên. |

- Mã hóa không có `padding`. Không nhận diện được gì thì `padding` vẫn có:
  `{count:0, positions:[], filtered:result}`.
- **Toggle** `Tự động lọc ký tự đệm (Playfair/Hill padding)`: bật thì hiển thị, sao
  chép và tải `padding.filtered`; tắt thì dùng `result`. Đổi toggle **không** gọi lại
  API. Mặc định bật hay tắt do FE chọn.
- Bản thô phải luôn xem được. Nên đánh dấu ký tự đệm trong bản thô bằng `positions`
  (duyệt các chữ `[A-Za-z]` của `result` theo thứ tự, đừng dùng chỉ số chuỗi trực tiếp
  cho Hill vì emoji chiếm hai UTF-16 code unit). File mẫu có `displayedResult`,
  `paddingCharIndexes` (chỉ số chuỗi để tô) và `hillPaddingCells` (khối/ô 1-based).
- **Giới hạn:** ciphertext không cho biết đâu là đệm, nên chữ thật trùng mẫu đệm có
  thể bị lọc nhầm: Hill `MAX` → `MA`; Playfair `AX` → `A`, `AXAB` → `AAB`.
- Quy tắc nhận diện:
  - **Playfair:** chữ thứ hai của một cặp là `X` (hoặc `Q` sau `X`), và cặp kế tiếp bắt
    đầu bằng đúng chữ đầu của cặp đó (`BALXLOON` → `BALLOON`) hoặc đó là cặp cuối
    (`TAXICABX` → `TAXICAB`). X thật giữa hai chữ khác nhau được giữ.
  - **Hill:** tối đa `m − 1` chữ cuối bằng `options.padChar` (mặc định `X`), không phân
    biệt hoa thường.
- File Playfair tải bằng attachment: gửi `strip_padding=true` khi toggle bật,
  `false` hoặc bỏ trống khi tắt (mục 8.1). JSON xem trước (`response_mode=content`)
  luôn có cả `result` thô và `padding`, bất kể `strip_padding`.
- **Khung Phân tích của Hill** nên có phần "Lọc ký tự đệm": `padChar` đang dùng, số ký
  tự đệm, khối/ô chứa chúng (ví dụ `positions [10,11]`, `m=3` → khối 4, ô 2–3), bản thô,
  bản lọc và toggle. Có thể tô các ô đó trong "Xem từng bước".

## 0. Thay đổi gần đây

### 0.0d RSA transform có server history (`2026-10-06`)

`POST /api/rsa/encrypt` và `/api/rsa/decrypt` giờ ghi metadata success/error theo
best-effort và có thể lọc bằng `GET /api/history?cipher=rsa`. Encrypt JSON là
`source=text`, encrypt multipart `.txt` là `source=file`, decrypt là `source=text`;
`responseMode` luôn null. Hai keygen route vẫn không ghi.

Không có content/key/package trong DB: không lưu plaintext, ciphertext, `p/q/e/d`,
public/private key, `data`, cipher array, `textMetadata`, `originalUtf8ByteLength`,
filename/file content, IP/user-agent hoặc trace. Number transform để hai length null;
text encrypt chỉ có input code-point length, text decrypt chỉ có output code-point
length, multipart chỉ có input raw-byte length.

Đoạn migration `0003` → `0004` dưới đây là lịch sử của PostgreSQL legacy. Runtime
SQLite hiện dùng baseline riêng đã có RSA; không chạy hoặc stamp các revision này
trên file SQLite. Transfer tooling vẫn kiểm tra nguồn PostgreSQL ở effective `0004`.

### 0.0c Lọc ký tự đệm Playfair/Hill (`2026-10-02`)

**Endpoint bị ảnh hưởng:** `POST /api/playfair/decrypt`, `POST /api/playfair/file` với
`action=decrypt`, `POST /api/hill/decrypt`. Encrypt, request JSON, status code, message
cũ và filename **không đổi**. Mục này **thay thế** quy tắc ở 0.3.

**Hành vi mới:**

- `result` khi giải mã luôn là **bản thô toán học**, không bỏ ký tự nào.
  **BREAKING (Playfair):** backend không còn tự bỏ một filler cuối.
- Response giải mã có thêm `padding: {count, positions, filtered}` (A.10). Playfair lọc cả
  filler giữa cặp chữ lặp lẫn filler cuối; Hill lọc tối đa `m − 1` chữ `padChar` ở cuối.
- `/api/playfair/file` nhận thêm `strip_padding=true|false` (mặc định `false`) để file
  đính kèm khi giải mã là bản lọc. Giá trị khác trả 422
  `Tùy chọn lọc ký tự đệm phải là true hoặc false.`

| Ciphertext | `result` trước | `result` sau | `padding.filtered` |
|---|---|---|---|
| Playfair `PDGW` (từ `ABX`) | `ABX` | `ABXQ` | `ABX` |
| Playfair `GWGW` (từ `XX`) | `XQX` | `XQXQ` | `XX` |
| Playfair `BMODZBXDNAGE` (từ `HIDE THE GOLD`) | `HIDETHEGOLD` | `HIDETHEGOLDX` | `HIDETHEGOLD` |
| Playfair `DPYRANQO` (từ `BALLOON`) | `BALXLOON` | `BALXLOON` | `BALLOON` |
| Playfair `VPMRDLGI` (từ `TAXICAB`) | `TAXICAB` | `TAXICABX` | `TAXICAB` |
| Hill `DPDKKB`, K `[[3,3],[2,5]]` | `HELLOX` | `HELLOX` | `HELLO` |
| Hill `HQKRJYDPDONU`, K `[[6,1,3],[17,5,7],[3,2,3]]` | `THUDOHANOIXX` | `THUDOHANOIXX` | `THUDOHANOI` |

**FE cần làm:**

1. Thêm toggle `Tự động lọc ký tự đệm (Playfair/Hill padding)` cho chế độ giải mã
   Playfair/Hill; bật thì dùng `padding.filtered`, tắt thì dùng `result` (A.10). Nếu chưa
   làm toggle, hiển thị `padding.filtered` để giữ trải nghiệm gần như cũ.
2. Playfair text: dùng `playfairDecrypt` thay cho `transformText` khi giải mã (helper cũ
   chỉ trả `result` thô). Playfair file: xem trước bằng `playfairPreviewDecryptFile`, tải
   bằng `downloadFile({..., stripPadding})` theo trạng thái toggle.
3. Hill: đọc thêm `padding` từ `transformHill` khi giải mã, gửi lại đúng `padChar` đã
   dùng lúc mã hóa, thêm phần "Lọc ký tự đệm" vào khung Phân tích.
4. Cập nhật mock/fixture/test theo bảng trên; bỏ mọi logic FE tự cắt X/Q.
5. Cập nhật copy cảnh báo Playfair theo mục 11.

### 0.0b Thêm DES (`2026-10-01`)

**Endpoint mới:** `POST /api/des/encrypt`, `/api/des/decrypt`, `/api/des/file`,
`/api/des/trace`. Route, request, response, status và message của sáu cipher cũ
không đổi.

**FE cần làm (nếu thêm DES):**

1. Thêm `des` vào selector cipher và union `Cipher` của lịch sử (`cipher=des`).
2. Gọi DES qua helper riêng (`desEncrypt`, `desDecrypt`, `desTrace`,
   `desPreviewFile`, `desDownloadFile`): success có thêm `warnings`, `/trace` có `trace`.
3. Lỗi DES là `{success:false,message}` (không có `code`); hiển thị nguyên `message`.
4. Hiện trạng thái đang xử lý cho input lớn (5 MiB mất khoảng 6 giây) và cảnh báo
   trước khi mã hóa văn bản lớn hơn 2.621.439 byte UTF-8: bản mã của nó vượt 5 MiB nên
   không giải mã lại được qua API (mục 4.7).
5. Với `mode=CBC`: bắt buộc nhập IV 16 hex, lưu/hiển thị IV cùng bản mã. **IV sai
   không bị server phát hiện**: kết quả vẫn có thể là HTTP 200 với 8 byte đầu bị lệch.
   Với `mode=ECB`: ẩn hoặc vô hiệu ô IV (server bỏ qua `iv`).
6. Kiểm tra sơ bộ phía FE chỉ để hỗ trợ trải nghiệm (khóa 16 hex, IV 16 hex khi CBC,
   bản mã hex bội 16 ký tự); server vẫn là nguồn validation có thẩm quyền.
7. Hiển thị `warnings` (W01 khóa yếu, W02 khóa nửa yếu, W03 ECB lộ khối lặp) như cảnh
   báo không chặn kết quả. Với file, `warnings` chỉ có ở request preview `content`.
8. Màn hình minh họa từng bước dùng `/api/des/trace` theo bảng ánh xạ ở mục 4.7
   (sinh khóa, IP, 16 vòng, hàm f, IP⁻¹); FE chỉ định dạng, không tự tính DES.

**Lịch sử backend:** PostgreSQL từng cần migration `0003` trước khi bật DES. Runtime
SQLite hiện dùng baseline riêng đã chứa DES; thông tin này không phải lệnh deploy
SQLite.

### 0.0a CORS tùy chọn cho FE khác origin (`2026-09-29`)

Mặc định backend vẫn **không** gửi header CORS; FE dùng proxy `/api` như cũ thì không
phải đổi gì. Khi FE deploy ở origin khác mà không có reverse proxy, phía BE đặt
biến môi trường:

```bash
CORS_ALLOW_ORIGINS=https://app.example.com,http://localhost:5173
```

- Chỉ đúng các origin trong danh sách được phép; không có `*`.
- Chỉ `GET`, `POST` và header `Content-Type`; không gửi cookie/credentials.
- Header `Content-Disposition` được expose, nên FE đọc được tên file từ response
  `response_mode=file`.
- Response lỗi từ guard (ví dụ 413) vẫn có header CORS. Riêng lỗi 500 ngoài dự
  kiến không có header CORS, nên trình duyệt báo lỗi mạng thay vì đọc được body;
  FE xử lý như lỗi hệ thống.
- Khi đó FE gọi URL đầy đủ của backend (đọc từ biến môi trường build, không ghi
  cứng trong code).

### 0.0 Backend bỏ UI static tại `/` (`2026-09-28`)

Backend không còn phục vụ giao diện: `GET /` và `/static/*` trả 404. Giao diện do
project FE sở hữu. `/docs` (Swagger) và `/openapi.json` vẫn là nơi xem và thử API;
15 route cipher, `/api/health` và `/api/history` không đổi.

Nếu backend trên máy vẫn là bản cũ (mở `/` còn thấy UI, hoặc `/api/health` thiếu
`history`), build lại từ `main` mới nhất:

```bash
git pull
docker compose up -d --build
curl -s http://localhost:8080/api/health
# {"success":true,"result":{"app":"ok","database":"ok","history":"enabled"}}
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8080/   # 404
```

FE không phải đổi code vì thay đổi này.

### 0.1 Khóa lịch sử server, retention 30 ngày, lịch sử trên trình duyệt (`2026-09-28`)

Project không có đăng nhập, nên:

- `GET /api/history` **mặc định tắt**. Khi tắt, endpoint trả HTTP 404 với message
  "Lịch sử không được bật trên máy chủ này.". Môi trường dev (`.env.example`) bật
  sẵn; môi trường dùng chung hoặc public sẽ tắt.
- `GET /api/health` có thêm `result.history`: `"enabled"` hoặc `"disabled"`.
- Lịch sử server mặc định giữ 30 ngày; cấu hình `HISTORY_RETENTION_DAYS` cho phép
  1–3650 ngày.
- Lịch sử **cá nhân** của người dùng (xem lại input/kết quả của chính họ) do FE lưu
  trên trình duyệt, không gửi lên server (mục 17).

**FE cần làm:**

1. Chỉ hiện màn hình lịch sử server khi health trả `history: "enabled"` và
   `database: "ok"`; xử lý thêm 404 từ `/api/history` (mục 16.3).
2. Làm lịch sử cá nhân trên trình duyệt theo mục 17 nếu cần tính năng "xem lại".

### 0.2 PostgreSQL, health và lịch sử thao tác (`2026-09-28`, lịch sử)

**Endpoint mới:** `GET /api/health` và `GET /api/history`. 15 route cipher giữ
nguyên request, response, status và message.

**Hành vi mới:**

- Backend ban đầu có thể chạy kèm PostgreSQL. Khi có DB, mỗi request cipher (kể cả request
  lỗi) được ghi lại dưới dạng metadata: cipher, operation, text/file, độ dài, status,
  thời gian xử lý. Không lưu text, key, tên file, nội dung file hay kết quả.
- Khi chạy bằng docker-compose, backend ở `http://localhost:8080`. Khi chạy bằng
  `uv run uvicorn` mặc định vẫn là `http://localhost:8000`.

**FE cần làm:**

1. Trỏ dev proxy `/api` tới đúng cổng backend đang chạy (mục 2 và 16.1).
2. Nếu làm màn hình lịch sử: gọi `GET /api/health` để biết có DB không, rồi dùng
   `GET /api/history` theo contract ở mục 16.
3. Không thay đổi gì ở luồng encrypt/decrypt.

### 0.3 Playfair decrypt bỏ filler cuối (`2026-09-28`, đã bị thay thế bởi 0.0c)

> Từ `2026-10-02`, `result` không còn bỏ filler cuối; bản đã lọc nằm ở
> `padding.filtered`. Phần dưới giữ lại làm lịch sử.

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
        ├── Columnar Transposition
        ├── Hill
        └── DES
  │
  ├── JSON preview/error hoặc text/plain attachment
  │
  └── SQLite local trên BE (tùy chọn): cipher_operations ← /api/history, /api/health
```

Backend chỉ phục vụ API, `/docs` và `/openapi.json`; không có UI. Trong container và khi chạy bằng uv, app
nghe cổng `8000`; docker-compose publish ra máy host ở cổng `8080`
(`APP_HOST_PORT`). FE gọi đường dẫn tương đối, ví dụ `/api/vigenere/encrypt`;
không ghi cứng backend host/port trong code.

Khi chạy FE dev server riêng, cấu hình dev proxy tới cổng backend đang chạy:

| Cách chạy backend | Proxy target |
|---|---|
| `docker compose up` (SQLite local) | `http://localhost:8080` |
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

Cách khuyến nghị vẫn là proxy `/api`, kể cả khi deploy (reverse proxy). Chỉ khi FE
buộc phải gọi backend ở origin khác mới dùng CORS theo mục 0.0a. Không khôi phục
`API_BASE` ghi cứng trong code, mock toggle hoặc local cipher service từ demo cũ.

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
Backend không lưu input, key, file, result hay session. Khi có SQLite, backend
chỉ lưu metadata thao tác, đọc qua `GET /api/history` (mục 16).

## 3. Danh mục cipher endpoint hiện tại

| Cipher | Text encrypt | Text decrypt | File |
|---|---|---|---|
| Caesar | `POST /api/caesar/encrypt` | `POST /api/caesar/decrypt` | `POST /api/caesar/file` |
| Vigenère | `POST /api/vigenere/encrypt` | `POST /api/vigenere/decrypt` | `POST /api/vigenere/file` |
| Playfair | `POST /api/playfair/encrypt` | `POST /api/playfair/decrypt` | `POST /api/playfair/file` |
| Affine | `POST /api/affine/encrypt` | `POST /api/affine/decrypt` | `POST /api/affine/file` |
| Columnar | `POST /api/columnar/encrypt` | `POST /api/columnar/decrypt` | `POST /api/columnar/file` |
| Hill | `POST /api/hill/encrypt` | `POST /api/hill/decrypt` | Không có |
| DES | `POST /api/des/encrypt` | `POST /api/des/decrypt` | `POST /api/des/file` |
| RSA | `POST /api/rsa/encrypt` | `POST /api/rsa/decrypt` | Multipart plaintext dùng chính `/api/rsa/encrypt` |

Các text endpoint không phải RSA nhận `application/json` hoặc `application/*+json`.
RSA chỉ nhận `application/json` cho hai route keygen và `/api/rsa/decrypt`;
`/api/rsa/encrypt` nhận `application/json` hoặc `multipart/form-data` cho plaintext
`.txt`. Mọi response RSA đều là JSON. Các file endpoint truyền thống nhận
`multipart/form-data` với response mode `content|file`; RSA multipart không có
`response_mode`.

Ngoài 22 route biến đổi được history matcher ghi nhận, Hill có
`POST /api/hill/key/analyze` và `GET /api/hill/key/random?m=2|3|4`; DES có
`POST /api/des/trace`; RSA có hai route keygen. Backend còn có hai route đọc dùng chung:
`GET /api/health` và `GET /api/history` (mục 16).

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
| Decrypt | `BMODZBXDNABEKUDMUIXMMOUVIF` | — | `HIDETHEGOLDINTHETREXESTUMP` (lọc: `HIDETHEGOLDINTHETREESTUMP`) |
| Encrypt | `XX` | `XQXQ` | `GWGW` |
| Encrypt | `ABX` | `ABXQ` | `PDGW` |
| Decrypt | `PDGW` | — | `ABXQ` (lọc: `ABX`) |
| Decrypt | `GWGW` | — | `XQXQ` (lọc: `XX`) |

Playfair output luôn uppercase ASCII. Decrypt trả `result` là prepared plaintext thô
(giữ mọi filler) và `padding` chỉ ra filler nhận diện được (A.10): filler giữa cặp chữ
lặp và filler cuối. Vì ciphertext không phân biệt filler với chữ thật, bản lọc mất chữ
thật trùng mẫu filler (`AX → A`). Backend không phục hồi `J`, case, whitespace, dấu câu
hoặc Unicode đã bị loại. FE **không được tự strip filler** ngoài `padding.filtered` và
**không được cố dựng lại formatting nguyên bản**. UI phải cảnh báo rõ rằng round-trip
Playfair chỉ trả prepared plaintext, không phải input ban đầu.

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

### 4.6 Hill vector hàng

Hill dùng `y = x·K mod 26`, với A=0…Z=25 và ma trận cấp 2–4. Không dùng quy ước
vector cột `K·x`. Key là ma trận JSON integer vuông hoặc keyword đúng `m²` chữ
ASCII đọc theo hàng; phần tử ma trận được chuẩn hóa mod 26. Key chỉ hợp lệ khi
`gcd(det K mod 26, 26) = 1`.

Chỉ ASCII letter tham gia khối, giữ case/vị trí của chữ gốc; dấu câu và Unicode
khác giữ nguyên. Mặc định chữ Việt có dấu NFC/NFD không tham gia khối và sinh W02;
`stripDiacritics=true` chuyển chúng (kể cả `đ/Đ`) thành ASCII trước khi mã hóa.
Encrypt đệm `padChar` (mặc định `X`) và nối vị trí padding sau toàn bộ text; decrypt
không xóa padding khỏi `result` mà trả `padding` nhận diện tối đa `m − 1` chữ `padChar`
ở cuối (A.10). Response trả toàn bộ `blocks`, phân tích `key` và warnings
W01/W02/W03. Vector kiểm nhanh: `HELP → DPLE`; vector cấp bốn `TEST → FNMP` với
K `[[3,1,2,0],[0,5,1,4],[0,0,7,2],[0,0,0,9]]`.

Hill không có file route. FE kiểm `.txt`, byte length tối đa 5.242.880, giải mã
UTF-8 nghiêm ngặt (E07 nếu thất bại), rồi gửi chuỗi qua JSON. Backend kiểm giới hạn
trên UTF-8 của trường `text` trước khi bỏ dấu. `TextDecoder` mặc định bỏ UTF-8 BOM
đầu file; BOM không phải dữ liệu Hill. Helper `readHillTextFile` trong file mẫu thực
thi đầy đủ flow này và không gửi request nếu extension, size hoặc UTF-8 không hợp lệ.

Bốn route Hill và shape chính xác:

| Method/path | Input | HTTP 200 |
|---|---|---|
| `POST /api/hill/encrypt` | `{text, key, options?}` hoặc `{text, keyword, m, options?}` | `{success,result,blocks,key,warnings}` |
| `POST /api/hill/decrypt` | Như encrypt; `options.padChar` dùng để nhận diện đệm | `{success,result,blocks,key,warnings,padding}` |
| `POST /api/hill/key/analyze` | `{key}` hoặc `{keyword,m}`; không nhận text/options | `{success,result,warnings}` |
| `GET /api/hill/key/random?m=2|3|4` | `m` bắt buộc, đúng một lần | `{success,result,warnings}` |

`key` trong transform và `result` trong hai key route cùng là
`{matrix,m,det,gcd,detInverse,adjugate,inverse}`. `blocks` dùng A=0…Z=25, mỗi item
là `{input:number[m],output:number[m]}` và bao gồm cả block padding; backend không
cắt danh sách theo độ dài. Analyze/random không được ghi vào history.

### 4.7 DES

DES mã khối 64 bit với khóa 64 bit, 16 vòng Feistel: sinh khóa PC-1 → C0/D0 → dịch
vòng LS → PC-2 cho K1…K16; mỗi vòng `Li = Ri−1`, `Ri = Li−1 ⊕ P(S(E(Ri−1) ⊕ Ki))`;
đầu ra `IP⁻¹(R16L16)`; giải mã dùng K16…K1. Backend tự cài đặt, không dùng thư viện
mật mã.

- **Khóa:** string đúng 16 ký tự hex sau khi bỏ khoảng trắng ASCII, không phân biệt
  hoa thường. 8 bit chẵn lẻ bị bỏ qua, không kiểm và không sửa: `123456789ABCDEF0`
  cho cùng kết quả với `133457799BBCDFF1`. FE gửi nguyên giá trị người dùng nhập.
- **Chế độ:** `mode` là `ECB` (mặc định) hoặc `CBC`, khớp chính xác (`cbc` bị từ chối).
  `CBC` bắt buộc `iv` 16 hex (cho phép khoảng trắng); `ECB` bỏ qua `iv`.
- **IV sai không bị phát hiện:** với CBC, IV chỉ ảnh hưởng khối 8 byte đầu tiên, nên
  giải mã bằng IV sai vẫn có thể trả **HTTP 200 với 8 byte đầu bị lệch** (ví dụ
  `Hello World, DES CBC!` thành `Hello Wnrld, DES CBC!`), hoặc lỗi UTF-8 nếu các byte
  lệch không còn là UTF-8 hợp lệ. Backend không có cách nào biết IV đúng hay sai; FE
  phải lưu/hiển thị IV cùng bản mã và không được coi HTTP 200 là bằng chứng IV đúng.
  Sai khóa hoặc sai mode (ECB ↔ CBC) thì hầu như luôn ra lỗi padding.
- **Mã hóa:** `inputFormat=text` (mặc định) mã UTF-8 rồi luôn đệm PKCS#7 (đủ bội 8 byte
  vẫn thêm một khối); `inputFormat=hex` nhận hex bội 16 ký tự (cho phép khoảng trắng,
  chữ thường), không đệm. Kết quả luôn là hex in hoa không khoảng trắng.
- **Giải mã:** `text` là bản mã hex (khoảng trắng, xuống dòng, chữ thường đều được).
  `outputFormat=text` (mặc định) gỡ PKCS#7 rồi giải mã UTF-8 nghiêm ngặt;
  `outputFormat=hex` trả nguyên byte dạng hex, không gỡ padding.

Cặp định dạng FE phải giữ:

| Mã hóa với | Giải mã với | Kết quả |
|---|---|---|
| `inputFormat=text` | `outputFormat=text` | Văn bản gốc |
| `inputFormat=hex` | `outputFormat=hex` | Hex gốc |
| `inputFormat=hex` | `outputFormat=text` | Thường lỗi `Padding không hợp lệ: sai khóa hoặc bản mã bị hỏng.` (hoặc lỗi UTF-8) |
| `inputFormat=text` | `outputFormat=hex` | Byte bản rõ kèm byte PKCS#7, ví dụ `Hello World` → `48656C6C6F20576F726C640505050505` |

Vector kiểm nhanh với khóa `133457799BBCDFF1`:

| Request | `result` |
|---|---|
| encrypt hex `0123456789ABCDEF` | `85E813540F0AB405` |
| encrypt text `Hello World` (ECB) | `B1CA74BB3514268701A9ACC3E4E69FAA` |
| encrypt text `Hello World`, CBC, IV `0000000000000000` | `B1CA74BB351426875F9A5BCA734D9EF4` |
| encrypt text `Xin chào DES!` | `06602CF53D9AD6AAC800F8D8643F636C` |
| encrypt hex `0123456789ABCDEF0123456789ABCDEF` (ECB) | `85E813540F0AB40585E813540F0AB405`, kèm W03 |
| decrypt `B1CA74BB3514268701A9ACC3E4E69FAA` | `Hello World` |
| decrypt `85E813540F0AB405`, `outputFormat=hex` | `0123456789ABCDEF` |

Bốn route DES và shape chính xác:

| Method/path | Input | HTTP 200 |
|---|---|---|
| `POST /api/des/encrypt` | `{text, key, inputFormat?, mode?, iv?}` | `{success,result,warnings}` |
| `POST /api/des/decrypt` | `{text, key, outputFormat?, mode?, iv?}` | `{success,result,warnings}` |
| `POST /api/des/trace` | `{block, key, operation?}` | `{success,result,trace,warnings}` |
| `POST /api/des/file` | multipart `file, key, action, mode?, iv?, response_mode?` | `content`: `{success,result,warnings}`; `file`: attachment `text/plain; charset=utf-8` |

`iv` có thể là string hoặc `null`. `text`, `key`, `block`, `iv` gửi kiểu khác (number,
boolean, array, object) hoặc field lạ/trùng (ví dụ gửi `outputFormat` cho encrypt) trả
422 `Dữ liệu gửi lên không hợp lệ.`.

**Trace.** `block` phải là đúng một khối 16 hex sau khi bỏ khoảng trắng; `operation`
là `encrypt` (mặc định) hoặc `decrypt`. Trace không có mode, IV, padding và không
được ghi lịch sử server. Response đầy đủ:

```json
{
  "success": true,
  "result": "85E813540F0AB405",
  "trace": {
    "operation": "encrypt",
    "input": "0123456789ABCDEF",
    "key": "133457799BBCDFF1",
    "pc1": "F0CCAAF556678F",
    "subkeys": [
      {"n": 1, "shift": 1, "c": "E19955F", "d": "AACCF1E", "k": "1B02EFFC7072"}
    ],
    "ip": "CC00CCFFF0AAF0AA",
    "l0": "CC00CCFF",
    "r0": "F0AAF0AA",
    "rounds": [
      {
        "n": 1,
        "subkey": 1,
        "expansion": "7A15557A1555",
        "xorKey": "6117BA866527",
        "sbox": [
          {"row": 0, "col": 12, "value": 5}, {"row": 1, "col": 8, "value": 12},
          {"row": 0, "col": 15, "value": 8}, {"row": 2, "col": 13, "value": 2},
          {"row": 3, "col": 0, "value": 11}, {"row": 2, "col": 3, "value": 5},
          {"row": 0, "col": 10, "value": 9}, {"row": 3, "col": 3, "value": 7}
        ],
        "sboxOutput": "5C82B597",
        "f": "234AA9BB",
        "l": "F0AAF0AA",
        "r": "EF4A6544"
      }
    ],
    "preOutput": "0A4CD99543423234"
  },
  "warnings": []
}
```

Ví dụ trên chỉ in phần tử đầu; response thật luôn có 16 `subkeys` (n = 1…16) và 16
`rounds`. Độ dài hex cố định: `pc1` 14; `c`, `d` 7; `k`, `expansion`, `xorKey` 12;
`l0`, `r0`, `sboxOutput`, `f`, `l`, `r` 8; `input`, `ip`, `preOutput`, `result` 16.
`input` và `key` là giá trị đã chuẩn hóa (chữ hoa, không khoảng trắng). `l`, `r` là
Li, Ri sau vòng; `preOutput` là R16L16. Với `operation=decrypt`, `input` là bản mã,
`result` là bản rõ hex, `rounds[i].subkey` chạy 16 → 1, còn `subkeys` vẫn K1…K16.
`warnings` của trace chỉ có thể là W01/W02.

**Hiển thị từng bước từ trace.** Mọi giá trị trung gian đều do server tính; FE chỉ
định dạng (hex → nhị phân nhóm 4/6/7 bit) và sắp xếp, không tự tính DES. Gợi ý ánh
xạ field → bước của bài giảng:

| Bước | Field trong `trace` | Hiển thị gợi ý |
|---|---|---|
| 1. Sinh khóa | `key` → `pc1` → `subkeys[n].shift/c/d/k` | Bảng 16 dòng `n, shift, Cn, Dn, Kn`; `pc1` = C0D0 (7 hex đầu là C0, 7 hex sau là D0); C16D16 bằng C0D0 |
| 2. Hoán vị IP | `input` → `ip` → `l0`, `r0` | Hai dòng 64 bit trước/sau IP, rồi tách L0/R0 |
| 3. 16 vòng | `rounds[i].l`, `rounds[i].r`, `rounds[i].f`, `rounds[i].subkey` | Bảng 16 dòng `vòng, Kn dùng, f, Li, Ri`; với decrypt, cột khóa con chạy 16 → 1 |
| 4. Hàm f (vòng được chọn) | `expansion` (E), `xorKey` (E ⊕ K), `sbox[0..7]`, `sboxOutput`, `f` (= P(S)) | Chia `xorKey` thành 8 nhóm 6 bit B1…B8; mỗi nhóm hiện `row` (bit đầu + bit cuối), `col` (4 bit giữa), `value` (4 bit) |
| 5. Đầu ra | `preOutput` (R16L16) → `result` (IP⁻¹) | Nhấn mạnh R16 đứng trước L16 |

Server không trả nội dung các bảng PC-1, PC-2, IP, E, P, S1–S8. Nếu muốn tô sáng ô
trong hộp S, FE nhúng bảng S-box tĩnh (lấy từ tài liệu thuật toán) chỉ để hiển thị;
`row`/`col`/`value` từ server là giá trị đúng.

**Trace một khối của văn bản.** `/trace` chỉ nhận đúng một khối hex. Muốn minh họa
khối đầu khi người dùng đang ở `inputFormat=text`:

- ECB: khối đầu là 8 byte đầu của UTF-8 + PKCS#7 dưới dạng hex. Ví dụ `Hello World`
  → `48656C6C6F20576F`, trace ra `B1CA74BB35142687` = 16 hex đầu của bản mã.
- CBC: trace khối `P1 ⊕ IV` (trace không nhận IV). Ví dụ `Hello World`, IV
  `1234567890ABCDEF` → block `5A513A14FF8B9A80`, trace ra `FE6885B7E58524D4` = 16 hex
  đầu của bản mã CBC.

Helper `desPlaintextBlocksHex` và `xorHexBlocks` trong file mẫu làm đúng hai phép này.

**File.** `/api/des/file` kế thừa toàn bộ contract file ở mục 8 (`.txt`, 5 MiB, UTF-8,
BOM, hai request preview/download, filename từ `Content-Disposition`). `action=encrypt`
đọc nội dung file như `inputFormat=text` và trả hex; `action=decrypt` đọc file hex
(nhiều dòng được) và luôn trả văn bản như `outputFormat=text`, nên file không giải mã
được bản mã tạo từ `inputFormat=hex`. Multipart chỉ nhận đúng `file,key,action,mode,iv,
response_mode`; không có `inputFormat`/`outputFormat`. Preview (`content`) có
`warnings`; attachment (`file`) không mang warnings. Tên file là
`<tên>.encrypted.txt`/`<tên>.decrypted.txt` như mọi route file khác.

**Giới hạn và thời gian.** `text` (JSON), `block` (trace) và nội dung file đều tối đa
5 MiB = 5.242.880 byte UTF-8, áp dụng cho **cả hai chiều**. Bản mã hex dài gấp đôi
dữ liệu (cộng khối padding), nên:

- văn bản lớn nhất còn giải mã lại được là **2.621.439 byte UTF-8** (bản mã đúng
  5.242.880 ký tự hex);
- mã hóa văn bản lớn hơn vẫn thành công, nhưng gửi bản mã đó tới `/decrypt` hoặc
  `/file` decrypt sẽ nhận 413. FE nên cảnh báo trước khi mã hóa (helper
  `DES_MAX_ROUND_TRIP_TEXT_BYTES`, `utf8ByteLength`, `desCiphertextHexLength` trong
  file mẫu). Với file có BOM, `File.size` tính cả 3 byte BOM nên phép kiểm này hơi
  thận trọng.

Xử lý 5 MiB mất khoảng **6 giây** mỗi chiều mã hóa (giải mã 5 MiB hex khoảng 3 giây)
trên máy đo của backend; FE phải hiện trạng thái đang xử lý, khóa control và không
đặt timeout ngắn hơn mức này.

## 5. TypeScript contract dùng trực tiếp

Các type legacy dưới đây mô tả năm cipher cũ; Hill và DES dùng các type/helper riêng
trong [`examples/cipher-api.ts`](examples/cipher-api.ts) (`DesEncryptRequest`,
`DesDecryptRequest`, `DesTraceRequest`, `DesFileRequest`, `DesResponse`, `DesWarning`,
`DesTraceResponse`). Caesar text dùng một integer token,
Affine dùng hai integer token; Vigenère, Playfair và Columnar dùng string key. Multipart
truyền mọi scalar dưới dạng string nhưng Affine dùng field `a`/`b`, không dùng `key`.

```ts
export type Cipher =
  | "caesar" | "vigenere" | "playfair" | "affine" | "columnar" | "hill" | "des";
export type StringKeyCipher = "vigenere" | "playfair" | "columnar";
export type Operation = "encrypt" | "decrypt";
export type ResponseMode = "content" | "file";

export interface SuccessResponse {
  success: true;
  result: string;
}

/** Ký tự đệm nhận diện khi giải mã Playfair/Hill (mục A.10). */
export interface PaddingInfo {
  count: number;
  /** Vị trí 0-based trong dãy chữ cái A–Z/a–z của result, tăng dần. */
  positions: number[];
  /** result bỏ các chữ tại positions. */
  filtered: string;
}

/** Playfair decrypt (text và file content mode). */
export interface PlayfairDecryptResponse extends SuccessResponse {
  padding: PaddingInfo;
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
  cipher: Exclude<Cipher, "affine" | "hill" | "des">;
  file: File;
  key: string;
  action: Operation;
  /** Chỉ Playfair, chỉ ảnh hưởng attachment khi giải mã (`strip_padding`). */
  stripPadding?: boolean;
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

Mọi success dùng đúng HTTP `200`. Với năm cipher cũ, success JSON luôn đúng hai trường:

```json
{"success":true,"result":"Khoor Zruog"}
```

Ngoại lệ duy nhất: **Playfair decrypt** (text và file `response_mode=content`) có ba
trường `success,result,padding` (A.10):

```json
{"success":true,"result":"ABXQ","padding":{"count":1,"positions":[3],"filtered":"ABX"}}
```

Với năm cipher cũ, JSON error luôn đúng hai trường, kể cả request `response_mode=file`:

```json
{"success":false,"message":"Khóa phải là số nguyên."}
```

Hill là ngoại lệ: success transform có `blocks,key,warnings` (decrypt thêm `padding`),
success key API có `result,warnings`, và lỗi nghiệp vụ có `code,details`. `ApiError` trong client mẫu
giữ hai field này. DES success có `warnings` (`/trace` thêm `trace`), nhưng lỗi DES
dùng đúng envelope hai trường `{success,message}` như năm cipher cũ; helper DES trong
file mẫu không đọc `code`. Năm cipher cũ không có machine `code`, `detail`, field errors,
`normalizedInput`, matrix hoặc metadata bổ sung. FE phải hiển thị `message` tiếng Việt hợp lệ do server trả về,
nhưng **không dùng nội dung message làm stable identifier hoặc nhánh business**.
Để quản lý UI, dùng request context (cipher/field/action) và HTTP status; message
chỉ dành cho người dùng.

Helper TypeScript framework-neutral bên dưới chỉ nhận response hai trường; Playfair
decrypt dùng `playfairDecrypt`/`playfairPreviewDecryptFile` trong file mẫu để giữ `padding`.

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

curl -sS -X POST http://localhost:8000/api/des/encrypt \
  -H 'Content-Type: application/json' \
  -d '{"text":"0123456789ABCDEF","key":"133457799BBCDFF1","inputFormat":"hex"}'
# {"success":true,"result":"85E813540F0AB405","warnings":[]}

curl -sS -X POST http://localhost:8000/api/des/encrypt \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello World","key":"133457799BBCDFF1"}'
# {"success":true,"result":"B1CA74BB3514268701A9ACC3E4E69FAA","warnings":[]}

curl -sS -X POST http://localhost:8000/api/des/decrypt \
  -H 'Content-Type: application/json' \
  -d '{"text":"B1CA74BB3514268701A9ACC3E4E69FAA","key":"133457799BBCDFF1"}'
# {"success":true,"result":"Hello World","warnings":[]}

curl -sS -X POST http://localhost:8000/api/des/trace \
  -H 'Content-Type: application/json' \
  -d '{"block":"0123456789ABCDEF","key":"133457799BBCDFF1"}'
# {"success":true,"result":"85E813540F0AB405","trace":{...},"warnings":[]}

# Representative text error: Vigenère key có khoảng trắng
curl -sS -i -X POST http://localhost:8000/api/vigenere/encrypt \
  -H 'Content-Type: application/json' \
  -d '{"text":"Attack","key":"LE MON"}'
# HTTP 422; {"success":false,"message":"Khóa Vigenère chỉ được chứa chữ cái A-Z hoặc a-z."}
```

Đổi `encrypt` thành `decrypt` và truyền ciphertext tương ứng để gọi năm endpoint
decrypt. Ví dụ Playfair decrypt trả normalized/prepared plaintext thô kèm `padding`
(A.10), không phục hồi input.

## 8. File flow

### 8.1 Multipart contract

Ba route Caesar/Vigenère/Playfair dùng:

| Field | Bắt buộc | Giá trị |
|---|---:|---|
| `file` | Có | File có filename kết thúc bằng `.txt`, không phân biệt hoa thường |
| `key` | Có | String trong multipart; policy phụ thuộc cipher |
| `action` | Có | Chính xác `encrypt` hoặc `decrypt` |
| `response_mode` | Không | `content` hoặc `file`; mặc định `content` |
| `strip_padding` | Không (chỉ Playfair) | `true` hoặc `false`; mặc định `false` |

Không tự đặt `Content-Type` khi gửi `FormData`; browser phải thêm multipart boundary.
`action`, `response_mode` và `strip_padding` phân biệt hoa thường.

`strip_padding` chỉ đổi **attachment** của Playfair khi `action=decrypt`: `true` trả bản
lọc (`padding.filtered`), `false`/bỏ trống trả bản thô. Preview `content` luôn trả
`{success,result,padding}` với `result` thô; encrypt bỏ qua giá trị hợp lệ. Giá trị khác
`true`/`false` (kể cả `TRUE`, `1`, chuỗi rỗng) trả 422. Gửi trường này theo trạng thái
toggle lọc ký tự đệm (A.10); Caesar/Vigenère không đọc nó.

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

Route DES dùng exact field set `file,key,action` và optional `mode` (`ECB` mặc định
hoặc `CBC`), `iv` (16 hex, chỉ đọc khi `CBC`), `response_mode`; field lạ (kể cả
`inputFormat`) hoặc trùng bị từ chối, key upload part bị từ chối. Xem mục 4.7.

Route Columnar cũng dùng exact field set, gồm required `file,key,action` và optional
`response_mode`. `file` phải là upload part có filename; scalar `file` là invalid
body, còn upload part với `filename=""` đi đến lỗi extension `415`. MIME khai báo
không quyết định validity. `key` phải là scalar string theo §4.5; key upload part,
field lạ hoặc duplicate đều bị từ chối. OpenAPI mô tả key bằng prose cùng examples
`3 1 4 2`, `BALLOON`, không dùng `pattern`, `oneOf` hoặc raw `maxLength` gây hiểu sai.

### 8.2 Hai request bắt buộc

1. Preview: gửi file gốc với `response_mode=content`; nhận HTTP `200`,
   `application/json` và đúng JSON `{success,result}` (DES: `{success,result,warnings}`;
   Playfair decrypt: `{success,result,padding}`).
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
  if (input.cipher === "playfair" && input.stripPadding !== undefined) {
    data.append("strip_padding", String(input.stripPadding));
  }
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

# Playfair decrypt, tải bản đã lọc ký tự đệm
curl -sS -OJ -X POST http://localhost:8000/api/playfair/file \
  -F 'file=@cipher.txt;type=text/plain' -F 'key=PLAYFAIR EXAMPLE' \
  -F 'action=decrypt' -F 'response_mode=file' -F 'strip_padding=true'

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

# DES preview: CBC cần iv; content mode có warnings
curl -sS -X POST http://localhost:8000/api/des/file \
  -F 'file=@input.txt;type=text/plain' -F 'key=133457799BBCDFF1' \
  -F 'action=encrypt' -F 'mode=CBC' -F 'iv=0000000000000000' -F 'response_mode=content'

# DES official attachment: input.encrypted.txt, không mang warnings
curl -sS -OJ -X POST http://localhost:8000/api/des/file \
  -F 'file=@input.txt;type=text/plain' -F 'key=133457799BBCDFF1' \
  -F 'action=encrypt' -F 'mode=CBC' -F 'iv=0000000000000000' -F 'response_mode=file'

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
  Caesar/Vigenère/Affine/Columnar và DES encrypt
  nhưng không hợp lệ với Playfair sau normalization và DES decrypt (E01).
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
| Playfair | Bị loại khi normalize | Bị loại | Uppercase ASCII, `J→I`, decrypt giữ filler `X/Q` (lọc qua `padding`/`strip_padding`) |
| Affine | Giữ nguyên | Giữ nguyên | Chỉ ASCII letter đổi, giữ case; round-trip lossless |
| Columnar | Hoán vị nguyên trạng | Hoán vị theo code point | Không đổi code point; round-trip lossless |
| DES | encrypt: là dữ liệu (UTF-8 + PKCS#7); decrypt: khoảng trắng/xuống dòng bị bỏ khỏi hex | encrypt: mã theo byte UTF-8 | encrypt ra hex in hoa; decrypt ra văn bản gốc; lossless |

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
| `422` | `strip_padding` của Playfair file khác `true`/`false` | `Tùy chọn lọc ký tự đệm phải là true hoặc false.` |
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
→ strip_padding (chỉ Playfair)
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

### 9.1 Lỗi và cảnh báo Hill

Mọi lỗi nghiệp vụ từ bốn route Hill có đúng envelope
`{success:false,message:string,code:string,details:object}`. FE hiển thị `message`,
nhưng branch/focus control theo `code` và `details`; không branch theo câu tiếng Việt.

| Code | HTTP | Ý nghĩa / `details` hữu ích |
|---|---:|---|
| E01 | 422 | `text` thiếu, null hoặc blank |
| E02 | 422 | Sau chuẩn bị không có ASCII letter để xử lý |
| E03 | 422 | Dạng key/matrix sai; `reason` là `key_variant`, `invalid_shape` hoặc `invalid_cell`; cell sai có `row`/`column` 1-based |
| E04 | 422 | Key không khả nghịch; `det`, `gcd`, `divisor` |
| E05 | 422 | Ciphertext không đủ block khi decrypt; `n`, `m` |
| E06 | 413 | `text` vượt 5 MiB UTF-8; `actualBytes`, `maxBytes` |
| E07 | — | Chỉ FE phát sinh khi file không phải UTF-8; không có response backend |
| E08 | 422 | `m` ngoài 2–4, thiếu/trùng/sai token; `min`, `max`, có thể có `m` |
| E09 | 422 | Keyword không đúng `m²` ASCII letter; `m`, `expected`, `actual` (số ASCII letter hợp lệ, hoặc `null` nếu sai kiểu) |
| E10 | 422 | `options`/`stripDiacritics`/`padChar` sai; `field` |
| E11 | 422 | Media type/JSON/object/member/kiểu dữ liệu không hợp lệ; `details={}` |

Lỗi 500 bất ngờ và guard hạ tầng 64 MiB dùng envelope chung `{success,message}`,
không giả thành E-code. Precedence transform ổn định:

```text
guard 64 MiB
→ media type / JSON / object / duplicate / unknown / surrogate (E11)
→ byte length của text string (E06)
→ text thiếu/null/blank (E01) hoặc sai kiểu (E11)
→ key shape/value/m/keyword (E03/E08/E09)
→ options (E10)
→ key invertibility (E04)
→ không có ASCII letter sau chuẩn bị (E02)
→ decrypt ciphertext không chia hết block (E05)
```

Analyze chỉ chạy các bước wire/key/invertibility liên quan; random chỉ validate query
`m`. Backend trả lỗi đầu tiên, nên FE không suy ra các field phía sau đã hợp lệ.

Warning không chặn HTTP 200 và luôn có `{code,message,details}` theo thứ tự W01,
W02, W03:

| Code | Khi nào | `details` |
|---|---|---|
| W01 | Encrypt thêm padding | `{count,char,m}` |
| W02 | Có chữ Việt có dấu được giữ nguyên vì `stripDiacritics=false` | `{count}` |
| W03 | Key là identity hoặc self-inverse | `{reason:"identity"|"self_inverse"}` |

W01 chỉ có ở encrypt; W02 chỉ ở transform; W03 có thể có ở cả bốn route. Decrypt
không xóa padding khỏi `result`; FE chọn hiển thị `result` hoặc `padding.filtered`
theo toggle lọc ký tự đệm (A.10) và luôn hiển thị warning server trả.

### 9.2 Lỗi và cảnh báo DES

Mọi lỗi của bốn route DES là đúng `{"success":false,"message":"<tiếng Việt>"}`, kể cả
khi `response_mode=file` (không có attachment). Không có `code`/`details`; mã DES-Exx
dưới đây chỉ để đối chiếu tài liệu/test. FE hiển thị nguyên `message` và gắn lỗi vào
control theo request context, không branch theo câu chữ. `{n}` là số ký tự sau khi bỏ
khoảng trắng ASCII; `{name}` là tên field.

| Mã | HTTP | Khi nào | `message` |
|---|---:|---|---|
| Body | 422 | Media type không phải JSON, JSON hỏng/không phải object, field lạ hoặc trùng, `text`/`key`/`block`/`iv` không phải string và khác null; multipart field lạ/trùng, `file` không phải upload, key là upload, multipart bị cắt | `Dữ liệu gửi lên không hợp lệ.` |
| E01 | 422 | `text` thiếu/null/rỗng; dữ liệu hex (encrypt hex, decrypt, file decrypt) rỗng sau khi bỏ khoảng trắng | `Nhập văn bản hoặc tải file .txt để bắt đầu.` |
| E02 | 422 | `key` thiếu/null/rỗng sau khi bỏ khoảng trắng | `Thiếu khóa. Khóa DES gồm 16 ký tự hex (64 bit).` |
| E03 | 422 | Khóa có ký tự ngoài `0–9`, `a–f`, `A–F` | `Khóa chỉ được chứa ký tự hex 0–9, A–F.` |
| E04 | 422 | Khóa hex khác 16 ký tự | `Khóa phải đúng 16 ký tự hex (64 bit), hiện có {n}.` |
| E05 | 422 | Dữ liệu hex có ký tự không hợp lệ | `Dữ liệu hex chỉ được chứa ký tự hex 0–9, A–F.` |
| E06 | 422 | Dữ liệu hex không phải bội 16 ký tự | `Dữ liệu hex phải có độ dài là bội của 16 ký tự hex (64 bit), hiện có {n}.` |
| E07 | 422 | Giải mã ra text nhưng PKCS#7 sai (thường do sai khóa, sai mode, hoặc bản mã từ `inputFormat=hex`). **IV sai không gây E07**: xem mục 4.7 | `Padding không hợp lệ: sai khóa hoặc bản mã bị hỏng.` |
| E08 | 422 | Giải mã ra byte không phải UTF-8 | `Kết quả giải mã không phải văn bản UTF-8 hợp lệ. Thử outputFormat = hex.` |
| E09 | 422 | `mode=CBC` mà `iv` thiếu/null/không đúng 16 hex | `IV phải đúng 16 ký tự hex khi dùng chế độ CBC.` |
| E10 | 422 | `inputFormat`, `outputFormat`, `mode`, `operation` sai giá trị, sai kiểu hoặc `null` | `Tham số {name} không hợp lệ.` |
| E11 | 415/413/422/500 | Lỗi file: dùng message file hiện hành của mục 9 | `Chỉ chấp nhận file .txt.`, `File phải sử dụng UTF-8.`, `File vượt quá dung lượng tối đa 5 MB.`, `Thiếu file.`, `File không được để trống.`, `Action phải là encrypt hoặc decrypt.`, `Response mode phải là content hoặc file.`, `Không thể đọc file.` |
| E12 | 413 | UTF-8 của `text`/`block` vượt 5.242.880 byte (cả encrypt lẫn decrypt) | `Dữ liệu vượt quá 5 MiB.` |
| E13 | 422 | `/trace` với `block` thiếu/null/rỗng/không phải đúng 16 hex | `Trace chỉ áp dụng cho đúng 1 khối 16 ký tự hex.` |
| Guard | 413 | `Content-Length` hợp lệ > 64 MiB: route JSON DES | `Yêu cầu vượt quá dung lượng cho phép.` |
| Guard | 413 | `Content-Length` hợp lệ > 64 MiB: `/api/des/file` | `File vượt quá dung lượng tối đa 5 MB.` |
| — | 500 | Lỗi bất ngờ | `Đã xảy ra lỗi hệ thống.` |

Thứ tự lỗi JSON DES (dừng ở lỗi đầu tiên):

```text
guard 64 MiB
→ body: media type / JSON / object / field lạ, trùng / kiểu string field
→ 5 MiB của text/block (E12)
→ E10: inputFormat|outputFormat → mode → operation
→ khóa: E02 → E03 → E04
→ IV khi mode=CBC (E09)
→ dữ liệu: E01/E05/E06 (hoặc E13 với /trace)
→ khi giải mã: E07 → E08
```

Thứ tự lỗi file DES:

```text
guard 64 MiB / multipart framing
→ exact field set / duplicate
→ file presence/type
→ khóa (E02/E03/E04)
→ action → response_mode → mode (E10) → IV khi CBC (E09)
→ extension → 5 MiB → 0 byte → UTF-8
→ nội dung hex khi decrypt (E01/E05/E06) → E07 → E08
```

Ví dụ: body có field lạ thắng mọi lỗi khác; `mode:"XYZ"` thắng khóa sai; khóa 8 ký tự
thắng thiếu IV và text rỗng; với file, thiếu file thắng khóa, khóa sai thắng `action`
sai và extension sai.

Cảnh báo không chặn HTTP 200, luôn là object `{code,message,details}` theo thứ tự W01
→ W02 → W03, mỗi mã tối đa một lần:

| Code | Khi nào | `message` | `details` |
|---|---|---|---|
| W01 | Khóa yếu (so sánh sau khi xóa bit chẵn lẻ); mọi route dùng khóa: encrypt, decrypt, file content cả hai chiều, trace | `Khóa yếu: mã hóa hai lần sẽ trả lại bản rõ. Không nên dùng.` | `{}` |
| W02 | Khóa nửa yếu; cùng phạm vi W01 | `Khóa nửa yếu: tồn tại khóa khác giải mã được bản mã của khóa này.` | `{}` |
| W03 | Chỉ khi mã hóa `ECB` (JSON encrypt hoặc file `action=encrypt`, content mode) và bản mã có ít nhất hai khối 8 byte giống nhau | `Chế độ ECB: có khối bản mã lặp lại, lộ cấu trúc bản rõ. Cân nhắc dùng CBC.` | `{"repeatedBlocks": <số khối trùng một khối trước nó>}` |

Ví dụ: encrypt hex `0123456789ABCDEF0123456789ABCDEF` với `133457799BBCDFF1` (ECB) trả
W03 `repeatedBlocks: 1`; cùng dữ liệu ở CBC không có warning. Encrypt hex
`00000000000000000000000000000000` với khóa `0000000000000000` trả `[W01, W03]`.
Attachment `response_mode=file` không mang warnings; nếu UI cần hiện cảnh báo cho file,
lấy từ response preview.

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
| Toggle lọc ký tự đệm, đánh dấu vị trí đệm | Nhận diện ký tự đệm (`padding`) và attachment theo `strip_padding` |
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
- tự xóa filler Playfair/padding Hill ngoài `padding.filtered`, hoặc phục hồi formatting
  bằng heuristic;
- dùng preview Blob làm official download cho nguồn file;
- branch business logic theo chuỗi message tiếng Việt.

## 11. UI state và transition

State tối thiểu:

```text
cipher     = caesar | vigenere | playfair | affine | columnar | hill | des
mode       = encrypt | decrypt
source     = text | file
text/file  = input hiện tại
key/a/b    = raw input theo cipher; Hill thêm keyVariant, matrix/keyword, m
options    = Hill stripDiacritics, padChar; DES format (text|hex), mode (ECB|CBC), iv
filterPad  = boolean; toggle lọc ký tự đệm cho Playfair/Hill decrypt (A.10)
result     = null | server result
loading    = boolean
error      = null | user-facing message
view       = result | analysis
```

| Event | State bắt buộc | UX |
|---|---|---|
| Mở trang | `cipher=caesar`, `mode=encrypt`, `source=text`, `result=null`, `loading=false` | Action disabled tới khi hợp lệ |
| Đổi cipher | Xóa result/analysis/error; validate lại key/input/options | Đổi key hint và warning phù hợp |
| Đổi encrypt/decrypt | Giữ input/key/a/b nếu phù hợp; xóa stale result/error | Đổi label plaintext/ciphertext |
| Đổi text/file | Bắt buộc giữ draft riêng của text và file; xóa result/error | Hiện panel nguồn mới |
| Sửa text, file, key, `a`, `b`, Hill key variant/`m`/option, DES format/mode/IV | Xóa result/analysis/error | Validate lại ngay |
| Submit preview/text | Xóa result; `loading=true` | Khóa control và chặn submit lặp |
| Success | Lưu đúng server response; xóa error | Hill giữ cả blocks/key/warnings; DES giữ warnings (và trace); mở copy/download phù hợp nguồn |
| API/network failure | `result=null`, xóa analysis; lưu fallback/message | Mở khóa để retry |
| Download click | Năm cipher cũ hoặc DES + nguồn file: request file mode lần hai | Không áp dụng `/file` cho Hill; Hill có thể tạo Blob từ `result` JSON đã nhận |
| Download failure | Xóa trạng thái success cũ | Hiện lỗi, không kích hoạt download |
| Đổi toggle lọc ký tự đệm | Giữ result; chỉ đổi giá trị hiển thị (`result` ↔ `padding.filtered`) | Không gửi request; với file Playfair, lần tải kế tiếp gửi `strip_padding` mới |
| Clear output | Chỉ xóa result/analysis | Giữ input/key/a/b |
| Reset | Xóa toàn bộ state/draft/result/error; đưa status về neutral và view về result | Quay lại `caesar` + `encrypt` + `text` |

Playfair phải có cảnh báo luôn nhìn thấy trước submit hoặc cạnh result:

> Playfair chuẩn hóa thành chữ hoa ASCII, gộp J/I, loại định dạng; khi giải mã, bản
> thô giữ mọi filler X/Q, bộ lọc ký tự đệm có thể bỏ nhầm X/Q thật; kết quả không khôi
> phục nguyên văn đầu vào.

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
- [ ] Với năm cipher cũ, error parser nhận `{success:false,message}`; với Hill giữ thêm
  `code,details`. Không branch theo nội dung message.
- [ ] Cập nhật OpenAPI snapshot/generated types nếu FE thực sự dùng chúng; thêm
  contract test đếm đúng 15 route và test Columnar text/preview/download/error.
- [ ] Gỡ mock, `USE_MOCK`, local cipher result và `API_BASE` ghi cứng trong code.
- [ ] Dev server proxy `/api` tới backend (`8080` khi chạy compose, `8000` khi chạy uv);
  không yêu cầu CORS.
- [ ] Health check dùng `GET /api/health`, không dùng `/health`.

## 13. Hành vi demo cũ không được sao chép

[`Caesar_Cipher_Tool_Demo.html`](../Caesar_Cipher_Tool_Demo.html) chỉ là reference UI cũ.
Không sao chép:

- giới hạn `1 MB` thay vì 5 MiB;
- `_encrypted.txt`/`_decrypted.txt` thay vì `.encrypted.txt`/`.decrypted.txt`;
- mock API, `USE_MOCK` hoặc local Caesar service;
- `API_BASE=http://localhost:8080` hay backend URL hard-coded;
- CORS như một yêu cầu mặc định cho dev;
- bỏ `response_mode` hoặc tải file từ preview Blob;
- message/label tiếng Anh; không thêm `code` cho năm cipher cũ và DES (Hill có contract riêng);
- bất kỳ client-generated production result nào.

`affine-cipher.html` là reference ngoài repository chỉ xác nhận công thức, residue hợp lệ
và vector `HELLO → RCLLA`. Các điểm cố ý khác production là default UI `(5,8)`,
input `type=number`/JavaScript `Number`, validation message động và kết quả tính
client-side: không điểm nào là wire contract hay result authority. Runtime/OpenSpec
hiện tại luôn thắng demo.

## 14. Acceptance checklist

- [ ] Cả 22 POST transform, bốn POST helper/trace/keygen và GET random Hill được chọn
  đúng theo cipher/source/operation.
- [ ] Caesar vector `Hello World`, key `3` cho `Khoor Zruog` và decrypt đúng chiều ngược lại.
- [ ] Vigenère vector `Attack at dawn!`/`LEMON` cho `Lxfopv ef rnhr!` và decrypt đúng.
- [ ] Playfair canonical vector cho `BMODZBXDNABEKUDMUIXMMOUVIF`: decrypt trả `result` thô `HIDETHEGOLDINTHETREXESTUMP` và `padding.filtered` `HIDETHEGOLDINTHETREESTUMP`.
- [ ] Playfair `XX→XQXQ→GWGW`, `ABX→ABXQ→PDGW`; decrypt `PDGW→ABXQ` (lọc `ABX`), `GWGW→XQXQ` (lọc `XX`) đều đúng.
- [ ] Affine `HELLO→RCLLA→HELLO` với `(5,8)` và mixed/Unicode/CRLF giữ đúng contract.
- [ ] Affine có đúng 12 residue `a'`, 26 residue `b'` và 312 cặp normalized hợp lệ.
- [ ] Columnar `ABCDE → BDAEC → ABCDE` với `3 1 4 2`, keyword `BALLOON` và
  Unicode/CRLF/uneven/`m>n` round-trip đúng contract, không padding/normalize.
- [ ] Hill `HELP → DPLE → HELP` với T01; `blocks` xác nhận vector hàng `x·K`, không
  dùng quy ước cột `K·x`.
- [ ] Hill matrix variant không gửi `m`; keyword variant gửi đúng `keyword,m`; analyze
  và random trả cùng shape phân tích key như transform.
- [ ] Hill padding chỉ thêm ở encrypt; decrypt giữ padding trong `result` và trả
  `padding` (`DPDKKB → HELLOX`, lọc `HELLO`); warning luôn theo thứ tự W01, W02, W03 và
  UI giữ nguyên `blocks`, `key`, `warnings`, `padding` từ server.
- [ ] Toggle lọc ký tự đệm đổi giữa `result` và `padding.filtered` mà không gọi lại API;
  bản thô luôn xem được; file Playfair tải về gửi `strip_padding` theo toggle; khung
  Phân tích Hill có phần "Lọc ký tự đệm".
- [ ] Hill file được FE kiểm `.txt`, tối đa 5 MiB raw bytes và UTF-8 fatal/E07 trước
  khi gọi JSON; không gọi hoặc giả lập `/api/hill/file`.
- [ ] DES T01 `0123456789ABCDEF` + `133457799BBCDFF1` (hex) → `85E813540F0AB405` → hex
  gốc; `Hello World` → `B1CA74BB3514268701A9ACC3E4E69FAA` → `Hello World`; CBC IV
  `0000000000000000` → `B1CA74BB351426875F9A5BCA734D9EF4`.
- [ ] DES giữ cặp `inputFormat`/`outputFormat` (text ↔ text, hex ↔ hex); `iv` chỉ gửi
  khi CBC; enum gửi đúng hoa thường (`ECB`, `CBC`, `text`, `hex`).
- [ ] DES hiển thị `warnings` W01/W02/W03 theo thứ tự server trả; trace hiển thị đủ 16
  khóa con và 16 vòng, decrypt có `subkey` 16 → 1.
- [ ] DES lỗi đọc như envelope hai trường; file DES preview/download hai request, tên
  `.encrypted.txt`/`.decrypted.txt`.
- [ ] DES có trạng thái đang xử lý cho input lớn (khoảng 6 giây với 5 MiB) và cảnh báo
  trước khi mã hóa văn bản lớn hơn 2.621.439 byte UTF-8.
- [ ] DES CBC lưu/hiển thị IV cùng bản mã và không coi HTTP 200 khi giải mã là bằng
  chứng IV đúng (IV sai chỉ làm lệch 8 byte đầu); ECB ẩn hoặc vô hiệu ô IV.
- [ ] DES trace chỉ hiển thị giá trị server trả; muốn trace khối đầu của văn bản thì
  dùng `desPlaintextBlocksHex` (và `xorHexBlocks` với IV khi CBC), kết quả trace phải
  bằng 16 hex đầu của bản mã.
- [ ] RSA chỉ gọi đúng bốn endpoint bằng URL tương đối; crypto integer là decimal
  string, control integer là JSON integer theo exact request variant.
- [ ] RSA number/char/block response giữ exact shape và `trace:null|object`; block
  decrypt gửi lại nguyên `cipher` + `originalUtf8ByteLength`, không trim/normalize
  BOM, newline, Unicode composition hoặc trailing NUL.
- [ ] RSA multipart chỉ encrypt plaintext `.txt` tại `/api/rsa/encrypt`, dùng
  `FormData` không tự đặt `Content-Type`, không gửi `action/response_mode`, và luôn
  đọc JSON; error xử lý theo `{success,code,message,field}`.
- [ ] RSA UI luôn cảnh báo textbook/insecure, không claim phát hiện wrong key; nếu có
  history thì chỉ hai transform được ghi metadata best-effort, keygen bị loại.
- [ ] FE không tự strip filler ngoài `padding.filtered` và hiển thị cảnh báo Playfair không lossless.
- [ ] Caesar text gửi một JSON integer; Affine gửi hai integer `a,b`;
  Vigenère/Playfair/Columnar gửi string key.
- [ ] Affine integer ngoài JS safe range không bị chuyển qua `number` hoặc làm tròn.
- [ ] FE không trim/rewrite text, string key hoặc multipart key trước khi gửi; raw
  numeric JSON state chỉ được canonicalize thành number token ở serializer.
- [ ] Whitespace-only: Caesar/Vigenère/Affine/Columnar thành công, Playfair trả normalized-empty 422.
- [ ] Vigenère giữ Unicode/CRLF và không làm key tiến; Caesar giữ non-ASCII/CRLF.
- [ ] Playfair loại Unicode/CRLF/format và trả uppercase ASCII.
- [ ] Validation hiển thị server message nhưng không dùng message làm identifier.
- [ ] Năm cipher cũ và DES giữ envelope lỗi hai field; Hill giữ exact envelope mở rộng và
  `code/details` cho lỗi nghiệp vụ.
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

1. Primary authority: spec hiện hành trong [`openspec/specs/`](../openspec/specs/)
   (mỗi capability một file, ví dụ `text-cipher-api`, `history-api`, `app-runtime`);
   lịch sử quyết định nằm trong [`openspec/changes/archive/`](../openspec/changes/archive/).
   Riêng RSA đã ship nhưng change chưa sync/archive, accepted Q1–Q16 cùng hai làm rõ
   corrective R1–R2 tại
   [`openspec/changes/add-rsa-cipher/`](../openspec/changes/add-rsa-cipher/) là authority;
   Q16 thay thế riêng quyết định no-history bằng safe transform metadata; R1–R2
   reconcile hai error edge mà không mở rộng API. UI không có spec ở backend: giao
   diện thuộc project FE. Sau spec là
   current implementation/tests cho observed behavior; cuối cùng runtime
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
[`routes_hill.py`](../app/api/routes_hill.py) và
[`hill_schemas.py`](../app/api/hill_schemas.py),
[`routes_des.py`](../app/api/routes_des.py),
[`routes_des_file.py`](../app/api/routes_des_file.py) và
[`des_schemas.py`](../app/api/des_schemas.py),
[`routes_rsa.py`](../app/api/routes_rsa.py),
[`rsa_schemas.py`](../app/api/rsa_schemas.py) và contract FE chuyên biệt
[`rsa-frontend-contract.md`](rsa-frontend-contract.md),
[`routes_health.py`](../app/api/routes_health.py) và
[`routes_history.py`](../app/api/routes_history.py). File mẫu
[`examples/cipher-api.ts`](examples/cipher-api.ts) phải được cập nhật cùng tài liệu
khi contract đổi.

Guide không lặp toàn bộ ma trận scenario hoặc decision history của OpenSpec. Khi
API/behavior thay đổi, cập nhật OpenSpec trước, rồi cập nhật guide này trong cùng
change. Không thêm `/v1`, endpoint, field hoặc behavior mới chỉ bằng cách sửa tài liệu.

## 16. Health và lịch sử thao tác

Backend có thể chạy với SQLite cục bộ trên máy BE. Khi bật, mỗi request tới 22 route biến đổi được
ghi lại dưới dạng **metadata**. Backend không lưu text, key, IV, tên file, nội dung file
hay kết quả. Hai route khóa Hill, hai route khóa RSA và `/api/des/trace` không được ghi.
Hai RSA transform được ghi kể cả request lỗi, nhưng không lưu key/data/cipher array,
metadata lossless hoặc trace. Contract của các route hiện hữu không đổi.

### 16.1 Chạy backend có SQLite khi dev FE

Cần Docker. Trong thư mục repo backend:

```bash
cp .env.example .env
docker compose up -d --build  # migrate + one-process app, cùng SQLite volume
curl -s http://localhost:8080/api/health
# {"success":true,"result":{"app":"ok","database":"ok","history":"enabled"}}
```

- Backend ở `http://localhost:8080`; proxy `/api` của FE dev server về đây.
- Dữ liệu lịch sử được giữ qua các lần khởi động lại trong named volume local. Không
  dùng `docker compose down -v`; backup ngoài volume và restore rehearsal mới là
  bằng chứng phục hồi.
- Muốn thử màn hình lịch sử khi không có DB: chạy backend bằng
  `HISTORY_API_ENABLED=true uv run uvicorn app.main:app --port 8000` mà không đặt
  `DATABASE_URL`; khi đó `database` là `disabled` và `/api/history` trả 503. Nếu
  không bật flag (mặc định), `/api/history` trả 404 trước khi kiểm tra DB.
- Tạo dữ liệu mẫu: gọi vài request encrypt/decrypt bất kỳ qua `/docs` hoặc `curl`, mỗi
  request sinh một dòng lịch sử.
- Deploy backend mới theo thứ tự SQLite migrate-first rồi mới restart đúng một app
  process. Không chạy hoặc stamp migration PostgreSQL `0001`–`0004` trên SQLite.

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
| `cipher` | `caesar`, `vigenere`, `playfair`, `affine`, `columnar`, `hill`, `des`, `rsa` | tất cả |
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

- `source`: `text` cho route JSON, `file` cho route multipart. DES và RSA encrypt có
  thể có cả hai; RSA decrypt chỉ có `text`.
- `operation`: `null` khi request lỗi trước lúc backend đọc được `action` của file.
- `responseMode`: `content` hoặc `file` cho route file truyền thống; RSA luôn `null`.
- `inputLength`/`outputLength`: số Unicode code point với text, số byte UTF-8 với
  file (tính cả BOM nếu file gửi lên có BOM); `null` khi request lỗi trước lúc đo được.
  Riêng RSA: number để cả hai null; text encrypt chỉ input length; text decrypt chỉ
  output length; multipart encrypt chỉ input raw-byte length vì phía còn lại là cipher array.
- `httpStatus`/`succeeded`: status backend đã trả; `succeeded` đúng khi status 2xx.
  Request lỗi (413/415/422/500) cũng có trong lịch sử.

```ts
type HistoryItem = {
  id: number;
  createdAt: string; // ISO 8601
  cipher: "caesar" | "vigenere" | "playfair" | "affine" | "columnar" | "hill" | "des" | "rsa";
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
curl -s 'http://localhost:8080/api/history?limit=5&cipher=rsa'
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
- Server mặc định giữ 30 ngày gần nhất, có thể cấu hình 1–3650 ngày bằng
  `HISTORY_RETENTION_DAYS` (purge có thể lệch tối đa 6 giờ). Không có API xóa.

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
- Với Hill, lưu đúng key variant đã gửi (`{key:number[][]}` hoặc `{keyword,m}`),
  không lưu `blocks`, phân tích inverse hoặc warnings nếu UI không cần xem lại chúng.
- Với DES, lưu khóa, `mode`, `iv` (khi CBC) và định dạng đã dùng để xem lại được đúng
  cặp `inputFormat`/`outputFormat`; không cần lưu `trace`. Kết quả DES có thể dài tới
  10 MiB hex, dễ vượt quota `localStorage`: cân nhắc chỉ lưu kết quả ngắn.

### 17.2 Mẫu code

```ts
const STORAGE_KEY = "cipher-workbench.history.v1";
const ENABLED_KEY = "cipher-workbench.history.enabled";
const MAX_ENTRIES = 50;

type LocalHistoryEntry = {
  at: string; // new Date().toISOString()
  cipher: "caesar" | "vigenere" | "playfair" | "affine" | "columnar" | "hill" | "des";
  operation: "encrypt" | "decrypt";
  source: "text" | "file";
  input: string;          // text nhập, hoặc tên file với source "file"
  key:
    | { key: string }                    // Caesar/Vigenère/Playfair/Columnar
    | { a: string; b: string }           // Affine
    | { key: number[][] }                // Hill matrix
    | { keyword: string; m: 2 | 3 | 4 }  // Hill keyword
    | { key: string; mode: "ECB" | "CBC"; iv?: string; format: "text" | "hex" }; // DES
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
| Nơi lưu | `localStorage` trên máy người dùng | SQLite cục bộ trên backend |
| Ai xem được | Người dùng trên đúng trình duyệt đó | Ai gọi được `/api/history` khi cờ bật |
| Nội dung | Input, key, kết quả | Chỉ metadata, không có nội dung |
| Thời hạn | Đến khi người dùng xóa (tối đa 50 mục) | Mặc định 30 ngày; cấu hình 1–3650 ngày |
| Mục đích | Xem lại thao tác của mình | Thống kê và theo dõi vận hành |
