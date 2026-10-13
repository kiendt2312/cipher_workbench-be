# Proposal

## Why

Lịch sử Diffie–Hellman hiện chỉ ghi integration `/api/dh/caesar`, nên năm thao tác
standalone không xuất hiện trong lịch sử dù là các workflow chính của feature. Chủ sở
hữu ngày 2026-10-12 đã đảo quyết định D8 trước đây và yêu cầu đồng bộ history end-to-end
cho cả sáu route DH.

## What Changes

- Ghi đúng một history row cho mỗi request tới năm route DH standalone và tiếp tục ghi
  `/api/dh/caesar`, kể cả request lỗi theo semantics best-effort hiện hữu.
- Gán operation metadata ổn định cho từng thao tác standalone để history có thể phân biệt
  validate params, generate params, generate keypair, derive shared secret và exchange.
- Mở rộng SQLite constraints, runtime validation, continuity và history filter cho các
  operation DH mới, bảo toàn dữ liệu/index/sequence qua migration.
- Giữ owner scoping và privacy contract: không lưu q, alpha, private/public/shared key,
  request/response body, trace, warning, filename, header hay dữ liệu định danh.
- Cập nhật regression tests và tài liệu tích hợp để contract code/schema/API thống nhất.

## Capabilities

### New Capabilities

Không có.

### Modified Capabilities

- `operation-history`: mở rộng tập route/operation DH được ghi và schema metadata tương ứng.
- `history-api`: cho phép đọc và lọc các operation DH standalone mới.

## Impact

- Code: route matcher, operation model/validation, continuity và owner-scoped history.
- Database: thêm revision SQLite sau `sqlite_0003`; chỉ chạy trên disposable/test DB trong
  change này, không áp dụng lên DB thật.
- API: response các endpoint DH không đổi; `GET /api/history` có thể trả thêm operation
  DH và nhận chúng ở query filter.
- Docs/spec: supersede riêng quyết định D8 ngày 2026-10-08; các quyết định DH khác giữ nguyên.

## Ngoài phạm vi

- Không lưu hoặc backfill nội dung/bí mật mật mã; không khôi phục các request đã bị bỏ lỡ.
- Không migrate, seed, xóa hay deploy DB thật; không thay đổi signing secret hoặc retention.
- Không thay đổi wire schema/kết quả tính toán của sáu endpoint DH.
- Không thay đổi owner scoping, authentication hoặc cho phép profile này đọc history của
  profile khác.
