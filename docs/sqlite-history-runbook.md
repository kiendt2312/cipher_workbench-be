# Runbook chuyển history PostgreSQL sang SQLite

Runbook này dành cho một máy backend chạy đúng một app process. Máy frontend chỉ
gọi HTTP `/api`; không mount hoặc đọc file SQLite. Các lệnh rollout thật chỉ được
chạy sau khi operator điền và xác minh target cụ thể. Implementation/test dùng file
SQLite tạm và không phải bằng chứng cho dữ liệu production.

## 1. Input bắt buộc trước rollout

Ghi vào evidence package, không commit secret:

- absolute local data directory, runtime file và staging file trên cùng filesystem;
- UID/GID chạy app, migrate và backup; quyền directory tối thiểu;
- backup destination nằm ngoài SQLite/PostgreSQL volume sẽ retire;
- lịch backup, retention và người chịu trách nhiệm restore rehearsal;
- exact PostgreSQL database, container và volume thuộc riêng `cipher_workbench-be`;
- SQLite version trong image, dung lượng/inode trống và độ lệch clock/NTP ≤ 60 giây;
- FE dùng reverse proxy `/api` hay exact origin cho `CORS_ALLOW_ORIGINS`.

Không tiếp tục nếu data path là network/shared filesystem, mount type không xác
định, có nhiều app process, target PostgreSQL có thể dùng chung hoặc backup nằm
trong volume sẽ bị xóa.

Sau khi operator xác nhận host đã sync với nguồn NTP tin cậy, chạy preflight
read-only sau trên chính runtime SQLite; command không purge row:

```bash
uv run python -m app.history.retention --check-clock-only
```

Kết quả chỉ đạt khi SQLite UTC clock lệch process clock không quá 60 giây. Check
này không thay thế bằng chứng NTP của máy BE vì cả hai clock cùng lấy từ host.

## 2. Dry-run trên tài nguyên disposable

1. Tạo custom-format dump bằng PostgreSQL 17 `pg_dump`; không dùng `--no-sync`.
2. Kiểm tra archive bằng `pg_restore --list` và restore vào một database disposable.
3. Đo revision, schema, count, ID set, min/max ID và identity
   `last_value/is_called/increment` ở snapshot nguồn và bản restore.
4. Chạy transfer prepare vào một SQLite staging mới, không trùng runtime/backup.
5. Verify `integrity_check`, revision/schema/index/constraint, count, ID set,
   identity high-water và canonical SHA-256 của đủ 11 field.
6. Restore-rehearse backup SQLite vào file khác; đọc thử history/cursor/order.

Con số 15 row ở revision `0004` chỉ là bằng chứng lịch sử, không phải baseline.
Baseline luôn là phép đo trong rollout đã được ủy quyền.

Các command transfer không đọc `DATABASE_URL` làm nguồn. Cấp
`LEGACY_DATABASE_URL` qua secret environment của operator (không paste URL vào log
hoặc shell history), rồi dùng các biến path đã resolve trong evidence package:

```bash
uv run python -m app.history.postgres_source prepare \
  --staging "$STAGING_PATH" --runtime "$RUNTIME_PATH"
uv run python -m app.history.continuity verify \
  --database "$STAGING_PATH" --expected-manifest-digest "$MANIFEST_DIGEST" \
  --schema-revision sqlite_0001
```

Hai command trên fail-closed nếu staging đã tồn tại, nguồn không ở revision `0004`,
schema/identity/row không hợp lệ hoặc path staging trùng runtime. Output evidence đã
redact URL/path và không chứa payload.

## 3. Final cutover có write freeze

1. Dừng backend trước khi lấy mốc nguồn cuối; không có writer ứng dụng song song.
2. Tạo và restore-test PostgreSQL custom dump ở backup destination ngoài volume.
3. Chạy lại source measurement và transfer prepare/verify từ snapshot cuối.
4. Chỉ first-publish staging bằng atomic no-overwrite khi runtime chưa tồn tại,
   staging cùng filesystem và expected manifest digest khớp.
5. Chạy migrate/head check rồi khởi động đúng một app process.
6. Kiểm tra `/api/health`, `/api/history`, cursor/filter/order/UTC, một cipher smoke
   và RSA transform/keygen exclusion. Quan sát warning lock/disk trước khi đóng cửa
   sổ maintenance.

Mismatch, duplicate ID, invalid row, sai digest, thiếu backup hoặc lỗi I/O đều phải
dừng trước publish. Không sửa source để ép đối soát đạt.

`--app-stopped` là assertion do operator chịu trách nhiệm, không phải process lock.
Trước khi dùng publish/replace phải ghi evidence rằng service đã dừng và không còn
process/open connection giữ file. Không thay file dưới một process còn chạy vì nó
có thể tiếp tục ghi vào inode cũ.

First-publish dùng hard-link POSIX để tạo tên runtime theo kiểu no-overwrite, fsync
directory rồi mới unlink tên staging. Nếu process dừng giữa hai bước, hai tên có thể
cùng tồn tại nhưng phải trỏ tới cùng inode hợp lệ; giữ cả hai để đối soát và chỉ dọn
tên staging sau khi xác minh, không chạy publish lại mù quáng.

```bash
uv run python -m app.history.continuity publish \
  --staging "$STAGING_PATH" --runtime "$RUNTIME_PATH" \
  --expected-manifest-digest "$MANIFEST_DIGEST" --app-stopped
```

## 4. Backup và restore SQLite

Backup live dùng SQLite Online Backup API (`sqlite3.Connection.backup()`) hoặc
`VACUUM INTO`; không `cp` file database đang mở. Đích backup phải mới, ngoài runtime
volume và có quyền tối thiểu. Chỉ công nhận backup sau khi restore vào file tách
biệt, chạy integrity/revision/schema/digest check và đọc smoke thành công.
Manifest của backup phải được tính lại từ chính snapshot đích vì runtime có thể đã
nhận thêm row sau cutover; không tái dùng digest của manifest cutover làm digest
backup.

```bash
uv run python -m app.history.continuity backup \
  --source "$RUNTIME_PATH" --destination "$BACKUP_PATH"
uv run python -m app.history.continuity restore \
  --backup "$BACKUP_PATH" --target "$RESTORE_REHEARSAL_PATH" \
  --expected-manifest-digest "$BACKUP_MANIFEST_DIGEST" \
  --schema-revision sqlite_0001
```

Named volume giúp container restart nhưng không thay thế backup ngoài volume. Theo
dõi dung lượng, inode, lỗi permission và tỷ lệ history write bị bỏ do contention.

## 5. Rollback và fix-forward

- Replacement/restore runtime chỉ được dùng trước write SQLite đầu tiên, khi runtime
  vẫn khớp immutable cutover manifest. Không refresh manifest để lách gate.
- Trước khi SQLite nhận write mới: có thể dừng app mới và quay về code/PostgreSQL cũ.
- Sau khi SQLite có write mới: dừng write, tạo deterministic delta report; không tự
  ghi ngược PostgreSQL và không bỏ row. Delta gồm `sqlite_sequence`; sequence tăng
  vẫn chặn rollback dù row mới đã bị retention xóa. Owner phải phê duyệt remediation riêng.
- Sau khi PostgreSQL runtime đã retire: dùng recovery backup đã restore-test hoặc
  fix-forward; không giả định database/container/volume cũ còn live.

Không dùng SQLite downgrade phá hủy làm production rollback.

Delta report chỉ đọc hai SQLite snapshot/file đã xác định:

```bash
uv run python -m app.history.continuity delta \
  --before "$PRE_CUTOVER_SNAPSHOT" --after "$CURRENT_SQLITE_SNAPSHOT"
```

## 6. Gate retirement PostgreSQL dự án

Owner đã cho phép retirement sau cutover thành công, nhưng đây là operational phase
riêng. Trước thao tác phá hủy phải có đủ:

- read-only inventory ghi exact database/container/volume và bằng chứng chúng chỉ
  thuộc `cipher_workbench-be`;
- source/SQLite reconciliation cho count, ID set, identity high-water, UTC và digest;
- SQLite post-cutover health/history/cipher smoke đạt và đã quan sát ổn định;
- PostgreSQL recovery backup nằm ngoài volume sắp retire và restore rehearsal đạt;
- preview từng exact target, explicit operator confirmation và evidence package.

Nếu còn mơ hồ giữa database, container, volume, host package hay shared service thì
dừng và hỏi owner. Không xóa PostgreSQL host-wide, shared/unrelated resource,
original checkout, user stash, migration artifact hoặc recovery backup. Không dùng
glob và không dùng blanket `docker compose down -v`. Runbook này cố ý không chứa
lệnh delete khi exact target chưa được cung cấp.

## 7. Evidence package và dấu hiệu hoàn tất

Lưu command/version/output đã redaction cho: SQLite runtime version; path/mount và
UID/GID; PostgreSQL dump/list/restore; source measurement; manifest; staging verify;
SQLite backup/restore; health/history/cipher smoke; exact retirement inventory và
operator confirmation. Không lưu credential, absolute private path, plaintext,
ciphertext, key, filename, file content, trace, IP hoặc user-agent.

Rollout chỉ hoàn tất khi backup phục hồi vẫn còn sau retirement. Archive OpenSpec và
gỡ `asyncpg` là cleanup sau cùng, không phải điều kiện để chạy SQLite runtime.
