## 1. Code

- [x] 1.1 Gỡ route `/`, mount `/static`, `Jinja2Templates` khỏi `app/main.py`; xóa `app/templates/`, `app/static/`. **Xong khi:** `GET /` và `GET /static/app.js` trả 404, `/docs` vẫn 200.
- [x] 1.2 Bỏ `jinja2` khỏi `pyproject.toml` và cập nhật `uv.lock`. **Xong khi:** `uv sync --frozen` thành công.

## 2. Test

- [x] 2.1 Xóa `tests/integration/test_ui_assets.py`; sửa `test_app_runtime.py` và `test_layering.py` theo runtime mới. **Xong khi:** có test xác nhận `/` và `/static/*` trả 404.

## 3. Tài liệu

- [x] 3.1 Cập nhật README và `openspec/config.yaml` để không còn mô tả UI đi kèm. **Xong khi:** không còn hướng dẫn mở UI ở `/`.

## 4. Kiểm tra

- [x] 4.1 `ruff check`, `ruff format --check`, `pytest` có `TEST_DATABASE_URL`. **Xong khi:** exit 0, coverage ≥ 90%.
