# Design

## Context

Xem `proposal.md` cho động cơ. Runtime hiện dùng SQLite schema `sqlite_0003`, owner-scoped
history trong `private_history_records`, đồng thời giữ `cipher_operations` cho continuity/legacy.
Matcher chỉ nhận `/api/dh/caesar`; schema chỉ nhận encrypt/decrypt và RSA sign/verify. Ghi
history là best-effort sau response, nên app mới chạy trước migration sẽ bỏ row thay vì làm hỏng
DH response.

Owner directive 2026-10-12 supersede riêng D8 trong change `add-diffie-hellman`. Hai source DH
uncommitted ở checkout gốc được dùng làm provenance read-only; chúng không được copy, sửa hoặc
đưa vào branch này. Chúng mô tả sáu endpoint nhưng không định nghĩa taxonomy history mới.

## Goals / Non-Goals

**Goals:**

- Một row metadata phân biệt được cho mỗi request tới cả sáu exact DH routes.
- Schema/runtime/filter/continuity dùng cùng một operation vocabulary.
- Migration bảo toàn dữ liệu và downgrade fail-closed.
- Không mở thêm bất kỳ payload surface nào cho DH.

**Non-Goals:**

- Không backfill request cũ, không chạy migration trên DB thật và không deploy.
- Không thay đổi DH arithmetic, wire response, owner credential, retention hoặc quota.
- Không thêm route generic `/api/dh/encrypt|decrypt|file`.

## Decisions

### 1. Operation vocabulary là semantic snake_case

Năm mapping exact là:

| Route | Operation |
|---|---|
| `/api/dh/params` | `validate_params` |
| `/api/dh/params/random` | `generate_params` |
| `/api/dh/keypair` | `generate_keypair` |
| `/api/dh/shared-secret` | `derive_shared_secret` |
| `/api/dh/exchange` | `exchange` |

`/api/dh/caesar` giữ `encrypt|decrypt`. Tên semantic bền hơn path token và rõ cho UI/filter.
Alternative để operation NULL bị loại vì năm row sẽ không phân biệt được; thêm cột route bị loại
vì mở rộng schema/payload không cần thiết.

### 2. Matcher sở hữu operation standalone

Matcher map exact POST path sang `CipherRoute("dh", "text", operation)`. Nhờ đó request lỗi
trước parse vẫn có operation. Route handler standalone không gọi `note_history`; vì vậy không có
nguy cơ gắn q/key/length. Profile middleware dùng cùng `CIPHER_ROUTES`, nên exact route mới tự
nhận owner ID mà không thay đổi owner scoping.

### 3. Operation constants có domain restriction

Runtime tách transform operations, DH operations và private RSA operations. Validation SHALL
reject DH-only operation cho cipher khác và reject sign/verify cho cipher khác RSA. Model CHECK
của cả hai bảng thể hiện cùng restriction; continuity staging schema dùng cùng vocabulary.
Alternative chỉ nới một enum toàn cục bị loại vì sẽ cho phép row vô nghĩa như Caesar exchange.

### 4. SQLite revision `sqlite_0004` rebuild fail-closed

SQLite không sửa CHECK trực tiếp, nên migration rebuild lần lượt hai bảng qua Alembic, giữ toàn
bộ column/index/row và `sqlite_sequence`. Alembic 1.20.0 trong runtime này báo SQLite DDL là
non-transactional; vì vậy backup/restore rehearsal và write freeze là điều kiện vận hành, không
dựa vào rollback DDL toàn cục. Upgrade chỉ nới operation contract. Downgrade kiểm tra cả hai bảng
có operation DH standalone trước bất kỳ rename/drop nào; nếu có, nó raise và không tự xóa/sửa
row. Không tạo PostgreSQL revision vì runtime PostgreSQL đã retire.

### 5. API chỉ mở filter, không mở payload

`GET /api/history` dùng operation constants mới. Item standalone có `source=text`,
`responseMode/inputLength/outputLength=null`; không có field mới. Privacy tests dump toàn bộ row
để chứng minh marker q/key/result/trace không xuất hiện.

## Risks / Trade-offs

- **[Migration rebuild hai bảng có thể lỗi giữa chừng]** → SQLite DDL không được giả định atomic;
  bắt buộc backup/restore rehearsal + write freeze, đồng thời test preservation/index/sequence
  và fail-before-mutation downgrade trên disposable SQLite.
- **[App mới chạy trên schema cũ bỏ lỡ row]** → giữ best-effort response và warning redacted;
  deployment phải migrate trước app.
- **[Operation vocabulary trở thành API contract]** → khóa bằng model, filter, migration,
  OpenSpec và integration tests; không suy ra từ handler name động.
- **[History tăng số row]** → retention/quota hiện hữu vẫn áp dụng; mỗi row standalone không có
  payload và length metadata.

## Migration Plan

1. Deploy migration `sqlite_0004` trước app mới; migration thật cần backup/restore rehearsal theo
   runbook hiện hữu và owner approval riêng.
2. Deploy app mới sau khi health xác nhận schema supported revision.
3. Rollback app trước. Chỉ downgrade schema khi không còn row dùng operation DH standalone;
   migration không tự xóa chúng.
4. Change này chỉ chạy migration/tests trên disposable SQLite; không thao tác DB thật.
