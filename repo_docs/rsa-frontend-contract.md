# Hợp đồng tích hợp Frontend — RSA textbook

Tài liệu này là contract dành cho FE của phần RSA đã ship. Nó bổ sung cho
[`frontend-integration.md`](frontend-integration.md): guide chung giữ phần bắt đầu nhanh,
history và quy ước toàn hệ thống; file này là nơi tra cứu chi tiết duy nhất cho wire
contract RSA. Không suy ra endpoint hoặc field ngoài những gì được ghi ở đây.

> **Cảnh báo sản phẩm bắt buộc:** đây là textbook RSA để học thuật toán. Random
> keygen chỉ hỗ trợ modulus 16/32/64/128 bit; manual key có thể nhỏ hơn và chịu các
> giới hạn riêng. Không có OAEP, chữ ký hay xác thực dữ liệu; không bảo vệ dữ liệu
> thật và không phát hiện đáng tin cậy khóa/metadata sai.

## 1. Tóm tắt bắt buộc

- FE gọi URL tương đối `/api/...`; không ghi cứng host, port hoặc `/v1`.
- Có đúng bốn RSA endpoint, đều là `POST`.
- Crypto integer đi trên wire bằng **decimal string**, không dùng JSON number,
  hex hoặc base64. `bits`, `traceBlockIndex` và `originalUtf8ByteLength` là JSON
  integer thật theo từng request shape.
- JSON RSA chỉ nhận base media type `application/json`. Có thể có parameter như
  `application/json; charset=utf-8`, nhưng **không có cam kết nhận
  `application/*+json`**.
- Chỉ `/api/rsa/encrypt` nhận thêm `multipart/form-data`, và chỉ để mã hóa plaintext
  `.txt`. Không có upload ciphertext, `/api/rsa/file`, `/api/rsa/trace` hoặc download.
- Mọi response RSA, kể cả multipart và mọi lỗi, đều là JSON.
- Request strict: field lạ, field trùng, field không áp dụng và thiếu field bắt buộc
  đều bị từ chối. Không gửi object dùng chung có field thừa.
- `mode="block"` tạo một cipher package lossless. FE phải giữ nguyên
  `cipher`, `mode` và `originalUtf8ByteLength` để giải mã.
- `trace` luôn có mặt: mặc định `null`, hoặc full trace của đúng một block khi gửi
  `traceBlockIndex`.
- `blocks`, `cipher`, `egcdSteps` và selected `trace.steps` luôn là danh sách đầy đủ;
  không có cursor, pagination hoặc silent truncation.
- Chỉ hai transform encrypt/decrypt có metadata history best-effort. Hai keygen route
  không có history.

## 2. Endpoint và content type

| Method/path | Request được nhận | Response thành công |
|---|---|---|
| `POST /api/rsa/keys` | `application/json` | Manual key material, không có `p/q` |
| `POST /api/rsa/keys/random` | `application/json` | Random key material, có `p/q` |
| `POST /api/rsa/encrypt` | `application/json` number/text **hoặc** `multipart/form-data` plaintext `.txt` | Number/text encrypt JSON |
| `POST /api/rsa/decrypt` | `application/json` number/text | Number/text decrypt JSON |

Quy tắc media type:

- JSON: đặt `Content-Type: application/json`; body phải là một JSON object UTF-8.
  UTF-8 BOM đầu JSON được nhận; UTF-16/UTF-32 không được nhận.
- `application/problem+json`, `text/plain`, thiếu `Content-Type`, hoặc multipart gửi
  tới ba route chỉ nhận JSON trả 415 `UNSUPPORTED_MEDIA_TYPE`.
- Multipart: dùng `FormData` và **không tự đặt header `Content-Type`**; browser phải tự
  thêm boundary. Đây là cách dùng được tài liệu Web Platform hiện hành xác nhận tại
  [MDN FormData](https://developer.mozilla.org/en-US/docs/Web/API/XMLHttpRequest_API/Using_FormData_Objects).
- `fetch("/api/rsa/...")` là URL tương đối hợp lệ; browser resolve theo base URL của
  document. Xem [MDN `fetch()`](https://developer.mozilla.org/en-US/docs/Web/API/Window/fetch).

## 3. Consumer types

Các type dưới đây mô tả wire shape. `DecimalString` là string theo regex ASCII
`^[0-9]+$`; TypeScript alias không thay thế runtime validation.

```ts
type DecimalString = string;
type SignedDecimalString = string; // chỉ output hệ số t của Euclid có thể âm
type RsaMode = "char" | "block";

type RsaErrorCode =
  | "REQUEST_TOO_LARGE"
  | "UNSUPPORTED_MEDIA_TYPE"
  | "INVALID_REQUEST"
  | "NOT_INTEGER"
  | "NUMBER_TOO_LARGE"
  | "INVALID_BITS"
  | "NOT_PRIME"
  | "SAME_PRIME"
  | "E_OUT_OF_RANGE"
  | "D_OUT_OF_RANGE"
  | "E_NOT_COPRIME"
  | "PRIME_TOO_LARGE"
  | "P_TOO_LARGE"
  | "N_TOO_SMALL"
  | "CIPHER_TOO_LARGE"
  | "DECODE_FAILED"
  | "EMPTY_INPUT"
  | "INPUT_TOO_LARGE"
  | "FILE_INVALID"
  | "INVALID_LENGTH_METADATA"
  | "TRACE_INDEX_OUT_OF_RANGE"
  | "FILE_READ_FAILED"
  | "INTERNAL_ERROR";

type RsaErrorResponse = {
  success: false;
  code: RsaErrorCode;
  message: string;
  field: string | null; // ví dụ "n", "cipher", "cipher[3]"
};

type EuclidStep = {
  index: number;
  q: DecimalString | null;
  r: DecimalString;
  t: SignedDecimalString;
};

type KeyMaterial = {
  success: true;
  n: DecimalString;
  phi: DecimalString;
  e: DecimalString;
  d: DecimalString;
  publicKey: { e: DecimalString; n: DecimalString };
  privateKey: { d: DecimalString; n: DecimalString };
  egcdSteps: EuclidStep[];
};

type ManualKeyResponse = KeyMaterial; // exact: không có p, q
type RandomKeyResponse = KeyMaterial & {
  p: DecimalString;
  q: DecimalString;
};

type ModPowStep = {
  i: number;
  bit: 0 | 1;
  base: DecimalString;
  before: DecimalString;
  result: DecimalString;
};

type RsaTrace = {
  operation: "encrypt" | "decrypt";
  blockIndex: number;
  input: DecimalString;
  exponent: DecimalString;
  modulus: DecimalString;
  result: DecimalString;
  steps: ModPowStep[];
};

type NumberEncryptResponse = {
  success: true;
  inputType: "number";
  blocks: [DecimalString];
  cipher: [DecimalString];
  blockSize: null;
  trace: RsaTrace | null;
};

type TextEncryptResponse = {
  success: true;
  inputType: "text";
  mode: RsaMode;
  blocks: DecimalString[];
  cipher: DecimalString[];
  blockSize: number; // 1 với char; k byte với block
  originalUtf8ByteLength: number;
  trace: RsaTrace | null;
};

type NumberDecryptResponse = {
  success: true;
  inputType: "number";
  blocks: [DecimalString]; // số plaintext sau giải mã
  plaintext: DecimalString;
  blockSize: null;
  trace: RsaTrace | null;
};

type TextDecryptResponse = {
  success: true;
  inputType: "text";
  mode: RsaMode;
  blocks: DecimalString[]; // plaintext block/code point sau giải mã
  plaintext: string;
  blockSize: number;
  originalUtf8ByteLength: number;
  trace: RsaTrace | null;
};
```

Các field nullable của RSA chỉ gồm `q` ở hai dòng đầu `egcdSteps`, `blockSize` ở
number response, `trace` khi không opt-in và `field` ở lỗi toàn request/hệ thống.
Không có wrapper `result` và không có field `warnings` trong success response RSA.

## 4. Sinh khóa

### 4.1 Manual key — `POST /api/rsa/keys`

Request exact:

```ts
type ManualKeyRequest = {
  p: DecimalString;
  q: DecimalString;
  e: DecimalString;
};
```

```json
{"p":"17","q":"11","e":"7"}
```

Response exact:

```json
{
  "success": true,
  "n": "187",
  "phi": "160",
  "e": "7",
  "d": "23",
  "publicKey": {"e": "7", "n": "187"},
  "privateKey": {"d": "23", "n": "187"},
  "egcdSteps": [
    {"index": 0, "q": null, "r": "160", "t": "0"},
    {"index": 1, "q": null, "r": "7", "t": "1"},
    {"index": 2, "q": "22", "r": "6", "t": "-22"},
    {"index": 3, "q": "1", "r": "1", "t": "23"},
    {"index": 4, "q": "6", "r": "0", "t": "-160"}
  ]
}
```

- Manual response không trả `p` hoặc `q`.
- `egcdSteps` luôn là bảng đầy đủ: hai dòng khởi tạo có `q:null`, dòng cuối có
  `r:"0"`. `t` là decimal string có dấu khi âm.
- Validation theo thứ tự `p`, `q`, `e`; `p/q` phải khác nhau, là số nguyên tố và
  không vượt `10^12`; `1 < e < phi(n)` và `gcd(e,phi)=1`.

### 4.2 Random key — `POST /api/rsa/keys/random`

Request chỉ có `bits`, là JSON integer thật:

```ts
type RandomKeyRequest = { bits: 16 | 32 | 64 | 128 };
```

```json
{"bits":16}
```

Một response hợp lệ có shape sau. Giá trị được sinh ngẫu nhiên và có thể khác giữa
các request; API không cam kết uniqueness:

```json
{
  "success": true,
  "n": "59989",
  "phi": "59500",
  "e": "3",
  "d": "39667",
  "publicKey": {"e": "3", "n": "59989"},
  "privateKey": {"d": "39667", "n": "59989"},
  "egcdSteps": [
    {"index": 0, "q": null, "r": "59500", "t": "0"},
    {"index": 1, "q": null, "r": "3", "t": "1"},
    {"index": 2, "q": "19833", "r": "1", "t": "-19833"},
    {"index": 3, "q": "3", "r": "0", "t": "59500"}
  ],
  "p": "251",
  "q": "239"
}
```

`n` có đúng bit length đã yêu cầu. FE không được giả định `e` luôn là `65537`.

## 5. Transform number

### 5.1 Encrypt number

Request exact:

```ts
type NumberEncryptRequest = {
  e: DecimalString;
  n: DecimalString;
  inputType: "number";
  data: DecimalString;
  traceBlockIndex?: number;
};
```

```http
POST /api/rsa/encrypt
Content-Type: application/json

{"e":"7","n":"187","inputType":"number","data":"88"}
```

```json
{
  "success": true,
  "inputType": "number",
  "blocks": ["88"],
  "cipher": ["11"],
  "blockSize": null,
  "trace": null
}
```

`data="00088"` cũng hợp lệ nhưng output được canonicalize thành `"88"`.

### 5.2 Decrypt number

Request exact; `cipher` phải có đúng một item:

```ts
type NumberDecryptRequest = {
  d: DecimalString;
  n: DecimalString;
  inputType: "number";
  cipher: [DecimalString];
  traceBlockIndex?: number;
};
```

```http
POST /api/rsa/decrypt
Content-Type: application/json

{"d":"23","n":"187","inputType":"number","cipher":["11"]}
```

```json
{
  "success": true,
  "inputType": "number",
  "blocks": ["88"],
  "plaintext": "88",
  "blockSize": null,
  "trace": null
}
```

Number response vẫn dùng string cho plaintext; không chuyển qua JavaScript `number`.

## 6. Transform text

### 6.1 Request exact

```ts
type TextEncryptRequest = {
  e: DecimalString;
  n: DecimalString;
  inputType: "text";
  mode: "char" | "block";
  data: string;
  traceBlockIndex?: number;
};

type CharDecryptRequest = {
  d: DecimalString;
  n: DecimalString;
  inputType: "text";
  mode: "char";
  cipher: DecimalString[];
  traceBlockIndex?: number;
};

type BlockDecryptRequest = {
  d: DecimalString;
  n: DecimalString;
  inputType: "text";
  mode: "block";
  cipher: DecimalString[];
  originalUtf8ByteLength: number;
  traceBlockIndex?: number;
};
```

Không gửi `originalUtf8ByteLength` khi encrypt hoặc khi decrypt `mode="char"`.
Không gửi `mode` cho number. Những field không áp dụng này không bị bỏ qua mà trả
422 `INVALID_REQUEST`.

### 6.2 `mode="char"`

- Mỗi Unicode code point là một plaintext block (`ord(character)`), không phải mỗi
  UTF-8 byte hoặc mỗi UTF-16 code unit.
- Mỗi code point phải nhỏ hơn `n`.
- Không trim, normalize Unicode hoặc đổi newline.
- Encrypt/decrypt text response có `blockSize:1`.
- Encrypt trả `originalUtf8ByteLength` từ UTF-8 đầu vào; decrypt tính lại trường này
  từ plaintext đã phục hồi. Char decrypt không nhận length metadata.

Ví dụ giữ trailing NUL:

```json
{
  "e": "3",
  "n": "67591",
  "inputType": "text",
  "mode": "char",
  "data": "A\u0000"
}
```

```json
{
  "success": true,
  "inputType": "text",
  "mode": "char",
  "blocks": ["65", "0"],
  "cipher": ["4261", "0"],
  "blockSize": 1,
  "originalUtf8ByteLength": 2,
  "trace": null
}
```

Decrypt `cipher:["4261","0"]` với `d:"44715"`, `n:"67591"`, `mode:"char"`
trả `plaintext:"A\u0000"` và `blocks:["65","0"]`.

### 6.3 `mode="block"` và cipher package lossless

Backend:

1. Encode nguyên chuỗi thành UTF-8 strict.
2. Chọn `k` lớn nhất sao cho `256^k <= n - 1`; `blockSize` là `k` byte.
3. Chia bytes thành chunk `k`, pad **bên phải** block cuối bằng `0x00`, đọc
   big-endian thành plaintext blocks.
4. Trả `originalUtf8ByteLength` là số byte trước padding.
5. Khi decrypt, dùng length này để phân biệt padding với NUL thật, kiểm block count,
   zero padding và UTF-8 rồi mới trả plaintext.

Ví dụ copyable:

```http
POST /api/rsa/encrypt
Content-Type: application/json

{"e":"3","n":"67591","inputType":"text","mode":"block","data":"Hi!"}
```

```json
{
  "success": true,
  "inputType": "text",
  "mode": "block",
  "blocks": ["18537", "8448"],
  "cipher": ["37222", "6468"],
  "blockSize": 2,
  "originalUtf8ByteLength": 3,
  "trace": null
}
```

```http
POST /api/rsa/decrypt
Content-Type: application/json

{"d":"44715","n":"67591","inputType":"text","mode":"block","cipher":["37222","6468"],"originalUtf8ByteLength":3}
```

```json
{
  "success": true,
  "inputType": "text",
  "mode": "block",
  "blocks": ["18537", "8448"],
  "plaintext": "Hi!",
  "blockSize": 2,
  "originalUtf8ByteLength": 3,
  "trace": null
}
```

Nếu FE cần persist/import ở client, có thể tự định nghĩa record cục bộ tối thiểu:

```ts
type RsaBlockCipherRecord = {
  mode: "block";
  cipher: DecimalString[];
  originalUtf8ByteLength: number;
  n: DecimalString;
};

function toBlockDecryptRequest(
  record: RsaBlockCipherRecord,
  d: DecimalString,
): BlockDecryptRequest {
  return {
    d,
    n: record.n,
    inputType: "text",
    mode: "block",
    cipher: record.cipher,
    originalUtf8ByteLength: record.originalUtf8ByteLength,
  };
}
```

`RsaBlockCipherRecord` là gợi ý lưu trữ FE, **không phải** response, file download hay
wire shape mới của backend. Decrypt route vẫn yêu cầu full `BlockDecryptRequest`; khóa
private `d` được giữ riêng và không phải metadata server lưu. Nếu FE export/import
record, không đổi `cipher` hoặc `originalUtf8ByteLength`.

### 6.4 BOM, newline, Unicode composition và NUL

Route contract giữ nguyên:

- Leading UTF-8 BOM trong file trở thành ký tự plaintext `U+FEFF`; ba byte BOM được
  tính vào `originalUtf8ByteLength`.
- JSON `data` bắt đầu bằng `U+FEFF` cũng giữ ký tự đó như nội dung. Đây khác với BOM
  ở đầu **JSON document** dùng để nhận diện encoding; BOM transport không được chèn
  vào string `data`.
- `CR`, `LF` và `CRLF` được giữ đúng thứ tự; không có universal-newline conversion.
- `"é"` và `"e\u0301"` là hai plaintext khác nhau; backend không normalize.
- Leading/trailing whitespace và trailing `U+0000` là nội dung, không được trim.
- Block decrypt không dùng `rstrip(0x00)`; length metadata quyết định byte nào có nghĩa.

FE nên dùng trực tiếp `plaintext` server trả, không tự dựng text từ `blocks`. Nếu cần
hiển thị số code point, `[...text].length` gần với cách backend đếm hơn
`text.length` của JavaScript; đây là gợi ý UI, không thay server validation. Nếu cần
ước lượng số byte UTF-8, dùng `new TextEncoder().encode(text).byteLength`; Web
Platform định nghĩa `TextEncoder.encode()` trả UTF-8 bytes, xem
[MDN TextEncoder](https://developer.mozilla.org/en-US/docs/Web/API/TextEncoder/encode).

**Gợi ý client, không phải route contract:** decrypt luôn trả JSON, không có file
download từ server. Nếu UI cho tải plaintext, FE có thể tạo `Blob` từ chính
`plaintext` với `type:"text/plain;charset=utf-8"`. Không tự thêm/bỏ BOM hoặc trim
NUL/newline; `U+FEFF` và `U+0000` đã có trong string sẽ được UTF-8 encode như nội dung.
`Blob` mặc định giữ newline (`endings:"transparent"`) và encode string thành UTF-8;
xem [MDN `Blob()`](https://developer.mozilla.org/en-US/docs/Web/API/Blob/Blob). Tên file
download là quyết định UI của FE, không phải filename server trả.

## 7. Selected-block trace và Euclid table

`traceBlockIndex` là opt-in cho đúng một block, zero-based:

- number: chỉ index `0` hợp lệ;
- text: index phải nhỏ hơn số block/cipher item;
- không có nhiều index, all-block trace, pagination hoặc truncation;
- khi không gửi, `trace` vẫn có mặt và bằng `null`;
- bật trace không đổi bất kỳ field transform nào ngoài `trace`.

```http
POST /api/rsa/encrypt
Content-Type: application/json

{"e":"7","n":"187","inputType":"number","data":"88","traceBlockIndex":0}
```

```json
{
  "success": true,
  "inputType": "number",
  "blocks": ["88"],
  "cipher": ["11"],
  "blockSize": null,
  "trace": {
    "operation": "encrypt",
    "blockIndex": 0,
    "input": "88",
    "exponent": "7",
    "modulus": "187",
    "result": "11",
    "steps": [
      {"i": 0, "bit": 1, "base": "88", "before": "1", "result": "88"},
      {"i": 1, "bit": 1, "base": "77", "before": "88", "result": "44"},
      {"i": 2, "bit": 1, "base": "132", "before": "44", "result": "11"}
    ]
  }
}
```

`steps` đi từ bit thấp tới bit cao của exponent theo right-to-left
square-and-multiply, đầy đủ tối đa 128 dòng. Khi decrypt, `input` là cipher item và
`exponent` là `d`.

`egcdSteps` của keygen cũng luôn đầy đủ tới remainder 0. Hai loại steps là hai schema
khác nhau; FE không dùng chung renderer nếu renderer đang giả định cùng field.

## 8. Plaintext `.txt` multipart encrypt

Multipart chỉ dùng tại `POST /api/rsa/encrypt` và có exact parts:

| Part | Bắt buộc | Wire type | Quy tắc |
|---|---:|---|---|
| `file` | có | upload | Filename kết thúc `.txt`, không phân biệt hoa thường |
| `e` | có | scalar string | Decimal string |
| `n` | có | scalar string | Decimal string |
| `mode` | có | scalar string | `char` hoặc `block` |
| `traceBlockIndex` | không | scalar string | `0|[1-9][0-9]*`, tối đa 10 digit |

Không gửi `inputType`, `data`, `originalUtf8ByteLength`, `cipher`, `action`,
`response_mode` hoặc bất kỳ part nào khác. Part trùng cũng bị từ chối.

Browser example:

```ts
async function encryptRsaTextFile(input: {
  file: File;
  e: DecimalString;
  n: DecimalString;
  mode: RsaMode;
  traceBlockIndex?: number;
}): Promise<TextEncryptResponse> {
  const form = new FormData();
  form.append("file", input.file);
  form.append("e", input.e);
  form.append("n", input.n);
  form.append("mode", input.mode);
  if (input.traceBlockIndex !== undefined) {
    form.append("traceBlockIndex", String(input.traceBlockIndex));
  }

  const response = await fetch("/api/rsa/encrypt", {
    method: "POST",
    body: form,
    // Không đặt Content-Type; browser thêm multipart boundary.
  });
  const body = (await response.json()) as TextEncryptResponse | RsaErrorResponse;
  if (!response.ok) {
    const error = body as RsaErrorResponse;
    throw Object.assign(new Error(error.message), { response: error });
  }
  return body as TextEncryptResponse;
}
```

`curl` tương đương:

```bash
curl -sS -X POST http://localhost:8080/api/rsa/encrypt \
  -F 'file=@plain.txt;type=application/octet-stream' \
  -F 'e=3' \
  -F 'n=67591' \
  -F 'mode=block'
```

Backend không dùng MIME upload làm authority. Với file chứa bytes `Hi!`, response
giống hệt JSON block encrypt ở mục 6.3, có `Content-Type: application/json`, không có
`Content-Disposition` và không có attachment.

Validation file:

- `.TXT` hợp lệ; filename rỗng, không extension, `.txt.bin` hoặc đuôi khác trả 415.
- Tối đa đúng `1.000.000` raw byte **decimal**, tính cả BOM. `1.000.001` byte trả 413.
- File 0 byte trả 422 `EMPTY_INPUT`.
- Decode UTF-8 strict; invalid UTF-8 trả 415. MIME không cứu file bytes sai.
- Sau decode, tối đa 10.000 Unicode code point, gồm BOM, whitespace, newline và NUL.
- FE nên append `File` gốc vào `FormData`; không cần đọc/decode/re-encode trước request,
  vì làm vậy có thể thay đổi bytes/BOM.

Không có multipart decrypt. FE muốn giải mã phải lưu cipher package và gửi JSON tới
`/api/rsa/decrypt`.

## 9. Numeric, text, collection và request caps

| Phạm vi | Giới hạn hiện tại |
|---|---|
| Crypto input `p/q/e/d/n/data/cipher[i]` | ASCII decimal string, tối đa 128 raw digit **và** giá trị `<= 2^128 - 1` |
| Manual prime `p`, `q` | `<= 10^12` trước phép thử prime |
| Random modulus size | `bits` thuộc `16|32|64|128` |
| Transform exponent | `1 < e < n` hoặc `1 < d < n` |
| Number/plain block/cipher item | `0 <= value < n` |
| Block mode modulus | `n > 256` |
| JSON/file plaintext | `1..10.000` Unicode code point |
| Number decrypt cipher | đúng 1 item |
| Char decrypt cipher | `1..10.000` item |
| Block decrypt cipher | `1..40.000` item |
| `originalUtf8ByteLength` | JSON integer `1..40.000`, tối đa 10 raw digit trước parse và phải khớp block count/padding |
| `traceBlockIndex` | JSON integer không âm; multipart dùng canonical digit string; tối đa 10 raw digit và phải nằm trong collection |
| File | tối đa `1.000.000` raw byte decimal, rồi vẫn chịu cap 10.000 code point |
| Multipart scalar part | tối đa `1.000.000` byte ở parser hiện hành; decimal validator vẫn áp cap 128 digit/value |
| Request tầng hạ tầng | `> 64 MiB = 67.108.864` byte bị từ chối khi có đúng một `Content-Length` decimal hợp lệ; đúng trần qua guard |

Trần request 64 MiB là guard hạ tầng, không thay thế business cap. Nếu
`Content-Length` thiếu, trùng hoặc không parse được, request đi tiếp tới parser và các
cap nghiệp vụ; FE không được dựa vào trường hợp này để gửi payload lớn hơn.

JavaScript `Number` chỉ chính xác tới `2^53 - 1`; xem
[MDN `Number.MAX_SAFE_INTEGER`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Number/MAX_SAFE_INTEGER).
Vì RSA cho phép tới `2^128 - 1`, FE phải giữ crypto integer dưới dạng string. Có thể
dùng `BigInt` cho tính toán/validation cục bộ, nhưng serialize lại bằng decimal string;
không đưa `bigint` trực tiếp vào `JSON.stringify`.

Ngược lại, `bits`, `traceBlockIndex` và `originalUtf8ByteLength` nằm trong range nhỏ,
nên JSON request dùng JavaScript `number` nguyên. Không stringify ba control này;
chỉ `traceBlockIndex` trong `FormData` phải chuyển thành scalar string do transport
multipart.

## 10. Strict fields và validation precedence

### 10.1 Exact field matrix

| Variant | Bắt buộc | Tùy chọn | Field không áp dụng điển hình |
|---|---|---|---|
| Manual key | `p,q,e` | — | `bits,n,d` |
| Random key | `bits` | — | `p,q,e` |
| Number encrypt | `e,n,inputType,data` | `traceBlockIndex` | `mode,cipher,originalUtf8ByteLength` |
| Text encrypt | `e,n,inputType,mode,data` | `traceBlockIndex` | `cipher,originalUtf8ByteLength` |
| Number decrypt | `d,n,inputType,cipher` | `traceBlockIndex` | `mode,data,originalUtf8ByteLength` |
| Char decrypt | `d,n,inputType,mode,cipher` | `traceBlockIndex` | `data,originalUtf8ByteLength` |
| Block decrypt | `d,n,inputType,mode,cipher,originalUtf8ByteLength` | `traceBlockIndex` | `data` |
| Multipart encrypt | `file,e,n,mode` | `traceBlockIndex` | `inputType,data,cipher,action,response_mode,originalUtf8ByteLength` |

Các request JSON dùng object exact. Ví dụ sau đều là lỗi:

- number encrypt có thêm `mode`;
- char decrypt có thêm `originalUtf8ByteLength`;
- multipart có `action` hoặc `response_mode`;
- raw JSON có hai member cùng tên;
- crypto integer được gửi thành JSON number, boolean, `null` hoặc digit Unicode.

Unknown/duplicate/inapplicable field trả `INVALID_REQUEST` với `field` là tên member.
Missing required member cũng trả `INVALID_REQUEST` với `field` là tên member đang
thiếu, **ngoại trừ** block decrypt thiếu `originalUtf8ByteLength`: trường hợp đó trả
`INVALID_LENGTH_METADATA` với field cùng tên. Chỉ malformed JSON, root không phải
object hoặc lỗi không quy được cho member mới có `field:null`. Nếu có nhiều
unknown/duplicate cùng cấp, field xuất hiện đầu tiên trong raw JSON thắng; còn numeric
validation dùng schema order (`p,q,e`, `e,n,data`, `d,n,cipher[0..]`) chứ không phụ
thuộc member order client gửi.

### 10.2 Precedence thực tế cần biết

JSON dừng ở lỗi đầu theo nhóm:

```text
64 MiB guard
→ media type / parse UTF-8 JSON object / duplicate
→ inputType, mode và exact required/allowed field set
→ text hoặc collection cap
→ bits / originalUtf8ByteLength control validation khi áp dụng
→ crypto lexical/raw/value theo schema order
→ key/domain/item < n/package consistency
→ traceBlockIndex
→ transform
```

Multipart dừng ở lỗi đầu:

```text
64 MiB guard / multipart framing
→ exact field set / duplicate
→ file presence và upload type
→ e, n, mode presence
→ e lexical/value → n lexical/value → mode
→ filename extension → 1.000.000 raw byte → empty → UTF-8
→ 10.000 code point → key/block/domain
→ traceBlockIndex → transform
```

FE không nên suy ra field phía sau hợp lệ chỉ vì server trả lỗi sớm ở field khác.

## 11. Error contract và cách FE xử lý

Mọi lỗi trên đúng bốn RSA route dùng exact `RsaErrorResponse` đã định nghĩa tại mục 3:
`{success:false,code:RsaErrorCode,message:string,field:string|null}`.

FE nên hiển thị nguyên `message`, branch/focus control theo `code` và `field`, và có
fallback riêng cho lỗi mạng/JSON parse. Không branch theo câu tiếng Việt. `field` có
thể là path như `cipher[3]`.

| Code | HTTP | Exact message | `field` |
|---|---:|---|---|
| `REQUEST_TOO_LARGE` | 413 | `Yêu cầu vượt quá dung lượng cho phép.` | `null` |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | `Kiểu nội dung không được hỗ trợ.` | `null` |
| `INVALID_REQUEST` | 422 | `Dữ liệu gửi lên không hợp lệ.` | `null` hoặc field liên quan |
| `NOT_INTEGER` | 422 | `Giá trị phải là số nguyên không âm.` | numeric field/path |
| `NUMBER_TOO_LARGE` | 422 | `Giá trị không được vượt quá 2^128 - 1.` | numeric field/path |
| `INVALID_BITS` | 422 | `Số bit phải là một trong 16, 32, 64 hoặc 128.` | `bits` |
| `NOT_PRIME` | 422 | `{field} = {value} không phải số nguyên tố.` | `p` hoặc `q` |
| `SAME_PRIME` | 422 | `p và q phải khác nhau.` | `q` |
| `E_OUT_OF_RANGE` | 422 | Keygen: `e phải thỏa 1 < e < phi(n) = {phi}.`; transform: `e phải thỏa 1 < e < n.` | `e` |
| `D_OUT_OF_RANGE` | 422 | `d phải thỏa 1 < d < n.` | `d` |
| `E_NOT_COPRIME` | 422 | `gcd({e}, {phi}) = {g}, không tồn tại d. Gợi ý e = {suggestion}.` | `e` |
| `PRIME_TOO_LARGE` | 422 | `Hãy dùng p, q ≤ 10^12 hoặc sinh khóa ngẫu nhiên.` | `p` hoặc `q` |
| `P_TOO_LARGE` | 422 | `P = {P} ≥ n = {n}. Hãy chia khối hoặc dùng n lớn hơn.` | `data` hoặc `file` |
| `N_TOO_SMALL` | 422 | General: `n phải lớn hơn 1.`; block: `n phải lớn hơn 256 để chứa ít nhất 1 byte mỗi khối.` | `n` |
| `CIPHER_TOO_LARGE` | 422 | `Bản mã không hợp lệ với khóa này.` | `cipher[i]` |
| `DECODE_FAILED` | 422 | `Không khôi phục được văn bản hợp lệ từ dữ liệu đã giải mã.` | `data`, `cipher` hoặc `cipher[i]` |
| `EMPTY_INPUT` | 422 | `Dữ liệu đầu vào đang rỗng.` | `data`, `cipher` hoặc `file` |
| `INPUT_TOO_LARGE` | 422 | Text: `Dữ liệu văn bản không được vượt quá 10.000 ký tự Unicode.`; collection: `Danh sách bản mã vượt quá giới hạn cho phép.` | `data`, `file` hoặc `cipher` |
| `FILE_INVALID` | 413 | `File vượt quá dung lượng tối đa 1 MB.` | `file` |
| `FILE_INVALID` | 415 | `Chỉ nhận file .txt.` hoặc `File phải sử dụng UTF-8.` | `file` |
| `INVALID_LENGTH_METADATA` | 422 | `Độ dài UTF-8 gốc không khớp với danh sách bản mã.` | `originalUtf8ByteLength` |
| `TRACE_INDEX_OUT_OF_RANGE` | 422 | `Chỉ số khối cần xem không hợp lệ.` | `traceBlockIndex` |
| `FILE_READ_FAILED` | 500 | `Không thể đọc file.` | `file` |
| `INTERNAL_ERROR` | 500 | `Đã xảy ra lỗi hệ thống.` | `null` |

Ví dụ indexed error:

```json
{
  "success": false,
  "code": "NOT_INTEGER",
  "message": "Giá trị phải là số nguyên không âm.",
  "field": "cipher[3]"
}
```

Lỗi không trả partial key/result/trace, traceback hoặc exception string.

### 11.1 Hai edge error cần map chính xác

Block decrypt thiếu `originalUtf8ByteLength` dùng cùng code với metadata sai
type/range/count/padding:

```http
POST /api/rsa/decrypt
Content-Type: application/json
```

```json
{"d":"44715","n":"67591","inputType":"text","mode":"block","cipher":["37222","6468"]}
```

```json
{"success":false,"code":"INVALID_LENGTH_METADATA","message":"Độ dài UTF-8 gốc không khớp với danh sách bản mã.","field":"originalUtf8ByteLength"}
```

Nếu plaintext JSON chứa lone surrogate, ví dụ chuỗi escape `\ud800` không thể encode
thành UTF-8 strict, server trả lỗi gắn với plaintext `data`:

```http
POST /api/rsa/encrypt
Content-Type: application/json
```

```json
{"e":"3","n":"67591","inputType":"text","mode":"char","data":"\ud800"}
```

```json
{"success":false,"code":"DECODE_FAILED","message":"Không khôi phục được văn bản hợp lệ từ dữ liệu đã giải mã.","field":"data"}
```

FE nên focus control length cho lỗi đầu và control plaintext cho lỗi sau; không gộp
hai trường hợp thành generic `INVALID_REQUEST`.

## 12. Fetch helper tối thiểu

Helper dưới đây dành riêng cho JSON RSA. Nó không thay contract và không tự sửa input:

```ts
class RsaApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: RsaErrorResponse,
  ) {
    super(body.message);
  }
}

async function postRsaJson<TSuccess>(
  path: "/api/rsa/keys" | "/api/rsa/keys/random" | "/api/rsa/encrypt" | "/api/rsa/decrypt",
  body: object,
): Promise<TSuccess> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const payload = (await response.json()) as TSuccess | RsaErrorResponse;
  if (!response.ok) throw new RsaApiError(response.status, payload as RsaErrorResponse);
  return payload as TSuccess;
}

const encrypted = await postRsaJson<TextEncryptResponse>("/api/rsa/encrypt", {
  e: "3",
  n: "67591",
  inputType: "text",
  mode: "block",
  data: "Hi!",
});

const decrypted = await postRsaJson<TextDecryptResponse>("/api/rsa/decrypt", {
  d: "44715",
  n: "67591",
  inputType: "text",
  mode: "block",
  cipher: encrypted.cipher,
  originalUtf8ByteLength: encrypted.originalUtf8ByteLength,
});
```

`postRsaJson` là ví dụ cục bộ trong tài liệu này, không phải export hiện có của
[`examples/cipher-api.ts`](examples/cipher-api.ts). Khi đưa vào FE thật, giữ request
object riêng theo từng union variant để tránh spread field thừa.

## 13. History, privacy và statelessness

RSA transform vẫn stateless; server không lưu cipher package để dùng cho request sau.
Khi history server được bật:

- `POST /api/rsa/encrypt` và `/api/rsa/decrypt` ghi một row metadata cho cả success
  lẫn 413/415/422/500;
- `/keys` và `/keys/random` không ghi history;
- JSON encrypt/decrypt có `source:"text"`; multipart encrypt có `source:"file"`;
- `responseMode` luôn `null`;
- number transform có `inputLength:null`, `outputLength:null`;
- text encrypt chỉ có thể đặt `inputLength` là số Unicode code point;
- text decrypt chỉ có thể đặt `outputLength` là số Unicode code point;
- multipart encrypt chỉ có thể đặt `inputLength` là raw byte gồm BOM;
- phía cipher array không được biểu diễn bằng length.

Mọi length history đều nullable; request lỗi trước khi backend đo được thì giữ
`null`. Đây là metadata quan sát, không phải cipher package để FE dùng giải mã.

FE lọc bằng URL tương đối:

```text
GET /api/history?cipher=rsa
```

History không lưu plaintext, ciphertext, `p/q/e/d`, public/private key, `data`, cipher
array, `originalUtf8ByteLength`, filename, file content, IP/user-agent, trace hoặc
error message. Ghi là best-effort: DB tắt/lỗi/timeout hoặc schema chưa migrate có thể
bỏ lỡ row nhưng không được làm thay đổi response RSA.

`GET /api/history` là API chung, không có authentication và mặc định tắt trên môi
trường dùng chung. Contract query, pagination, error và privacy chung nằm tại
[mục 16 của guide](frontend-integration.md#16-health-và-lịch-sử-thao-tác).

## 14. Giới hạn phát hiện khóa sai và tính giáo dục

Textbook RSA ở đây không authenticated:

- khóa private sai có thể tạo code point/UTF-8/padding hợp lệ và server sẽ trả HTTP
  200 với plaintext khác;
- `originalUtf8ByteLength` bị sửa có thể vẫn khớp block count/zero padding và cho
  plaintext hợp lệ khác, ví dụ package `Hi!` với length 4 có thể thành `"Hi!\u0000"`;
- `DECODE_FAILED` chỉ nói server quan sát thấy width, padding hoặc UTF-8 không hợp lệ;
  nó không chứng minh nguyên nhân là wrong key;
- HTTP 200 không chứng minh key, cipher package hoặc metadata đúng.

FE không nên hiển thị “khóa đúng”/“khóa sai đã được xác minh”. Câu phù hợp là
“Không khôi phục được văn bản hợp lệ” khi server trả `DECODE_FAILED`; còn HTTP 200 thì
chỉ hiển thị plaintext quan sát được cùng cảnh báo textbook RSA.

## 15. Checklist handoff FE

- [ ] Chỉ gọi bốn endpoint exact bằng URL tương đối `/api/rsa/...`.
- [ ] JSON đặt `application/json`; không gửi `application/*+json`.
- [ ] Crypto integer được giữ và gửi bằng decimal string, không qua JavaScript
  `Number`; control integer gửi đúng JSON integer.
- [ ] Mỗi request variant chỉ có exact field set; không spread state chung có field
  không áp dụng.
- [ ] Manual response không giả định có `p/q`; random response không giả định `e=65537`.
- [ ] Number response giữ `plaintext`, `blocks`, `cipher` dưới dạng string.
- [ ] Char mode hiểu một block mỗi Unicode code point, không phải UTF-16 code unit.
- [ ] Block package lưu và gửi lại nguyên `cipher` + `originalUtf8ByteLength`.
- [ ] Không trim/normalize/rewrite BOM, newline, whitespace hoặc trailing NUL.
- [ ] Trace mặc định xử lý được `null`; opt-in chỉ một zero-based block và render full
  steps server trả.
- [ ] Multipart append file gốc, không tự đặt `Content-Type`, không gửi
  `action/response_mode/inputType` và luôn parse response JSON.
- [ ] UI xử lý 413/415/422/500 bằng exact RSA envelope; focus theo `code/field`, hiển
  thị `message`, lỗi mạng có fallback riêng.
- [ ] UI không claim wrong-key detection hoặc bảo mật production.
- [ ] Nếu hiển thị history server, hỗ trợ `cipher=rsa`, keygen exclusion,
  `responseMode:null`, nullable lengths và tính best-effort/shared-instance.

## 16. Nguồn bảo trì

Authority của contract này theo thứ tự:

1. Accepted OpenSpec change Q1–Q16 và hai làm rõ corrective R1–R2 tại
   [`openspec/changes/add-rsa-cipher/`](../openspec/changes/add-rsa-cipher/), trong đó
   Q16 thay thế riêng quyết định “no history” cho safe transform metadata; R1–R2 chỉ
   reconcile hai error edge nêu tại mục 11.1.
2. Runtime/schema/error mapping hiện tại:
   [`routes_rsa.py`](../app/api/routes_rsa.py),
   [`rsa_schemas.py`](../app/api/rsa_schemas.py),
   [`rsa.py`](../app/core/rsa.py),
   [`handlers.py`](../app/errors/handlers.py) và
   [`messages.py`](../app/errors/messages.py).
3. Contract tests:
   [`test_rsa_endpoints.py`](../tests/integration/test_rsa_endpoints.py),
   [`test_rsa_file_encrypt.py`](../tests/integration/test_rsa_file_encrypt.py),
   [`test_rsa_validation.py`](../tests/unit/test_rsa_validation.py),
   [`test_rsa.py`](../tests/unit/test_rsa.py) và các test history/guard liên quan.
4. `/openapi.json` là projection machine-readable hữu ích, nhưng hiện under-describe
   một số runtime constraint như minimum/raw-digit cap của control integer và một số
   array cardinality. Không dùng điểm thiếu đó để nới contract.

Nếu các nguồn trên lệch nhau, ghi nhận defect và reconcile với owner; FE không tự chọn
behavior mới. Không thêm endpoint, field, key format, warning hoặc file flow chỉ bằng
cách sửa tài liệu.
