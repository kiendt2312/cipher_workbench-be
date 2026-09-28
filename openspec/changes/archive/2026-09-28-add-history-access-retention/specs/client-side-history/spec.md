## Purpose

Định nghĩa hướng dẫn FE lưu lịch sử cá nhân của người dùng trên trình duyệt, thay cho lịch sử theo user trên server.

## ADDED Requirements

### Requirement: Lịch sử cá nhân nằm trên trình duyệt

Tài liệu FE SHALL hướng dẫn lưu lịch sử cá nhân trong `localStorage` của trình duyệt, với tối đa 50 mục, mới nhất trước, bỏ mục cũ nhất khi vượt giới hạn. Mỗi mục SHALL gồm thời điểm, cipher, operation, input, key và kết quả của request thành công; MUST NOT lưu nội dung file tải lên. Dữ liệu này MUST NOT được gửi lên server. (Truy vết: quyết định chủ sở hữu 2026-09-28)

#### Scenario: Vượt giới hạn
- **WHEN** người dùng thực hiện thao tác thứ 51
- **THEN** mục cũ nhất bị bỏ và danh sách còn 50 mục

### Requirement: Quyền kiểm soát của người dùng

Tài liệu FE SHALL yêu cầu UI có nút "Xóa lịch sử trên máy này", cho phép tắt việc lưu lịch sử, và nói rõ lịch sử chứa cả key nên chỉ nên bật trên máy cá nhân. Mọi lệnh đọc/ghi `localStorage` SHALL bọc `try/catch` để UI vẫn chạy khi trình duyệt chặn storage. (Truy vết: quyết định chủ sở hữu 2026-09-28)

#### Scenario: Storage bị chặn
- **WHEN** trình duyệt ở chế độ chặn storage
- **THEN** encrypt/decrypt vẫn hoạt động và UI không báo lỗi hệ thống
