# Tasks

> 46 checkbox này theo dõi implementation và disposable engineering proof; chỉ
> được đóng khi có bằng chứng tương ứng. Rollout/cutover/retirement thật
> được thực hiện sau ủy quyền operational riêng và ghi tại
> `docs/sqlite-history-local-rollout-20261007.md`; không dùng evidence operational
> để thổi phồng trạng thái engineering này.

## 1. Dependency và cấu hình storage

- [x] 1.1 Thêm/pin `aiosqlite` tương thích SQLAlchemy 2.1.1 bằng uv, giữ `asyncpg` trong giai đoạn transfer/rehearsal và không nâng package khác; **xong khi:** `uv.lock` chỉ có diff dependency có lý do và import driver chạy trong môi trường khóa.
- [x] 1.2 Đổi parser/preflight `DATABASE_URL` sang SQLite absolute path, canonicalize data root, từ chối relative/memory/symlink escape/remote hoặc mount không xác định, mở runtime mode `rw` và redaction path/URL; **xong khi:** unit test URI, mountinfo, missing/read-only file và sentinel leak xanh.
- [x] 1.3 Tách cấu hình nguồn legacy cho command chuyển đổi khỏi runtime app và không cho app đọc nhầm `LEGACY_DATABASE_URL`; **xong khi:** config tests chứng minh runtime chỉ dùng SQLite URL còn transfer command fail-closed khi thiếu input.
- [x] 1.4 Cập nhật `.env.example` và tài liệu cấu hình ngay trong nhóm này, ghi rõ FE chỉ gọi HTTP, one-process/local-filesystem, disabled/unavailable semantics và không điền origin giả; **xong khi:** examples dùng đúng bốn slash cho absolute SQLite URL và review không có wildcard CORS/credential/path production bịa đặt.

## 2. SQLite schema, migration và model

- [x] 2.1 Tạo Alembic config/script root SQLite riêng với baseline effective schema gồm RSA, giữ nguyên byte-content của PostgreSQL revisions `0001`–`0004`; **xong khi:** inventory test chứng minh chain tách biệt và git diff không sửa bốn revision legacy.
- [x] 2.2 Implement codec UTC aware datetime ↔ epoch microsecond 64-bit, từ chối naive/out-of-range và giữ exact PostgreSQL microsecond; **xong khi:** unit test epoch boundary, trước/sau 1970, timezone offset, round-trip và tie timestamp xanh.
- [x] 2.3 Map `cipher_operations` sang đúng 11 field logic với `INTEGER PRIMARY KEY AUTOINCREMENT`, CHECK đủ tám cipher/RSA, boolean `0|1` và hai index đã thiết kế; **xong khi:** schema introspection test trên SQLite disposable khớp column/nullability/constraint/index và không có payload column.
- [x] 2.4 Bảo đảm app không `create_all`, auto-upgrade, stamp hoặc tự tạo file rỗng; **xong khi:** startup test với missing file/wrong revision vẫn phục vụ cipher, health/history unavailable và filesystem không xuất hiện DB mới.
- [x] 2.5 Thêm migration tests fresh/repeat/downgrade/restart và ID không tái sử dụng; **xong khi:** `sqlite_sequence` lớn hơn cả max imported ID lẫn source identity high-water kể cả row cao nhất đã bị purge, second upgrade không đổi digest/count.
- [x] 2.6 Viết tài liệu migration SQLite/legacy chain ngay trong nhóm này; **xong khi:** command mẫu trỏ đúng config root và không hướng dẫn stamp `0004`, chạy PostgreSQL revision trên SQLite hoặc dùng destructive downgrade làm production rollback.

## 3. Engine, query và retention

- [x] 3.1 Tạo SQLite async engine pool một connection, busy/pool timeout 200 ms, rollback journal và durability bảo thủ; **xong khi:** tests xác nhận mode/timeout, không WAL, và timeout/cancel/commit error rollback rồi invalidate/close để checkout kế tiếp dùng được.
- [x] 3.2 Cập nhật write path để app gán UTC epoch microsecond và commit transaction ngắn; **xong khi:** integration test record/restart đọc đúng metadata, timezone và ID, kể cả hai row cùng microsecond.
- [x] 3.3 Thay keyset tuple comparison bằng predicate portable giữ thứ tự `(created_at DESC, id DESC)`, filter và `limit+1`; **xong khi:** SQLite tests phủ page boundary, tie timestamp, insert xen kẽ, cipher/operation filter, không lặp/bỏ row.
- [x] 3.4 Giữ nguyên wire cursor ISO+ID và thêm fixture cursor trước cutover; **xong khi:** cursor encode từ PostgreSQL fixture đọc tiếp đúng trên SQLite, invalid/naive/out-of-range vẫn trả HTTP 422/message hiện hành.
- [x] 3.5 Chuyển retention cutoff sang SQLite database-clock UTC epoch, giữ default/range/schedule/CLI và thêm rollout clock preflight ≤60 giây; **xong khi:** tests freeze DB clock, 29/30/31 ngày, DST/timezone host, skew gate, purge failure và manual command xanh.
- [x] 3.6 Thêm fault tests read-only, permission denied, missing schema, exclusive lock/cancellation và disk-full giả lập; **xong khi:** connection được rollback/recover hoặc loại khỏi pool, health tối đa 1 giây, recorder tối đa 500 ms và không lỗi nào lộ URL/path.

## 4. HTTP Adapter, Exception Handling, Caesar Core và File Processing boundary

- [x] 4.1 Giữ nguyên `GET /api/history`/health schema, status, message, filter/pagination/order và UTC serialization; **xong khi:** contract snapshot/API integration tests gồm `cipher=rsa`, 404 history disabled, 503 unavailable và 422 invalid query không drift.
- [x] 4.2 Giữ recorder post-response best-effort cho lock/read-only/disk-full/cancel/error; **xong khi:** response status/body/header của success và 413/415/422/500 giống history disabled, warning generic và không quá budget.
- [x] 4.3 Reconcile active RSA authority vào regression fixtures: đúng 22 transform, hai RSA transform, keygen/Hill key/DES trace excluded, length/source/null semantics và schema cũ failure không đổi transform; **xong khi:** route matcher/history tests chứng minh không lưu content/key/trace/filename/`originalUtf8ByteLength`/IP/user-agent.
- [x] 4.4 Không sửa Caesar Core hoặc thuật toán cipher; thêm boundary regression cho text/file/BOM/response mode và exact DOCX §5 errors; **xong khi:** targeted Caesar/File Processing suites xanh và diff review không có algorithm behavior change.
- [x] 4.5 Giữ exception/envelope hiện hành, chỉ thêm lỗi cấu hình/CLI nội bộ đã redaction; **xong khi:** API 404/413/415/422/500/503 snapshots không có field/message mới và CLI failure không in secret/path.
- [x] 4.6 Cập nhật README/frontend contract cùng nhóm HTTP, xóa mô tả PostgreSQL runtime lỗi thời nhưng giữ RSA Q16/R1/R2, proxy `/api` và exact CORS; **xong khi:** docs review đối chiếu main + active RSA không còn statement bảy cipher/no-RSA-history.

## 5. Chuyển đổi và đối soát PostgreSQL → SQLite

- [x] 5.1 Tạo mode `prepare`/`verify` chỉ đọc PostgreSQL và luôn dùng staging độc quyền, không chạm runtime, với preflight revision/schema/path/no-overwrite/redaction; **xong khi:** CLI tests từ chối wrong revision/existing staging/target=runtime và log không chứa URL/path.
- [x] 5.2 Implement source reader read-only snapshot theo ID và đọc identity `last_value/is_called/increment` để dẫn xuất last-issued high-water; **xong khi:** PostgreSQL `0004` disposable xuất đủ 11 field/RSA một lần, không SQL ghi và fixture sequence gap được capture đúng.
- [x] 5.3 Implement staging importer explicit ID + constraint validation + sequence seed sau `max(max_id,last_issued_high_water)`; **xong khi:** mixed fixture giữ exact value/order và row kế tiếp vượt cả max row lẫn ID nguồn đã cấp nhưng bị xóa.
- [x] 5.4 Implement manifest SHA-256 versioned với 11-field fixed order, type tag, ASCII byte length framing, raw UTF-8, canonical int/bool/null và identity state; **xong khi:** independent golden bytes/hash khớp hai engine, mutation/framing ambiguity làm mismatch.
- [x] 5.5 Implement command first-publish riêng nhận expected manifest digest, yêu cầu same-filesystem/app stopped/runtime absent và POSIX hard-link atomic no-overwrite + fsync + unlink staging; **xong khi:** mismatch/corrupt/duplicate/cross-filesystem/runtime-exists/I/O/crash-between-link-unlink tests giữ runtime/source/backup nguyên vẹn hoặc để lại hai tên cùng inode recoverable.
- [x] 5.6 Implement replacement/restore mode riêng chỉ trước write đầu tiên, yêu cầu restore-tested backup, immutable expected old/new digest, app stopped và explicit confirmation trước same-filesystem `os.replace`; **xong khi:** thiếu evidence hoặc runtime đã write fail trước replace, success giữ backup, fault-before-replace giữ runtime cũ, post-replace fsync failure báo trạng thái đã thay file và cấm retry trước re-verify.
- [x] 5.7 Thêm rerun/resume policy fail-closed và cleanup staging recoverable; **xong khi:** interrupted import chạy lại với staging mới không duplicate, prepare/verify không chạm runtime và material delete cần explicit target.
- [x] 5.8 Viết runbook dry-run/final freeze/prepare/verify/first-publish/replacement/smoke, nêu 15 row không phải current proof; **xong khi:** checklist đo row+identity thực và không chạm user DB trước authorization.

## 6. Backup, restore và rollback

- [x] 6.1 Thêm PostgreSQL 17 custom-format `pg_dump` step không `--no-sync`, archive inspection và redacted failure handling; **xong khi:** disposable source dump chứa table/sequence và wrong/partial archive bị từ chối.
- [x] 6.2 Restore PostgreSQL dump vào DB disposable và đối soát revision/schema/count/ID/identity/digest; **xong khi:** restore rehearsal khớp nguồn snapshot và không có lệnh restore vào user DB.
- [x] 6.3 Implement SQLite live backup bằng Online Backup API hoặc `VACUUM INTO`, không raw-copy; **xong khi:** concurrent writer test tạo snapshot integrity tốt, contention tuân 200/500 ms policy và không overwrite đích.
- [x] 6.4 Implement SQLite restore rehearsal vào file tách biệt với revision/schema/digest/integrity/read smoke; **xong khi:** valid backup giữ cursor/order, corrupt/wrong revision fail-closed và runtime không đổi.
- [x] 6.5 Implement rollback delta report deterministic gồm row/ID/digest/`sqlite_sequence`, không tự merge/write PostgreSQL; **xong khi:** tests phân biệt trước/sau write, collision và identity đã tiêu thụ nhưng row bị purge; case sau write dừng ở owner-approved remediation gate.
- [x] 6.6 Viết runbook rollback/fix-forward trước và sau retirement; **xong khi:** nêu fail-closed manual reconciliation, recovery backup evidence, owner gate và cấm `down -v`/drop/truncate ngoài exact retirement procedure.

## 7. Docker và storage persistence

- [x] 7.1 Chuyển compose mặc định sang migrate-once + one-process app dùng cùng named volume SQLite, không khởi động PostgreSQL; **xong khi:** compose config test xác nhận dependency order, port 8000→`${APP_HOST_PORT:-8080}` và volume restart giữ row.
- [x] 7.2 Giữ PostgreSQL legacy chỉ như profile/export path không mặc định và không gắn thao tác xóa volume vào compose lifecycle; **xong khi:** default `docker compose up` không có postgres, còn runbook mô tả cách operator map đúng volume cũ mà không tự đoán tên.
- [x] 7.3 Cấu hình image/data directory UID/GID và quyền tối thiểu cho app/migrate/backup; **xong khi:** container smoke với volume mới và volume sai quyền lần lượt health ok hoặc fail generic, không chạy root để né permission.
- [x] 7.4 Cập nhật Docker/ops docs về local filesystem, capacity/inode monitoring, backup ngoài volume, actual `sqlite3.sqlite_version` evidence và one-process limit; **xong khi:** docs không hứa WAL, network filesystem, HA hoặc production path/origin chưa được owner cung cấp.
- [x] 7.5 Viết operational retirement checklist project-scoped, không chạy thật trong apply turn; **xong khi:** checklist yêu cầu read-only exact target inventory, reconciliation + SQLite smoke + restore-tested backup ngoài volume, per-target preview/confirmation, giữ recovery backup và cấm host/shared/unrelated target, glob hoặc blanket `docker compose down -v`.

## 8. Validation tích hợp và review

- [x] 8.1 Chạy targeted SQLite/migration/history/RSA/transfer/backup/Docker suites trên tài nguyên disposable; **xong khi:** tất cả xanh và report ghi exact command/version, không có user DB/container access.
- [x] 8.2 Chạy full pytest với coverage ≥90%, Ruff check/format-check và kiểm tra dependency lock; **xong khi:** mọi gate xanh, không blanket upgrade và không regression cipher/OpenAPI.
- [x] 8.3 Chạy OpenSpec 1.13.2 strict cho change và toàn repo, rồi OpenSpec 1.14.1 như kiểm tra bổ sung; **xong khi:** change không có error/warning mới, mọi warning cũ được tách rõ và không broad-rewrite RSA/main specs ngoài scope.
- [x] 8.4 Thực hiện review độc lập về data-loss/privacy/concurrency/rollback và xử lý finding trong scope; **xong khi:** không còn finding mức chặn, counterevidence và residual risk được ghi trong handback.
- [x] 8.5 Chuẩn bị rollout/retirement evidence package nhưng không deploy/cutover/delete; **xong khi:** artifact liệt kê actual image SQLite version, source-measure command, backup/restore rehearsal, manifest mẫu không nhạy cảm, exact retirement targets còn chờ, FE proxy/CORS input còn chờ và operational authorization gate.
