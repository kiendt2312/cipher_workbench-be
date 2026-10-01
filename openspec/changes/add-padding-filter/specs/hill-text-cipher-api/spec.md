## MODIFIED Requirements

### Requirement: Success response Hill có dữ liệu giải thích

Encrypt SHALL trả HTTP 200 với đúng năm trường top-level `success:true`, `result:string`, `blocks:array`, `key:object`, `warnings:array`. Decrypt SHALL trả HTTP 200 với đúng sáu trường top-level: năm trường trên cộng `padding:object` theo `padding-filter`. `blocks` SHALL liệt kê tất cả khối, mỗi item có đúng `input:number[m]`, `output:number[m]` theo A=0…Z=25 và thứ tự xử lý. `key` SHALL có `matrix`, `m`, `det`, `gcd`, `detInverse`, `adjugate`, `inverse`; ma trận và det đã chuẩn hóa mod 26. Mỗi warning SHALL có `code`, `message`, `details`; các warning phát sinh được sắp theo thứ tự W01, W02, W03. Không cắt bớt `blocks` theo độ dài text hoặc theo bản lọc. Response của các cipher khác giữ nguyên contract của chúng. (Truy vết: HTML Hill §§1, 7, 11; quyết định chủ sở hữu Q2, Q7, Q9, Q16; main spec `columnar-text-cipher-api` về baseline cũ; yêu cầu chủ sở hữu ngày 2026-10-01 và quyết định (a) cho change này)

#### Scenario: Không có warning
- **WHEN** encrypt `HELP` với K T01
- **THEN** `warnings=[]`, `blocks` có đúng hai item và `key.matrix=[[3,3],[2,5]]`

#### Scenario: Padding và dấu Việt
- **WHEN** encrypt văn bản có số chữ lẻ và một chữ Việt có dấu được giữ nguyên
- **THEN** `warnings` chứa W01 rồi W02, mỗi warning có `code,message,details` và `blocks` gồm cả chữ đệm

#### Scenario: Decrypt trả padding
- **WHEN** decrypt `DPDKKB` với K T01
- **THEN** response có đúng sáu key `success`, `result`, `blocks`, `key`, `warnings`, `padding`
- **AND** `result` là `HELLOX`, `blocks` có ba item và `padding` là `{"count":1,"positions":[5],"filtered":"HELLO"}`

### Requirement: OpenAPI và hợp đồng FE

OpenAPI SHALL gắn hai operation vào tag `Hill` và mô tả: hai request variant, options/default (kể cả việc `padChar` lúc decrypt dùng để nhận diện ký tự đệm), giới hạn 5 MiB, quy ước vector hàng, success schema mở rộng có `padding` ở decrypt, và error 413/422/500. Hướng dẫn FE SHALL mô tả cách đọc `.txt` UTF-8 ở client, kiểm đuôi file và byte length tối đa 5.242.880, xử lý E07 tại FE khi decode UTF-8 thất bại, gọi endpoint JSON, và dùng helper client Hill riêng để giữ `blocks/key/warnings/padding` thay vì chỉ lấy chuỗi `result`. Hướng dẫn FE SHALL mô tả phần "Lọc ký tự đệm" trong khung Phân tích của Hill: hiển thị `padChar`, số ký tự đệm nhận diện, khối và ô chứa chúng (suy từ `positions` và `m`), bản thô, bản lọc, và toggle lọc ký tự đệm theo `padding-filter`. Không đổi `transformText` của năm cipher cũ ngoài phần Playfair decrypt được mô tả trong hướng dẫn FE. (Truy vết: quyết định chủ sở hữu ngày 2026-09-30; HTML Hill §§1, 6–7; quyết định Q1, Q2, Q6, Q9; `repo_docs/frontend-integration.md` và `repo_docs/examples/cipher-api.ts` baseline; yêu cầu chủ sở hữu ngày 2026-10-01 về phần lọc trong khung Phân tích)

#### Scenario: E07 thuộc FE
- **WHEN** người dùng chọn `.txt` không đọc được UTF-8
- **THEN** FE hiển thị E07 và không gửi request Hill
- **AND** backend không khai báo E07 như response có thể phát sinh của bốn API Hill

#### Scenario: Phần lọc ký tự đệm trong khung Phân tích
- **WHEN** FE nhận response decrypt Hill với `m=3` và `padding={"count":2,"positions":[10,11],"filtered":"THUDOHANOI"}`
- **THEN** khung Phân tích hiển thị hai ký tự `X` đệm ở khối 4, ô 2–3, kèm bản thô `THUDOHANOIXX` và bản lọc `THUDOHANOI`
- **AND** đổi toggle lọc ký tự đệm chỉ đổi kết quả hiển thị, không gửi request mới
