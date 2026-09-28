"""Static and rendered guards for the same-origin web UI covering all five ciphers."""

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app import config
from app.errors import messages
from app.main import app

ROOT = Path(__file__).parents[2]
SCRIPT = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
TEMPLATE = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")
CIPHERS = ("caesar", "vigenere", "playfair", "affine", "columnar")


def _section(start: str, end: str) -> str:
    return SCRIPT.split(start, 1)[1].split(end, 1)[0]


def test_root_renders_ui_with_server_injected_limit_and_messages() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert f'data-max-bytes="{config.MAX_FILE_BYTES}"' in response.text
    assert 'lang="vi"' in response.text
    assert "/static/styles.css" in response.text
    assert "/static/app.js" in response.text

    embedded = re.search(
        r'<script type="application/json" id="cipherMessages">(.*?)</script>', response.text
    )
    assert embedded is not None
    cipher_messages = json.loads(embedded.group(1))
    assert cipher_messages["vigenereKey"] == messages.INVALID_VIGENERE_KEY
    assert cipher_messages["affineNonInvertible"] == messages.NON_INVERTIBLE_AFFINE_MULTIPLIER
    assert cipher_messages["columnarKey"] == messages.INVALID_COLUMNAR_KEY
    assert cipher_messages["playfairText"] == messages.PLAYFAIR_TEXT_EMPTY


def test_static_assets_are_served_by_the_application() -> None:
    with TestClient(app) as client:
        script = client.get("/static/app.js")
        styles = client.get("/static/styles.css")

    assert script.status_code == 200
    assert script.headers["content-type"].startswith("text/javascript")
    assert styles.status_code == 200
    assert styles.headers["content-type"].startswith("text/css")


def test_every_cipher_has_a_selector_and_configuration() -> None:
    for cipher in CIPHERS:
        assert f'data-cipher="{cipher}"' in TEMPLATE
        assert f"\n  {cipher}: {{" in SCRIPT
    for label in ("Caesar", "Vigenère", "Playfair", "Affine", "Columnar"):
        assert f">{label}</button>" in TEMPLATE


def test_script_has_no_mock_cross_origin_or_embedded_business_limit() -> None:
    forbidden = (
        "mockApi",
        "USE_MOCK",
        "API_BASE",
        "localhost:8080",
        "_encrypted",
        str(config.MAX_FILE_BYTES),
        "1024 * 1024;",
        "1 MB",
    )
    assert all(token not in SCRIPT for token in forbidden)
    assert "document.body.dataset.maxBytes" in SCRIPT
    assert "fetchWithTimeout(`/api/${cipher}/${operation}`" in SCRIPT
    assert "fetchWithTimeout(`/api/${cipher}/file`" in SCRIPT
    assert 'fetchWithTimeout("/api/health"' in SCRIPT
    assert "fetchWithTimeout(`/api/history?${query}`" in SCRIPT


def test_integer_keys_are_sent_as_json_integer_tokens() -> None:
    caesar = _section("\n  caesar: {", "\n  vigenere: {")
    affine = _section("\n  affine: {", "\n  columnar: {")
    assert '"key":${BigInt(key.trim()).toString()}' in caesar
    assert '"a":${BigInt(a.trim()).toString()}' in affine
    assert '"b":${BigInt(b.trim()).toString()}' in affine
    assert 'fields: ["a", "b"]' in affine
    for cipher, following in (
        ("vigenere", "playfair"),
        ("playfair", "affine"),
        ("columnar", "\n};\n"),
    ):
        block = _section(f"\n  {cipher}: {{", following)
        assert "JSON.stringify({ text, key })" in block


def test_client_checks_mirror_the_key_contract() -> None:
    assert "^[+-]?[0-9]+$" in SCRIPT
    assert "MAX_MULTIPART_INTEGER_CHARS = 32" in SCRIPT
    assert "/^[A-Za-z]+$/.test(key)" in SCRIPT
    assert "/[A-Za-z]/.test(key)" in SCRIPT
    assert "gcd(normalizedA, 26) !== 1" in SCRIPT
    assert "/^[A-Za-z]{2,256}$/" in SCRIPT
    assert "tokens.length < 2 || tokens.length > 256" in SCRIPT
    assert "COLUMNAR_TRIM = /^[ \\t\\r\\n\\f\\v]+|[ \\t\\r\\n\\f\\v]+$/g" in SCRIPT


def test_no_client_side_cipher_results() -> None:
    assert "function shiftAlphabet" in SCRIPT
    assert "Display-only mapping for the alphabet table" in SCRIPT
    assert "String.fromCharCode" not in SCRIPT
    assert ".encrypt(" not in SCRIPT
    assert ".decrypt(" not in SCRIPT
    shift_table = _section("function renderShiftTable", "function formatSize")
    assert 'elements.shiftSection.hidden = state.cipher !== "caesar"' in shift_table
    assert "/^[A-Za-z]$/.test(letter)" in shift_table


def test_playfair_warning_is_the_contract_text() -> None:
    assert (
        "Playfair chuẩn hóa thành chữ hoa ASCII, gộp J/I, loại định dạng; khi giải mã giữ "
        "filler X/Q giữa chuỗi và bỏ filler cuối; kết quả không khôi phục nguyên văn đầu vào."
    ) in TEMPLATE
    assert 'elements.playfairWarning.hidden = state.cipher !== "playfair"' in SCRIPT


def test_file_flow_requests_both_preview_and_download_modes() -> None:
    file_api = _section("async file(cipher, operation, file, keys, responseMode)", "};\n")
    assert "for (const field of CIPHERS[cipher].fields) data.append(field, keys[field]);" in (
        file_api
    )
    assert 'data.append("action", operation);' in file_api
    assert 'data.append("response_mode", responseMode);' in file_api
    assert 'state.file, keys, "content"' in SCRIPT
    assert 'state.file, currentKeys(), "file"' in SCRIPT
    assert "response.blob()" in SCRIPT
    assert "content-disposition" in SCRIPT


def test_ui_keeps_required_controls_and_vietnamese_labels() -> None:
    for label in (
        "Sao chép",
        "Xóa",
        "Đổi file",
        "Gỡ file",
        "Tải kết quả",
        "Tạo ví dụ",
        "Làm mới",
        "Phân tích",
        "Mã hóa",
        "Giải mã",
        "Trên máy này",
        "Máy chủ",
        "Xóa lịch sử trên máy này",
        "Lưu lịch sử trên máy này",
        "Tải thêm",
    ):
        assert label in TEMPLATE
    assert "5 MiB = 5.242.880 byte" in TEMPLATE


def test_ui_has_no_out_of_scope_navigation_or_mock_notes() -> None:
    forbidden = ("CAESAR.IO", "Share feedback", "Report issue", "backend giả lập")
    combined = f"{TEMPLATE}\n{SCRIPT}"
    assert all(token not in combined for token in forbidden)
    assert "<nav" not in TEMPLATE
    assert "<footer" not in TEMPLATE


def test_ui_locks_every_control_while_loading() -> None:
    assert "if (text.length === 0)" in SCRIPT
    assert "ket-qua.encrypted.txt" in SCRIPT
    assert "ket-qua.decrypted.txt" in SCRIPT
    assert 'querySelectorAll("[data-lockable]")' in SCRIPT
    assert "control.disabled = state.loading" in SCRIPT
    assert "elements.dropZone.tabIndex = state.loading ? -1 : 0" in SCRIPT
    assert (
        'elements.dropZone.addEventListener("click", (event) => {\n  if (state.loading) return;'
    ) in SCRIPT
    assert (
        'elements.dropZone.addEventListener("keydown", (event) => {\n'
        '  if (event.key === "Enter" || event.key === " ") {\n'
        "    event.preventDefault();\n"
        "    if (state.loading) return;"
    ) in SCRIPT
    for cipher in CIPHERS:
        tab = re.search(rf'<button [^>]*data-cipher="{cipher}"[^>]*>', TEMPLATE)
        assert tab is not None
        assert "data-lockable" in tab.group(0)


def test_real_api_distinguishes_server_errors_from_network_failures() -> None:
    assert 'response.headers.get("content-type")' in SCRIPT
    assert "response.ok" in SCRIPT
    assert "error.isApiError" in SCRIPT
    assert "Lỗi kết nối" in SCRIPT
    assert "catch {}" not in SCRIPT


def test_ui_resets_result_tab_times_out_requests_and_ignores_stale_file_reads() -> None:
    clear_result = _section("function clearResult", "function renderOutputView")
    output_view = _section("function renderOutputView", "function renderCipherChrome")
    render = _section("function render()", "function selectCipher")
    assert 'state.view = "result"' in clear_result
    assert "renderOutputView();" in clear_result
    assert 'elements.analysis.hidden = state.view !== "analysis"' in output_view
    assert 'tab.setAttribute("aria-selected"' in output_view
    assert "renderOutputView();" in render
    assert "new AbortController()" in SCRIPT
    assert "controller.abort()" in SCRIPT
    assert "window.clearTimeout(timeout)" in SCRIPT
    assert "fileReadVersion !== state.fileReadVersion || state.file !== file" in SCRIPT


def test_changing_cipher_clears_result_and_keeps_key_drafts() -> None:
    select_cipher = _section("function selectCipher", "function selectMode")
    assert "syncKeyControls();" in select_cipher
    assert "clearResult();" in select_cipher
    assert "keys: emptyKeys()," in SCRIPT
    assert "currentKeys()[field] = value;" in SCRIPT


def test_ui_preserves_exact_result_and_clears_stale_download_success() -> None:
    colorize = _section("function colorize", "function setStatus")
    download = _section("async function downloadResult", "// ---- History on this device")
    assert "return result;" in colorize
    assert "clearResult({ keepNotice: true });" in download
    assert 'setStatus(elements.outputStatus, "Tải kết quả thất bại", "error")' in download


def test_file_download_names_come_only_from_content_disposition() -> None:
    filename_parser = _section("function filenameFromDisposition", "function saveBlob")
    download = _section("async function downloadResult", "// ---- History on this device")
    assert "return quotedMatch" in filename_parser
    assert ": null;" in filename_parser
    assert "textResultFilename()" in download
    assert "filenameFromDisposition(response.disposition)" in download


def test_local_history_follows_the_browser_history_contract() -> None:
    assert "LOCAL_HISTORY_LIMIT = 50" in SCRIPT
    local = _section("// ---- History on this device", "// ---- Server history")
    assert ".slice(0, LOCAL_HISTORY_LIMIT)" in local
    assert "result: fromFile ? null : result" in local
    assert "input: fromFile ? state.file.name : elements.textInput.value" in local
    # Every storage access is guarded so a blocked storage never breaks the cipher flow.
    storage_functions = [chunk for chunk in local.split("\nfunction ") if "localStorage." in chunk]
    assert len(storage_functions) == 3
    assert all("try {" in chunk for chunk in storage_functions)
    toggle = SCRIPT.split('elements.localHistoryEnabled.addEventListener("change"', 1)[1]
    assert toggle.index("try {") < toggle.index("localStorage.setItem")
    assert "fetch" not in local


def test_server_history_is_gated_by_health() -> None:
    detect = _section("async function detectServerHistory", "function resetAll")
    assert 'body?.result?.history === "enabled"' in detect
    assert 'body?.result?.database === "ok"' in detect
    assert "elements.historyTabServer.hidden = !state.server.available" in detect
    assert 'data-history-tab="server" hidden' in TEMPLATE
    server = _section("// ---- Server history", "async function detectServerHistory")
    assert 'query.set("cursor", state.server.cursor)' in server
    assert "body.result.nextCursor" in server
