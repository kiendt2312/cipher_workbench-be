# SQLite history rollout/retirement evidence

Điền file này trong operational phase đã được ủy quyền. Không commit credential,
connection URL, absolute private path hoặc dữ liệu người dùng.

## Runtime và topology

- Build/commit:
- Python / SQLAlchemy / Alembic / aiosqlite:
- `sqlite3.sqlite_version` trong image:
- Một BE process được xác nhận bằng:
- FE proxy `/api` hoặc exact CORS origin:
- Local filesystem/mount evidence (đã redaction):
- Runtime/staging cùng filesystem:
- Service stopped + không còn process/open connection trước publish/replace:
- UID/GID và permission check:
- Free bytes/inodes:
- NTP/clock skew (phải ≤ 60 giây):

## PostgreSQL source và recovery backup

- Exact project database/container/volume inventory:
- Bằng chứng target không shared/host-wide:
- Source revision/schema:
- Snapshot timestamp UTC:
- Row count / min ID / max ID:
- Identity `last_value` / `is_called` / `increment` / last-issued:
- ID-set SHA-256:
- Canonical row SHA-256:
- PostgreSQL 17 dump command/version (redacted):
- `pg_restore --list` result:
- Disposable restore rehearsal result:
- Backup destination nằm ngoài volume sẽ retire:
- Backup retention/owner:

## SQLite staging và publish

- Manifest format version/digest:
- Integrity/revision/schema/index/constraint result:
- Row count / ID set / min/max match:
- Identity high-water / `sqlite_sequence` match:
- UTC microsecond/canonical digest match:
- First-publish hoặc replacement mode:
- Replacement pre-write: immutable old manifest + exact `sqlite_sequence`:
- Same-filesystem/no-overwrite evidence:

## SQLite backup và restore

- Online Backup API hoặc `VACUUM INTO`:
- Backup integrity result:
- Separate-file restore rehearsal:
- Revision/schema/digest/read smoke:
- Backup nằm ngoài runtime/PostgreSQL volume:

## Post-cutover smoke

- `/api/health`:
- `/api/history` order/filter/pagination/cursor/UTC:
- Cipher response smoke:
- RSA transform history metadata-only:
- RSA/Hill keygen và DES trace exclusion:
- Lock/disk/permission warning observation window:
- Nếu đã có write: row/ID/digest/`sqlite_sequence` delta và remediation decision:

## Retirement gate

- Mọi gate trên đạt:
- Preview từng exact project target:
- Explicit operator confirmation/timestamp:
- Recovery backup vẫn tồn tại sau retirement:
- PostgreSQL host package/shared database/unrelated container-volume không bị chạm:
- Không dùng glob hoặc `docker compose down -v`:

Nếu bất kỳ mục nào chưa điền hoặc ownership target còn mơ hồ, dừng trước retirement.
