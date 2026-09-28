## Why

Chủ sở hữu quyết định (2026-09-28): UI do team FE làm ở project riêng, repo này chỉ lo BE. Hiện app vẫn tự phục vụ một UI static (`/`, `/static/*`, template Jinja2) và spec `app-runtime` bắt buộc điều đó, nên hai bên cùng giữ một UI và dễ lệch nhau.

## What Changes

- Gỡ trang `/`, mount `/static`, thư mục `app/templates/`, `app/static/` và dependency `jinja2`.
- `/` không còn là route: trả 404 JSON như mọi đường dẫn không tồn tại khác.
- Giữ nguyên `/docs`, `/openapi.json` và 17 endpoint `/api/*`.
- Không bật CORS: FE gọi API qua proxy `/api` (dev server hoặc reverse proxy), như tài liệu FE đã hướng dẫn.
- Cập nhật README, `openspec/config.yaml`, test runtime; xóa `tests/integration/test_ui_assets.py`.

## Capabilities

### Modified Capabilities

- `app-runtime`: bỏ yêu cầu phục vụ giao diện web và tài nguyên tĩnh; `/docs` thay `/` làm điểm kiểm tra runtime ở local và container.

## Impact

- Code: `app/main.py`, xóa `app/templates/`, `app/static/`.
- Dependency: bỏ `jinja2` khỏi `pyproject.toml`/`uv.lock`.
- Test: `tests/integration/test_app_runtime.py`, `tests/unit/test_layering.py`, xóa `tests/integration/test_ui_assets.py`.
- Tài liệu: README, `openspec/config.yaml`.
- Contract của 15 route cipher, health và history không đổi.

## Ngoài phạm vi

- Bật CORS cho FE khác origin.
- Viết lại `repo_docs/frontend-integration.md`: phần UI trong đó vẫn là hướng dẫn cho FE.
- Sửa requirement stateless cũ của `app-runtime` cho khớp lịch sử PostgreSQL.
