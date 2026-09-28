# web-ui-all-ciphers Specification

## Purpose

Hành vi quan sát được của UI tĩnh tại `/` khi hỗ trợ đủ 5 cipher và hai loại lịch sử.

## Requirements

### Requirement: Chọn cipher

UI SHALL có bộ chọn gồm Caesar, Vigenère, Playfair, Affine, Columnar; mặc định Caesar. Đổi cipher SHALL xóa kết quả, phân tích và thông báo, đổi tiêu đề, gợi ý, nhãn và ô khóa, và giữ nguyên input cùng bản nháp khóa riêng của từng cipher. (Truy vết: `repo_docs/frontend-integration.md` §11; quyết định chủ sở hữu 2026-09-28)

#### Scenario: Đổi cipher giữ bản nháp
- **WHEN** người dùng nhập key `LEMON` ở Vigenère, chuyển sang Caesar rồi quay lại Vigenère
- **THEN** ô khóa Vigenère vẫn là `LEMON` và kết quả cũ đã bị xóa

### Requirement: Request đúng contract cho mọi cipher

UI SHALL gọi `/api/{cipher}/{encrypt|decrypt}` với JSON và `/api/{cipher}/file` với multipart bằng đường dẫn tương đối. Caesar gửi `key`, Affine gửi `a`, `b` dưới dạng JSON integer token; Vigenère, Playfair, Columnar gửi `key` là chuỗi nguyên văn người dùng nhập. Multipart gửi `file`, `key` (hoặc `a`, `b` với Affine), `action`, `response_mode`, mỗi field đúng một lần. UI MUST NOT tự tính kết quả cipher. (Truy vết: `repo_docs/frontend-integration.md` §5, §7.1, §8.1, §10)

#### Scenario: Affine text
- **WHEN** người dùng mã hóa `HELLO` với Affine `a=5`, `b=8`
- **THEN** UI gửi `POST /api/affine/encrypt` với body `{"text":"HELLO","a":5,"b":8}` và hiển thị `RCLLA`

### Requirement: Kiểm tra sơ bộ khóa

Nút hành động SHALL chỉ bật khi input và khóa qua kiểm tra sơ bộ của cipher đang chọn: Caesar và Affine là số nguyên có dấu (tối đa 32 ký tự với file), Affine thêm `a` nguyên tố cùng nhau với 26; Vigenère chỉ chữ A-Z/a-z; Playfair có ít nhất một chữ cái; Columnar là hoán vị `1..m` hoặc từ khóa 2 đến 256 chữ cái. Thông báo lỗi dùng message canonical của server. (Truy vết: `repo_docs/frontend-integration.md` §4, §10)

#### Scenario: Affine a không khả nghịch
- **WHEN** người dùng nhập `a=2`, `b=3`
- **THEN** nút hành động bị tắt và trạng thái khóa báo "Khóa a phải nguyên tố cùng nhau với 26."

### Requirement: Visualization và cảnh báo theo cipher

Bảng dịch chuyển SHALL chỉ hiện với Caesar. Khi chọn Playfair, UI SHALL luôn hiện cảnh báo lossy của §11 tài liệu FE. Nút "Tạo ví dụ" SHALL điền ví dụ canonical của cipher đang chọn. (Truy vết: `repo_docs/frontend-integration.md` §11)

#### Scenario: Ví dụ Playfair
- **WHEN** người dùng chọn Playfair và bấm "Tạo ví dụ"
- **THEN** input là `HIDE THE GOLD IN THE TREE STUMP`, khóa là `PLAYFAIR EXAMPLE` và cảnh báo Playfair đang hiện

### Requirement: Lịch sử trên máy này

UI SHALL lưu mỗi thao tác thành công vào `localStorage` theo `repo_docs/frontend-integration.md` §17: tối đa 50 mục, mới nhất trước, file chỉ lưu tên. UI SHALL có nút xóa, công tắc tắt lưu, cảnh báo lịch sử chứa khóa, và nút dùng lại mục văn bản. Storage bị chặn MUST NOT làm hỏng luồng cipher. (Truy vết: change `add-history-access-retention`, spec `client-side-history`)

#### Scenario: Dùng lại
- **WHEN** người dùng bấm "Dùng lại" ở một mục Vigenère
- **THEN** UI chọn Vigenère, đúng chế độ, điền input và khóa của mục đó

### Requirement: Lịch sử máy chủ

Tab "Máy chủ" SHALL chỉ hiện khi `GET /api/health` trả `history` là `enabled` và `database` là `ok`. Tab SHALL hiện metadata từ `GET /api/history`, lọc theo cipher/operation, và nút "Tải thêm" dùng `nextCursor`. Lỗi 404/422/503 SHALL hiện message server. (Truy vết: `repo_docs/frontend-integration.md` §16)

#### Scenario: Server tắt lịch sử
- **WHEN** health trả `history: "disabled"`
- **THEN** UI không hiện tab "Máy chủ"
