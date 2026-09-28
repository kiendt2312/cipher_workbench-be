## Why

UI tĩnh phục vụ tại `/` vẫn là UI Caesar-only của Tuần 1, trong khi backend đã có 5 cipher (15 route), health và lịch sử. Người dùng mở app chỉ thấy một tính năng. Chủ sở hữu yêu cầu (2026-09-28) cập nhật UI theo contract FE hiện hành: đủ 5 cipher, lịch sử cá nhân trên trình duyệt và lịch sử server.

## What Changes

- Thêm bộ chọn cipher (Caesar, Vigenère, Playfair, Affine, Columnar); tiêu đề, gợi ý, ô khóa, ví dụ và phân tích đổi theo cipher.
- Ô khóa theo từng cipher: Caesar số nguyên, Vigenère/Playfair/Columnar chuỗi, Affine hai ô `a`/`b`. Mỗi cipher giữ bản nháp khóa riêng khi đổi qua lại.
- Kiểm tra sơ bộ phía client theo contract (chỉ để bật/tắt nút, server vẫn là authority), gửi request đúng wire format: Caesar/Affine là JSON integer token, chuỗi khóa gửi nguyên văn, multipart đúng field set.
- Bảng dịch chuyển chỉ hiện với Caesar; cảnh báo Playfair lossy luôn hiện khi chọn Playfair.
- Khu vực lịch sử: tab "Trên máy này" (`localStorage`, tối đa 50 mục, xóa, tắt lưu, dùng lại) và tab "Máy chủ" (chỉ hiện khi `/api/health` báo `history: "enabled"` và `database: "ok"`; lọc, tải thêm).
- Cập nhật test UI, README và tài liệu FE bỏ ghi chú "UI Caesar-only".

## Capabilities

### New Capabilities

- `web-ui-all-ciphers`: Hành vi UI cho 5 cipher và hai loại lịch sử.

### Modified Capabilities

- `web-ui` (change `caesar-cipher-week1-mvp`): mọi requirement giữ nguyên, được mở rộng từ "Caesar" sang cipher đang chọn. Tiêu đề trang không còn cố định "Caesar Cipher".

## Impact

- `app/templates/index.html`, `app/static/app.js`, `app/static/styles.css`, `app/main.py` (truyền thêm message cho UI).
- `tests/integration/test_ui_assets.py` viết lại theo cấu trúc mới.
- README, `repo_docs/frontend-integration.md`.
- Không đổi API.

## Ngoài phạm vi

- Visualization riêng cho Vigenère/Playfair/Affine/Columnar (ma trận, bảng hoán vị).
- Tách FE thành project riêng, framework, build step.
- Đa ngôn ngữ, dark mode.

## Giải quyết khác biệt giữa nguồn

- Spec `web-ui` Tuần 1 gắn với Caesar (tiêu đề, prefix `/api/caesar/`). Change này giữ mọi invariant của spec đó cho Caesar và áp cùng invariant cho 4 cipher còn lại theo `repo_docs/frontend-integration.md` §11.
