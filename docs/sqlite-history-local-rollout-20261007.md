# SQLite history local rollout evidence — 2026-10-07

Tài liệu này ghi operational evidence trên máy BE local, tách biệt với
46/46 checkbox implementation/disposable rehearsal trong OpenSpec. Owner chỉ cho
phép retire **dữ liệu PostgreSQL của project này**; không uninstall
PostgreSQL, không xóa service/role/database/volume/file dùng chung hay dữ liệu
khác.

## Source integration

- Checkout đích giữ nguyên `main@03c0c8568b98dc86ca301995e5472b71282a533d`.
- Manifest được chấp nhận gồm 41 file (19 file tracked sửa, 22 file mới),
  SHA-256 tổng hợp
  `3e88e2c05338975957118f1b002c7dfc6a602c4513e22d2bb2e75ec8df1dd807`.
- Mọi file đích trong manifest khớp byte với isolated worktree. Không stage,
  commit, push, merge, reset hay archive; 30 staged file, stash an toàn và các
  reference/untracked file của owner được giữ nguyên.
- `.env` chỉ đổi key `DATABASE_URL` sang scheme `sqlite+aiosqlite`; bản
  PostgreSQL trước cutover được giữ mode `600` ngoài volume. Không log
  credential.

## PostgreSQL source và backup

- Exact source: container `cipher_workbench-be-db-1`, Compose project
  `cipher_workbench-be`, service `db`, image PostgreSQL 17.11, database
  `cipher_workbench`, volume `cipher_workbench-be_pgdata`.
- Chỉ container trên reference volume; source database có revision `0004`, 15
  row, ID `1..16`, sequence `last_value=16/is_called=true/increment=1`, không có
  app connection khi freeze. Cluster còn database mặc định `postgres`; database
  này không có user table/sequence.
- ID-set SHA-256:
  `8408443678ac3f304aad1f71804227c761af298ebd96bb7a1d9d4d4d9a0db7e0`.
- Row SHA-256:
  `46c1dd96d5616d4692956d13747d44bd4a316d54a41a332e86ec7bc2f026a593`.
- Source/restore manifest SHA-256:
  `8e56e02322218cf7fcbbae3d1b363f89a998e883dc31116b2e05f2bd86723c07`.
- PG17 custom dump nằm ngoài volume tại
  `~/.local/share/cipher-workbench-be/backups/20261007-sqlite-cutover/postgresql-cipher_workbench.dump`,
  mode `600`, 5,421 byte, SHA-256
  `4dd60d7ae8eb332a7917d1c901ddd734a8c11ee2c8543fc3014faea29a6f77f9`.
  Archive list có table, sequence, table data và sequence set.
- Dump đã restore bằng PG17 vào database disposable, khớp revision/count/ID/
  sequence/các digest; database disposable sau đó được drop riêng. Evidence:
  `~/.local/share/cipher-workbench-be/backups/20261007-sqlite-cutover/postgres-restore-reconciliation.json`.

## Transfer, runtime và write proof

- Source freeze cuối cùng vẫn 15 row/sequence 16, không app connection; host
  báo NTP enabled/synchronized, timezone `Asia/Bangkok`.
- Prepare/publish manifest SHA-256:
  `22e8d611e46efc1fc97df22666a320c347354c2b6331357431425c745c78ee9d`;
  staging khớp source và first-publish không overwrite runtime.
- SQLite runtime: volume `cipher-workbench-be_history-data`, file
  `/data/cipher-history.sqlite3`, revision `sqlite_0001`, UID/GID `10001:10001`,
  Python 3.12.15, SQLite 3.46.1, `journal_mode=delete`, `synchronous=FULL`.
- App image
  `sha256:0490aa4215d90d1c3807b64f80c52cbdc2db73f38a9a6e1641ddda0c8d6883ae`;
  migrate image
  `sha256:4ed258ea8a37d71b186dc69783b77315747c40ec6d394cc311e66a2a382e4061`.
  Migrate exit `0`; app chạy đúng một Uvicorn process.
- Sau restart, health báo database `ok`, history `enabled`; 17 row vẫn còn,
  ID 18 (RSA) và 17 (Caesar) đứng đầu. Filter RSA trả đúng một row.
- Smoke trước retirement ghi Caesar ID 17 và RSA metadata-only ID 18; RSA
  keygen và DES trace không ghi history.
- Sau khi database PostgreSQL đã drop và container dừng, một Caesar request
  HTTP 200 tạo đúng row SQLite ID 19. History khi đó có 18 row,
  sequence 19; row chỉ chứa metadata hiện hành, không payload/key.

## SQLite backup và restore proof

Tất cả file dưới đây nằm ngoài runtime volume, trong parent directory
mode `700`, và phải được giữ vô thời hạn cho tới khi owner có retention
policy khác.

- Pre-write Online Backup/restore có cùng manifest digest
  `e255d7ae44d2ec3d5b34bb1fbda01b83192e1c75299200aa1fd8972b8c671365`.
- Post-write backup/restore 17 row/sequence 18 có cùng manifest digest
  `7e51177a1162167659a4ffb8b0c5180b2361539a257eee2e0ad1a7452707f84a`.
- Recovery point cuối sau retirement và write proof:
  - `sqlite-final-after-retirement.backup.sqlite3`: SHA-256
    `30820d507487e667eaff6b96056b27de30f4e0f2f979bfbd32645c5b10283062`.
  - `sqlite-final-after-retirement.restore.sqlite3`: SHA-256
    `d1f868b726c22e8237dd224f75555fc9de14b8e6d3324463a2f9a9b33a45ffae`.
  - Cả hai cùng manifest digest
    `22fad764656cd1c583a840abea081770af2d9914e5ae2c00d049ae69aefa18cb`;
    restore verify có 18 row, ID `1..19`, sequence 19, revision
    `sqlite_0001`, `quick_check=ok`.

## Project-data retirement

- Sau khi dump/PG17 restore, transfer reconciliation, SQLite write, restart,
  Online Backup và restore proof đều đạt, chỉ database literal
  `cipher_workbench` được drop; không dùng `--force`, glob, prune hay
  `docker compose down -v`.
- Postcondition: project database không còn trong `pg_database`; database mặc
  định `postgres` vẫn còn và không có user table/sequence; role login
  `cipher` vẫn còn.
- Container `cipher_workbench-be-db-1` chỉ bị dừng, không xóa. Volume
  `cipher_workbench-be_pgdata` và dữ liệu cluster khác được giữ nguyên.
  Host PostgreSQL/package/service, unrelated Docker resource và backup không bị
  đụng tới. Project database có thể phục hồi từ custom dump đã
  restore-test.

## Residual operational limits

- `/api/health` chỉ là read probe (`SELECT 1`), không phát hiện mọi lỗi
  write-only. Write proof thật đã chạy trong cutover, nhưng monitoring dài
  hạn cần synthetic write có cleanup/quy ước riêng nếu muốn phủ gap này.
- History API vẫn giữ public/unauthenticated behavior cũ; startup log cảnh báo
  không expose shared/public deployment khi chưa có access control.
- `CORS_ALLOW_ORIGINS` hiện không được cấu hình và không bị nới
  lỏng. FE khác máy phải dùng reverse proxy same-origin hiện có; nếu browser
  gọi trực tiếp BE cross-origin thì owner/operator phải cung cấp exact FE origin
  trước khi thay config.
- Runtime được chấp nhận cho một BE process trên local filesystem;
  không suy rộng sang multi-process/HA/network filesystem.

Hai sai lệch command không gây mutation đã được fail-closed: health path
ban đầu thiếu `/api`, và `dropdb` 17.11 từ chối option `--no-sync` không
được hỗ trợ. Lệnh drop sau đó dùng cú pháp từ `dropdb --help` của
binary thực tế và exact literal target.
