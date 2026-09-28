## Context

App phục vụ UI static từ Week 1 theo spec `app-runtime`. UI giờ thuộc team FE.

## Decisions

### 1. `/` trả 404, không redirect

Không giữ route `/`. Request tới `/` đi vào 404 JSON sẵn có, giống mọi đường dẫn lạ. Phương án không chọn: redirect `/` sang `/docs` (thêm một route chỉ để tiện, và dễ bị hiểu là trang chính thức).

### 2. Không bật CORS

FE gọi API bằng đường dẫn tương đối `/api/...` và đặt proxy ở dev server hoặc reverse proxy khi deploy, như `repo_docs/frontend-integration.md` đã hướng dẫn. Bật CORS là quyết định riêng khi có origin FE cụ thể.
