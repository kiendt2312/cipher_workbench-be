## Why

Requirement "Ứng dụng stateless, không lưu dữ liệu người dùng" của `app-runtime` vẫn ghi quy tắc Week 1: không database, không lịch sử thao tác. Từ change `add-postgres-persistence` và `add-history-access-retention`, app có PostgreSQL tùy chọn, ghi metadata thao tác và có `GET /api/history`. Hai change đó không sửa requirement này nên spec đang tự mâu thuẫn.

## What Changes

- Viết lại requirement cho khớp runtime hiện tại: vẫn không lưu nội dung người dùng và không có session; được phép lưu metadata thao tác theo `operation-history`, đọc qua `history-api` khi `history-access` cho phép.
- Thay scenario cũ "không có endpoint lịch sử" bằng scenario lịch sử chỉ chứa metadata.
- Chỉ sửa spec; code và test không đổi.

## Capabilities

### Modified Capabilities

- `app-runtime`: requirement stateless khớp với lịch sử metadata.

## Impact

- Chỉ `openspec/specs/app-runtime/spec.md`. Test `test_only_metadata_history_route_exists_and_no_previous_results` đã kiểm tra đúng hành vi mới.
