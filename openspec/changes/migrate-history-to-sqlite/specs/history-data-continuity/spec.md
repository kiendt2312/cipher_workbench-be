# Spec Delta

## Purpose

Bảo đảm toàn bộ lịch sử metadata PostgreSQL được chuyển sang SQLite có thể kiểm chứng, sao lưu và rollback; chỉ retire nguồn dự án sau khi đủ bằng chứng và không xóa recovery backup.

## ADDED Requirements

### Requirement: Nguồn PostgreSQL được giữ nguyên trong transfer và cutover

Quy trình SHALL coi PostgreSQL hiện hữu là nguồn chỉ đọc trong export/import và MUST NOT drop, truncate, mutate hoặc xóa nguồn trước khi mọi transfer/cutover gate đạt. Trước cutover SHALL tạo PostgreSQL 17 custom-format dump và restore-rehearse trên database disposable. (Truy vết: quyết định chủ sở hữu và retirement 2026-10-07; PostgreSQL 17 `pg_dump`/`pg_restore`)

#### Scenario: Chuẩn bị cutover

- **WHEN** operator bắt đầu một rollout đã được ủy quyền
- **THEN** quy trình xác nhận revision/schema nguồn, đo số row thực tế và tạo backup trước import
- **AND** không câu lệnh ghi hay xóa nào được thực thi trên nguồn PostgreSQL
- **AND** 15 row ở revision `0004` chỉ được coi là bằng chứng lịch sử, không phải số đo rollout

#### Scenario: Restore rehearsal nguồn

- **WHEN** custom-format dump PostgreSQL đã được tạo
- **THEN** archive được inspect và restore vào database disposable
- **AND** schema, row count, ID set, identity state và digest của restore khớp nguồn tại snapshot

#### Scenario: Không dùng số đếm lịch sử làm bằng chứng hiện tại

- **WHEN** số row nguồn tại rollout khác 15
- **THEN** quy trình dùng số đo tại rollout làm baseline đối soát và không coi khác biệt đó là lỗi tự thân

### Requirement: Cô lập mốc dữ liệu cutover

Trong cửa sổ cutover, backend SHALL dừng nhận thao tác có thể tạo history trước khi lấy mốc nguồn cuối cùng. Snapshot/transaction nguồn dùng cho import SHALL biểu diễn một mốc nhất quán và không có writer ứng dụng chạy song song. (Truy vết: quyết định chủ sở hữu 2026-10-07 về data preservation)

#### Scenario: Dừng ghi trước snapshot cuối

- **WHEN** operator bắt đầu final cutover đã được ủy quyền
- **THEN** backend được dừng trước khi đo mốc nguồn và chạy import cuối
- **AND** không có row history mới được tạo sau mốc nguồn đó

### Requirement: Chuyển toàn bộ row giữ nguyên ngữ nghĩa

Công cụ chuyển SHALL đưa mọi row tại mốc nguồn vào một file SQLite staging mới và giữ nguyên đủ 11 field, gồm ID, UTC microsecond, nullable field và tám cipher gồm `rsa`. Công cụ MUST không thêm, bỏ, làm tròn, đổi timezone, tái tạo ID hoặc thu thập content/key/trace/filename/IP/user-agent. (Truy vết: quyết định chủ sở hữu 2026-10-07; main `operation-history`; active `add-rsa-cipher` Q16)

#### Scenario: Import có timestamp trùng nhau

- **WHEN** nguồn có nhiều row cùng `created_at` nhưng ID khác nhau
- **THEN** đích giữ nguyên mọi ID và epoch microsecond
- **AND** thứ tự `(created_at DESC, id DESC)` trên đích giống nguồn

#### Scenario: Import row RSA nullable

- **WHEN** nguồn có row RSA number transform với length và `response_mode` là NULL
- **THEN** đích giữ nguyên các giá trị NULL và mọi metadata còn lại
- **AND** không payload RSA nào được xuất hay tạo trong artifact chuyển đổi

### Requirement: Giữ identity high-water PostgreSQL

Preflight SHALL đọc sequence gắn với PostgreSQL identity và ghi `last_value`, `is_called`, `increment` cùng last-issued high-water dẫn xuất vào manifest. SQLite `sqlite_sequence` SHALL được đặt bằng giá trị lớn hơn hoặc bằng max row ID và last-issued high-water trước publish. (Truy vết: quyết định chủ sở hữu 2026-10-07 về không tái sử dụng ID; schema PostgreSQL `0001`)

#### Scenario: Row cao nhất đã bị purge

- **WHEN** identity nguồn đã cấp ID 100 nhưng max row còn tồn tại là 90
- **THEN** manifest ghi high-water 100 và row SQLite mới đầu tiên có ID lớn hơn 100

#### Scenario: Sequence chưa từng được gọi

- **WHEN** sequence nguồn có `is_called=false`
- **THEN** last-issued high-water được dẫn xuất theo `last_value`/`increment` thay vì coi `last_value` là ID đã cấp

### Requirement: Đối soát trước khi publish

File staging MUST chỉ được publish sau khi SQLite integrity, revision/schema/constraint/index, row count, ID set, min/max ID và canonical digest của đủ 11 field đều khớp snapshot nguồn. Mọi mismatch, row không hợp lệ, duplicate ID hoặc lỗi I/O SHALL làm cutover dừng trước publish. (Truy vết: quyết định chủ sở hữu 2026-10-07 về data preservation và reconciliation)

#### Scenario: Đối soát thành công

- **WHEN** schema, integrity, count, ID set và canonical digest của staging đều khớp nguồn
- **THEN** file staging được phép publish bằng thao tác atomic khi không có connection đang mở

#### Scenario: Đối soát thất bại

- **WHEN** bất kỳ count, ID, digest, constraint hoặc integrity check nào không khớp
- **THEN** file staging không trở thành database runtime
- **AND** nguồn PostgreSQL và backup vẫn nguyên vẹn để điều tra hoặc chạy lại

### Requirement: Digest đối soát tái lập

Digest SHALL là SHA-256 trên stream versioned, sort theo ID tăng dần. Mỗi row SHALL encode 11 field theo thứ tự schema bằng type tag, byte length thập phân canonical, dấu `:` và payload; text dùng UTF-8 nguyên trạng, số/UTC microsecond dùng ASCII decimal tối giản, boolean dùng `0|1`, null có tag riêng. (Truy vết: quyết định kỹ thuật change này để thực thi đối soát đã được chủ sở hữu yêu cầu ngày 2026-10-07)

#### Scenario: Hai engine có cùng dữ liệu

- **WHEN** PostgreSQL và SQLite có cùng 11 field sau canonical conversion
- **THEN** hai stream bytes và SHA-256 digest giống hệt dù driver/type storage khác nhau

#### Scenario: Phân biệt null, text và framing

- **WHEN** một field đổi null/text/value/byte length hoặc hai field có nội dung nối chuỗi gây mơ hồ nếu không framing
- **THEN** canonical stream khác và digest mismatch

### Requirement: Prepare và publish là hai mode tách biệt

Mode prepare/verify SHALL chỉ tạo/đọc staging mới và MUST không chạm runtime. Mode publish SHALL là command riêng, yêu cầu manifest digest mong đợi, app đã dừng, staging cùng filesystem và runtime chưa tồn tại; khi đó publish SHALL tạo runtime bằng atomic hard-link no-overwrite, fsync directory rồi unlink tên staging. Runtime tồn tại SHALL làm publish từ chối. (Truy vết: quyết định chủ sở hữu 2026-10-07 về cutover fail-closed; quyết định kỹ thuật Lead về POSIX no-overwrite)

#### Scenario: Publish cùng filesystem

- **WHEN** staging đã đối soát đạt, nằm cùng filesystem, manifest digest khớp, app đã dừng và runtime chưa tồn tại
- **THEN** command publish riêng được phép tạo atomic hard-link runtime không-overwrite, fsync directory rồi unlink tên staging
- **AND** nếu crash sau khi link nhưng trước unlink thì cả hai tên vẫn trỏ tới cùng file hợp lệ để cleanup chạy lại an toàn

#### Scenario: Cross-filesystem hoặc app còn mở

- **WHEN** staging khác filesystem với runtime hoặc app còn connection mở
- **THEN** publish bị từ chối và runtime/backup hiện hữu không đổi

#### Scenario: Runtime đã tồn tại

- **WHEN** mode publish thấy runtime path đã tồn tại
- **THEN** command từ chối và yêu cầu quy trình replacement/restore được ủy quyền riêng

### Requirement: Replacement runtime là mode được ủy quyền riêng

Replacement/restore SHALL là command khác publish lần đầu và chỉ hợp lệ trước write đầu tiên sau cutover. Nó MUST yêu cầu backup đã verify, immutable expected digests, app-stopped evidence, explicit confirmation và cùng filesystem. Manifest cutover MUST giữ bất biến; backup MUST được giữ. (Truy vết: quyết định chủ sở hữu 2026-10-07 về rollback/backup; quyết định kỹ thuật Lead 2026-10-07 về pre-write-only replacement)

#### Scenario: Replacement có đủ evidence

- **WHEN** runtime chưa nhận write mới, backup đã restore-test, expected digests khớp và operator gọi explicit replacement mode
- **THEN** staging được atomic replace vào runtime và backup cũ vẫn được giữ

#### Scenario: Replacement thiếu evidence

- **WHEN** thiếu backup verify, digest mismatch, app còn mở hoặc thiếu explicit confirmation
- **THEN** replacement bị từ chối trước atomic replace

#### Scenario: Evidence app-stopped do operator cung cấp

- **WHEN** operator chuẩn bị gọi replacement
- **THEN** runbook yêu cầu bằng chứng service đã dừng và không còn process/open connection
- **AND** command không được diễn giải cờ `app stopped` như process lock tự kiểm chứng

#### Scenario: Replacement sau write mới

- **WHEN** runtime đã nhận ít nhất một write hoặc sequence đã tăng so với immutable cutover manifest
- **THEN** replacement bị từ chối trước mutation, staging/backup/runtime được giữ
- **AND** operator phải dừng write, tạo delta report và đi qua owner-approved remediation

#### Scenario: Directory fsync lỗi sau atomic replace

- **WHEN** atomic replace đã thành công nhưng directory fsync thất bại
- **THEN** command báo rõ runtime đã bị thay và durability chưa chắc chắn
- **AND** operator phải re-verify trạng thái trước mọi retry

### Requirement: Chạy lại không ghi đè dữ liệu

Migration schema, export/import và restart SHALL có hành vi chạy lại được xác định. Import bình thường MUST tạo staging mới và từ chối ghi đè file runtime hoặc backup đã tồn tại; một lần chạy hỏng MUST không làm file runtime trước đó mất hiệu lực. App restart MUST mở file đã publish và không tự seed/import/làm trống history. (Truy vết: quyết định chủ sở hữu 2026-10-07 về repeat startup/restart và bảo toàn dữ liệu)

#### Scenario: Chạy import lần hai

- **WHEN** runtime SQLite đã tồn tại và operator chạy import lại mà không chọn đích staging mới
- **THEN** công cụ từ chối trước khi ghi và không thay đổi runtime/source/backup

#### Scenario: Restart backend

- **WHEN** backend container/process được restart sau khi có row history
- **THEN** các row và cursor hợp lệ trước restart vẫn đọc được với cùng thứ tự và giá trị

### Requirement: Backup SQLite nhất quán

Backup SQLite đang live SHALL dùng snapshot nhất quán qua SQLite Online Backup API hoặc `VACUUM INTO`, không dùng raw file copy khi còn connection ghi. Backup SHALL được integrity-check trước khi được công nhận. (Truy vết: quyết định chủ sở hữu 2026-10-07 về backup; SQLite Online Backup documentation)

#### Scenario: Backup khi app đang chạy

- **WHEN** operator tạo backup trong lúc SQLite runtime có thể có writer
- **THEN** backup dùng cơ chế snapshot SQLite được hỗ trợ và vượt integrity check
- **AND** không dùng `cp` trực tiếp file database đang live

### Requirement: Restore được diễn tập trước rollout

Mỗi backup candidate SHALL được restore vào file tách biệt, kiểm tra integrity/revision/schema và đọc smoke trước rollout. Restore MUST không ghi đè runtime đang dùng trước khi mọi check đạt và app đã dừng. (Truy vết: quyết định chủ sở hữu 2026-10-07 về backup/restore)

#### Scenario: Restore backup hợp lệ

- **WHEN** operator diễn tập restore một backup candidate vào file tách biệt
- **THEN** file restore vượt integrity/revision/schema/read checks
- **AND** runtime hiện tại không bị thay đổi trong lúc diễn tập

#### Scenario: Restore backup lỗi

- **WHEN** backup candidate hỏng hoặc sai revision
- **THEN** restore dừng trước publish và runtime hiện tại vẫn nguyên vẹn

### Requirement: Rollback không âm thầm mất row hoặc identity high-water

Rollback trước write SQLite mới SHALL không sửa nguồn PostgreSQL. Sau write mới, quy trình SHALL dừng ghi và đối soát row cùng `sqlite_sequence`, không tự merge. Mọi delta chỉ được xử lý theo remediation do chủ sở hữu phê duyệt; nếu không bảo toàn được hai phía thì rollback MUST dừng. (Truy vết: quyết định chủ sở hữu 2026-10-07 về rollback và không mất dữ liệu)

#### Scenario: Rollback trước write mới

- **WHEN** cutover bị hủy trước khi SQLite có row mới
- **THEN** operator có thể khởi động lại phiên bản cũ với PostgreSQL giữ nguyên

#### Scenario: Rollback sau write mới

- **WHEN** SQLite đã có row không tồn tại trong snapshot PostgreSQL và operator yêu cầu rollback
- **THEN** không được âm thầm bỏ các row đó hoặc tự ghi ngược vào PostgreSQL
- **AND** rollout dừng ở bước đối soát/xin phê duyệt cho phương án hợp nhất đã xác định

#### Scenario: Row mới đã bị retention xóa

- **WHEN** hai snapshot có cùng row nhưng `sqlite_sequence` phía sau cutover cao hơn
- **THEN** delta report vẫn đánh dấu có thay đổi và rollback/replacement tự động bị chặn

### Requirement: Retirement PostgreSQL chỉ diễn ra sau evidence gate

Operational procedure SHALL chỉ retire exact PostgreSQL target được chứng minh thuộc riêng `cipher_workbench-be`, sau khi transfer/SQLite/backup gates đạt. Procedure MUST giữ recovery backup và MUST NOT xóa host-wide, shared hoặc unrelated resource. (Truy vết: quyết định chủ sở hữu 2026-10-07 cho phép retirement sau chuyển dữ liệu thành công)

#### Scenario: Đủ điều kiện retirement project-scoped

- **WHEN** exact project database/container/volume đã được resolve, mọi reconciliation/smoke gate đạt và backup ngoài volume đã restore-test
- **THEN** operator có thể retire từng target dự án đã preview bằng operational authorization riêng
- **AND** recovery backup và evidence package vẫn được giữ
- **AND** reconciliation bao gồm count, ID, identity high-water, UTC và canonical digest; smoke bao gồm SQLite health, history và cipher

#### Scenario: Target hoặc bằng chứng chưa rõ

- **WHEN** ownership target còn mơ hồ, target có thể shared/host-wide, backup nằm trong volume sắp xóa hoặc bất kỳ gate nào chưa đạt
- **THEN** retirement dừng trước thao tác phá hủy và yêu cầu owner/operator làm rõ
- **AND** procedure không dùng glob, blanket `docker compose down -v`, host package removal hoặc xóa user artifact

#### Scenario: Rollback sau retirement

- **WHEN** PostgreSQL project runtime đã được retire và cần rollback
- **THEN** runbook dùng recovery backup đã restore-test hoặc fix-forward
- **AND** không giả định database/container/volume cũ vẫn còn live
