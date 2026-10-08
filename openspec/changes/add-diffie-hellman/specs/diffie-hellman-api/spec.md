# Spec Delta

## Purpose

Định nghĩa sáu HTTP endpoint Diffie–Hellman giáo dục và các schema JSON/multipart ổn định để client có thể kiểm tra từng bước mà không phụ thuộc trạng thái server.

## ADDED Requirements

### Requirement: Inventory API DH cố định
Ứng dụng SHALL cung cấp đúng sáu DH operation: `POST /api/dh/params`, `/params/random`, `/keypair`, `/shared-secret`, `/exchange`, `/caesar`; không thêm route DH khác. (Truy vết: Scope DH §API; quyết định chủ sở hữu DH về phạm vi sáu endpoint)

#### Scenario: OpenAPI liệt kê đúng sáu operation
- **WHEN** đọc `/openapi.json`
- **THEN** có đúng sáu POST operation DH nêu trên với JSON schemas và response schemas tương ứng

### Requirement: Quy ước type và schema nghiêm ngặt
Mọi đại lượng mật mã `q,alpha,p,privateKey,publicKey,sharedKey,factors`, operand/result check và `shift` SHALL là canonical decimal string. `bits`, trace index/bit SHALL là JSON integer; `success,match` SHALL là boolean. Request/response MUST từ chối field lạ. (Truy vết: Tài liệu thuật toán DH §10; Scope DH §API; quyết định chủ sở hữu DH Q7; strict RSA precedent)

#### Scenario: Numeric q bị từ chối
- **WHEN** JSON gửi `q=23` thay vì `q="23"`
- **THEN** trả HTTP 422 `NOT_INTEGER`, field `q`, message `Giá trị phải là số nguyên dương.`

#### Scenario: Control bits là integer
- **WHEN** `/params/random` nhận `{"bits":32}`
- **THEN** request qua type validation
- **AND** `{"bits":"32"}` bị HTTP 422 `BITS_INVALID`

### Requirement: Params manual với alpha tùy chọn
`/params` SHALL nhận đúng `q` và optional `alpha`. Nếu thiếu alpha, response success SHALL có `alpha:null`, `primitiveRootChecks:[]`, và chỉ `suggestedAlpha` chứa nguyên căn nhỏ nhất; server MUST NOT tự chọn hoặc thay alpha. (Truy vết: Scope DH BE-02 và §API; quyết định chủ sở hữu DH Q2)

#### Scenario: Thiếu alpha chỉ trả suggestion
- **WHEN** gửi `{"q":"23"}`
- **THEN** HTTP 200 trả `success=true`, `q="23"`, `alpha=null`, `factors=["2","11"]`, `primitiveRootChecks=[]`, `suggestedAlpha="5"`

#### Scenario: Alpha hợp lệ
- **WHEN** gửi `{"q":"23","alpha":"5"}`
- **THEN** HTTP 200 trả `alpha="5"`, full primitive-root checks và `suggestedAlpha=null`

### Requirement: Params random
`/params/random` SHALL nhận đúng `bits` thuộc `16,32,64,128` và trả success gồm `q,p,alpha,factors,primitiveRootChecks`, mọi số trừ control/bit dùng decimal string. (Truy vết: Scope DH BE-03, §API, TC-08)

#### Scenario: Random response composable
- **WHEN** yêu cầu `{"bits":128}` thành công
- **THEN** response có q đúng 128 bit, p/alpha/checks và có thể gửi trực tiếp tới keypair/exchange

### Requirement: Keypair API
`/keypair` SHALL nhận đúng `q,alpha,privateKey?` và trả `success,privateKey,publicKey,steps`; bỏ private key SHALL sinh ngẫu nhiên. Endpoint SHALL tự kiểm tra q/alpha tới 128 bit. (Truy vết: Scope DH BE-04, §API, TC-02–TC-03, TC-09; quyết định chủ sở hữu DH Q1/Q4)

#### Scenario: Private key được sinh
- **WHEN** gửi q/alpha hợp lệ và bỏ `privateKey`
- **THEN** HTTP 200 trả private key trong `2..q-2`, public key và full left-to-right steps

### Requirement: Shared-secret API
`/shared-secret` SHALL nhận đúng `q,privateKey,otherPublicKey`, tự kiểm tra q/domain và trả `success,sharedKey,steps`. Endpoint không nhận hoặc cần alpha. (Truy vết: Tài liệu thuật toán DH §§5,12; Scope DH BE-05 và §API)

#### Scenario: Shared secret mẫu Stallings
- **WHEN** gửi `q="353", privateKey="97", otherPublicKey="248"`
- **THEN** HTTP 200 trả `sharedKey="160"` và trace kết thúc ở `"160"`

### Requirement: Exchange API trả khóa riêng giáo dục
`/exchange` SHALL nhận `q,alpha,privateKeyA?,privateKeyB?`, sinh khóa bị thiếu và trả cả private/public/shared keys, `match`, cùng grouped steps cho bốn modPow. Response SHALL có warning giáo dục rằng private key không được trả trong hệ thống thật. (Truy vết: Scope DH luồng, BE-06, §API; quyết định chủ sở hữu DH Q3)

#### Scenario: Exchange sinh cả hai khóa
- **WHEN** gửi q/alpha hợp lệ và bỏ hai private key
- **THEN** HTTP 200 trả `privateKeyA`, `privateKeyB`, hai public keys, hai shared keys, `match=true`, grouped steps và educational warning
- **AND** warning đúng bằng `{"code":"EDUCATIONAL_PRIVATE_KEYS","message":"Chỉ dùng để học: response có khóa riêng; hệ thống thật không được gửi hoặc lưu khóa riêng."}`

### Requirement: DH Caesar JSON
`/caesar` với `application/json` SHALL nhận đúng `q,privateKey,otherPublicKey,action,data`, trong đó action là `encrypt|decrypt`, và luôn trả JSON `success,sharedKey,shift,result,warning?`. Không có attachment hoặc `response_mode`. (Truy vết: Tài liệu thuật toán DH §11; Scope DH BE-06 và §API, TC-11–TC-12; quyết định chủ sở hữu DH)

#### Scenario: Encrypt JSON TC-11
- **WHEN** gửi q `"353"`, privateKey `"97"`, otherPublicKey `"248"`, action `encrypt`, data `Hello World`
- **THEN** HTTP 200 JSON trả sharedKey `"160"`, shift `"4"`, result `Lipps Asvph` và không có warning

### Requirement: DH Caesar multipart JSON-only
`/caesar` với `multipart/form-data` SHALL nhận đúng `file,q,privateKey,otherPublicKey,action`; chỉ `.txt` UTF-8 tối đa chính xác 5 MiB. Response SHALL luôn là JSON và không nhận `response_mode`. BOM đầu vào được xử lý như Caesar content mode hiện hữu. (Truy vết: Scope DH §API và bảng lỗi 1 MB; `file-cipher-api`; quyết định chủ sở hữu DH Q5 và JSON-only)

#### Scenario: File đúng 5 MiB
- **WHEN** upload `.txt` UTF-8 đúng 5,242,880 byte với DH fields hợp lệ
- **THEN** request không bị từ chối vì kích thước và trả JSON result

#### Scenario: File có BOM
- **WHEN** upload file bắt đầu UTF-8 BOM và nội dung `Hello World`
- **THEN** BOM không xuất hiện trong `result`, text được Caesar-transform đúng, và server không trả attachment

### Requirement: Stateless và không dùng provenance
Mỗi DH request SHALL độc lập; server MUST NOT lưu khóa/tham số hoặc yêu cầu q phải được sinh bởi request trước. Cùng input xác định MUST cho cùng output, ngoại trừ field được sinh bằng random. (Truy vết: Scope DH §Phạm vi; `app-runtime` stateless; quyết định chủ sở hữu DH Q1/Q4)

#### Scenario: Downstream chấp nhận q bên ngoài
- **WHEN** client gửi trực tiếp q/alpha 128-bit hợp lệ chưa từng xuất hiện ở `/params/random`
- **THEN** endpoint downstream tự kiểm tra và xử lý như tham số được server sinh
