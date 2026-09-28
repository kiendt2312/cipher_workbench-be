## Why

Backend hiện có bốn cipher và 12 endpoint nhưng chưa có Columnar Transposition để phục vụ bài học “hệ mã hàng”. Change này xác lập contract backend đầy đủ, lossless cho Columnar dựa trên quyết định chủ sở hữu và các contract API/file/error/guard hiện hành, đồng thời chỉ dùng HTML upload làm tham chiếu thuật toán cơ bản và cách xếp hạng keyword.

## What Changes

- Thêm lõi Columnar Transposition thuần: ghi plaintext theo hàng, đọc các cột theo thứ hạng khóa; decrypt tính độ dài cột theo vị trí vật lý, không padding và round-trip chính xác mọi Unicode code point.
- Thêm parser khóa chuỗi dùng chung cho JSON và multipart: trim đúng ASCII whitespace, giới hạn 2.048 ký tự sau trim, ưu tiên nhận grammar hoán vị số `1..m`, nếu không thì nhận keyword ASCII `[A-Za-z]+`; keyword xếp hạng không phân biệt hoa thường và phá hòa từ trái sang phải; `2 <= m <= 256`.
- Thêm đúng ba route `POST /api/columnar/encrypt`, `POST /api/columnar/decrypt` và `POST /api/columnar/file`, đưa tổng số route cipher từ 12 lên 15; không thêm generalized/versioned cipher API.
- Hai route text nhận JSON object chính xác gồm `text,key`, từ chối member lạ/trùng và lone surrogate, nhưng nhận `application/json` lẫn `application/*+json`; success/error giữ envelope hai trường hiện hành.
- Route file nhận exact multipart `file,key,action` và optional `response_mode`, kế thừa `.txt`, UTF-8, giới hạn đúng 5 MiB, zero-byte, BOM, preview/download, attachment filename/media type và stateless behavior hiện hành.
- Mở rộng đúng file-route allowlist từ bốn lên năm route để guard 64 MiB và multipart-completion áp dụng cho Columnar mà không đổi threshold hoặc behavior của 12 route cũ.
- Bổ sung OpenAPI dưới tag `Columnar Transposition`, trong đó `key` luôn là `type:string` với mô tả/ví dụ chính xác, không dùng `pattern`, `oneOf` hoặc raw `maxLength` gây hiểu sai contract sau trim.
- Bổ sung unit/integration/contract tests cho parser, ranking, vectors, Unicode, exact request shape, precedence, file/BOM/UTF-8/size, guards, logging và inventory đúng 15 route; chỉ cập nhật README và guide FE sau khi implementation vượt quality gates.

## Capabilities

### New Capabilities

- `columnar-core`: Thuật toán Columnar không padding, parser/ranking khóa, Unicode code-point semantics, canonical vectors và exact round-trip.
- `columnar-text-cipher-api`: Hai endpoint JSON strict, surrogate validation, media types, exact success schema và OpenAPI text contract.
- `columnar-file-cipher-api`: Endpoint multipart strict kế thừa byte/file/BOM/preview/attachment contract hiện hành với một khóa chuỗi Columnar.
- `columnar-error-handling`: Canonical key error, status/message/precedence, guard extension, safe logging, statelessness và regression boundary cho 12 route cũ.

### Modified Capabilities

Không có. Repository chưa có main spec Columnar; change tạo các delta spec mới và không sửa hoặc archive completed change Caesar, Vigenère, Playfair hay Affine.

## Impact

- Khi apply trong một workflow sau: thêm core/parser Columnar và HTTP adapters/schemas, nối ba route vào app assembly, bổ sung message/exception tối thiểu, mở rộng file-route allowlist từ bốn lên năm và tái sử dụng helper file hiện tại.
- OpenAPI sẽ công bố đúng 15 cipher POST routes; text có response 200/413/422/500, file có 200/413/415/422/500 và success 200 hỗ trợ JSON lẫn `text/plain`.
- Test scope gồm unit/integration/contract cho Columnar và regression toàn bộ 12 endpoint hiện hữu; backend branch coverage vẫn tối thiểu 90%, không thêm dependency.
- README và `repo_docs/frontend-integration.md` chỉ được sửa sau quality gates implementation; planning-only workflow này chỉ tạo artifact dưới `openspec/changes/add-columnar-transposition-cipher/`.

## Ngoài phạm vi

- Không triển khai Frontend, animation, CSS/theme/fonts, visual matrix, tutorial/security prose hoặc client-side calculation; không copy/import/commit HTML upload.
- Không thêm generalized cipher API, factory/registry/interface rộng, authentication, database, persistence/history, CORS, deployment hay dependency mới.
- Không đổi contract, runtime hoặc artifact của 12 route hiện hữu; không sửa hoặc archive completed OpenSpec changes.
- Không thêm padding, normalization, accent stripping, case conversion hoặc chính sách key ngoài contract đã duyệt.

## Giải quyết khác biệt giữa nguồn

- Thứ tự ưu tiên bắt buộc là: (1) quyết định chủ sở hữu trong handoff; (2) completed OpenSpec/runtime/tests cho contract dùng chung; (3) README/guide FE; (4) HTML upload chỉ cho thuật toán transposition cơ bản và keyword ranking.
- Vì vậy `clean()`, padding, UI, prose/tutorial và mọi hành vi trình diễn trong HTML không trở thành backend contract. Backend giữ nguyên từng Unicode code point, không padding, và server result là authority.
- Contract file/error/guard/envelope lấy từ runtime đã nghiệm thu; HTML không được ghi đè message, validation order, MIME/filename/BOM, size limit hoặc request shape.
