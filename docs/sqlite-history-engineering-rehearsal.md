# SQLite history engineering rehearsal — 2026-10-07

Đây là bằng chứng disposable trong worktree, không phải rollout hoặc số đo dữ liệu
production. Không DB/container/volume người dùng nào được đọc hoặc thay đổi.

## PostgreSQL 17 → SQLite

- Container riêng dùng PostgreSQL server và `pg_dump`/`pg_restore` 17.11.
- Legacy migrations chạy tới revision `0004`; test nguồn thật: 9 passed, 11
  PostgreSQL-runtime tests retired được skip có chủ đích.
- Fixture gồm Caesar/RSA/DES, nullable RSA, UTC microsecond trùng nhau và identity
  high-water cao hơn max row. Adapter giữ đúng `last_value/is_called/increment`;
  SQLite row kế tiếp vượt high-water.
- Custom-format archive chứa table, sequence, table data và sequence-set. Archive
  bị cắt ngắn bị `pg_restore --list` từ chối.
- Restore vào database disposable khớp revision `0004`, count 3, ID `[2,7,11]`,
  identity last-issued 123, ID-set digest, row digest và manifest digest.

## Docker/SQLite

- Docker Engine 29.8.1; image build từ lockfile thành công.
- Compose chỉ chạy `migrate` rồi một process `app`, cùng named volume riêng.
- App chạy UID/GID `10001:10001`; đúng một Uvicorn process.
- Python trong image liên kết SQLite 3.46.1; runtime xác nhận
  `journal_mode=delete`, `synchronous=2 (FULL)` và revision `sqlite_0001`.
- Health trả database/history `ok/enabled`. Một row metadata được ghi và vẫn còn
  nguyên ID/timestamp sau force-recreate app và migrate chạy lặp lại.
- Bind directory sai quyền làm app non-root fail startup với lỗi cấu hình generic;
  output không chứa host path hoặc connection URL.

SQLite 3.46.1 chỉ là evidence của image engineering này. Operational evidence vẫn
phải đo image digest/version, mount, UID/GID và clock của máy BE thật trước cutover.

## Source measurement và manifest mẫu

Trong operational phase, operator cấp `LEGACY_DATABASE_URL` qua secret environment
và chạy command read-only/prepare dưới đây. JSON stdout là phép đo nguồn và không
chứa URL, path hay payload; staging/runtime vẫn phải là path đã resolve trên BE:

```bash
uv run python -m app.history.postgres_source prepare \
  --staging "$STAGING_PATH" --runtime "$RUNTIME_PATH"
```

Manifest dưới đây được tạo từ fixture tổng hợp rỗng, sequence PostgreSQL
`last_value=50`, `is_called=false`; đây chỉ là ví dụ format không nhạy cảm, không
phải baseline production:

```json
{
  "format_version": "history-continuity-v1",
  "source_revision": "0004",
  "schema_revision": "sqlite_0001",
  "snapshot_epoch_us": 1791334923456789,
  "count": 0,
  "min_id": null,
  "max_id": null,
  "identity": {
    "source": "postgresql",
    "last_value": 50,
    "is_called": false,
    "increment": 1,
    "last_issued": 49
  },
  "id_set_digest": "20d204cfdf437c79baf76b00736ce0a963f3f58c957885cbb4ba508e0df37509",
  "row_digest": "02a88a73af71e9d6eac71fa6719c78997f598c97c6acae38ed90597d2eb48714"
}
```

SHA-256 của canonical manifest mẫu là
`2ba29fecf02d51faf3c8462211b33a4e077f1baabe516a1f6e0e064615a1ca5e`.

## Input/gate còn chờ operational phase

- Exact database/container/volume PostgreSQL chỉ thuộc `cipher_workbench-be`, cùng
  preview từng target sẽ retire; chưa được cung cấp và chưa target nào bị xóa.
- Absolute local SQLite path/mount, UID/GID, free bytes/inodes, clock skew và backup
  destination ngoài volume sẽ retire trên máy BE thật.
- FE dùng reverse proxy `/api` hay exact origin để cấu hình CORS; không suy đoán địa
  chỉ FE và không nới wildcard/credential policy.
- Source measurement thật, custom dump/restore thật, staging manifest, SQLite
  backup/restore và post-cutover health/history observation phải được điền vào
  `docs/sqlite-history-evidence-template.md`.
- Cutover/deploy/retirement chỉ chạy trong operational phase được ủy quyền riêng;
  recovery backup vẫn phải tồn tại sau khi exact project PostgreSQL targets bị gỡ.
