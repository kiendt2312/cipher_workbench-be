# Design

## Context

Xem `proposal.md` cho động cơ. Backend hiện dùng Python 3.12, SQLAlchemy async và Alembic; dependency lock thực tế tại thời điểm lập kế hoạch là SQLAlchemy 2.1.1, Alembic 1.20.0 và asyncpg 0.31.0. DB runtime được bật tùy chọn bằng `DATABASE_URL`; engine hiện mang pool option PostgreSQL, model dùng `BigInteger + Identity` và `DateTime(timezone=True)`, retention dùng `func.now() - timedelta`, còn migration `0002`–`0004` drop/recreate CHECK constraint theo cách không portable sang SQLite.

Contract phải bảo toàn là effective state của main specs cộng active change `add-rsa-cipher` đã hoàn thành 51/51 task. Vì RSA chưa sync/archive vào main specs, thiết kế này xem Q1–Q16 và R1–R2 là authority: history có tám cipher, đúng 22 transform route; hai RSA transform được ghi metadata best-effort, keygen bị loại; không lưu content/key/trace/filename/`originalUtf8ByteLength`; lỗi storage không đổi safe transform response.

Mô hình mục tiêu là một máy FE và một máy BE. FE là entry point chính nhưng chỉ gọi HTTP; SQL engine và file nằm cùng máy với process BE. Không có địa chỉ/origin FE cụ thể được cung cấp, nên không thay CORS allowlist hoặc giả định hostname.

Nguồn chính thức đã kiểm tra ngày 2026-10-07:

- SQLite “Appropriate Uses”: local application-server storage phù hợp khi application code và file cùng máy, nhưng SQLite chỉ có một writer tại một thời điểm và không nên dùng file qua network filesystem: <https://www.sqlite.org/whentouse.html>.
- SQLite WAL: WAL chỉ có một writer, yêu cầu cùng host; lỗi WAL-reset ảnh hưởng nhiều version `3.7.0`–`3.51.2`, sửa ở `3.51.3` hoặc backport `3.44.6`/`3.50.7`: <https://www.sqlite.org/wal.html>.
- SQLite backup: Online Backup API tạo snapshot nhất quán; `VACUUM INTO` là lựa chọn backup live khác, trong khi raw copy live có rủi ro: <https://www.sqlite.org/backup.html>.
- SQLAlchemy 2.1 SQLite dialect: `aiosqlite` hỗ trợ async qua thread nền; SQLite auto-ID yêu cầu type render chính xác là `INTEGER`; SQLite không có native datetime và SQLAlchemy lưu dạng format; pooling/transaction control cần cấu hình theo driver: <https://docs.sqlalchemy.org/en/21/dialects/sqlite.html>.
- Alembic 1.20 batch mode: thay đổi schema SQLite thường dùng “move and copy”; đây không phải lý do để chạy chuỗi PostgreSQL hiện hữu trên SQLite: <https://alembic.sqlalchemy.org/en/latest/batch.html>.
- PostgreSQL 17 `pg_dump` tạo backup nhất quán và custom format có thể inspect/restore bằng `pg_restore`; sequence values thuộc data dump: <https://www.postgresql.org/docs/17/app-pgdump.html> và <https://www.postgresql.org/docs/17/app-pgrestore.html>.

Chẩn đoán local hiện tại cho Python 3.12.3 cho thấy `sqlite3.sqlite_version == 3.45.1`. Đây không chứng minh version trong image production tương lai, nhưng đủ để bác bỏ giả định rằng WAL mặc định an toàn. Image/container rollout phải tự báo và kiểm tra version thực tế.

## Goals / Non-Goals

**Goals:**

- Một storage SQLite local, bền vững, ít thành phần vận hành, phù hợp một BE process.
- Bảo toàn public history/API, effective RSA semantics và mọi row PostgreSQL tại mốc cutover.
- Tách rõ schema evolution SQLite khỏi migration chain PostgreSQL đã áp dụng.
- Có failure model rõ cho lock, read-only, permission, disk-full, corruption, restart và backup/restore.
- Cho phép dry-run, đối soát và rollback trước rollout; rollout thực tế cần ủy quyền riêng.
- Sau cutover thành công, cho phép retire PostgreSQL project-scoped theo checklist có bằng chứng trong khi giữ recovery backup phục hồi được.

**Non-Goals:**

- Không hỗ trợ nhiều BE process, nhiều container app đồng thời, network/shared filesystem, active-active hay dual-write PostgreSQL/SQLite.
- Không thay API, cipher behavior, retention/access/CORS policy hoặc mở rộng metadata.
- Không tự động cutover, truy cập user DB/container, xóa PostgreSQL hoặc nâng dependency không liên quan.
- Không xóa PostgreSQL host-wide, database/service dùng chung, target chưa resolve chắc chắn hoặc backup phục hồi; không dùng blanket `docker compose down -v`.
- Không biến các migration PostgreSQL `0001`–`0004` thành migration đa dialect và không reinterpret `add-rsa-cipher` thành change DB.

## Decisions

### 1. Giữ `DATABASE_URL`, nhưng runtime chỉ nhận SQLite file tuyệt đối

Giữ biến hiện hành để không tạo thêm một cơ chế enable/disable: rỗng vẫn là `disabled`; compose/deploy mới đặt `sqlite+aiosqlite:////data/cipher-history.sqlite3`. Parser xác nhận dialect/driver, absolute path và không `:memory:`. Linux preflight resolve path/data root, từ chối symlink escape, kiểm tra parent/quyền, đọc mount type từ `/proc/self/mountinfo`, deny remote filesystem đã biết và fail-closed khi không chứng minh được local. Engine mở URI mode `rw` để missing DB không bị tự tạo; migrate command mới được tạo file. Mọi lỗi redacted. Test có thể tạo engine/file tạm trực tiếp mà không nới contract production.

Phương án thêm `SQLITE_PATH` bị loại vì tạo hai nguồn cấu hình. Phương án tiếp tục nhận PostgreSQL runtime bị loại vì làm “switch” thành hỗ trợ hai backend vô thời hạn và kéo theo matrix migration/query lớn hơn. `LEGACY_DATABASE_URL` chỉ tồn tại cho command chuyển đổi/rollback, không được app runtime đọc.

### 2. Một SQLite engine/pool bị giới hạn; một process app

Thêm đúng driver `aiosqlite` tương thích SQLAlchemy 2.1.1. `aiosqlite` vẫn dùng thread nền cho mỗi connection chứ không phải socket I/O thật; vì vậy async API hiện hữu được giữ nhưng không được hiểu là SQLite có multi-writer concurrency. Engine SQLite không tái dùng mù quáng `pool_size=5/max_overflow=5` của PostgreSQL. Thiết kế dùng pool giới hạn một connection cho workload nhỏ này để tuần tự hóa write/read/retention trong process; compose chạy một Uvicorn process.

SQLite `busy_timeout` và pool checkout timeout đều là 200 ms, trong khi toàn bộ record operation vẫn bị bọc bởi deadline 500 ms và health bởi 1 giây. Khi timeout/cancellation/commit error, session phải rollback; connection lỗi được invalidate/close trước khi trả pool, rồi test checkout/query kế tiếp. Mọi commit phải ngắn. Import, migration, publish và restore không chạy đồng thời với app; riêng online backup được phép chạy live bằng API snapshot ở quyết định 9.

Phương án nhiều connection + WAL bị loại vì version chưa an toàn và tăng state checkpoint. Phương án driver sync trực tiếp trong event loop bị loại vì có thể block API.

### 3. Rollback journal + durability bảo thủ, không bật WAL

Database giữ `journal_mode=DELETE` và durability tương đương `synchronous=FULL`; không gửi `PRAGMA journal_mode=WAL`. Khi mở connection, app xác nhận journal mode/durability mong đợi và đặt busy timeout mà không log path. Mọi thay đổi journal mode trong tương lai là change riêng: phải đo runtime SQLite trong image, yêu cầu `>=3.51.3` hoặc bản backport có fix, test ít nhất hai connection với write/checkpoint cạnh tranh, và có backup/restore evidence.

Rollback journal cho phép ít read/write concurrency hơn WAL, nhưng phù hợp tải metadata nhỏ và một process. Khi contention làm vượt budget, history row được phép rơi theo best-effort; cipher response không đổi.

### 4. SQLite baseline riêng; PostgreSQL chain bất biến

Tạo Alembic config/script location riêng cho SQLite với baseline full schema ở effective head (gồm RSA). Không sửa nội dung hoặc giả lập execution của `0001`–`0004`; chúng tiếp tục mô tả PostgreSQL legacy. Default migration command/documentation sau switch trỏ rõ SQLite config. Migration service chạy trước app và mount cùng data volume; app không `create_all`, auto-upgrade hoặc stamp. Runtime mở database ở chế độ không tự tạo file; nếu file/revision chưa sẵn sàng thì health/history unavailable nhưng cipher vẫn phục vụ.

Các migration SQLite tương lai dùng native ALTER khi đủ và Alembic batch “move and copy” khi cần; mỗi migration phải có test upgrade trên file có dữ liệu và chạy lại ở head. Không dùng destructive `downgrade base` như rollback production.

Phương án “stamp 0004 rồi thêm 0005” bị loại vì giả vờ hai schema cùng chain và làm fresh SQLite chạy sai dialect. Phương án rewrite `0001`–`0004` bị loại vì phá lịch sử đã áp dụng và rollback PostgreSQL.

### 5. Schema giữ 11 field logic, ID/timestamp có representation SQLite rõ

- `id`: `INTEGER PRIMARY KEY AUTOINCREMENT`. Từ khóa `AUTOINCREMENT` có overhead nhỏ nhưng được chọn có chủ đích để không tái sử dụng ID sau delete, giữ cursor/ordering tương đương PostgreSQL identity. Preflight đọc sequence identity nguồn (`last_value`, `is_called`, `increment`) và dẫn xuất last-issued high-water; `sqlite_sequence.seq` được đặt thành `max(max imported id, last-issued high-water)` để ID đã cấp nhưng bị retention xóa cũng không tái xuất hiện.
- `created_at`: INTEGER epoch microsecond UTC 64-bit, do app gán từ clock UTC cho row mới. Cách này giữ exact instant/precision PostgreSQL, sort số đúng và tránh SQLite/driver làm mất timezone trên `DateTime(timezone=True)`. Adapter duy nhất chuyển aware UTC datetime ↔ epoch microsecond và từ chối naive/out-of-range.
- Text/nullability/length/status/duration dùng affinity phù hợp và CHECK hiện hành; `succeeded` là `0|1`; cipher CHECK bao gồm RSA. Không dùng JSON/blob hoặc thêm cột payload.
- Index dùng `(created_at DESC, id DESC)` và `(cipher, created_at DESC, id DESC)`; operation filter vẫn đúng semantics dù không thêm index ngoài scope.

Cursor wire format không đổi: ISO timestamp + ID. Query chuyển timestamp cursor sang epoch microsecond và dùng predicate portable `created_at < :ts OR (created_at = :ts AND id < :id)` thay vì phụ thuộc row-value SQL theo dialect. API convert lại ISO 8601 UTC như hiện tại. Test mang cursor tạo trước cutover qua DB sau cutover.

Phương án SQLite `BIGINT PRIMARY KEY` bị loại vì không alias ROWID/auto-ID. Phương án `DATETIME(timezone=True)` trực tiếp bị loại vì SQLite không có native timezone và retrieval có thể naive. Phương án millisecond text default bị loại vì có thể làm mất precision/dest ordering.

### 6. Retention tiếp tục dùng database clock UTC

Cutoff dùng SQLite database expression lấy current UTC epoch rồi trừ số ngày và so với epoch microsecond; không dùng clock Python riêng cho purge. Điều này giữ mô hình “DB now” hiện hành dù database đã chuyển cùng máy BE. Rollout preflight phải xác nhận clock/NTP máy BE lệch không quá 60 giây so với nguồn tin cậy; vượt ngưỡng thì không cutover. Schedule, khoảng 6 giờ, default/range 1–3650 ngày, CLI output và failure logging giữ nguyên. Test freeze/inject database clock để kiểm tra boundary và timezone host.

### 7. Công cụ chuyển đổi tạo staging mới và có manifest đối soát

Command prepare nhận URL nguồn legacy riêng và đường dẫn staging mới; nguồn luôn transaction/read-only theo khả năng driver. Nó kiểm tra revision/schema nguồn hỗ trợ (effective `0004` cho RSA), đọc row theo ID ổn định theo batch, canonicalize timestamp về UTC microsecond, validate type/constraint và insert explicit ID. Preflight đọc identity sequence state và đặt SQLite sequence sau cả max imported ID lẫn last-issued high-water.

Manifest không chứa secret/path/payload, nhưng ghi format version, schema revision, snapshot time, count, min/max ID, identity `last_value/is_called/increment/last-issued`, ID-set digest và row digest. Digest là SHA-256 trên header versioned và rows sort ID tăng; mỗi field theo thứ tự 11 cột dùng type tag + ASCII byte length tối giản + `:` + payload. Text là UTF-8 nguyên trạng, integer/timestamp là ASCII decimal tối giản, boolean `0|1`, null có tag riêng. Source/target dùng cùng serializer độc lập.

Prepare/verify chỉ tạo hoặc đọc staging tên độc quyền trong cùng filesystem và không chạm runtime. Sau `integrity_check`, revision/schema/index/constraint/count/ID/digest/sequence khớp, command publish riêng nhận expected manifest digest, yêu cầu app dừng và runtime chưa tồn tại. First-publish dùng POSIX hard-link creation atomic no-overwrite, fsync directory rồi unlink tên staging; nếu crash giữa link/unlink thì cả hai tên cùng trỏ tới file hợp lệ và có thể dọn lại an toàn. Nếu runtime đã tồn tại, publish fail-closed. Replacement/restore là mode riêng chỉ dành cho runtime **chưa nhận write sau cutover**: yêu cầu backup runtime đã restore-test, expected digests và explicit confirmation, sau đó `os.replace` cùng filesystem; lỗi trước replace giữ runtime cũ, backup được giữ để recovery. Manifest cutover trong runtime là provenance bất biến, không được refresh để lách gate. Một write mới làm runtime không còn khớp expected old digest, nên replacement dừng trước mutation và chuyển sang delta/manual remediation. `--app-stopped` là operator assertion; command không thể tự chứng minh không còn process/open file descriptor, vì vậy evidence vận hành phải ghi shutdown và kiểm tra process trước publish/replace.

Không dùng dual-write vì làm failure/reconciliation khó hơn và có thể lệch semantics best-effort. Không export qua CSV vì null/timestamp/bool dễ drift. Không copy raw PostgreSQL files vì khác engine.

### 8. Cutover có write freeze ngắn; source được giữ tới khi đủ bằng chứng

Dry-run trên disposable target được phép trước. Final cutover sau này theo runbook owner duyệt: dừng BE; tạo PostgreSQL 17 custom-format `pg_dump` không dùng `--no-sync`; inspect archive và restore-rehearse trên disposable PostgreSQL; đối soát schema/rows/identity/digest; đo source thực; prepare/verify SQLite staging; first-publish; health/history/cipher smoke; rồi mở BE. PostgreSQL database/container/volume dự án chưa được retire trong bước cutover; dump/recovery backup đã verify không bị xóa.

Đây là lựa chọn bảo toàn dữ liệu. Nếu không chấp nhận write freeze, cần objective mới cho dual-write/CDC; không âm thầm đổi approach trong implementation.

### 9. Backup SQLite bằng snapshot API và restore rehearsal

Backup định kỳ SQLite được phép chạy khi app live bằng Python `sqlite3.Connection.backup()` hoặc `VACUUM INTO`; không `cp` file đang mở. Command mở snapshot connection riêng, chịu busy timeout/lock ngắn; history write cạnh tranh vẫn theo best-effort 500 ms. Backup đặt ngoài runtime filename, quyền chỉ app/operator, kèm revision/manifest và `integrity_check`. Restore luôn vào file tách biệt, validate/read smoke trước replacement mode khi app dừng.

Named volume bảo vệ restart container nhưng không thay thế backup ngoài volume. Runbook phải nêu quyền UID/GID, dung lượng/inode, monitoring, lịch backup/retention và test restore định kỳ; chính sách lịch backup cụ thể là input vận hành trước deploy, không đổi code/spec.

### 10. Rollback phân biệt trước và sau write mới

Trước khi SQLite nhận write mới, rollback là dừng app mới và chạy code cũ với PostgreSQL nguồn giữ nguyên. Sau write mới, runbook dừng write và tạo delta report deterministic (row/ID/digest cùng `sqlite_sequence`) nhưng không tự ghi ngược PostgreSQL. Sequence tăng vẫn là delta material dù row tương ứng đã bị retention xóa, vì nếu bỏ qua có thể tái sử dụng ID khi quay về nguồn cũ. Fail-closed/manual reconciliation là endpoint được chấp nhận của change này: rollback/replacement bị chặn cho tới khi owner phê duyệt target/phương án hợp nhất riêng. Nếu có phê duyệt sau đó, thao tác merge là một rollout/remediation được ủy quyền riêng, không nằm trong app runtime hay command import mặc định.

Fix-forward với SQLite thường an toàn hơn rollback sau write, nhưng đây là quyết định rollout theo sự cố, không phải quyền của migration command. Không tự động ghi ngược PostgreSQL trong app runtime.

### 11. FE topology và CORS không đổi

FE tiếp tục gọi relative `/api` qua proxy là mặc định. Nếu hai máy dùng cross-origin trực tiếp, operator đặt đúng origin hiện có vào `CORS_ALLOW_ORIGINS`; không biết origin không phải lý do dùng wildcard, credentials hoặc nới allowlist. SQLite path/volume không expose khỏi BE. `GET /api/history`, health shape, 404/503/422 và mọi cipher route không đổi.

### 12. Dependency và test matrix tối thiểu, có lý do

Chỉ thêm/pin `aiosqlite` qua uv và lockfile. Giữ asyncpg trong giai đoạn chuyển đổi vì công cụ import/rollback cần đọc PostgreSQL; việc gỡ asyncpg là cleanup sau khi transfer tooling không còn cần source và retirement evidence đã được chấp nhận. Không nâng FastAPI/SQLAlchemy/Alembic/SQLite một cách ngầm định để “tiện migration”.

### 13. Retirement PostgreSQL là operational gate project-scoped

Owner đã cho phép retire PostgreSQL sau chuyển dữ liệu thành công, nhưng lệnh phá hủy chỉ được lập trong operational phase riêng. Trước đó operator phải resolve exact database/container/volume thuộc duy nhất `cipher_workbench-be` bằng read-only inventory; lưu evidence count/ID/high-water/UTC/digest; chứng minh SQLite post-cutover health/history/cipher; và restore recovery backup ngoài volume đã được kiểm tra. Runbook phải preview exact targets, yêu cầu explicit confirmation và xóa từng target cụ thể; cấm glob, target suy diễn, `docker compose down -v`, host package removal hoặc đụng shared service/database.

Nếu không phân biệt chắc chắn DB, container, volume hay host/shared PostgreSQL, retirement dừng để hỏi owner. Sau retirement, rollback dùng recovery backup đã giữ hoặc fix-forward; không được tuyên bố rollback tức thời về live PostgreSQL cũ. Backup retention/schedule vẫn là input vận hành và không bị quyền “xóa PostgreSQL” supersede.

Validation implementation gồm:

- unit cho URL validation/redaction, UTC microsecond codec, cursor cũ, predicate pagination, schema checks và manifest digest;
- SQLite integration trên file tạm cho fresh migration, repeat upgrade, restart, retention, ordering/filter/pagination, constraint/ID sequence, history API/status/timezone và RSA privacy/keygen exclusion;
- fault/concurrency cho read-only, permission, disk-full giả lập, exclusive lock vượt timeout, cancelled write/rollback, health 1 giây và recorder 500 ms;
- disposable PostgreSQL + SQLite cho import đủ schema 0004, null/RSA/timestamp trùng, count/ID/digest mismatch, rerun/no-overwrite và rollback delta;
- backup/restore/integrity test trên file tạm; Docker volume/recreate/UID permission smoke;
- toàn bộ regression cipher/OpenAPI/history/RSA, Ruff, coverage ≥90%, OpenSpec strict. Không dùng DB/volume của owner cho test.

## Risks / Trade-offs

- **[Một writer và lock contention làm rơi metadata]** → một process/pool giới hạn, transaction ngắn, busy timeout dưới 500 ms, fault test; giữ semantics best-effort và đo warning rate.
- **[Rollback journal làm reader/writer chặn nhau]** → page nhỏ, query keyset/index, session ngắn; không bật WAL trên runtime chưa được vá. Nếu tải thực vượt ngưỡng, đánh giá lại PostgreSQL hoặc SQLite version/workload bằng change riêng.
- **[SQLite runtime trong image khác máy lập kế hoạch]** → log version không nhạy cảm lúc startup, assert mode/config và capture version trong deployment evidence; không dựa trên host 3.45.1 như production proof.
- **[Mất timezone/precision hoặc cursor drift]** → epoch microsecond UTC + explicit codec + cross-cutover cursor fixtures/digest.
- **[ID bị tái sử dụng sau retention]** → capture PostgreSQL identity high-water, `INTEGER PRIMARY KEY AUTOINCREMENT`, seed `sqlite_sequence` sau cả high-water/max row, test delete/restart/import.
- **[Import snapshot không nhất quán]** → write freeze cuối, source read-only transaction/backup, deterministic reconciliation trước publish.
- **[Disk/permission/volume lỗi]** → preflight path/UID/free space, health/fault tests, named volume + backup ngoài volume; không log path.
- **[Backup tưởng an toàn nhưng không restore được]** → PostgreSQL custom dump + disposable restore, SQLite Online Backup/VACUUM INTO + restore rehearsal, integrity/digest bắt buộc.
- **[Rollback sau cutover làm mất row mới]** → phân nhánh rollback, freeze + delta reconciliation, fail-closed khi collision; trước retirement có thể dùng source live, sau retirement chỉ dùng recovery backup hoặc fix-forward.
- **[Retirement xóa nhầm shared/host resource hoặc cả backup]** → exact read-only inventory, project ownership proof, per-target confirmation, cấm blanket cleanup và giữ restore-tested backup ngoài volume.
- **[Main specs cũ ghi bảy cipher/PostgreSQL]** → implementation/review dùng effective RSA authority; archive/sync theo thứ tự không được làm mất Q16/R1/R2 hoặc đổi 22-route matcher.
- **[SQLite không phù hợp khi scale]** → giới hạn được tài liệu hóa: một BE process, file local, tải writer thấp. Nhiều process/máy hoặc write-heavy là trigger quay lại client/server DB.

## Migration Plan

Phần 1–6 dưới đây là kế hoạch implementation trong worktree/disposable DB sau khi có request apply mới; phần 7 là rollout production cần ủy quyền riêng:

1. Đóng băng effective contract bằng regression tests, đặc biệt API/cursor/UTC, 22 route, RSA privacy/keygen exclusion và best-effort 500 ms.
2. Thêm aiosqlite, SQLite config/engine/codec/model/query/retention và migration root riêng; giữ PostgreSQL migrations bất biến.
3. Thêm prepare/verify/first-publish/replacement, reconciliation, PostgreSQL/SQLite backup-restore commands fail-closed, kèm fixtures disposable ở revision `0004` và SQLite staging.
4. Chuyển compose/docs sang SQLite volume local, migration-before-app, one process; giữ legacy PostgreSQL path cho export/rollback cho tới operational retirement.
5. Chạy targeted fault/migration/transfer/Docker tests, full suite, coverage/Ruff/OpenSpec strict; review độc lập privacy/data-loss/rollback.
6. Tạo runbook dry-run/cutover/rollback, ghi rõ production path/volume/UID, backup destination/schedule, actual SQLite version và FE proxy/exact CORS origin. Không điền origin giả.
7. Chỉ sau ủy quyền rollout: dry-run → maintenance/write freeze → PostgreSQL backup + source measure → staging import/reconcile → atomic publish → migration/health/history/cipher smoke → mở traffic → quan sát. Sau khi evidence được duyệt, operational phase riêng mới retire exact PostgreSQL database/container/volume dự án và giữ recovery backup; rollback theo nhánh trước/sau write mới và trước/sau retirement.

## Open Questions

- Đường dẫn volume, UID/GID và nơi lưu backup ngoài volume trên máy BE sẽ được operator cung cấp trước rollout; compose development mặc định `/data/cipher-history.sqlite3` không tự động trở thành production path.
- FE origin cụ thể và việc dùng reverse proxy hay CORS trực tiếp sẽ được xác nhận trong runbook; code giữ proxy `/api` và exact allowlist hiện hành.
- Backup frequency/retention, exact project-scoped retirement targets và thời điểm gỡ asyncpg là input vận hành trước cleanup; owner đã chấp nhận retirement sau khi đủ bằng chứng nhưng chưa cung cấp các target/path cụ thể.
