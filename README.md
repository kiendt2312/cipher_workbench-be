# Backend Caesar, Vigenère, Playfair, Affine, Columnar, Hill, DES, RSA và Diffie–Hellman

Backend FastAPI cung cấp API mã hóa/giải mã và trao đổi khóa cho chín thuật toán: năm hệ mã cổ điển
**Caesar**, **Vigenère**, **Playfair**, **Affine**, **Columnar Transposition**, hệ mã
khối cổ điển **Hill**, hệ mã khối **DES**, textbook **RSA**, và **Diffie–Hellman** phục vụ học tập.
API nhận văn bản JSON hoặc file `.txt`, trả kết quả xem trước dạng JSON hoặc file
đính kèm do server tạo.

Đây là dự án học tập, không phải công cụ bảo vệ dữ liệu nhạy cảm. Server là nguồn
có thẩm quyền cho validation và kết quả cipher. Với nguồn file upload, server còn
quyết định bytes/BOM và tên attachment; với nguồn text, client có thể tạo file từ
chính `result` server trả về. Client chỉ nên kiểm tra sơ bộ để hỗ trợ trải nghiệm.

Đội Frontend dùng
[`repo_docs/frontend-integration.md`](repo_docs/frontend-integration.md) làm contract
canonical, self-contained duy nhất cho cả 32 POST endpoint cipher, health và lịch sử.
Tổng snapshot là 35 operations: 32 POST và ba GET (random Hill, health, history).
Các file [`repo_docs/rsa-frontend-contract.md`](repo_docs/rsa-frontend-contract.md) và
[`repo_docs/dh-frontend-contract.md`](repo_docs/dh-frontend-contract.md) chỉ là
supporting reference theo feature.

## 1. Tổng quan hành vi

Ứng dụng chạy trong một tiến trình FastAPI trên cổng `8000`. Runtime phục vụ API
và OpenAPI; không có authentication hay session, và không lưu
input, key, tên file, nội dung file hay kết quả sau request. Khi đặt `DATABASE_URL`,
app ghi thêm **metadata** của mỗi request cipher vào SQLite cục bộ trên backend
(xem mục 9.1).

```text
JSON text hoặc multipart .txt
              │
              ▼
 request guards + validation xác định
              │
              ▼
 Caesar | Vigenère | Playfair | Affine | Columnar | Hill | DES | RSA | DH core
              │
              ▼
 JSON (hai trường; Hill/DES thêm warnings) hoặc attachment UTF-8
```

Repo này chỉ có backend. UI do project FE riêng đảm nhiệm và tích hợp theo
`repo_docs/frontend-integration.md`; app không phục vụ trang nào ở `/`.

## 2. Thuật toán

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
| Decrypt | `PDGW` | — | `ABXQ` (lọc: `ABX`) |
| Decrypt | `GWGW` | — | `XQXQ` (lọc: `XX`) |

Playfair cố ý mất thông tin. Decrypt trả `result` là uppercase prepared plaintext
**thô** (giữ mọi filler) cùng `padding: {count, positions, filtered}`. Filler được nhận
diện theo cấu trúc digraph: chữ thứ hai của một cặp là `X` (hoặc `Q` sau `X`) và cặp kế
tiếp bắt đầu bằng đúng chữ đầu của cặp đó (`BALXLOON → BALLOON`), hoặc đó là cặp cuối
(`TAXICABX → TAXICAB`). Vì ciphertext không phân biệt được filler với chữ thật, bản lọc
mất chữ thật trùng mẫu filler (ví dụ `AX → A`). Server không phục hồi `J`, case,
whitespace, dấu câu hay Unicode đã bị loại, nên round-trip không nhất thiết bằng
input gốc. `/api/playfair/file` nhận thêm `strip_padding=true|false` để attachment khi
decrypt là bản lọc.

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

### 2.6 DES

DES được tự cài đặt chỉ bằng thư viện chuẩn Python theo đúng các bảng PC-1, PC-2,
LS, IP, IP⁻¹, E, P, S1–S8 của tài liệu thuật toán; lõi dùng bảng tra dẫn xuất
(SP-box) để tăng tốc. `cryptography` chỉ nằm trong nhóm dev để test đối chiếu, không
phải dependency runtime.

- Khối 64 bit, khóa 64 bit nhập dưới dạng **đúng 16 ký tự hex**. Server bỏ khoảng
  trắng ASCII (space, tab, CR, LF, FF, VT) và không phân biệt hoa thường. 8 bit chẵn
  lẻ (bit 8, 16, …, 64) bị PC-1 loại và **không được kiểm tra hay tự sửa**, nên
  `123456789ABCDEF0` cho cùng kết quả với `133457799BBCDFF1`.
- Sinh khóa: PC-1 → C0, D0 (28 bit) → dịch vòng trái theo LS → PC-2 cho K1…K16.
- 16 vòng Feistel: `Li = Ri−1`, `Ri = Li−1 ⊕ P(S(E(Ri−1) ⊕ Ki))`; đầu ra là
  `IP⁻¹(R16L16)`. Giải mã dùng cùng thuật toán với khóa con K16…K1.
- Chế độ: `ECB` (mặc định, mỗi khối độc lập) hoặc `CBC` với IV đúng 16 hex. Ở `ECB`
  server bỏ qua `iv` dù có giá trị gì. IV sai khi giải mã `CBC` chỉ làm lệch khối 8
  byte đầu nên có thể vẫn trả 200; server không phát hiện được IV sai.
- Dữ liệu văn bản (`inputFormat=text`, mặc định) được mã UTF-8 rồi **luôn** đệm
  PKCS#7; dữ liệu đã đủ bội 8 byte vẫn thêm một khối `0808080808080808`.
- Dữ liệu hex (`inputFormat=hex`) là một hoặc nhiều khối, độ dài bội của 16 ký tự
  hex, **không đệm**; dùng cho bài tập trên slide.
- Bản mã luôn là hex in hoa, không khoảng trắng. Giải mã `outputFormat=text` gỡ
  PKCS#7 rồi giải mã UTF-8 nghiêm ngặt; `outputFormat=hex` trả nguyên byte dạng hex,
  không gỡ padding.
- 4 khóa yếu và 12 khóa nửa yếu được nhận diện sau khi xóa bit chẵn lẻ; chúng chỉ
  sinh cảnh báo W01/W02, không chặn thao tác.

```text
0123456789ABCDEF + 133457799BBCDFF1 (hex, ECB)              → 85E813540F0AB405
Hello World      + 133457799BBCDFF1 (text, ECB)             → B1CA74BB3514268701A9ACC3E4E69FAA
Hello World      + 133457799BBCDFF1 (text, CBC, IV 0…0)     → B1CA74BB351426875F9A5BCA734D9EF4
8787878787878787 + 0E329232EA6D0D73 (hex, ECB)              → 0000000000000000
```

### 2.7 Textbook RSA (chỉ dùng để học)

RSA dùng số nguyên Python và phép lũy thừa modulo trực tiếp, không OAEP, không
PKCS#1 v1.5, không chữ ký và không serialization khóa. Khóa ngẫu nhiên chỉ có
modulus đúng 16/32/64/128 bit, vì vậy **không an toàn cho dữ liệu thật**. Server
không thể xác thực ciphertext, private key hoặc metadata; khóa/metadata sai vẫn có
thể tạo plaintext hợp lệ quan sát được.

- Mọi số mật mã là chuỗi thập phân ASCII, tối đa `2^128-1`; `p,q` thủ công tối đa
  `10^12`. Control như `bits`, `traceBlockIndex`, `originalUtf8ByteLength` là JSON integer.
- `inputType=number|text`; text dùng `mode=char|block`. Char ánh xạ từng Unicode code
  point. Block ghép UTF-8 big-endian theo `k` lớn nhất thỏa `256^k <= n-1`.
- Text được giữ nguyên, gồm whitespace, CR/LF/CRLF, composition, trailing NUL và BOM
  `U+FEFF`. Block decrypt phải nhận lại `originalUtf8ByteLength` do encrypt trả.
- Transform luôn trả toàn bộ blocks/result. `traceBlockIndex` tùy chọn trả bảng
  square-and-multiply đầy đủ cho đúng một block; keygen luôn trả full Euclid table.
- RSA stateless về nội dung/khóa. Hai route transform ghi history **metadata** chuẩn
  theo best-effort khi có DB; hai route keygen không ghi. File chỉ là plaintext `.txt`
  để encrypt, tối đa 1.000.000 byte và 10.000 code point; không upload/download ciphertext.

```json
POST /api/rsa/keys
{"p":"17","q":"11","e":"7"}

POST /api/rsa/encrypt
{"e":"17","n":"3233","inputType":"number","data":"65"}

POST /api/rsa/decrypt
{"d":"23","n":"187","inputType":"number","cipher":["11"]}
```

Lỗi RSA có đúng `{success:false,code,message,field}` với status 413/415/422/500;
field lạ, trùng hoặc không áp dụng đều bị từ chối.

### 2.8 Diffie–Hellman standalone và integration Caesar

DH là feature độc lập ngang cấp Caesar: năm endpoint đầu sinh/kiểm tra tham số,
tạo cặp khóa, tính shared secret, trao đổi hai phía và trả trace từ phép tính thật.
Endpoint thứ sáu `/api/dh/caesar` là integration dùng `K mod 26` với Caesar core;
nó không thay thế hay thay đổi ba endpoint Caesar standalone. Tất cả đại lượng mật
mã là decimal string; `bits` và index/bit của trace là JSON integer. Đây không phải giao thức DH production:
không có ECDH, KDF, xác thực chống MITM hoặc lưu khóa server-side. `/exchange` cố ý
trả private key để minh họa/đối chiếu phép tính và kèm cảnh báo về sở hữu private key,
xác thực public key. Trace lũy thừa modulo chạy từ bit trái sang phải.

`/params` thủ công giới hạn `q ≤ 10^12`; các endpoint downstream tự kiểm tra q đến
128 bit và không dùng provenance/state. Nếu bỏ `alpha`, `/params` chỉ trả
`suggestedAlpha`, không tự chọn thay client.

Primality 128-bit là Miller–Rabin xác suất, không phải proof deterministic và không
tái dùng claim deterministic `<2^64` của RSA. Factorization tham số tùy ý có thể tốn
tài nguyên dù đã bounded và chạy ngoài event loop; xem
[`docs/dh-engineering-evidence.md`](docs/dh-engineering-evidence.md).

## 3. API: 33 endpoint (32 POST, 1 GET)

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
| Hill | `POST /api/hill/encrypt` | JSON | Mã hóa text và trả dữ liệu từng khối |
| Hill | `POST /api/hill/decrypt` | JSON | Giải mã text và trả dữ liệu từng khối |
| Hill | `POST /api/hill/key/analyze` | JSON | Phân tích khóa |
| Hill | `GET /api/hill/key/random?m=3` | Query | Sinh khóa hợp lệ cấp 2–4 |
| DES | `POST /api/des/encrypt` | JSON | Mã hóa text hoặc hex, ECB/CBC |
| DES | `POST /api/des/decrypt` | JSON | Giải mã bản mã hex ra text hoặc hex |
| DES | `POST /api/des/file` | Multipart | Mã hóa/giải mã file |
| DES | `POST /api/des/trace` | JSON | Giá trị trung gian của đúng một khối |
| RSA | `POST /api/rsa/keys` | JSON | Sinh khóa thủ công và full Euclid table |
| RSA | `POST /api/rsa/keys/random` | JSON | Sinh modulus đúng 16/32/64/128 bit |
| RSA | `POST /api/rsa/encrypt` | JSON hoặc multipart | Mã hóa number/text hoặc plaintext `.txt` |
| RSA | `POST /api/rsa/decrypt` | JSON | Giải mã number/text từ cipher package |
| DH | `POST /api/dh/params` | JSON | Kiểm tra q/alpha thủ công, alpha có thể bỏ để lấy suggestion |
| DH | `POST /api/dh/params/random` | JSON | Sinh safe-prime group 16/32/64/128 bit |
| DH | `POST /api/dh/keypair` | JSON | Sinh hoặc kiểm tra private key và trả public key/trace |
| DH | `POST /api/dh/shared-secret` | JSON | Tính shared secret và trace |
| DH standalone | `POST /api/dh/exchange` | JSON | Tính cả hai phía, trả private/public/shared keys, match và traces |
| DH–Caesar integration | `POST /api/dh/caesar` | JSON hoặc multipart | Tính K thật rồi Caesar bằng `K mod 26`; file `.txt` luôn trả JSON |

Consumer đang dùng allowlist 12 route phải mở lên đúng ba path Columnar trên để
thành 15 route; không có route generalized hoặc versioned mới. OpenAPI gắn cả ba
operation vào tag `Columnar Transposition` và là projection machine-readable của
contract request/response đã test.

Hill là ngoại lệ có chủ đích: không có `/api/hill/file`. FE đọc `.txt` UTF-8,
kiểm tối đa 5 MiB (5.242.880 byte), rồi gửi nội dung qua endpoint JSON. Hai route biến đổi
trả `{success,result,blocks,key,warnings}`, riêng decrypt thêm `padding` nhận diện tối đa
`m − 1` chữ `padChar` ở cuối (`result` vẫn giữ chúng); hai route khóa trả
`{success,result,warnings}`. Lỗi nghiệp vụ Hill trả thêm `code` và `details`.

DES có đủ text/file như năm cipher cổ điển, thêm `/api/des/trace`. Ba route
encrypt/decrypt/file (content mode) trả `{success,result,warnings}`; `/trace` trả
thêm `trace`. Lỗi DES dùng envelope hai trường `{success,message}` như năm cipher cổ
điển, không có `code`. Chi tiết ở §3.3 và §4.1.

RSA chỉ có đúng bốn POST route trên, không có `/file`, `/trace`, download hay history
route riêng; metadata transform được đọc qua `GET /api/history` chung. `/encrypt` là
route duy nhất nhận cả JSON và multipart; mọi response RSA kể cả file encrypt đều là JSON.

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
| DES | `{"text":"Hello World","key":"133457799BBCDFF1"}` | String 16 hex; thêm `inputFormat`/`outputFormat`, `mode`, `iv` (§3.3) |

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
| `strip_padding` | Không (chỉ Playfair) | `true` hoặc `false`; mặc định `false`; `true` cho attachment decrypt là bản đã lọc ký tự đệm |

`action`, `response_mode` và `strip_padding` phân biệt hoa thường; `strip_padding` sai trả
422 `Tùy chọn lọc ký tự đệm phải là true hoặc false.`. Với Caesar, key multipart được
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

`POST /api/des/file` cũng là exact multipart object với field `file,key,action` và
optional `mode`, `iv`, `response_mode` (§3.3).

### 3.3 DES

Ba route JSON nhận object strict, field camelCase; field lạ, trùng hoặc sai kiểu trả
422 `Dữ liệu gửi lên không hợp lệ.`. Giá trị enum khớp chính xác, phân biệt hoa thường.

| Route | Field (★ bắt buộc) | Ghi chú |
|---|---|---|
| `POST /api/des/encrypt` | `text`★, `key`★, `inputFormat` (`text`\|`hex`, mặc định `text`), `mode` (`ECB`\|`CBC`, mặc định `ECB`), `iv` (string hoặc `null`) | `text` UTF-8 + PKCS#7; `hex` bội 16 ký tự, không đệm |
| `POST /api/des/decrypt` | `text`★ (bản mã hex), `key`★, `outputFormat` (`text`\|`hex`, mặc định `text`), `mode`, `iv` | Bản mã được bỏ khoảng trắng/xuống dòng, nhận chữ thường |
| `POST /api/des/trace` | `block`★ (đúng 16 hex, cho phép khoảng trắng), `key`★, `operation` (`encrypt`\|`decrypt`, mặc định `encrypt`) | Không có mode, IV, padding; không ghi lịch sử |
| `POST /api/des/file` | Multipart `file`★, `key`★, `action`★, `mode`, `iv`, `response_mode` | encrypt: file text → hex; decrypt: file hex (nhiều dòng được) → text |

`iv` bắt buộc là 16 hex khi `mode=CBC` và bị bỏ qua khi `mode=ECB`. Cặp định dạng
phải khớp: bản mã của `inputFormat=text` giải mã bằng `outputFormat=text`; bản mã
của `inputFormat=hex` giải mã bằng `outputFormat=hex`. Giải mã bản mã hex bằng
`outputFormat=text` thường gặp lỗi padding; giải mã bản mã text bằng
`outputFormat=hex` trả cả các byte PKCS#7 (ví dụ `…0505050505`).

```bash
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
  -d '{"block":"0123456789ABCDEF","key":"133457799BBCDFF1","operation":"encrypt"}'

curl -sS -X POST http://localhost:8000/api/des/file \
  -F 'file=@input.txt;type=text/plain' -F 'key=133457799BBCDFF1' \
  -F 'action=encrypt' -F 'mode=CBC' -F 'iv=0000000000000000' -F 'response_mode=content'
```

Response `/trace` (rút gọn; `subkeys` và `rounds` luôn đủ 16 phần tử, `sbox` đủ 8):

```json
{
  "success": true,
  "result": "85E813540F0AB405",
  "trace": {
    "operation": "encrypt",
    "input": "0123456789ABCDEF",
    "key": "133457799BBCDFF1",
    "pc1": "F0CCAAF556678F",
    "subkeys": [{"n": 1, "shift": 1, "c": "E19955F", "d": "AACCF1E", "k": "1B02EFFC7072"}],
    "ip": "CC00CCFFF0AAF0AA",
    "l0": "CC00CCFF",
    "r0": "F0AAF0AA",
    "rounds": [{
      "n": 1, "subkey": 1,
      "expansion": "7A15557A1555", "xorKey": "6117BA866527",
      "sbox": [{"row": 0, "col": 12, "value": 5}, {"row": 1, "col": 8, "value": 12}],
      "sboxOutput": "5C82B597", "f": "234AA9BB", "l": "F0AAF0AA", "r": "EF4A6544"
    }],
    "preOutput": "0A4CD99543423234"
  },
  "warnings": []
}
```

Với `operation=decrypt`, `input` là bản mã, `result` là bản rõ hex và
`rounds[i].subkey` chạy từ 16 về 1; `subkeys` vẫn theo thứ tự K1…K16.

`/api/des/file` dùng lại toàn bộ pipeline file hiện hành (§5): `response_mode=content`
trả `{success,result,warnings}`; `response_mode=file` trả attachment
`<tên>.encrypted.txt`/`<tên>.decrypted.txt`, không mang warnings. Chiều decrypt của
file luôn ra text, nên file chỉ giải mã được bản mã của văn bản UTF-8.

Giới hạn 5 MiB (5.242.880 byte UTF-8 của `text`/`block`, hoặc byte file) áp dụng cho
**cả hai chiều**. Bản mã hex dài gấp đôi dữ liệu, nên văn bản lớn nhất còn giải mã lại
được qua API là **2.621.439 byte UTF-8**; bản mã của văn bản lớn hơn bị 413 ở chiều
giải mã. Trên máy đo (Ryzen 7, Python 3.12), mã hóa 5 MiB mất khoảng 6 giây mỗi
chiều; giải mã 5 MiB hex (2,5 MiB dữ liệu) khoảng 3 giây.

## 4. Response và lỗi

Với năm cipher cũ, text thành công và file `response_mode=content` trả HTTP `200`
với đúng hai field:

```json
{"success":true,"result":"Khoor Zruog"}
```

Lỗi của năm cipher cũ trả JSON đúng hai field, kể cả request dùng `response_mode=file`:

```json
{"success":false,"message":"Khóa phải là số nguyên."}
```

Hill là ngoại lệ đã duyệt: transform trả `blocks,key,warnings` (decrypt thêm `padding`),
key API trả `result,warnings`, và lỗi nghiệp vụ trả thêm `code,details`. Playfair decrypt
(text và file content mode) trả thêm `padding`. DES thành công trả
`{success,result,warnings}` (`/trace` thêm `trace`), nhưng lỗi DES giữ đúng envelope
hai trường `{success,message}`. Contract năm cipher cũ
không có machine error `code`, `detail`, field errors, `normalizedInput`, matrix,
prepared text hoặc metadata bổ sung. Client nên dùng
HTTP status và request context cho logic, còn `message` tiếng Việt để hiển thị.

File `response_mode=file` thành công là ngoại lệ không dùng JSON: server trả body
bytes UTF-8 với `Content-Type: text/plain; charset=utf-8` và
`Content-Disposition: attachment`.

Các nhóm status chính:

| Status | Ý nghĩa |
|---:|---|
| `200` | Thành công; JSON preview hoặc attachment |
| `413` | File vượt 5 MiB, text Hill/DES vượt 5 MiB hoặc request rõ ràng vượt trần hạ tầng |
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

### 4.1 Lỗi và cảnh báo DES

Mọi lỗi của bốn route DES là đúng `{"success":false,"message":"…"}`, kể cả ở
`response_mode=file`; mã DES-Exx chỉ dùng để đặt tên test/tài liệu, không có trong
response. `{n}` là số ký tự sau khi bỏ khoảng trắng ASCII.

| Mã | Điều kiện | HTTP | `message` |
|---|---|---:|---|
| Body | Media type không phải JSON, JSON hỏng, không phải object, field lạ/trùng, `text`/`key`/`block`/`iv` sai kiểu (khác string và null); multipart field lạ/trùng hoặc bị cắt | 422 | `Dữ liệu gửi lên không hợp lệ.` |
| E01 | `text` thiếu/null/rỗng; dữ liệu hex rỗng sau khi bỏ khoảng trắng | 422 | `Nhập văn bản hoặc tải file .txt để bắt đầu.` |
| E02 | `key` thiếu/null/rỗng sau khi bỏ khoảng trắng | 422 | `Thiếu khóa. Khóa DES gồm 16 ký tự hex (64 bit).` |
| E03 | Khóa có ký tự ngoài `0–9`, `a–f`, `A–F` | 422 | `Khóa chỉ được chứa ký tự hex 0–9, A–F.` |
| E04 | Khóa hex khác 16 ký tự | 422 | `Khóa phải đúng 16 ký tự hex (64 bit), hiện có {n}.` |
| E05 | Dữ liệu hex có ký tự không hợp lệ | 422 | `Dữ liệu hex chỉ được chứa ký tự hex 0–9, A–F.` |
| E06 | Dữ liệu hex không phải bội 16 ký tự | 422 | `Dữ liệu hex phải có độ dài là bội của 16 ký tự hex (64 bit), hiện có {n}.` |
| E07 | Giải mã ra text nhưng PKCS#7 sai | 422 | `Padding không hợp lệ: sai khóa hoặc bản mã bị hỏng.` |
| E08 | Giải mã ra byte không phải UTF-8 | 422 | `Kết quả giải mã không phải văn bản UTF-8 hợp lệ. Thử outputFormat = hex.` |
| E09 | `mode=CBC` mà `iv` thiếu/null/không đúng 16 hex | 422 | `IV phải đúng 16 ký tự hex khi dùng chế độ CBC.` |
| E10 | `inputFormat`, `outputFormat`, `mode`, `operation` sai giá trị, sai kiểu hoặc `null` | 422 | `Tham số {name} không hợp lệ.` |
| E11 | Lỗi file | 415/413/422/500 | Message file hiện hành (§5): `Chỉ chấp nhận file .txt.`, `File phải sử dụng UTF-8.`, `File vượt quá dung lượng tối đa 5 MB.`, `Thiếu file.`, `File không được để trống.`, `Action phải là encrypt hoặc decrypt.`, `Response mode phải là content hoặc file.`, `Không thể đọc file.` |
| E12 | UTF-8 của `text`/`block` vượt 5.242.880 byte | 413 | `Dữ liệu vượt quá 5 MiB.` |
| E13 | `/trace` với `block` không phải đúng 16 hex | 422 | `Trace chỉ áp dụng cho đúng 1 khối 16 ký tự hex.` |

Request có `Content-Length` hợp lệ lớn hơn 64 MiB bị guard chặn trước: route JSON DES
trả 413 `Yêu cầu vượt quá dung lượng cho phép.`, `/api/des/file` trả 413
`File vượt quá dung lượng tối đa 5 MB.`. Lỗi bất ngờ trả 500 `Đã xảy ra lỗi hệ thống.`.

Thứ tự JSON: `guard 64 MiB → body → 5 MiB (E12) → E10 (inputFormat/outputFormat →
mode → operation) → khóa (E02/E03/E04) → IV khi CBC (E09) → dữ liệu (E01/E05/E06,
hoặc E13 với /trace) → E07 → E08`. Thứ tự file: `guard/multipart framing → exact
field set → file → khóa → action → response_mode → mode → IV khi CBC → extension →
5 MiB → file rỗng → UTF-8 → nội dung hex khi decrypt → E07 → E08`.

Cảnh báo không chặn kết quả, luôn là object `{code,message,details}`, theo thứ tự W01
→ W02 → W03, mỗi mã tối đa một lần:

| Mã | Khi nào | `message` | `details` |
|---|---|---|---|
| W01 | Khóa yếu (mọi thao tác dùng khóa: encrypt, decrypt, file, trace) | `Khóa yếu: mã hóa hai lần sẽ trả lại bản rõ. Không nên dùng.` | `{}` |
| W02 | Khóa nửa yếu (như W01) | `Khóa nửa yếu: tồn tại khóa khác giải mã được bản mã của khóa này.` | `{}` |
| W03 | Chỉ khi mã hóa `ECB` (JSON hoặc file content) và bản mã có ít nhất hai khối giống nhau | `Chế độ ECB: có khối bản mã lặp lại, lộ cấu trúc bản rõ. Cân nhắc dùng CBC.` | `{"repeatedBlocks": <số khối trùng một khối trước nó>}` |

## 5. Contract file

- Chỉ nhận filename kết thúc bằng `.txt`, không phân biệt hoa thường; ví dụ
  `.TXT` hợp lệ nhưng `.txt.exe` không hợp lệ. MIME upload không quyết định tính
  hợp lệ; filename và bytes là authority.
- File phải là UTF-8 thường hoặc UTF-8 có BOM.
- Giới hạn chính xác là `5 MiB = 5 * 1024 * 1024 = 5.242.880 byte` nội dung file.
  Đúng giới hạn được chấp nhận; `5.242.881` byte trả HTTP `413`. Message public
  vẫn ghi “5 MB” để giữ contract đã chấp nhận.
- File `0` byte bị từ chối, nhưng file chỉ có UTF-8 BOM hợp lệ. Whitespace-only
  hợp lệ với Caesar/Vigenère/Affine/Columnar và DES encrypt,
  nhưng Playfair từ chối sau normalization và DES decrypt trả
  `Nhập văn bản hoặc tải file .txt để bắt đầu.`.
- `response_mode=content` trả JSON preview và loại BOM khỏi chuỗi `result`; với DES
  preview có thêm mảng `warnings`.
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
- App không phục vụ UI. Mặc định không bật CORS: FE dev server nên proxy `/api` tới
  `http://localhost:8000` và giữ URL API tương đối. Khi FE chạy ở origin khác mà
  không có proxy, đặt `CORS_ALLOW_ORIGINS` (xem mục 9.1).
- Swagger UI: <http://localhost:8000/docs>
- OpenAPI JSON: <http://localhost:8000/openapi.json>
- Health: `GET /api/health` trả `{"success":true,"result":{"app":"ok","database":…}}`
  với `database` là `ok`, `unavailable` (HTTP 503) hoặc `disabled` (không có
  `DATABASE_URL`).
- Lịch sử: `GET /api/history?limit=&cursor=&cipher=&operation=` trả metadata thao
  tác, mới nhất trước; contract chi tiết nằm trong `repo_docs/frontend-integration.md`.
- Request guard có trần hạ tầng `64 MiB` cho một `Content-Length` decimal hợp lệ;
  trần này không thay đổi giới hạn nghiệp vụ file 5 MiB. Cả sáu route file (năm cipher
  cổ điển và DES) được phân loại bằng file-size message và multipart-completion guard;
  các route text Affine/Columnar/Hill/DES (gồm `/api/des/trace`) dùng message request
  generic giống các route text khác.

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

Không đặt `DATABASE_URL` thì app chạy không có database: 26 POST route cipher hoạt
động bình thường, `/api/health` báo `database: "disabled"` và `/api/history` trả
503. Muốn chạy app bằng uv (có `--reload`) với SQLite, tạo file bằng migration
SQLite trước rồi trỏ `DATABASE_URL` tới absolute local path; app không tự tạo file:

```bash
export DATABASE_URL="sqlite+aiosqlite:////tmp/cipher-history.sqlite3"
uv run alembic -c alembic_sqlite.ini upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Nếu service `app` của compose cũng đang chạy thì dừng nó trước
(`docker compose stop app`) để giải phóng cổng host `${APP_HOST_PORT:-8080}`.

Sau khi server khởi động, đối chiếu runtime tại `/docs` hoặc `/openapi.json` thay
vì duy trì một bản OpenAPI sao chép trong README.

## 8. Test, lint và format

```bash
uv run pytest
uv run pytest --no-cov tests/integration/test_app_runtime.py
uv run ruff check .
uv run ruff format --check .
```

Các test runtime SQLite dùng file tạm. Test legacy transfer đánh dấu `db` vẫn cần
PostgreSQL disposable chỉ kiểm legacy migration/source và tự bỏ qua khi không có
`TEST_DATABASE_URL`; app runtime PostgreSQL đã retire và được thay bằng các test
SQLite disposable. Không trỏ biến
này tới database người dùng.

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
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:8000/docs
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:8000/openapi.json
```

### 9.1 docker-compose với SQLite local trên backend

`docker-compose.yml` chạy migration SQLite một lần rồi khởi động đúng một process
`app`; hai service dùng cùng named volume local ở `/data`. Stack mặc định không
khởi động PostgreSQL. Frontend ở máy khác vẫn chỉ gọi HTTP API.

```bash
cp .env.example .env
docker compose up --build
curl -s http://localhost:8080/api/health
# {"success":true,"result":{"app":"ok","database":"ok","history":"enabled"}}
curl -s 'http://localhost:8080/api/history?limit=5'
docker compose down        # giữ dữ liệu
```

`.env` bị gitignore và dockerignore. App không tự tạo bảng khi khởi động; schema
chỉ thay đổi qua migration SQLite riêng. Không dùng `docker compose down -v`: named
volume là dữ liệu history, còn PostgreSQL legacy chỉ được retire theo checklist
project-scoped sau backup/restore/reconciliation. Xem
[`docs/sqlite-history-runbook.md`](docs/sqlite-history-runbook.md).

Bảng `cipher_operations` chỉ lưu metadata: cipher, operation, nguồn text/file,
response mode, độ dài input/output (code point cho text, byte UTF-8 cho file),
HTTP status, thành công hay lỗi và thời gian xử lý. Không lưu plaintext,
ciphertext, key, tên file, nội dung file, IP hay user agent. Với RSA, bảng cũng không
lưu `p/q/e/d`, public/private key, `data`, cipher array, `textMetadata`,
`originalUtf8ByteLength` hoặc trace Euclid/per-bit. Ghi lịch sử là
best-effort: DB lỗi hoặc chậm quá 500 ms thì bản ghi bị bỏ qua, response cipher
không đổi.

Có 23 route biến đổi được ghi: encrypt/decrypt/file của năm cipher cổ điển và DES,
encrypt/decrypt của Hill, cùng hai transform RSA. RSA encrypt JSON có `source=text`,
encrypt multipart `.txt` có `source=file`, decrypt có `source=text`; `responseMode`
luôn null. JSON RSA text encrypt chỉ ghi `inputLength` code point, text decrypt chỉ
ghi `outputLength` code point, multipart chỉ ghi `inputLength` raw byte; phía cipher
array và number để length null. Chỉ `/api/dh/caesar` ghi metadata DH; năm route DH
còn lại không ghi, và không tham số/khóa/content/file/trace/warning nào được lưu.
Hai route khóa Hill/RSA và `/api/des/trace` không ghi.

SQLite dùng baseline riêng ở effective schema có đủ `des` và `rsa`; không chạy hoặc
stamp chuỗi PostgreSQL `0001`–`0004` trên file SQLite. PostgreSQL legacy chỉ được đọc
trong transfer/reconciliation. Cutover và rollback/retirement theo runbook, không
dùng destructive SQLite downgrade làm production rollback.

Project không có authentication, nên việc đọc lịch sử được khóa bằng cấu hình:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `HISTORY_API_ENABLED` | tắt | `true`/`1`/`yes`/`on` mới bật `GET /api/history`; khi tắt endpoint trả 404, việc ghi lịch sử vẫn chạy. Khi bật, app log một cảnh báo lúc khởi động vì endpoint không có xác thực |
| `HISTORY_RETENTION_DAYS` | `30` | Bản ghi cũ hơn số ngày này bị xóa (1 đến 3650; giá trị sai làm app không khởi động) |
| `CORS_ALLOW_ORIGINS` | rỗng | Danh sách origin FE chính xác, cách nhau bằng dấu phẩy, ví dụ `https://app.example.com,http://localhost:5173`. Rỗng thì không gửi header CORS. Không nhận `*`, wildcard hay dấu `/` cuối; giá trị sai làm app không khởi động |

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
├── main.py                         # assembly, router, middleware
├── config.py                       # giới hạn file/request, cổng, DATABASE_URL
├── core/
│   ├── caesar.py                   # Caesar thuần
│   ├── vigenere.py                 # Vigenère repeating-key thuần
│   ├── playfair.py                 # Playfair 5×5 thuần
│   ├── affine.py                   # Affine modulo 26 thuần
│   ├── columnar.py                 # Columnar Transposition thuần
│   ├── hill.py                     # Hill vector hàng, ma trận cấp 2–4
│   ├── des.py                      # DES 16 vòng, ECB/CBC, PKCS#7, trace
│   └── rsa.py                      # textbook RSA, Unicode và block UTF-8
├── api/
│   ├── routes_text.py              # Caesar JSON
│   ├── routes_file.py              # Caesar multipart
│   ├── routes_additional_text.py   # Vigenère/Playfair JSON
│   ├── routes_additional_file.py   # Vigenère/Playfair multipart
│   ├── routes_affine_text.py       # Affine JSON strict
│   ├── routes_affine_file.py       # Affine multipart strict
│   ├── routes_columnar_text.py     # Columnar JSON strict
│   ├── routes_columnar_file.py     # Columnar multipart strict
│   ├── routes_hill.py              # bốn API Hill
│   ├── hill_schemas.py             # decoder/validator Hill strict
│   ├── routes_des.py               # DES encrypt/decrypt/trace JSON
│   ├── routes_des_file.py          # DES multipart strict
│   ├── des_schemas.py              # decoder/validator DES strict
│   ├── routes_rsa.py               # bốn endpoint RSA JSON/multipart
│   ├── rsa_schemas.py              # decoder/validator RSA strict
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
│   ├── routes.py                   # 23 route biến đổi được ghi lịch sử
│   ├── cursor.py                   # cursor phân trang opaque
│   └── store.py                    # ghi/đọc cipher_operations
└── errors/
    ├── messages.py                 # message public canonical
    ├── exceptions.py               # lỗi ứng dụng có status
    └── handlers.py                 # JSON envelope và log an toàn

alembic/                            # chuỗi migration PostgreSQL legacy 0001-0004
alembic_sqlite/                     # baseline/migration SQLite riêng
alembic_sqlite.ini                  # uv run alembic -c ... upgrade head
docker-compose.yml                  # migrate + one-process app + local data volume

tests/
├── unit/                            # core, validation, file helpers, layering
└── integration/                     # HTTP/OpenAPI, guards, SQLite/continuity
```

Các core là module thuần, không phụ thuộc FastAPI/file transport. HTTP adapters
chịu trách nhiệm validation và gọi đúng core; helper file dùng chung kiểm soát
bytes, encoding, BOM và attachment; error handlers dùng một envelope thống nhất.

## 11. Phạm vi và ngoài phạm vi

Repository này là backend cipher service cho tám cipher: Caesar, Vigenère, Playfair,
Affine, Columnar Transposition, Hill, DES và RSA.
UI thuộc project FE riêng, là consumer tách biệt tích hợp theo
`repo_docs/frontend-integration.md`.

Ngoài phạm vi hiện tại:

- authentication, authorization, session và lịch sử theo từng user trên server;
- lưu nội dung người dùng (input, key, file, kết quả) vào database;
- cipher khác ngoài tám cipher này, autokey Vigenère, Playfair 6×6 hoặc Playfair Unicode/lossless;
- 3DES, AES, các chế độ CFB/OFB/CTR, sinh khóa từ mật khẩu (KDF), xác thực bản mã
  (MAC), kiểm tra/tự sửa bit chẵn lẻ của khóa DES và demo thám mã DES;
- phục hồi format hoặc `J` khi decrypt Playfair, và phân biệt chữ thật với ký tự đệm
  trùng mẫu (bản lọc `padding.filtered` có thể bỏ nhầm; `result` luôn là bản thô);
- CORS có credentials (cookie) hoặc mở cho mọi origin;
- production reverse proxy, TLS, rate limiting, cloud deployment và CI/CD;
- streaming file lớn hơn giới hạn nghiệp vụ.

Dockerfile chỉ đóng gói app hiện có; nó không phải cấu hình production deployment
hoàn chỉnh.

## 12. Nguồn đặc tả và thứ tự áp dụng

README là bản nhập môn, không thay thế đặc tả hoặc OpenAPI. Khi có khác biệt, dùng
thứ tự sau:

1. [OpenSpec Diffie–Hellman đang hoạt động](openspec/changes/add-diffie-hellman/) cho DH,
   [OpenSpec RSA đang hoạt động](openspec/changes/add-rsa-cipher/) cho RSA (gồm quyết định chủ sở
   hữu Q1–Q16 ngày 2026-10-06), [OpenSpec DES](openspec/changes/archive/2026-10-01-add-des-cipher/)
   cho DES (gồm quyết định chủ sở hữu Q1–Q22 ngày 2026-10-01),
   [OpenSpec Hill đã hoàn thành](openspec/changes/archive/2026-10-01-add-hill-cipher/)
   cho Hill, [OpenSpec Columnar đã hoàn thành](openspec/changes/archive/2026-09-28-add-columnar-transposition-cipher/)
   cho Columnar, [OpenSpec Affine](openspec/changes/archive/2026-09-28-add-affine-cipher/) cho Affine,
   [OpenSpec Playfair/Vigenère đã hoàn thành](openspec/changes/archive/2026-09-28-add-playfair-vigenere-ciphers/)
   cho hai cipher đó, cùng
   [OpenSpec Caesar Week 1 đã hoàn thành](openspec/changes/archive/2026-09-28-caesar-cipher-week1-mvp/)
   cho Caesar và contract dùng chung.
2. Runtime trong `app/`, các test contract và `/openapi.json` xác nhận cách đặc tả
   được hiện thực ở revision đang chạy.
3. [Frontend integration guide](repo_docs/frontend-integration.md) diễn giải
   consumer contract chi tiết và phải được đồng bộ nếu lệch hai nguồn trên.
4. [Bản scope Caesar bảo tồn](docs/reference/be-scope-v1.0.md) và các source DOCX
   dùng để truy vết yêu cầu gốc. Với DES, `Scope Backend_ Hệ mã hóa DES.html` là nguồn
   tham số, bảng lỗi/cảnh báo, API, test vector T01–T20 và tiêu chí nghiệm thu;
   `Hệ mã hóa DES_ thuật toán và logic.html` là nguồn bảng hoán vị, hộp S, quy ước bit
   và giá trị trung gian. Cả hai bị các quyết định chủ sở hữu ngày 2026-10-01 ghi đè ở
   các điểm trong bảng dưới.
5. `Caesar_Cipher_Tool_Demo.html` và `affine-cipher.html` chỉ là UI/algorithm
   reference; mock, client-side result/default, giới hạn 1 MB,
   filename dấu gạch dưới, host/cổng hard-code hoặc local cipher trong demo không
   ghi đè accepted behavior.

Khác biệt có chủ đích giữa scope DES và runtime:

| Scope DES nói | Runtime làm | Quyết định |
|---|---|---|
| Lỗi validation HTTP 400 | HTTP 422; vượt 5 MiB vẫn 413 | Q7 |
| E05/E06 "Bản mã chỉ được…" | "Dữ liệu hex chỉ được…" (dùng cho bản rõ hex, bản mã) | Q3 |
| E11 một message chung cho lỗi file | Dùng lại message file hiện hành (415/413/422/500) | Q11 |
| File kết quả `<tên>.des.txt` | `<tên>.encrypted.txt` / `<tên>.decrypted.txt` | Q11 |
| Mảng `warnings` không nêu hình dạng | Object `{code,message,details}` như Hill | Q8 |
| File 5 MiB xử lý dưới 2 giây | Khoảng 6 giây mỗi chiều đo thực tế; không có performance gate | Q20, Q21 |
| E12 đứng đầu luồng xử lý | Giới hạn đo sau khi parse JSON; body hỏng cú pháp vẫn trả 422 trước | Q13 |
| (không nêu) | 5 MiB áp dụng cả chiều giải mã; văn bản lớn nhất còn giải mã lại được là 2.621.439 byte UTF-8 | Q22 |

Ngoài bảng lỗi/cảnh báo DES ở §4.1, README cố ý không sao chép toàn bộ OpenAPI,
bảng message hay validation matrix.
Khi contract thay đổi, cập nhật OpenSpec/runtime trước rồi đồng bộ các tài liệu
consumer tương ứng.
