# Tasks

## 1. Regression contract

- [x] 1.1 Đổi history integration test để cả sáu DH routes phải tạo row với exact operation mapping; hoàn tất khi targeted test fail trên matcher hiện tại đúng triệu chứng năm standalone route bị thiếu.
- [x] 1.2 Thêm assertions privacy cho standalone success/error (length/payload null, không q/key/result/trace/warning); hoàn tất khi test có marker nhạy cảm và chứng minh row/log không chứa marker.

## 2. Runtime history model và matcher

- [x] 2.1 Thêm shared DH operation vocabulary, cipher-operation validation và exact matcher cho năm standalone routes; hoàn tất khi unit matcher/store tests nhận đúng mapping và reject operation DH trên cipher khác.
- [x] 2.2 Mở history query filter cho operation DH mới mà không đổi owner scoping/response shape; hoàn tất khi API tests lọc `cipher=dh&operation=exchange`, empty valid filter và invalid filter đều xanh.

## 3. SQLite schema và continuity

- [x] 3.1 Thêm revision `sqlite_0004` nới CHECK hai bảng, giữ row/index/sequence và fail-before-mutation downgrade; hoàn tất khi disposable migration round-trip/preservation tests xanh.
- [x] 3.2 Đồng bộ required revision, continuity registries/staging constraints và cross-cipher validation; hoàn tất khi continuity round-trip DH operations xanh và invalid pairing bị từ chối.
- [x] 3.3 Verify app mới trên schema `sqlite_0003` vẫn trả DH response và warning redacted; hoàn tất khi best-effort compatibility test xanh.

## 4. Tài liệu tích hợp

- [x] 4.1 Cập nhật README, DH/frontend contract và engineering evidence để supersede D8, mô tả operation mapping/table owner-scoped và privacy; hoàn tất khi không còn tài liệu runtime tuyên bố năm DH standalone không ghi.
- [x] 4.2 Ghi rollout/rollback requirement migration-before-app và không backfill/live migration trong change; hoàn tất khi docs nêu rõ operator approval cho DB thật.

## 5. Integration gates

- [x] 5.1 Chạy targeted DH/history/migration/continuity suites; hoàn tất khi mọi test xanh và original six-route repro xanh.
- [x] 5.2 Chạy full `uv run --frozen pytest`, Ruff check/format, compile và `git diff --check`; hoàn tất khi coverage >=90% và mọi gate exit 0.
- [x] 5.3 Chạy `openspec validate expand-dh-operation-history --strict`; hoàn tất khi validation exit 0 và tasks/evidence phản ánh đúng kết quả.

## Workflow follow-up

- Sau review/owner acceptance, archive change ở lượt riêng và verify main specs đã nhận delta.
- Migration DB thật, backup/restore rehearsal, backfill hoặc deploy cần owner approval riêng.
