"use strict";

const byId = (id) => document.getElementById(id);
const ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
const MAX_FILE_BYTES = Number(document.body.dataset.maxBytes);
const REQUEST_TIMEOUT_MS = 15000;
const SIGNED_INTEGER_PATTERN = /^[+-]?[0-9]+$/;
const MAX_MULTIPART_INTEGER_CHARS = 32;
const MESSAGES = {
  fileType: document.body.dataset.messageFileType,
  fileSize: document.body.dataset.messageFileSize,
  fileEmpty: document.body.dataset.messageFileEmpty,
  keyMissing: document.body.dataset.messageKeyMissing,
  keyInvalid: document.body.dataset.messageKeyInvalid,
  system: document.body.dataset.messageSystem,
  ...JSON.parse(byId("cipherMessages").textContent),
};

const LOCAL_HISTORY_KEY = "cipher-workbench.history.v1";
const LOCAL_HISTORY_ENABLED_KEY = "cipher-workbench.history.enabled";
const LOCAL_HISTORY_LIMIT = 50;
const SERVER_HISTORY_PAGE_SIZE = 20;

// Client-side checks only enable the action button; the server stays authoritative.
function parseSignedInteger(raw, { forFile }) {
  const trimmed = raw.trim();
  if (trimmed === "") return { missing: true };
  if ((forFile && trimmed.length > MAX_MULTIPART_INTEGER_CHARS) || !SIGNED_INTEGER_PATTERN.test(trimmed)) {
    return { invalid: true };
  }
  return { value: BigInt(trimmed) };
}

const modulo26 = (value) => Number(((value % 26n) + 26n) % 26n);
const gcd = (left, right) => (right === 0 ? left : gcd(right, left % right));

// Columnar trims only the six ASCII whitespace characters, never Unicode spaces.
const COLUMNAR_TRIM = /^[ \t\r\n\f\v]+|[ \t\r\n\f\v]+$/g;

function isColumnarPermutation(key) {
  let body = key;
  if (body.startsWith("{") && body.endsWith("}")) body = body.slice(1, -1).replace(COLUMNAR_TRIM, "");
  const tokens = body.split(/[ \t\r\n\f\v]*,[ \t\r\n\f\v]*|[ \t\r\n\f\v]+/);
  if (tokens.length < 2 || tokens.length > 256) return false;
  if (!tokens.every((token) => /^[1-9][0-9]*$/.test(token))) return false;
  const ranks = new Set(tokens.map(Number));
  return ranks.size === tokens.length && [...ranks].every((rank) => rank <= tokens.length);
}

const CIPHERS = {
  caesar: {
    name: "Caesar",
    subtitle: "Dịch mỗi chữ cái ASCII A–Z, a–z đi một số vị trí cố định; ký tự khác giữ nguyên.",
    keyPanelTitle: "Khóa dịch chuyển",
    keyDescription: "Nhập số nguyên có dấu. Khóa được chuẩn hóa về 0–25 trước khi xử lý.",
    keyNote: "Ví dụ: 29 → 3, −3 → 23, 26 → 0.",
    placeholder: "ví dụ: +3 hoặc -3",
    numeric: true,
    fields: ["key"],
    example: { text: "Hello World", keys: { key: "3" } },
    validateKey({ key }, forFile) {
      const parsed = parseSignedInteger(key, { forFile });
      if (parsed.missing) return { missing: true, message: MESSAGES.keyMissing };
      if (parsed.invalid) return { message: MESSAGES.caesarKey };
      const normalized = modulo26(parsed.value);
      return { valid: true, note: parsed.value === BigInt(normalized) ? "" : `Chuẩn hóa → ${normalized}` };
    },
    textBody: (text, { key }) => `{"text":${JSON.stringify(text)},"key":${BigInt(key.trim()).toString()}}`,
    describeKey: ({ key }) => key.trim(),
  },
  vigenere: {
    name: "Vigenère",
    subtitle: "Dịch từng chữ cái theo một từ khóa lặp lại; ký tự khác giữ nguyên và không làm tiến khóa.",
    keyPanelTitle: "Từ khóa",
    keyDescription: "Từ khóa chỉ gồm chữ cái A–Z hoặc a–z, không có khoảng trắng hay dấu.",
    keyNote: "Ví dụ: LEMON.",
    placeholder: "ví dụ: LEMON",
    fields: ["key"],
    example: { text: "Attack at dawn!", keys: { key: "LEMON" } },
    validateKey({ key }) {
      if (key === "") return { missing: true, message: MESSAGES.keyMissing };
      return /^[A-Za-z]+$/.test(key) ? { valid: true } : { message: MESSAGES.vigenereKey };
    },
    textBody: (text, { key }) => JSON.stringify({ text, key }),
    describeKey: ({ key }) => key,
  },
  playfair: {
    name: "Playfair",
    subtitle: "Mã hóa theo từng cặp chữ trên ma trận 5×5 dựng từ từ khóa; I và J dùng chung một ô.",
    keyPanelTitle: "Từ khóa ma trận",
    keyDescription: "Từ khóa cần ít nhất một chữ cái A–Z; khoảng trắng và ký tự khác bị bỏ qua khi dựng ma trận.",
    keyNote: "Ví dụ: PLAYFAIR EXAMPLE.",
    placeholder: "ví dụ: PLAYFAIR EXAMPLE",
    fields: ["key"],
    example: { text: "HIDE THE GOLD IN THE TREE STUMP", keys: { key: "PLAYFAIR EXAMPLE" } },
    validateText: (text) => (/[A-Za-z]/.test(text) ? null : MESSAGES.playfairText),
    validateKey({ key }) {
      if (key === "") return { missing: true, message: MESSAGES.keyMissing };
      return /[A-Za-z]/.test(key) ? { valid: true } : { message: MESSAGES.playfairKey };
    },
    textBody: (text, { key }) => JSON.stringify({ text, key }),
    describeKey: ({ key }) => key,
  },
  affine: {
    name: "Affine",
    subtitle: "Biến đổi mỗi chữ cái theo E(x) = (a·x + b) mod 26; ký tự khác giữ nguyên.",
    keyPanelTitle: "Hệ số a và b",
    keyDescription: "Nhập hai số nguyên a và b. a phải nguyên tố cùng nhau với 26: 1, 3, 5, 7, 9, 11, 15, 17, 19, 21, 23 hoặc 25 (sau khi lấy mod 26).",
    keyNote: "Ví dụ: a = 5, b = 8.",
    numeric: true,
    fields: ["a", "b"],
    example: { text: "HELLO", keys: { a: "5", b: "8" } },
    validateKey({ a, b }, forFile) {
      const parsedA = parseSignedInteger(a, { forFile });
      if (parsedA.missing) return { missing: true, message: MESSAGES.affineMissingA };
      if (parsedA.invalid) return { message: MESSAGES.affineInvalidA };
      const normalizedA = modulo26(parsedA.value);
      if (gcd(normalizedA, 26) !== 1) return { message: MESSAGES.affineNonInvertible };
      const parsedB = parseSignedInteger(b, { forFile });
      if (parsedB.missing) return { missing: true, message: MESSAGES.affineMissingB };
      if (parsedB.invalid) return { message: MESSAGES.affineInvalidB };
      return { valid: true, note: `a′ = ${normalizedA}, b′ = ${modulo26(parsedB.value)}` };
    },
    textBody: (text, { a, b }) => (
      `{"text":${JSON.stringify(text)},"a":${BigInt(a.trim()).toString()},"b":${BigInt(b.trim()).toString()}}`
    ),
    describeKey: ({ a, b }) => `a = ${a.trim()}, b = ${b.trim()}`,
  },
  columnar: {
    name: "Columnar",
    subtitle: "Ghi văn bản theo hàng rồi đọc các cột theo thứ tự khóa; giữ nguyên mọi ký tự, không thêm ký tự đệm.",
    keyPanelTitle: "Khóa cột",
    keyDescription: "Nhập hoán vị số 1..m (2 đến 256 cột, cách nhau bằng dấu cách hoặc dấu phẩy) hoặc từ khóa gồm 2 đến 256 chữ cái A–Z.",
    keyNote: "Ví dụ: 3 1 4 2 hoặc BALLOON.",
    placeholder: "ví dụ: 3 1 4 2 hoặc BALLOON",
    fields: ["key"],
    example: { text: "MEET ME AT NOON", keys: { key: "BALLOON" } },
    validateKey({ key }) {
      const trimmed = key.replace(COLUMNAR_TRIM, "");
      if (trimmed === "") return { missing: true, message: MESSAGES.keyMissing };
      const valid = [...trimmed].length <= 2048
        && (isColumnarPermutation(trimmed) || /^[A-Za-z]{2,256}$/.test(trimmed));
      return valid ? { valid: true } : { message: MESSAGES.columnarKey };
    },
    textBody: (text, { key }) => JSON.stringify({ text, key }),
    describeKey: ({ key }) => key.replace(COLUMNAR_TRIM, ""),
  },
};

const emptyKeys = () => Object.fromEntries(
  Object.entries(CIPHERS).map(([cipher, config]) => [
    cipher,
    Object.fromEntries(config.fields.map((field) => [field, ""])),
  ]),
);

const elements = {
  cipherTitle: byId("cipherTitle"),
  cipherSubtitle: byId("cipherSubtitle"),
  playfairWarning: byId("playfairWarning"),
  modeEncrypt: byId("modeEncrypt"),
  modeDecrypt: byId("modeDecrypt"),
  helperText: byId("helperText"),
  typeText: byId("typeText"),
  typeFile: byId("typeFile"),
  inputTitle: byId("inputTitle"),
  outputTitle: byId("outputTitle"),
  textWrap: byId("textWrap"),
  fileWrap: byId("fileWrap"),
  textInput: byId("textInput"),
  inputHighlight: byId("inputHighlight"),
  fileInput: byId("fileInput"),
  dropZone: byId("dropZone"),
  fileCard: byId("fileCard"),
  fileName: byId("fileName"),
  fileSize: byId("fileSize"),
  filePreview: byId("filePreview"),
  inputStatus: byId("inputStatus"),
  keyHeading: byId("keyHeading"),
  keyDescription: byId("keyDescription"),
  keyPanelTitle: byId("keyPanelTitle"),
  keyNote: byId("keyNote"),
  singleKeyRow: byId("singleKeyRow"),
  affineKeyRow: byId("affineKeyRow"),
  keyInput: byId("keyInput"),
  affineA: byId("affineA"),
  affineB: byId("affineB"),
  keyStatus: byId("keyStatus"),
  normalizedKey: byId("normalizedKey"),
  outputStatus: byId("outputStatus"),
  result: byId("result"),
  analysis: byId("analysis"),
  actionButton: byId("actionButton"),
  copyInput: byId("copyInput"),
  copyKey: byId("copyKey"),
  copyOutput: byId("copyOutput"),
  clearOutput: byId("clearOutput"),
  downloadOutput: byId("downloadOutput"),
  notice: byId("notice"),
  noticeTitle: byId("noticeTitle"),
  noticeMessage: byId("noticeMessage"),
  shiftSection: byId("shiftSection"),
  shiftTitle: byId("shiftTitle"),
  sourceAlphabet: byId("sourceAlphabet"),
  shiftedAlphabet: byId("shiftedAlphabet"),
  sourceLabel: byId("sourceLabel"),
  shiftedLabel: byId("shiftedLabel"),
  historyTabLocal: byId("historyTabLocal"),
  historyTabServer: byId("historyTabServer"),
  localHistoryPanel: byId("localHistoryPanel"),
  localHistoryEnabled: byId("localHistoryEnabled"),
  localHistoryList: byId("localHistoryList"),
  localHistoryEmpty: byId("localHistoryEmpty"),
  serverHistoryPanel: byId("serverHistoryPanel"),
  serverHistoryCipher: byId("serverHistoryCipher"),
  serverHistoryOperation: byId("serverHistoryOperation"),
  serverHistoryRows: byId("serverHistoryRows"),
  serverHistoryStatus: byId("serverHistoryStatus"),
  loadMoreServerHistory: byId("loadMoreServerHistory"),
};

const state = {
  cipher: "caesar",
  mode: "encrypt",
  inputType: "text",
  keys: emptyKeys(),
  file: null,
  fileText: "",
  result: null,
  view: "result",
  loading: false,
  requestVersion: 0,
  fileReadVersion: 0,
  historyTab: "local",
  server: { available: false, items: [], cursor: null, loading: false, version: 0 },
};

const cipherConfig = () => CIPHERS[state.cipher];
const currentKeys = () => state.keys[state.cipher];

const escapeHtml = (value) => String(value).replace(
  /[&<>"]/g,
  (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[character],
);

function colorize(text) {
  let result = "";
  let group = "";
  let buffer = "";
  const flush = () => {
    if (buffer !== "") {
      result += `<span class="${group}">${escapeHtml(buffer)}</span>`;
      buffer = "";
    }
  };
  for (const character of text) {
    const code = character.charCodeAt(0);
    const nextGroup = code >= 65 && code <= 90
      ? "char-upper"
      : code >= 97 && code <= 122
        ? "char-lower"
        : "char-other";
    if (nextGroup !== group) {
      flush();
      group = nextGroup;
    }
    buffer += character;
  }
  flush();
  return result;
}

function setStatus(element, text, kind = "neutral") {
  element.className = `status-bar${kind === "neutral" ? "" : ` ${kind}`}`;
  element.querySelector(".status-icon").textContent = kind === "valid" ? "✓" : kind === "error" ? "!" : "·";
  element.querySelector("span:last-child").textContent = text;
}

function showNotice(kind, title, message = "") {
  elements.notice.className = `notice ${kind}`;
  elements.notice.hidden = false;
  elements.noticeTitle.textContent = title;
  elements.noticeMessage.textContent = message;
}

function hideNotice() {
  elements.notice.hidden = true;
  elements.noticeTitle.textContent = "";
  elements.noticeMessage.textContent = "";
}

function currentInputText() {
  return state.inputType === "text" ? elements.textInput.value : state.fileText;
}

function checkKey() {
  return cipherConfig().validateKey(currentKeys(), state.inputType === "file");
}

function caesarShift() {
  const parsed = parseSignedInteger(state.keys.caesar.key, { forFile: state.inputType === "file" });
  return parsed.value === undefined ? 0 : modulo26(parsed.value);
}

function shiftAlphabet(key, operation) {
  // Display-only mapping for the alphabet table; server responses remain authoritative.
  const direction = operation === "encrypt" ? 1 : -1;
  return [...ALPHABET].map((_, index) => ALPHABET[(index + direction * key + 26) % 26]);
}

const sourceCells = [];
const shiftedCells = [];
for (const letter of ALPHABET) {
  const sourceCell = document.createElement("span");
  sourceCell.textContent = letter;
  elements.sourceAlphabet.appendChild(sourceCell);
  sourceCells.push(sourceCell);

  const shiftedCell = document.createElement("span");
  elements.shiftedAlphabet.appendChild(shiftedCell);
  shiftedCells.push(shiftedCell);
}

function renderShiftTable() {
  elements.shiftSection.hidden = state.cipher !== "caesar";
  if (elements.shiftSection.hidden) return;
  const key = caesarShift();
  const shifted = shiftAlphabet(key, state.mode);
  const used = new Set(
    [...currentInputText()]
      .filter((letter) => /^[A-Za-z]$/.test(letter))
      .map((letter) => letter.toUpperCase()),
  );
  for (let index = 0; index < ALPHABET.length; index += 1) {
    shiftedCells[index].textContent = shifted[index];
    sourceCells[index].classList.toggle("used", used.has(ALPHABET[index]));
    shiftedCells[index].classList.toggle("used", used.has(ALPHABET[index]));
  }
  const encrypting = state.mode === "encrypt";
  elements.sourceLabel.textContent = encrypting ? "Bản rõ" : "Bản mã";
  elements.shiftedLabel.textContent = encrypting ? "Bản mã" : "Bản rõ";
  elements.shiftTitle.textContent = `Khóa ${key} · A → ${shifted[0]}`;
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} byte`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MiB`;
}

function validateInput() {
  if (state.inputType === "text") {
    const text = elements.textInput.value;
    if (text.length === 0) {
      setStatus(elements.inputStatus, "Chưa có dữ liệu");
      return false;
    }
    const textError = cipherConfig().validateText?.(text);
    if (textError) {
      setStatus(elements.inputStatus, textError, "error");
      return false;
    }
    const lineCount = text.split(/\r\n|\r|\n/).length;
    setStatus(elements.inputStatus, `Văn bản hợp lệ · ${[...text].length} ký tự · ${lineCount} dòng`, "valid");
    return true;
  }

  if (state.file === null) {
    setStatus(elements.inputStatus, "Chưa chọn file");
    return false;
  }
  if (!/\.txt$/i.test(state.file.name)) {
    setStatus(elements.inputStatus, MESSAGES.fileType, "error");
    return false;
  }
  if (state.file.size > MAX_FILE_BYTES) {
    setStatus(elements.inputStatus, MESSAGES.fileSize, "error");
    return false;
  }
  if (state.file.size === 0) {
    setStatus(elements.inputStatus, MESSAGES.fileEmpty, "error");
    return false;
  }
  setStatus(elements.inputStatus, `File .txt hợp lệ · ${formatSize(state.file.size)}`, "valid");
  return true;
}

function validateKey() {
  const checked = checkKey();
  if (!checked.valid) {
    elements.normalizedKey.textContent = "";
    setStatus(elements.keyStatus, checked.message, checked.missing ? "neutral" : "error");
    return false;
  }
  elements.normalizedKey.textContent = state.cipher === "affine" ? "" : checked.note ?? "";
  setStatus(elements.keyStatus, checked.note && state.cipher === "affine" ? `Khóa hợp lệ · ${checked.note}` : "Khóa hợp lệ", "valid");
  return true;
}

function clearResult({ keepNotice = false } = {}) {
  state.result = null;
  state.view = "result";
  elements.result.className = "output empty";
  elements.result.textContent = "Kết quả sẽ hiển thị ở đây sau khi xử lý.";
  elements.analysis.replaceChildren();
  renderOutputView();
  setStatus(elements.outputStatus, "Chưa xử lý");
  if (!keepNotice) hideNotice();
}

function renderOutputView() {
  elements.result.hidden = state.view !== "result";
  elements.analysis.hidden = state.view !== "analysis";
  document.querySelectorAll("#outputPanel [data-view]").forEach((tab) => {
    tab.setAttribute("aria-selected", String(tab.dataset.view === state.view));
  });
}

function renderCipherChrome() {
  const config = cipherConfig();
  const encrypting = state.mode === "encrypt";
  document.querySelectorAll("[data-cipher]").forEach((tab) => {
    const active = tab.dataset.cipher === state.cipher;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  elements.cipherTitle.textContent = `${config.name} Cipher`;
  elements.cipherSubtitle.textContent = `${config.subtitle} Hỗ trợ văn bản và file .txt.`;
  elements.helperText.textContent = encrypting
    ? `Nhập bản rõ bên dưới để mã hóa bằng hệ mật ${config.name}.`
    : `Nhập bản mã bên dưới để giải mã bằng hệ mật ${config.name}.`;
  elements.playfairWarning.hidden = state.cipher !== "playfair";
  elements.keyHeading.textContent = `Khóa ${config.name}`;
  elements.keyDescription.textContent = config.keyDescription;
  elements.keyPanelTitle.textContent = config.keyPanelTitle;
  elements.keyNote.textContent = config.keyNote;
  const affine = state.cipher === "affine";
  elements.singleKeyRow.hidden = affine;
  elements.affineKeyRow.hidden = !affine;
  if (!affine) {
    elements.keyInput.placeholder = config.placeholder;
    elements.keyInput.inputMode = config.numeric ? "numeric" : "text";
  }
}

function syncKeyControls() {
  if (state.cipher === "affine") {
    elements.affineA.value = state.keys.affine.a;
    elements.affineB.value = state.keys.affine.b;
  } else {
    elements.keyInput.value = currentKeys().key;
  }
}

function render() {
  const encrypting = state.mode === "encrypt";
  const hasResult = state.result !== null;
  const inputValid = validateInput();
  const keyValid = validateKey();
  const hasKeyText = cipherConfig().fields.some((field) => currentKeys()[field] !== "");

  renderCipherChrome();
  elements.modeEncrypt.classList.toggle("active", encrypting);
  elements.modeDecrypt.classList.toggle("active", !encrypting);
  elements.modeEncrypt.setAttribute("aria-selected", String(encrypting));
  elements.modeDecrypt.setAttribute("aria-selected", String(!encrypting));
  elements.typeText.setAttribute("aria-pressed", String(state.inputType === "text"));
  elements.typeFile.setAttribute("aria-pressed", String(state.inputType === "file"));
  elements.textWrap.hidden = state.inputType !== "text";
  elements.fileWrap.hidden = state.inputType !== "file";
  elements.inputTitle.textContent = encrypting ? "Bản rõ" : "Bản mã";
  elements.outputTitle.textContent = encrypting ? "Bản mã" : "Bản rõ";

  elements.inputHighlight.innerHTML = colorize(elements.textInput.value);
  elements.actionButton.classList.toggle("loading", state.loading);
  elements.actionButton.textContent = state.loading ? "Đang xử lý…" : encrypting ? "Mã hóa" : "Giải mã";

  document.querySelectorAll("[data-lockable]").forEach((control) => {
    control.setAttribute("aria-disabled", String(state.loading));
    control.disabled = state.loading;
  });
  elements.dropZone.tabIndex = state.loading ? -1 : 0;
  if (!state.loading) {
    elements.copyInput.disabled = currentInputText() === "";
    elements.copyKey.disabled = !hasKeyText;
    elements.copyOutput.disabled = !hasResult;
    elements.clearOutput.disabled = !hasResult;
    elements.downloadOutput.disabled = !hasResult;
    elements.actionButton.disabled = !(inputValid && keyValid);
  }

  renderOutputView();
  renderShiftTable();
}

function selectCipher(cipher) {
  if (!(cipher in CIPHERS) || cipher === state.cipher) return;
  state.cipher = cipher;
  syncKeyControls();
  clearResult();
  render();
}

function selectMode(mode) {
  state.mode = mode;
  clearResult();
  render();
}

function selectInputType(type) {
  state.inputType = type;
  clearResult();
  setStatus(elements.inputStatus, type === "text" ? "Chưa có dữ liệu" : "Chưa chọn file");
  render();
}

function displaySelectedFile() {
  elements.fileName.textContent = state.file.name;
  elements.fileSize.textContent = formatSize(state.file.size);
  elements.dropZone.hidden = true;
  elements.fileCard.hidden = false;
}

async function setFile(file) {
  const fileReadVersion = state.fileReadVersion + 1;
  state.fileReadVersion = fileReadVersion;
  state.file = file;
  state.fileText = "";
  clearResult();
  displaySelectedFile();
  const preliminarilyValid = /\.txt$/i.test(file.name) && file.size > 0 && file.size <= MAX_FILE_BYTES;
  if (preliminarilyValid) {
    try {
      const fileText = await file.text();
      if (fileReadVersion !== state.fileReadVersion || state.file !== file) return;
      state.fileText = fileText;
    } catch (error) {
      if (fileReadVersion !== state.fileReadVersion || state.file !== file) return;
      showNotice("warning", "Không thể xem trước file", "Máy chủ vẫn sẽ kiểm tra file khi xử lý.");
    }
  }
  if (fileReadVersion !== state.fileReadVersion || state.file !== file) return;
  const preview = state.fileText.length > 12000 ? `${state.fileText.slice(0, 12000)}\n…` : state.fileText;
  elements.filePreview.innerHTML = colorize(preview);
  render();
}

function removeFile() {
  state.fileReadVersion += 1;
  state.file = null;
  state.fileText = "";
  elements.fileInput.value = "";
  elements.filePreview.textContent = "";
  elements.dropZone.hidden = false;
  elements.fileCard.hidden = true;
  clearResult();
  render();
}

async function copyText(text, successTitle) {
  try {
    await navigator.clipboard.writeText(text);
    showNotice("success", successTitle);
  } catch (error) {
    showNotice("warning", "Không thể sao chép", "Trình duyệt đã chặn bộ nhớ tạm; hãy sao chép thủ công.");
  }
}

function addAnalysisRow(term, description) {
  const row = document.createElement("div");
  const label = document.createElement("dt");
  const value = document.createElement("dd");
  label.textContent = term;
  value.textContent = description;
  row.append(label, value);
  elements.analysis.appendChild(row);
}

function showResult(result, source) {
  state.result = result;
  state.view = "result";
  elements.result.className = "output";
  elements.result.innerHTML = colorize(result);
  elements.analysis.replaceChildren();

  const config = cipherConfig();
  addAnalysisRow("Hệ mã", config.name);
  addAnalysisRow("Chế độ", state.mode === "encrypt" ? "Mã hóa" : "Giải mã");
  addAnalysisRow("Nguồn", state.inputType === "text" ? "Văn bản" : `File · ${state.file.name}`);
  addAnalysisRow("Khóa", config.describeKey(currentKeys()));
  addAnalysisRow("Ký tự đầu vào", String([...source].length));
  addAnalysisRow("Ký tự kết quả", String([...result].length));
  if (state.cipher === "caesar") {
    let uppercase = 0;
    let lowercase = 0;
    let unchanged = 0;
    for (const character of source) {
      const code = character.charCodeAt(0);
      if (code >= 65 && code <= 90) uppercase += 1;
      else if (code >= 97 && code <= 122) lowercase += 1;
      else unchanged += 1;
    }
    addAnalysisRow("Khóa chuẩn hóa", String(caesarShift()));
    addAnalysisRow("Chữ hoa dịch chuyển", String(uppercase));
    addAnalysisRow("Chữ thường dịch chuyển", String(lowercase));
    addAnalysisRow("Ký tự giữ nguyên", String(unchanged));
  }
  if (state.cipher === "playfair") {
    addAnalysisRow("Lưu ý", "Kết quả là văn bản đã chuẩn hóa, không phải nguyên văn đầu vào");
  }
}

async function parseApiResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.toLowerCase().includes("application/json")) {
    const error = new Error(MESSAGES.system);
    error.isApiError = true;
    error.status = response.status;
    throw error;
  }
  let body;
  try {
    body = await response.json();
  } catch (error) {
    const responseError = new Error(MESSAGES.system);
    responseError.isApiError = true;
    responseError.status = response.status;
    throw responseError;
  }
  if (!response.ok || body.success !== true) {
    const apiError = new Error(typeof body.message === "string" ? body.message : MESSAGES.system);
    apiError.isApiError = true;
    apiError.status = response.status;
    throw apiError;
  }
  return body;
}

async function fetchWithTimeout(url, options) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    window.clearTimeout(timeout);
  }
}

const realApi = {
  async text(cipher, operation, text, keys) {
    const response = await fetchWithTimeout(`/api/${cipher}/${operation}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: CIPHERS[cipher].textBody(text, keys),
    });
    return parseApiResponse(response);
  },

  async file(cipher, operation, file, keys, responseMode) {
    const data = new FormData();
    data.append("file", file);
    for (const field of CIPHERS[cipher].fields) data.append(field, keys[field]);
    data.append("action", operation);
    data.append("response_mode", responseMode);
    const response = await fetchWithTimeout(`/api/${cipher}/file`, { method: "POST", body: data });
    if (responseMode === "content") return parseApiResponse(response);

    const contentType = response.headers.get("content-type") || "";
    if (!response.ok || contentType.toLowerCase().includes("application/json")) {
      return parseApiResponse(response);
    }
    if (!contentType.toLowerCase().startsWith("text/plain")) {
      const error = new Error(MESSAGES.system);
      error.isApiError = true;
      error.status = response.status;
      throw error;
    }
    return {
      blob: await response.blob(),
      disposition: response.headers.get("content-disposition") || "",
    };
  },
};

function textResultFilename() {
  return state.mode === "encrypt" ? "ket-qua.encrypted.txt" : "ket-qua.decrypted.txt";
}

function filenameFromDisposition(disposition) {
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch (error) {
      // Continue to the server-provided ASCII fallback below.
    }
  }
  const quotedMatch = disposition.match(/filename="((?:\\.|[^"])*)"/i);
  return quotedMatch ? quotedMatch[1].replace(/\\([\\"])/g, "$1") : null;
}

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function processInput() {
  if (elements.actionButton.disabled) return;
  const requestVersion = state.requestVersion + 1;
  state.requestVersion = requestVersion;
  state.loading = true;
  hideNotice();
  clearResult({ keepNotice: true });
  setStatus(elements.outputStatus, "Đang gửi yêu cầu…");
  render();

  const source = currentInputText();
  const keys = { ...currentKeys() };
  const actionLabel = state.mode === "encrypt" ? "Mã hóa" : "Giải mã";
  try {
    const response = state.inputType === "text"
      ? await realApi.text(state.cipher, state.mode, elements.textInput.value, keys)
      : await realApi.file(state.cipher, state.mode, state.file, keys, "content");
    if (requestVersion !== state.requestVersion) return;
    showResult(response.result, source);
    setStatus(elements.outputStatus, `${actionLabel} thành công · ${[...response.result].length} ký tự`, "valid");
    showNotice("success", `${actionLabel} thành công`, "Kết quả đã sẵn sàng để sao chép hoặc tải xuống.");
    recordLocalHistory(response.result, keys);
    if (state.historyTab === "server") loadServerHistory({ reset: true });
  } catch (error) {
    if (requestVersion !== state.requestVersion) return;
    clearResult({ keepNotice: true });
    if (error.isApiError) {
      setStatus(elements.outputStatus, `${actionLabel} thất bại`, "error");
      showNotice("error", `${actionLabel} thất bại`, error.message);
    } else {
      setStatus(elements.outputStatus, "Không thể kết nối tới máy chủ", "error");
      showNotice("error", "Lỗi kết nối", "Không thể gọi máy chủ. Vui lòng thử lại.");
    }
  } finally {
    if (requestVersion === state.requestVersion) {
      state.loading = false;
      render();
    }
  }
}

async function downloadResult() {
  if (state.result === null || state.loading) return;
  state.loading = true;
  render();
  try {
    let filename;
    if (state.inputType === "file") {
      const response = await realApi.file(state.cipher, state.mode, state.file, currentKeys(), "file");
      filename = filenameFromDisposition(response.disposition);
      if (filename === null) {
        const error = new Error(MESSAGES.system);
        error.isApiError = true;
        throw error;
      }
      saveBlob(response.blob, filename);
    } else {
      filename = textResultFilename();
      saveBlob(new Blob([state.result], { type: "text/plain;charset=utf-8" }), filename);
    }
    showNotice("success", "Đã tạo file tải xuống", filename);
  } catch (error) {
    clearResult({ keepNotice: true });
    const message = error.isApiError ? error.message : "Không thể tải kết quả. Vui lòng thử lại.";
    setStatus(elements.outputStatus, "Tải kết quả thất bại", "error");
    showNotice("error", "Tải kết quả thất bại", message);
  } finally {
    state.loading = false;
    render();
  }
}

// ---- History on this device (localStorage; never sent to the server) ----

function readLocalHistory() {
  try {
    const parsed = JSON.parse(localStorage.getItem(LOCAL_HISTORY_KEY) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    return [];
  }
}

function isLocalHistoryEnabled() {
  try {
    return localStorage.getItem(LOCAL_HISTORY_ENABLED_KEY) !== "false";
  } catch (error) {
    return false;
  }
}

function writeLocalHistory(entries) {
  try {
    if (entries.length === 0) localStorage.removeItem(LOCAL_HISTORY_KEY);
    else localStorage.setItem(LOCAL_HISTORY_KEY, JSON.stringify(entries));
  } catch (error) {
    // Storage blocked or full: skip history, never break the cipher flow.
  }
}

function recordLocalHistory(result, keys) {
  if (!isLocalHistoryEnabled()) return;
  const fromFile = state.inputType === "file";
  const entry = {
    at: new Date().toISOString(),
    cipher: state.cipher,
    operation: state.mode,
    source: state.inputType,
    input: fromFile ? state.file.name : elements.textInput.value,
    key: keys,
    result: fromFile ? null : result,
  };
  writeLocalHistory([entry, ...readLocalHistory()].slice(0, LOCAL_HISTORY_LIMIT));
  renderLocalHistory();
}

const excerpt = (text, length = 90) => {
  const characters = [...text];
  return characters.length > length ? `${characters.slice(0, length).join("")}…` : text;
};

const formatTime = (iso) => {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString("vi-VN");
};

function reuseLocalEntry(entry) {
  if (state.loading || !(entry.cipher in CIPHERS)) return;
  state.cipher = entry.cipher;
  state.mode = entry.operation === "decrypt" ? "decrypt" : "encrypt";
  state.inputType = "text";
  state.keys[entry.cipher] = { ...state.keys[entry.cipher], ...entry.key };
  elements.textInput.value = entry.input;
  syncKeyControls();
  clearResult();
  render();
  elements.actionButton.focus();
}

function renderLocalHistory() {
  const entries = readLocalHistory();
  elements.localHistoryEnabled.checked = isLocalHistoryEnabled();
  elements.localHistoryEmpty.hidden = entries.length > 0;
  elements.localHistoryList.replaceChildren(...entries.map((entry) => {
    const item = document.createElement("li");
    const head = document.createElement("div");
    head.className = "history-item-head";
    const title = document.createElement("strong");
    const config = CIPHERS[entry.cipher];
    title.textContent = `${config ? config.name : entry.cipher} · ${entry.operation === "decrypt" ? "Giải mã" : "Mã hóa"}`;
    const time = document.createElement("time");
    time.dateTime = entry.at;
    time.textContent = formatTime(entry.at);
    head.append(title, time);
    if (entry.source === "text" && config) {
      const reuse = document.createElement("button");
      reuse.type = "button";
      reuse.className = "mini-button";
      reuse.textContent = "Dùng lại";
      reuse.dataset.lockable = "";
      reuse.disabled = state.loading;
      reuse.addEventListener("click", () => reuseLocalEntry(entry));
      head.append(reuse);
    }
    const details = document.createElement("dl");
    const addDetail = (term, value) => {
      const label = document.createElement("dt");
      const content = document.createElement("dd");
      label.textContent = term;
      content.textContent = value;
      details.append(label, content);
    };
    addDetail(entry.source === "file" ? "File" : "Đầu vào", excerpt(String(entry.input ?? "")));
    if (config) addDetail("Khóa", config.describeKey({ ...emptyKeys()[entry.cipher], ...entry.key }));
    if (entry.result !== null && entry.result !== undefined) addDetail("Kết quả", excerpt(String(entry.result)));
    item.append(head, details);
    return item;
  }));
}

// ---- Server history (metadata only; shown when /api/health allows it) ----

const CIPHER_LABELS = Object.fromEntries(Object.entries(CIPHERS).map(([cipher, config]) => [cipher, config.name]));

function renderServerRows() {
  elements.serverHistoryRows.replaceChildren(...state.server.items.map((item) => {
    const row = document.createElement("tr");
    const lengths = `${item.inputLength ?? "—"} → ${item.outputLength ?? "—"}`;
    const source = item.source === "file" ? `File${item.responseMode ? ` (${item.responseMode})` : ""}` : "Văn bản";
    const cells = [
      formatTime(item.createdAt),
      CIPHER_LABELS[item.cipher] ?? item.cipher,
      item.operation === "encrypt" ? "Mã hóa" : item.operation === "decrypt" ? "Giải mã" : "—",
      source,
      lengths,
      `${item.succeeded ? "Thành công" : "Lỗi"} · ${item.httpStatus}`,
      `${item.durationMs} ms`,
    ];
    cells.forEach((text, index) => {
      const cell = document.createElement("td");
      cell.textContent = text;
      if (index === 5) cell.className = item.succeeded ? "ok" : "failed";
      row.appendChild(cell);
    });
    return row;
  }));
  elements.loadMoreServerHistory.hidden = state.server.cursor === null;
  elements.loadMoreServerHistory.disabled = state.server.loading;
}

async function loadServerHistory({ reset }) {
  if (!state.server.available) return;
  const version = state.server.version + 1;
  state.server.version = version;
  state.server.loading = true;
  if (reset) {
    state.server.items = [];
    state.server.cursor = null;
  }
  renderServerRows();
  setStatus(elements.serverHistoryStatus, "Đang tải…");
  const query = new URLSearchParams({ limit: String(SERVER_HISTORY_PAGE_SIZE) });
  if (elements.serverHistoryCipher.value) query.set("cipher", elements.serverHistoryCipher.value);
  if (elements.serverHistoryOperation.value) query.set("operation", elements.serverHistoryOperation.value);
  if (!reset && state.server.cursor) query.set("cursor", state.server.cursor);
  try {
    const body = await parseApiResponse(await fetchWithTimeout(`/api/history?${query}`, {}));
    if (version !== state.server.version) return;
    state.server.items = [...state.server.items, ...body.result.items];
    state.server.cursor = body.result.nextCursor;
    const count = state.server.items.length;
    setStatus(elements.serverHistoryStatus, count === 0 ? "Chưa có thao tác nào" : `Đang hiện ${count} thao tác`, "valid");
  } catch (error) {
    if (version !== state.server.version) return;
    state.server.cursor = null;
    const message = error.isApiError ? error.message : "Không thể gọi máy chủ. Vui lòng thử lại.";
    setStatus(elements.serverHistoryStatus, message, "error");
  } finally {
    if (version === state.server.version) {
      state.server.loading = false;
      renderServerRows();
    }
  }
}

function selectHistoryTab(tab) {
  if (tab === "server" && !state.server.available) return;
  state.historyTab = tab;
  const server = tab === "server";
  elements.historyTabLocal.setAttribute("aria-selected", String(!server));
  elements.historyTabServer.setAttribute("aria-selected", String(server));
  elements.localHistoryPanel.hidden = server;
  elements.serverHistoryPanel.hidden = !server;
  if (server) loadServerHistory({ reset: true });
}

async function detectServerHistory() {
  try {
    const response = await fetchWithTimeout("/api/health", {});
    const body = await response.json();
    state.server.available = body?.result?.history === "enabled" && body?.result?.database === "ok";
  } catch (error) {
    state.server.available = false;
  }
  elements.historyTabServer.hidden = !state.server.available;
}

function resetAll() {
  state.requestVersion += 1;
  state.cipher = "caesar";
  state.mode = "encrypt";
  state.inputType = "text";
  state.keys = emptyKeys();
  state.file = null;
  state.fileText = "";
  state.view = "result";
  state.loading = false;
  state.fileReadVersion += 1;
  elements.textInput.value = "";
  syncKeyControls();
  elements.fileInput.value = "";
  elements.filePreview.textContent = "";
  elements.dropZone.hidden = false;
  elements.fileCard.hidden = true;
  document.querySelectorAll("#outputPanel [data-view]").forEach((tab) => {
    tab.setAttribute("aria-selected", String(tab.dataset.view === "result"));
  });
  clearResult();
  setStatus(elements.inputStatus, "Chưa có dữ liệu");
  setStatus(elements.keyStatus, "Chưa nhập khóa");
  render();
}

function onKeyEdited(field, value) {
  currentKeys()[field] = value;
  hideNotice();
  clearResult();
  render();
}

document.querySelectorAll("[data-cipher]").forEach((tab) => {
  tab.addEventListener("click", () => selectCipher(tab.dataset.cipher));
});
elements.modeEncrypt.addEventListener("click", () => selectMode("encrypt"));
elements.modeDecrypt.addEventListener("click", () => selectMode("decrypt"));
elements.typeText.addEventListener("click", () => selectInputType("text"));
elements.typeFile.addEventListener("click", () => selectInputType("file"));
elements.textInput.addEventListener("input", () => { hideNotice(); clearResult(); render(); });
elements.textInput.addEventListener("scroll", () => { elements.inputHighlight.scrollTop = elements.textInput.scrollTop; });
elements.keyInput.addEventListener("input", () => onKeyEdited("key", elements.keyInput.value));
elements.affineA.addEventListener("input", () => onKeyEdited("a", elements.affineA.value));
elements.affineB.addEventListener("input", () => onKeyEdited("b", elements.affineB.value));
byId("clearInput").addEventListener("click", () => {
  if (state.inputType === "file") removeFile();
  else {
    elements.textInput.value = "";
    clearResult();
    render();
    elements.textInput.focus();
  }
});
byId("clearKey").addEventListener("click", () => {
  state.keys[state.cipher] = emptyKeys()[state.cipher];
  syncKeyControls();
  clearResult();
  render();
  (state.cipher === "affine" ? elements.affineA : elements.keyInput).focus();
});
elements.copyInput.addEventListener("click", () => copyText(currentInputText(), "Đã sao chép đầu vào"));
elements.copyKey.addEventListener("click", () => copyText(cipherConfig().describeKey(currentKeys()), "Đã sao chép khóa"));
elements.copyOutput.addEventListener("click", () => copyText(state.result, "Đã sao chép kết quả"));
elements.clearOutput.addEventListener("click", () => { clearResult(); render(); });
elements.downloadOutput.addEventListener("click", downloadResult);
elements.actionButton.addEventListener("click", processInput);
byId("resetAll").addEventListener("click", resetAll);
byId("closeNotice").addEventListener("click", hideNotice);
byId("pickFile").addEventListener("click", (event) => { event.stopPropagation(); elements.fileInput.click(); });
byId("changeFile").addEventListener("click", () => elements.fileInput.click());
byId("removeFile").addEventListener("click", removeFile);
elements.fileInput.addEventListener("change", () => {
  const [file] = elements.fileInput.files;
  if (file) setFile(file);
});
elements.dropZone.addEventListener("click", (event) => {
  if (state.loading) return;
  if (event.target !== byId("pickFile")) elements.fileInput.click();
});
elements.dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    if (state.loading) return;
    elements.fileInput.click();
  }
});
for (const eventName of ["dragenter", "dragover"]) {
  elements.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    if (!state.loading) elements.dropZone.classList.add("drag-over");
  });
}
for (const eventName of ["dragleave", "drop"]) {
  elements.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.dropZone.classList.remove("drag-over");
  });
}
elements.dropZone.addEventListener("drop", (event) => {
  if (state.loading) return;
  const [file] = event.dataTransfer.files;
  if (file) setFile(file);
});
byId("example").addEventListener("click", () => {
  const { example } = cipherConfig();
  state.mode = "encrypt";
  state.inputType = "text";
  state.keys[state.cipher] = { ...example.keys };
  elements.textInput.value = example.text;
  syncKeyControls();
  clearResult();
  render();
  elements.actionButton.focus();
});
document.querySelectorAll("#outputPanel [data-view]").forEach((tab) => {
  tab.addEventListener("click", () => {
    state.view = tab.dataset.view;
    render();
  });
});
elements.historyTabLocal.addEventListener("click", () => selectHistoryTab("local"));
elements.historyTabServer.addEventListener("click", () => selectHistoryTab("server"));
elements.localHistoryEnabled.addEventListener("change", () => {
  const enabled = elements.localHistoryEnabled.checked;
  try {
    localStorage.setItem(LOCAL_HISTORY_ENABLED_KEY, String(enabled));
  } catch (error) {
    showNotice("warning", "Không thể lưu lựa chọn", "Trình duyệt đang chặn bộ nhớ cục bộ.");
  }
  if (!enabled && readLocalHistory().length > 0) {
    showNotice("success", "Đã tắt lưu lịch sử", "Các mục đã lưu vẫn còn; bấm “Xóa lịch sử trên máy này” để xóa.");
  }
  renderLocalHistory();
});
byId("clearLocalHistory").addEventListener("click", () => {
  writeLocalHistory([]);
  renderLocalHistory();
  showNotice("success", "Đã xóa lịch sử trên máy này");
});
elements.serverHistoryCipher.addEventListener("change", () => loadServerHistory({ reset: true }));
elements.serverHistoryOperation.addEventListener("change", () => loadServerHistory({ reset: true }));
byId("refreshServerHistory").addEventListener("click", () => loadServerHistory({ reset: true }));
elements.loadMoreServerHistory.addEventListener("click", () => loadServerHistory({ reset: false }));

syncKeyControls();
render();
renderLocalHistory();
detectServerHistory();
