# Proposal

## Why

Mô hình triển khai đã chốt chỉ có một máy backend phát hành HTTP API và một máy frontend, nên PostgreSQL tạo thêm dịch vụ vận hành không cần thiết cho tải lịch sử metadata hiện tại. Chủ sở hữu ngày 2026-10-07 đã chọn SQLite lưu cục bộ trên máy backend, đồng thời yêu cầu giữ nguyên hành vi công khai và toàn bộ dữ liệu PostgreSQL cũ.

## What Changes

- **BREAKING (hạ tầng nội bộ):** backend lịch sử chuyển từ PostgreSQL/asyncpg sang một file SQLite/aiosqlite trên filesystem cục bộ, bền vững của máy backend; URL PostgreSQL không còn là storage runtime được hỗ trợ sau cutover.
- Giữ nguyên toàn bộ HTTP contract của cipher, `GET /api/history`, `GET /api/health`, cờ `HISTORY_API_ENABLED`, retention, cursor, filter, phân trang, thứ tự `(created_at DESC, id DESC)`, status/message và UTC output.
- Giữ nguyên ranh giới metadata-only và semantics RSA đang có hiệu lực theo Q1–Q16/R1–R2: chỉ hai route transform được ghi best-effort, keygen bị loại, không lưu content/key/trace/filename/`originalUtf8ByteLength` hay dữ liệu định danh.
- Tạo schema/migration SQLite riêng thay vì chạy chuỗi migration PostgreSQL `0001`–`0004` như một chuỗi đa dialect; chuỗi PostgreSQL cũ được giữ nguyên để đọc nguồn, đối soát và rollback.
- Thêm quy trình chuyển dữ liệu một lần PostgreSQL → SQLite: dừng ghi ngắn, snapshot/backup nguồn, import giữ nguyên ID và timestamp, kiểm tra schema/count/range/digest, chỉ publish file đích sau khi đối soát đạt. Sau khi backup ngoài volume đã restore-test, SQLite post-cutover đã qua health/history smoke và mọi đối soát đạt, owner cho phép retire đúng PostgreSQL database/container/volume chỉ thuộc dự án; recovery backup tiếp tục được giữ.
- Lưu file SQLite và backup trên đường dẫn/volume cục bộ có quyền tối thiểu; migration chạy trước app, restart không tạo lại hay ghi đè file đã có.
- Dùng rollback journal mặc định. Không bật WAL trong change này vì runtime kiểm tra hiện tại liên kết SQLite 3.45.1, thuộc dải có lỗi WAL-reset đã được SQLite công bố; mọi đề xuất WAL sau này phải kiểm tra thư viện runtime đã có bản vá và có test cạnh tranh/checkpoint.
- Cập nhật test và tài liệu vận hành cho SQLite, import/reconciliation, backup/restore, permission/disk-full/lock contention, restart và rollback; không nâng cấp dependency hàng loạt.

## Capabilities

### New Capabilities

- `history-data-continuity`: chuyển toàn bộ lịch sử PostgreSQL sang SQLite có đối soát, backup/restore và rollback, rồi retire nguồn PostgreSQL dự án theo gate có bằng chứng mà không xóa recovery backup.

### Modified Capabilities

- `database-infrastructure`: thay kết nối, migration và docker-compose PostgreSQL bằng SQLite cục bộ bền vững trên backend trong khi giữ nguyên trạng thái health/disabled/unavailable.
- `operation-history`: thay biểu diễn schema PostgreSQL bằng schema SQLite tương đương, vẫn giữ nguyên 11 field metadata, tính riêng tư, best-effort, ID/thời gian/thứ tự và authority RSA đang hoạt động.

## Impact

- Code dự kiến chịu tác động: `app/config.py`, `app/db/`, `app/history/`, Alembic environment/version tree mới cho SQLite và công cụ chuyển/đối soát dữ liệu; cipher core và public route shape không đổi.
- Dependency: thêm driver async SQLite phù hợp SQLAlchemy 2.1.1; giữ `asyncpg` có chủ đích trong giai đoạn chuyển đổi/diễn tập. Việc gỡ driver chỉ được thực hiện sau khi transfer tooling không còn cần kết nối nguồn và không kéo theo nâng cấp package hàng loạt.
- Runtime/Docker: bỏ PostgreSQL khỏi đường chạy mặc định, mount một thư mục dữ liệu cục bộ ghi được cho backend/migrate, giữ volume PostgreSQL cũ ngoài thao tác xóa và giữ FE chỉ gọi HTTP API.
- Test/docs dự kiến chịu tác động: DB integration, migration, history ordering/cursor/UTC, contention/failure, restart/persistence, data-transfer reconciliation, backup/restore, README, `.env.example`, Docker và hướng dẫn FE/deploy.

## Ngoài phạm vi

- Không chuyển SQL/file SQLite sang máy frontend, browser, network filesystem hay shared volume giữa nhiều máy; frontend không được truy cập DB trực tiếp.
- Không thay đổi endpoint, payload, status, message, thuật toán cipher, RSA contract, metadata privacy, retention window, history access policy hay CORS allowlist.
- Không thêm auth, user/session, lịch sử theo user, analytics, sync đa backend, replication, HA, cloud deployment, CI/CD hay hỗ trợ nhiều writer process.
- Không xóa hoặc sửa tại chỗ PostgreSQL trước khi hoàn thành transfer/cutover gates. Quyền retire sau thành công chỉ áp dụng cho target được xác minh là của riêng `cipher_workbench-be`; không bao gồm PostgreSQL cài host-wide, database/service dùng chung, container/volume không liên quan, migration backup hay recovery backup. Không chạy cutover/deploy/data migration/retirement trong implementation turn khi chưa có operational authorization và target inventory cụ thể.
- Không giải quyết lại khác biệt nghiệp vụ giữa DOCX và HTML demo: DOCX vẫn ưu tiên cho giới hạn/error/file behavior; quyết định chủ sở hữu 2026-10-07 chỉ là ngoại lệ hạ tầng cho storage lịch sử metadata.

## Giải quyết khác biệt giữa nguồn

- DOCX §8 cấm lưu nội dung người dùng và HTML demo không có thẩm quyền về database. Change này chỉ thay engine lưu metadata đã được phê duyệt, không mở rộng dữ liệu được phép lưu; ràng buộc DOCX và các quyết định RSA Q1–Q16/R1–R2 tiếp tục ưu tiên.
- `openspec/config.yaml` và main specs còn mô tả PostgreSQL; quyết định chủ sở hữu 2026-10-07 supersede riêng lựa chọn engine/deployment đó, không supersede contract history hoặc các delta RSA chưa sync.
