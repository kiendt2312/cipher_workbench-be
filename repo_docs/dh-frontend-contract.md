# Supporting reference — Diffie–Hellman standalone và integration Caesar

Tài liệu này giữ phần tra cứu DH theo feature. Contract canonical, self-contained
và có quyền cao hơn cho FE là [`frontend-integration.md`](frontend-integration.md),
đặc biệt mục 19. Không suy ra endpoint hoặc field ngoài contract canonical.

DH là feature standalone ngang cấp Caesar. Năm endpoint params/key/exchange trả dữ
liệu số học DH được tính thật; `/api/dh/caesar` là integration riêng dùng shared key
và không biến DH thành Caesar mode. Caesar standalone giữ nguyên route/response và
integer behavior, đồng thời nhận thêm decimal string canonical từ `sharedKey` DH.

> **Giới hạn an toàn bắt buộc:** Contract này không có xác thực chống MITM, ECDH,
> KDF, nhóm production hoặc lưu khóa server-side. `/exchange` cố ý trả khóa riêng để
> minh họa/đối chiếu phép tính; client phải luôn hiển thị warning đi kèm.

## 1. Tóm tắt bắt buộc

- Có đúng sáu endpoint DH, tất cả là `POST` dưới `/api/dh`.
- Mọi đại lượng mật mã và `shift` là **decimal string ASCII canonical**: `"0"` hoặc
  `[1-9][0-9]*`. Không gửi JSON number, dấu, khoảng trắng, Unicode digit hay leading zero.
- `bits`, `index`, `bit` là JSON integer thật; `success`, `passes`, `match` là boolean.
- JSON chỉ nhận base media type `application/json`; `/caesar` nhận thêm
  `multipart/form-data`. Mọi response, kể cả file upload và lỗi, đều là JSON.
- Request strict: field lạ, trùng, thiếu hoặc không áp dụng bị từ chối. Không gửi
  object dùng chung có field thừa.
- `alpha`, `privateKey`, `privateKeyA`, `privateKeyB` là optional bằng cách **bỏ field**;
  gửi explicit `null` không tương đương omission và bị lỗi.
- Manual `/params` chỉ nhận `5 <= q <= 10^12`; các endpoint downstream tự kiểm tra q
  tới `2^128-1`, không cần provenance token hay request trước đó.
- Trace DH là square-and-multiply từ trái sang phải, đầy đủ, tối đa 128 rows mỗi phép.
- Chỉ `/api/dh/caesar` ghi metadata history best-effort. Không lưu tham số, khóa,
  input/result/file, trace hoặc warning.

## 2. Endpoint và media type

| Method/path | Request | Success |
|---|---|---|
| `POST /api/dh/params` | JSON `q,alpha?` | Kiểm q/alpha; thiếu alpha chỉ gợi ý |
| `POST /api/dh/params/random` | JSON `bits` | Safe-prime `q=2p+1`, alpha và checks |
| `POST /api/dh/keypair` | JSON `q,alpha,privateKey?` | Private/public key và trace |
| `POST /api/dh/shared-secret` | JSON `q,privateKey,otherPublicKey` | Shared key và trace |
| `POST /api/dh/exchange` | JSON `q,alpha,privateKeyA?,privateKeyB?` | Hai phía, grouped traces và warning |
| `POST /api/dh/caesar` | JSON hoặc multipart `.txt` | Caesar bằng `K mod 26`, luôn JSON |

Với JSON, đặt `Content-Type: application/json`. Parameter như `charset=utf-8` được
nhận; không có cam kết nhận `application/*+json`. Body phải là một object UTF-8;
UTF-8 BOM đầu JSON được nhận. Với `FormData`, không tự đặt `Content-Type`: browser
phải tự thêm multipart boundary, theo [MDN FormData](https://developer.mozilla.org/en-US/docs/Web/API/XMLHttpRequest_API/Using_FormData_Objects).

## 3. Consumer types

```ts
type DecimalString = string;
type DhAction = "encrypt" | "decrypt";

type DhErrorCode =
  | "REQUEST_TOO_LARGE" | "UNSUPPORTED_MEDIA_TYPE" | "INVALID_REQUEST"
  | "NOT_INTEGER" | "Q_OUT_OF_RANGE" | "NOT_PRIME"
  | "ALPHA_OUT_OF_RANGE" | "NOT_PRIMITIVE_ROOT" | "BITS_INVALID"
  | "PRIVATE_KEY_OUT_OF_RANGE" | "PRIVATE_KEY_WEAK" | "PUBLIC_KEY_INVALID"
  | "INVALID_ACTION" | "EMPTY_INPUT" | "MISSING_FILE" | "FILE_INVALID"
  | "UNSUPPORTED_ENCODING" | "FILE_READ_FAILED" | "INTERNAL_ERROR"
  // Resource-bound domain failures có thể xuất hiện với group khó:
  | "FACTORIZATION_FAILED" | "PRIMITIVE_ROOT_NOT_FOUND" | "GENERATION_FAILED";

type DhErrorResponse = {
  success: false;
  code: DhErrorCode;
  message: string;
  field: string | null;
};

type EducationalPrivateKeysWarning = {
  code: "EDUCATIONAL_PRIVATE_KEYS";
  message: string;
};

type ShiftZeroWarning = {
  code: "SHIFT_ZERO";
  message: string;
};

type ParamsRequest = {q: DecimalString; alpha?: DecimalString};
type RandomParamsRequest = {bits: 16 | 32 | 64 | 128};
type KeyPairRequest = {
  q: DecimalString; alpha: DecimalString; privateKey?: DecimalString;
};
type SharedSecretRequest = {
  q: DecimalString; privateKey: DecimalString; otherPublicKey: DecimalString;
};
type ExchangeRequest = {
  q: DecimalString; alpha: DecimalString;
  privateKeyA?: DecimalString; privateKeyB?: DecimalString;
};
type DhCaesarJsonRequest = SharedSecretRequest & {
  action: DhAction; data: string;
};

type ModPowStep = {
  index: number;
  bit: 0 | 1;
  exponentPrefix: DecimalString;
  squared: DecimalString;
  multiplied: DecimalString | null;
  result: DecimalString;
};

type PrimitiveRootCheck = {
  factor: DecimalString;
  exponent: DecimalString;
  result: DecimalString;
  passes: boolean;
};

type ParamsResponse = {
  success: true;
  q: DecimalString;
  alpha: DecimalString | null;
  factors: DecimalString[];
  primitiveRootChecks: PrimitiveRootCheck[];
  suggestedAlpha: DecimalString | null;
};

type RandomParamsResponse = Omit<ParamsResponse, "alpha" | "suggestedAlpha"> & {
  p: DecimalString;
  alpha: DecimalString;
  suggestedAlpha: null;
};

type KeyPairResponse = {
  success: true;
  privateKey: DecimalString;
  publicKey: DecimalString;
  steps: ModPowStep[];
};

type SharedSecretResponse = {
  success: true;
  sharedKey: DecimalString;
  steps: ModPowStep[];
};

type ExchangeResponse = {
  success: true;
  privateKeyA: DecimalString;
  privateKeyB: DecimalString;
  publicKeyA: DecimalString;
  publicKeyB: DecimalString;
  sharedKeyA: DecimalString;
  sharedKeyB: DecimalString;
  match: boolean;
  steps: {
    publicKeyA: ModPowStep[];
    publicKeyB: ModPowStep[];
    sharedKeyA: ModPowStep[];
    sharedKeyB: ModPowStep[];
  };
  warning: EducationalPrivateKeysWarning;
};

type DhCaesarResponse = {
  success: true;
  sharedKey: DecimalString;
  shift: DecimalString;
  result: string;
  warning?: ShiftZeroWarning; // field bị bỏ khi shift khác 0; không trả null
};
```

`multiplied` luôn hiện diện nhưng là `null` ở row có bit `0`. Trong params response,
`alpha` và `suggestedAlpha` luôn hiện diện và một trong hai có thể là `null`. Riêng
`warning` của Caesar bị bỏ hoàn toàn khi không có warning.

## 4. Tham số DH

### 4.1 Manual params — `/api/dh/params`

Request exact: `ParamsRequest`. Chỉ endpoint này áp trần
manual `10^12`.

```json
{"q":"23"}
```

```json
{
  "success":true,
  "q":"23",
  "alpha":null,
  "factors":["2","11"],
  "primitiveRootChecks":[],
  "suggestedAlpha":"5"
}
```

Đây chỉ là suggestion. FE không được coi `alpha:"5"` là đã được chọn; muốn dùng nó,
người dùng hoặc FE phải gửi lại rõ ràng ở request tiếp theo. Khi gửi
`{"q":"23","alpha":"5"}`, response có `alpha:"5"`, hai checks đầy đủ và
`suggestedAlpha:null`. Alpha được gửi nhưng sai trả error; server không silent replace.

### 4.2 Random params — `/api/dh/params/random`

Request exact: `RandomParamsRequest`; `bits` là number, không phải string.
Response là `RandomParamsResponse`; `alpha` luôn là string và
`suggestedAlpha` luôn `null`. `q`, `p`, `alpha`, `factors` và operand/result của checks
có thể chuyển nguyên văn sang `/keypair` hoặc `/exchange`.

```json
{"bits":32}
```

Primality tới 128 bit là probable-prime Miller–Rabin trong phạm vi giáo dục, không
phải chứng minh nguyên tố hay nhóm DH production.

## 5. Keypair, shared secret và exchange

### 5.1 Keypair — `/api/dh/keypair`

Request exact:

Request exact là `KeyPairRequest`; bỏ `privateKey` để server sinh, không gửi null.

Private key phải nằm trong `2..q-2` và public key suy ra không được là `1` hoặc
`q-1`. Nếu bỏ `privateKey`, server dùng CSPRNG và response vẫn trả private key để
minh họa. Ví dụ `q=23, alpha=5, privateKey=6` trả `publicKey="8"` cùng full trace.

### 5.2 Shared secret — `/api/dh/shared-secret`

Request exact là `SharedSecretRequest`. Endpoint này cố ý không nhận `alpha`.
Private key và peer public key đều phải thuộc `2..q-2`.

```json
{"q":"353","privateKey":"97","otherPublicKey":"248"}
```

trả `sharedKey:"160"` và trace kết thúc ở result `"160"`.

### 5.3 Exchange — `/api/dh/exchange`

Request exact là `ExchangeRequest`. Bỏ một hoặc cả hai private key
để server sinh; explicit `null` bị từ chối. Response luôn trả cả hai private keys,
`match`, bốn nhóm trace và warning exact:

```json
{
  "code":"EDUCATIONAL_PRIVATE_KEYS",
  "message":"Response trả khóa riêng để minh họa và đối chiếu phép tính. Trong hệ thống thực tế, khóa riêng không được gửi hoặc lưu ngoài bên sở hữu; khóa công khai phải được xác thực để chống tấn công người đứng giữa (MITM)."
}
```

FE phải render warning này như cảnh báo không chặn kết quả. Không log, persist hoặc
đưa private key vào URL/analytics.

## 6. Luồng A/B hoàn chỉnh tới Caesar

Luồng dưới đây dùng số cố định để FE test deterministic:

1. `/params` với `{"q":"23"}` → `suggestedAlpha:"5"`; chọn alpha ở UI.
2. A gọi `/keypair` với private key `"6"` → public key A `"8"`.
3. B gọi `/keypair` với private key `"15"` → public key B `"19"`.
4. A gọi `/shared-secret` với `privateKey:"6", otherPublicKey:"19"` → `sharedKey:"2"`.
5. B gọi `/shared-secret` với `privateKey:"15", otherPublicKey:"8"` → `sharedKey:"2"`.
6. Caesar dùng `shift = K mod 26 = "2"`.

```ts
const encrypted = await dhCaesarJson({
  q: "23", privateKey: "6", otherPublicKey: "19",
  action: "encrypt", data: "Hello World",
}); // result: "Jgnnq Yqtnf", sharedKey: "2", shift: "2"

const decrypted = await dhCaesarJson({
  q: "23", privateKey: "15", otherPublicKey: "8",
  action: "decrypt", data: encrypted.result,
}); // result: "Hello World"
```

Caesar chỉ đổi ASCII `A-Z/a-z`; Unicode, dấu câu và line ending được giữ nguyên.
Nếu `K mod 26 == 0`, request vẫn thành công và `warning.code == "SHIFT_ZERO"`; warning
không phải error và text không đổi.

`/api/dh/caesar` vẫn là đường tích hợp ưu tiên. Khi một caller đã lấy `sharedKey`
từ `/shared-secret` và cần dùng hai route Caesar standalone, có thể gửi nguyên decimal
string canonical đó làm `key`; backend giảm modulo 26 an toàn ở adapter. Không đổi
qua JavaScript `number`, vì shared key có thể vượt `Number.MAX_SAFE_INTEGER`.

## 7. `/api/dh/caesar`: JSON và multipart

JSON request exact:

```ts
type DhCaesarJsonRequest = SharedSecretRequest & {action: DhAction; data: string};
```

`action` là bắt buộc ở runtime; thiếu hoặc sai trả `INVALID_ACTION`. `data=""` bị
từ chối, nhưng whitespace-only hợp lệ. Response luôn là `DhCaesarResponse`.

Multipart dùng đúng năm parts: `file`, `q`, `privateKey`, `otherPublicKey`, `action`.
Không gửi `data`, `response_mode` hoặc field khác.

```ts
async function dhCaesarFile(input: {
  file: File; q: string; privateKey: string; otherPublicKey: string;
  action: "encrypt" | "decrypt";
}): Promise<DhCaesarResponse> {
  const form = new FormData();
  form.set("file", input.file);
  form.set("q", input.q);
  form.set("privateKey", input.privateKey);
  form.set("otherPublicKey", input.otherPublicKey);
  form.set("action", input.action);
  const response = await fetch("/api/dh/caesar", {method: "POST", body: form});
  const body = await response.json();
  if (!response.ok) throw body as DhErrorResponse;
  return body as DhCaesarResponse;
}
```

- Extension `.txt` không phân biệt hoa thường; file phải UTF-8 strict, không rỗng.
- Chính xác 5.242.880 byte được nhận; 5.242.881 byte bị 413. Đây là raw file bytes.
- UTF-8 BOM đầu file được nhận và bỏ khỏi visible `result`; response không phải file
  download, không có `Content-Disposition`, filename hoặc `response_mode`.
- Không tự thêm multipart `Content-Type`; không tạo attachment client-side như thể
  server đã trả file. Nếu product muốn nút tải, đó là quyết định FE riêng ngoài API.

## 8. Error contract và precedence

Mọi lỗi DH có đúng bốn field `{success:false,code,message,field}`. FE hiển thị
`message` tiếng Việt từ server; dùng `field` để focus control và `code` cho nhánh UX.

| HTTP | Code | Message exact / quy tắc | Field |
|---:|---|---|---|
| 413 | `REQUEST_TOO_LARGE` | `Yêu cầu vượt quá dung lượng cho phép.` | `null` |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | `Kiểu nội dung không được hỗ trợ.` | `null` |
| 422 | `INVALID_REQUEST` | `Dữ liệu gửi lên không hợp lệ.` | field đầu tiên hoặc `null` |
| 422 | `NOT_INTEGER` | `Giá trị phải là số nguyên dương.` | input tương ứng |
| 422 | `Q_OUT_OF_RANGE` | manual: `q phải từ 5 đến 10¹², hoặc dùng sinh tham số ngẫu nhiên.`; downstream: `q không được vượt quá 128 bit.` | `q` |
| 422 | `NOT_PRIME` | `q = {q} không phải số nguyên tố.` | `q` |
| 422 | `ALPHA_OUT_OF_RANGE` | `α phải thỏa 1 < α < q = {q}.` | `alpha` |
| 422 | `NOT_PRIMITIVE_ROOT` | `α = {alpha} không phải nguyên căn của {q}. Gợi ý α = {suggestion}.` | `alpha` |
| 422 | `BITS_INVALID` | `Chỉ hỗ trợ 16, 32, 64 hoặc 128 bit.` | `bits` |
| 422 | `PRIVATE_KEY_OUT_OF_RANGE` | `Khóa riêng phải thỏa 2 ≤ X ≤ q − 2 = {q-2}.` | private-key field |
| 422 | `PRIVATE_KEY_WEAK` | `Khóa riêng tạo khóa công khai không hợp lệ. Hãy chọn khóa riêng khác.` | private-key field |
| 422 | `PUBLIC_KEY_INVALID` | `Khóa công khai của bên kia không hợp lệ.` | `otherPublicKey` |
| 422 | `INVALID_ACTION` | `Action phải là encrypt hoặc decrypt.` | `action` |
| 422 | `EMPTY_INPUT` | `Dữ liệu đầu vào đang rỗng.` | `data` hoặc `file` |
| 422 | `MISSING_FILE` | `Thiếu file.` | `file` |
| 415 | `FILE_INVALID` | `Chỉ chấp nhận file .txt.` | `file` |
| 413 | `FILE_INVALID` | `File vượt quá dung lượng tối đa 5 MB.` | `file` |
| 415 | `UNSUPPORTED_ENCODING` | `File phải sử dụng UTF-8.` | `file` |
| 500 | `FILE_READ_FAILED` | `Không thể đọc file.` | `file` |
| 500 | `INTERNAL_ERROR` | `Đã xảy ra lỗi hệ thống.` | `null` |

Request có declared `Content-Length > 64 MiB` bị `REQUEST_TOO_LARGE` trước các lỗi
khác. Sau đó thứ tự chính là media/parse/duplicate → exact fields/control → q → alpha
→ private key → public key → action/data → computation. Multipart kiểm scalar trước
extension → size → empty → encoding.

Factorization, primitive-root search hoặc random generation có bound tài nguyên.
Group khó có thể trả 422 `FACTORIZATION_FAILED`, `PRIMITIVE_ROOT_NOT_FOUND` hoặc
`GENERATION_FAILED`; message public hiện là `Dữ liệu gửi lên không hợp lệ.` và `field`
có thể là `value`, `q`, `bits` hoặc private-key field. FE nên đề nghị người dùng sinh
group khác/thử lại; không biến các code này thành 500 và không giả định mọi prime 128-bit
tùy ý sẽ hoàn tất. Backend giới hạn bốn DH CPU jobs đồng thời; request vượt capacity
chờ lượt thay vì nhận một status “busy” riêng, nên FE phải giữ loading/cancel UX phù hợp.

## 9. BigInt, warning và state FE

Giữ decimal input/output dưới dạng string. Chỉ dùng [`BigInt(value)`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/BigInt)
cho tính toán hoặc so sánh cục bộ; `JSON.stringify` không serialize `bigint`, nên
phải đổi lại `.toString()`.
Không dùng `Number`, `parseInt` hoặc unary `+` cho q/keys vì có thể vượt
`Number.MAX_SAFE_INTEGER`.

```ts
function decimal(value: string): DecimalString {
  if (!/^(0|[1-9][0-9]*)$/.test(value)) throw new Error("invalid decimal string");
  return value;
}

const shift = BigInt(response.sharedKey) % 26n;
// Khi gửi lại: shift.toString(), không gửi shift bigint trực tiếp.
```

`response.ok === false` là error. `warning` trong HTTP 200 là kết quả thành công có
cảnh báo: UI vẫn hiển thị output, đồng thời render warning cạnh nó. Xóa trace/result
cũ khi q/alpha/key/action/data/file đổi; disable submit khi request đang chạy vì việc
kiểm q/factorization có thể tốn CPU.

## 10. History và privacy

- Chỉ `/api/dh/caesar` match server history; năm endpoint tham số/khóa không tạo row.
- JSON ghi `source="text"`; multipart ghi `source="file"`; `operation` theo action;
  `responseMode` luôn `null`.
- JSON lengths là Unicode code points. File lengths là raw/output UTF-8 bytes và tính
  cả 3 byte BOM nếu input có BOM.
- Không row/log nào được chứa q, alpha, private/public/shared key, shift, data/result,
  filename/content, trace hoặc warning. FE cũng không nên đưa các giá trị này vào
  telemetry hay local history ngoài lựa chọn rõ ràng của product.
- History best-effort: DB tắt/lỗi/schema cũ không được làm đổi status/body DH.

## 11. Checklist tích hợp

- [ ] Chỉ gọi đúng sáu URL tương đối và chỉ gửi field của request variant hiện tại.
- [ ] Crypto integer/shift là decimal string; `bits/index/bit` là number; boolean giữ boolean.
- [ ] Omit optional request fields; không gửi `null` thay omission.
- [ ] Missing alpha chỉ hiện suggestion; không tự coi suggestion là selected alpha.
- [ ] Trace/check/grouped steps giữ exact shape và left-to-right order.
- [ ] `/exchange` luôn hiển thị cảnh báo private keys giáo dục.
- [ ] Caesar hỗ trợ encrypt/decrypt, `SHIFT_ZERO` là warning chứ không phải error.
- [ ] Multipart đúng năm parts, `.txt`, UTF-8, exact 5 MiB; luôn parse JSON response.
- [ ] Error handler giữ exact four-field envelope và status 413/415/422/500.
- [ ] Không lưu/log/analytics parameters, keys, content, file, trace hoặc warning.
- [ ] UI không quảng bá ECDH/KDF/MITM protection hay production security.
