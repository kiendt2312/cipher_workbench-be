# des-trace-api Specification

## Purpose
Định nghĩa endpoint `/api/des/trace` trả toàn bộ giá trị trung gian của đúng một khối DES để FE hiển thị từng bước sinh khóa, 16 vòng Feistel và hàm f. Nguồn: `Scope Backend_ Hệ mã hóa DES.html` §§5, 7, 8 BE-D09; quyết định chủ sở hữu Q4, Q8, Q9, Q12, Q18 ngày 2026-10-01.
## Requirements
### Requirement: Request trace một khối

Hệ thống SHALL cung cấp `POST /api/des/trace` nhận JSON object chỉ gồm `block` (bắt buộc, string), `key` (bắt buộc, string) và `operation` (tùy chọn, `"encrypt"` mặc định hoặc `"decrypt"`, khớp chính xác). `block` SHALL được bỏ khoảng trắng ASCII và chấp nhận chữ thường; sau đó phải là đúng 16 ký tự hex. Trace không có padding, mode hay IV. Media type, body strict và giới hạn 5 MiB (đo trên `block`) theo cùng quy tắc text API. Trace MUST NOT ghi lịch sử. (Truy vết: HTML DES scope §§5, 7; quyết định chủ sở hữu Q9, Q12, Q18)

#### Scenario: Khối có khoảng trắng
- **WHEN** client gửi `{"block":"01234567 89abcdef","key":"133457799BBCDFF1"}`
- **THEN** hệ thống trả HTTP 200 với `result` = `85E813540F0AB405` và `trace.input` = `0123456789ABCDEF`

#### Scenario: Field lạ
- **WHEN** client gửi thêm field `mode`
- **THEN** hệ thống trả HTTP 422 với message `Dữ liệu gửi lên không hợp lệ.`

### Requirement: Response trace

Response thành công SHALL là HTTP 200 với đúng các field `success` (true), `result` (hex in hoa của khối kết quả), `trace`, `warnings`. `trace` SHALL có đúng: `operation`; `input` (khối đã chuẩn hóa); `key` (khóa đã chuẩn hóa: chữ hoa, không khoảng trắng); `pc1` (14 hex); `subkeys` gồm 16 phần tử theo n = 1…16, mỗi phần tử `{n, shift, c, d, k}` với `c`, `d` 7 hex và `k` 12 hex; `ip` (16 hex); `l0`, `r0` (8 hex); `rounds` gồm 16 phần tử, mỗi phần tử `{n, subkey, expansion, xorKey, sbox, sboxOutput, f, l, r}` với `subkey` là số thứ tự khóa con được dùng, `expansion` và `xorKey` 12 hex, `sbox` là 8 object `{row, col, value}` theo S1…S8, `sboxOutput` và `f` 8 hex, `l` và `r` là Li, Ri sau vòng (8 hex); `preOutput` (R16L16, 16 hex). Mọi giá trị hex là chữ hoa. Với `operation="decrypt"`, `input` là bản mã, `result` là bản rõ hex và `rounds[i].subkey` chạy từ 16 về 1; `subkeys` vẫn theo thứ tự K1…K16. `warnings` chỉ có thể chứa W01/W02 theo quy tắc text API; trace không bao giờ có W03. (Truy vết: HTML DES scope §7 response mẫu cho T01; quyết định chủ sở hữu Q4, Q8, Q18)

#### Scenario: Trace T01
- **WHEN** client gửi `{"block":"0123456789ABCDEF","key":"133457799BBCDFF1","operation":"encrypt"}`
- **THEN** `result` = `85E813540F0AB405`, `trace.pc1` = `F0CCAAF556678F`, `trace.ip` = `CC00CCFFF0AAF0AA`, `trace.l0` = `CC00CCFF`, `trace.r0` = `F0AAF0AA`
- **AND** `trace.subkeys[0]` = `{"n":1,"shift":1,"c":"E19955F","d":"AACCF1E","k":"1B02EFFC7072"}`
- **AND** `trace.rounds[0]` có `subkey=1`, `expansion="7A15557A1555"`, `xorKey="6117BA866527"`, `sbox[0]={"row":0,"col":12,"value":5}`, `sbox[1]={"row":1,"col":8,"value":12}`, `sboxOutput="5C82B597"`, `f="234AA9BB"`, `l="F0AAF0AA"`, `r="EF4A6544"`
- **AND** `trace.preOutput` = `0A4CD99543423234` và `warnings` rỗng

#### Scenario: Trace giải mã
- **WHEN** client gửi `{"block":"85E813540F0AB405","key":"133457799BBCDFF1","operation":"decrypt"}`
- **THEN** `result` = `0123456789ABCDEF`, `trace.rounds[0].subkey` = 16 và `trace.rounds[15].subkey` = 1

#### Scenario: Trace với khóa yếu
- **WHEN** client gửi trace với khóa `0101010101010101`
- **THEN** `warnings` chỉ có W01

### Requirement: Khối trace phải đúng một khối

Sau các kiểm tra body, dung lượng, `operation` và khóa, nếu `block` thiếu, null, rỗng, chứa ký tự không phải hex hoặc khác đúng 16 ký tự hex sau khi bỏ khoảng trắng, hệ thống SHALL trả HTTP 422 `Trace chỉ áp dụng cho đúng 1 khối 16 ký tự hex.` (DES-E13). (Truy vết: HTML DES scope §§5–6 DES-E13; quyết định chủ sở hữu Q18)

#### Scenario: Hai khối
- **WHEN** `block` là `0123456789ABCDEF0123456789ABCDEF`
- **THEN** hệ thống trả HTTP 422 với message `Trace chỉ áp dụng cho đúng 1 khối 16 ký tự hex.`

#### Scenario: Ký tự không phải hex
- **WHEN** `block` là `0123456789ABCDEG`
- **THEN** hệ thống trả HTTP 422 với message `Trace chỉ áp dụng cho đúng 1 khối 16 ký tự hex.`
