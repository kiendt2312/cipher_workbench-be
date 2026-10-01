/**
 * Framework-neutral API client for the cipher backend.
 *
 * Copy this file into the FE project. It only uses `fetch`, `FormData`, `Blob`
 * and `localStorage`, calls relative `/api/...` URLs (same origin or dev proxy)
 * and follows repo_docs/frontend-integration.md. Results always come from the server.
 */

export type Cipher =
  | "caesar"
  | "vigenere"
  | "playfair"
  | "affine"
  | "columnar"
  | "hill"
  | "des";
export type Operation = "encrypt" | "decrypt";
export type ResponseMode = "content" | "file";

/** Raw UI values: keep them as strings; never parse integer keys through `number`. */
export type KeyInput =
  | { cipher: "caesar"; key: string }
  | { cipher: "vigenere" | "playfair" | "columnar"; key: string }
  | { cipher: "affine"; a: string; b: string };

export type TextRequest = KeyInput & { operation: Operation; text: string };
/** `stripPadding` is Playfair-only and only changes a decrypt attachment (`strip_padding`). */
export type FileRequest = KeyInput & { operation: Operation; file: File; stripPadding?: boolean };

/** Padding letters detected on Playfair/Hill decrypt (frontend-integration.md A.9). */
export interface PaddingInfo {
  count: number;
  /** 0-based indexes into the A-Z/a-z letters of `result`, ascending; not string indexes. */
  positions: number[];
  /** `result` without the letters at `positions`. */
  filtered: string;
}
/** Playfair decrypt (text and file content mode): raw `result` plus detected fillers. */
export interface PlayfairDecryptResponse {
  success: true;
  result: string;
  padding: PaddingInfo;
}

export type HillKeyInput =
  | { key: number[][]; keyword?: never; m?: never }
  | { keyword: string; m: 2 | 3 | 4; key?: never };
export type HillOptions = { stripDiacritics?: boolean; padChar?: string };
export type HillTransformRequest = HillKeyInput & {
  operation: Operation;
  text: string;
  options?: HillOptions;
};
export interface HillWarning {
  code: "W01" | "W02" | "W03";
  message: string;
  details: Record<string, unknown>;
}
export interface HillKeyAnalysis {
  matrix: number[][];
  m: 2 | 3 | 4;
  det: number;
  gcd: number;
  detInverse: number;
  adjugate: number[][];
  inverse: number[][];
}
export interface HillTransformResponse {
  success: true;
  result: string;
  blocks: Array<{ input: number[]; output: number[] }>;
  key: HillKeyAnalysis;
  warnings: HillWarning[];
  /** Decrypt only. */
  padding?: PaddingInfo;
}

function isPaddingInfo(value: unknown): value is PaddingInfo {
  if (typeof value !== "object" || value === null) return false;
  const padding = value as Record<string, unknown>;
  return (
    typeof padding.count === "number"
    && Array.isArray(padding.positions)
    && padding.positions.every((position) => Number.isInteger(position))
    && typeof padding.filtered === "string"
  );
}

function isHillTransformResponse(value: unknown): value is HillTransformResponse {
  if (typeof value !== "object" || value === null) return false;
  const body = value as Record<string, unknown>;
  return (
    body.success === true
    && typeof body.result === "string"
    && Array.isArray(body.blocks)
    && typeof body.key === "object"
    && body.key !== null
    && Array.isArray(body.warnings)
    && (body.padding === undefined || isPaddingInfo(body.padding))
  );
}

// ---- DES (strict JSON, camelCase fields; errors are the two-field envelope) ----

export type DesMode = "ECB" | "CBC";
export type DesFormat = "text" | "hex";

/** `iv` (16 hex) is required for CBC and ignored by the server for ECB. */
export interface DesModeInput {
  mode?: DesMode;
  iv?: string;
}
/** `inputFormat: "text"` = UTF-8 + PKCS#7; `"hex"` = whole 16-hex blocks, no padding. */
export interface DesEncryptRequest extends DesModeInput {
  text: string;
  key: string;
  inputFormat?: DesFormat;
}
/** Use the same format that produced the ciphertext: text ↔ text, hex ↔ hex. */
export interface DesDecryptRequest extends DesModeInput {
  text: string;
  key: string;
  outputFormat?: DesFormat;
}
export interface DesTraceRequest {
  block: string;
  key: string;
  operation?: Operation;
}
/** File encrypt reads UTF-8 text; file decrypt reads hex (multi-line allowed) and returns text. */
export interface DesFileRequest extends DesModeInput {
  operation: Operation;
  file: File;
  key: string;
}

/** Order is always W01 → W02 → W03; W03 only for ECB encryption with repeated blocks. */
export type DesWarning =
  | { code: "W01" | "W02"; message: string; details: Record<string, never> }
  | { code: "W03"; message: string; details: { repeatedBlocks: number } };

export interface DesResponse {
  success: true;
  result: string;
  warnings: DesWarning[];
}
export interface DesSubkey {
  n: number;
  shift: number;
  c: string;
  d: string;
  k: string;
}
export interface DesRound {
  n: number;
  /** Index of the subkey used: 1…16 for encrypt, 16…1 for decrypt. */
  subkey: number;
  expansion: string;
  xorKey: string;
  /** S1…S8 lookups. */
  sbox: Array<{ row: number; col: number; value: number }>;
  sboxOutput: string;
  f: string;
  l: string;
  r: string;
}
export interface DesTrace {
  operation: Operation;
  input: string;
  key: string;
  pc1: string;
  /** Always K1…K16, even for decrypt. */
  subkeys: DesSubkey[];
  ip: string;
  l0: string;
  r0: string;
  rounds: DesRound[];
  preOutput: string;
}
export interface DesTraceResponse extends DesResponse {
  trace: DesTrace;
}

/** Text, hex ciphertext and trace blocks are limited to 5 MiB of UTF-8 in both directions. */
export const DES_MAX_INPUT_BYTES = 5 * 1024 * 1024;
/** Largest UTF-8 text whose hex ciphertext still fits the 5 MiB decrypt limit. */
export const DES_MAX_ROUND_TRIP_TEXT_BYTES = 2_621_439;

export function utf8ByteLength(text: string): number {
  return new TextEncoder().encode(text).byteLength;
}

/** Length of the hex ciphertext for `inputFormat: "text"` (PKCS#7 always adds 1–8 bytes). */
export function desCiphertextHexLength(plaintextBytes: number): number {
  return 2 * (Math.floor(plaintextBytes / 8) * 8 + 8);
}

/**
 * Display-only: the 16-hex plaintext blocks the server encrypts for `inputFormat: "text"`
 * (UTF-8 + PKCS#7), e.g. to pick a block for `desTrace`. Never use it to build ciphertext.
 */
export function desPlaintextBlocksHex(text: string): string[] {
  const bytes = new TextEncoder().encode(text);
  const padding = 8 - (bytes.length % 8);
  const padded = new Uint8Array(bytes.length + padding);
  padded.set(bytes);
  padded.fill(padding, bytes.length);
  const hex = Array.from(padded, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return hex.toUpperCase().match(/.{16}/g) ?? [];
}

/** XOR two 16-hex blocks, e.g. `P1 ⊕ IV` to trace the first CBC block. */
export function xorHexBlocks(a: string, b: string): string {
  const value = BigInt(`0x${a}`) ^ BigInt(`0x${b}`);
  return value.toString(16).toUpperCase().padStart(16, "0");
}

function isDesResponse(value: unknown): value is DesResponse {
  if (typeof value !== "object" || value === null) return false;
  const body = value as Record<string, unknown>;
  return body.success === true && typeof body.result === "string" && Array.isArray(body.warnings);
}

export interface HillTextFile {
  filename: string;
  text: string;
  bytes: number;
}

export interface AttachmentResult {
  blob: Blob;
  filename: string;
}

export interface Health {
  app: "ok";
  database: "ok" | "disabled" | "unavailable";
  history: "enabled" | "disabled";
}

export interface HistoryItem {
  id: number;
  createdAt: string;
  cipher: Cipher;
  operation: Operation | null;
  source: "text" | "file";
  responseMode: ResponseMode | null;
  inputLength: number | null;
  outputLength: number | null;
  httpStatus: number;
  succeeded: boolean;
  durationMs: number;
}

export interface HistoryPage {
  items: HistoryItem[];
  nextCursor: string | null;
}

export interface HistoryQuery {
  limit?: number;
  cursor?: string;
  cipher?: Cipher;
  operation?: Operation;
}

const SYSTEM_ERROR = "Đã xảy ra lỗi hệ thống.";

/** A failure the server explained; show `message` to the user as-is. */
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
    public readonly details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface ErrorBody {
  success: false;
  message: string;
  code?: string;
  details?: Record<string, unknown>;
}

function isErrorBody(value: unknown): value is ErrorBody {
  if (typeof value !== "object" || value === null) return false;
  const body = value as Record<string, unknown>;
  return (
    body.success === false
    && typeof body.message === "string"
    && (body.code === undefined || typeof body.code === "string")
    && (
      body.details === undefined
      || (typeof body.details === "object" && body.details !== null && !Array.isArray(body.details))
    )
  );
}

/** Read `{"success": true, "result": ...}` or throw `ApiError` with the server message. */
async function readResult<T>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";
  if (!contentType.includes("application/json")) throw new ApiError(SYSTEM_ERROR, response.status);
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new ApiError(SYSTEM_ERROR, response.status);
  }
  if (isErrorBody(body)) {
    throw new ApiError(body.message, response.status, body.code, body.details);
  }
  const success = body as { success?: unknown; result?: unknown };
  if (response.status !== 200 || success.success !== true || success.result === undefined) {
    throw new ApiError(SYSTEM_ERROR, response.status);
  }
  return success.result as T;
}

/**
 * JSON integer token (no quotes, no `+`, no leading zeros) built without `number`.
 * Validate in the UI first; this only guards against sending a malformed body.
 */
function integerToken(raw: string, invalidMessage: string): string {
  const value = raw.trim();
  if (!/^[+-]?[0-9]+$/.test(value)) throw new Error(invalidMessage);
  return BigInt(value).toString();
}

function textBody(request: TextRequest): string {
  const text = JSON.stringify(request.text);
  switch (request.cipher) {
    case "caesar":
      return `{"text":${text},"key":${integerToken(request.key, "Khóa phải là số nguyên.")}}`;
    case "affine":
      return (
        `{"text":${text},"a":${integerToken(request.a, "Khóa a phải là số nguyên.")},`
        + `"b":${integerToken(request.b, "Khóa b phải là số nguyên.")}}`
      );
    default:
      return JSON.stringify({ text: request.text, key: request.key });
  }
}

/**
 * Encrypt or decrypt text. Returns the server `result`.
 * Playfair decrypt `result` is raw (fillers kept); use `playfairDecrypt` to also get `padding`.
 */
export async function transformText(request: TextRequest): Promise<string> {
  const response = await fetch(`/api/${request.cipher}/${request.operation}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: textBody(request),
  });
  return readResult<string>(response);
}

/** Hill uses a richer response and intentionally has no backend file endpoint. */
export async function transformHill(request: HillTransformRequest): Promise<HillTransformResponse> {
  const { operation, ...body } = request;
  const response = await fetch(`/api/hill/${operation}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";
  const payload: unknown = contentType.includes("application/json")
    ? await response.json()
    : null;
  if (isErrorBody(payload)) {
    throw new ApiError(payload.message, response.status, payload.code, payload.details);
  }
  if (response.status !== 200 || !isHillTransformResponse(payload)) {
    throw new ApiError(SYSTEM_ERROR, response.status);
  }
  return payload;
}

export async function analyzeHillKey(
  request: HillKeyInput,
): Promise<{ result: HillKeyAnalysis; warnings: HillWarning[] }> {
  const response = await fetch("/api/hill/key/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";
  const body = contentType.includes("application/json") ? await response.json() : null;
  if (isErrorBody(body)) {
    throw new ApiError(body.message, response.status, body.code, body.details);
  }
  if (response.status !== 200 || typeof body !== "object" || body === null) {
    throw new ApiError(SYSTEM_ERROR, response.status);
  }
  const success = body as {
    success?: unknown;
    result?: HillKeyAnalysis;
    warnings?: HillWarning[];
  };
  if (success.success !== true || success.result === undefined) {
    throw new ApiError(SYSTEM_ERROR, response.status);
  }
  return { result: success.result, warnings: success.warnings ?? [] };
}

export async function randomHillKey(
  m: 2 | 3 | 4,
): Promise<{ result: HillKeyAnalysis; warnings: HillWarning[] }> {
  const response = await fetch(`/api/hill/key/random?m=${m}`);
  const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";
  const body = contentType.includes("application/json") ? await response.json() : null;
  if (isErrorBody(body)) {
    throw new ApiError(body.message, response.status, body.code, body.details);
  }
  if (response.status !== 200 || typeof body !== "object" || body === null) {
    throw new ApiError(SYSTEM_ERROR, response.status);
  }
  const success = body as {
    success?: unknown;
    result?: HillKeyAnalysis;
    warnings?: HillWarning[];
  };
  if (success.success !== true || success.result === undefined) {
    throw new ApiError(SYSTEM_ERROR, response.status);
  }
  return { result: success.result, warnings: success.warnings ?? [] };
}

/**
 * Read a Hill .txt upload in the browser. Hill intentionally has no backend file route.
 * E07 is client-owned: invalid UTF-8 must not be sent to the backend.
 */
export async function readHillTextFile(file: File): Promise<HillTextFile> {
  if (!file.name.toLowerCase().endsWith(".txt")) {
    throw new ApiError("Chỉ chấp nhận file .txt.", 415);
  }
  const bytes = new Uint8Array(await file.arrayBuffer());
  if (bytes.byteLength > 5 * 1024 * 1024) {
    throw new ApiError(
      "Văn bản vượt quá giới hạn 5 MiB.",
      413,
      "E06",
      { actualBytes: bytes.byteLength, maxBytes: 5 * 1024 * 1024 },
    );
  }
  let text: string;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    throw new ApiError("File phải sử dụng UTF-8.", 415, "E07", {});
  }
  return { filename: file.name, text, bytes: bytes.byteLength };
}

function fileForm(request: FileRequest, responseMode: ResponseMode): FormData {
  const data = new FormData();
  data.append("file", request.file);
  if (request.cipher === "affine") {
    data.append("a", request.a);
    data.append("b", request.b);
  } else {
    data.append("key", request.key);
  }
  data.append("action", request.operation);
  data.append("response_mode", responseMode);
  if (request.cipher === "playfair" && request.stripPadding !== undefined) {
    data.append("strip_padding", String(request.stripPadding));
  }
  return data; // Never set Content-Type yourself; the browser adds the boundary.
}

/**
 * First request for a file: returns the transformed text for preview.
 * Playfair decrypt: use `playfairPreviewDecryptFile` to also get `padding`.
 */
export async function previewFile(request: FileRequest): Promise<string> {
  const response = await fetch(`/api/${request.cipher}/file`, {
    method: "POST",
    body: fileForm(request, "content"),
  });
  return readResult<string>(response);
}

function attachmentFilename(disposition: string): string | null {
  const utf8 = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8) {
    try {
      return decodeURIComponent(utf8[1]);
    } catch {
      // Fall back to the ASCII filename below.
    }
  }
  const quoted = disposition.match(/filename="((?:\\.|[^"])*)"/i);
  return quoted ? quoted[1].replace(/\\([\\"])/g, "$1") : null;
}

async function readAttachment(response: Response): Promise<AttachmentResult> {
  const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";
  if (response.status !== 200 || contentType.includes("application/json")) {
    await readResult<never>(response);
  }
  const filename = attachmentFilename(response.headers.get("content-disposition") ?? "");
  if (!contentType.startsWith("text/plain") || filename === null) {
    throw new ApiError(SYSTEM_ERROR, response.status);
  }
  return { blob: await response.blob(), filename };
}

/**
 * Second request for a file: the official attachment with the server's filename and BOM.
 * Playfair decrypt: pass `stripPadding` from the padding toggle to download the filtered text.
 */
export async function downloadFile(request: FileRequest): Promise<AttachmentResult> {
  const response = await fetch(`/api/${request.cipher}/file`, {
    method: "POST",
    body: fileForm(request, "file"),
  });
  return readAttachment(response);
}

// ---- Padding filter (Playfair/Hill decrypt) ----

async function readPlayfairDecrypt(response: Response): Promise<PlayfairDecryptResponse> {
  const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";
  if (!contentType.includes("application/json")) throw new ApiError(SYSTEM_ERROR, response.status);
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new ApiError(SYSTEM_ERROR, response.status);
  }
  if (isErrorBody(body)) throw new ApiError(body.message, response.status);
  const success = body as Record<string, unknown>;
  if (
    response.status !== 200
    || success.success !== true
    || typeof success.result !== "string"
    || !isPaddingInfo(success.padding)
  ) {
    throw new ApiError(SYSTEM_ERROR, response.status);
  }
  return { success: true, result: success.result, padding: success.padding };
}

/** Playfair text decrypt: raw `result` (fillers kept) plus `padding`. */
export async function playfairDecrypt(request: {
  text: string;
  key: string;
}): Promise<PlayfairDecryptResponse> {
  const response = await fetch("/api/playfair/decrypt", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: request.text, key: request.key }),
  });
  return readPlayfairDecrypt(response);
}

/** Preview of a Playfair file decrypt: always the raw `result` plus `padding`. */
export async function playfairPreviewDecryptFile(request: {
  file: File;
  key: string;
}): Promise<PlayfairDecryptResponse> {
  const response = await fetch("/api/playfair/file", {
    method: "POST",
    body: fileForm(
      { cipher: "playfair", operation: "decrypt", file: request.file, key: request.key },
      "content",
    ),
  });
  return readPlayfairDecrypt(response);
}

/** Text to show, copy or save for the "Tự động lọc ký tự đệm" toggle. */
export function displayedResult(
  response: { result: string; padding?: PaddingInfo },
  filterPadding: boolean,
): string {
  return filterPadding && response.padding ? response.padding.filtered : response.result;
}

/** String indexes of `result` holding padding letters, for highlighting the raw text. */
export function paddingCharIndexes(result: string, padding: PaddingInfo): number[] {
  const wanted = new Set(padding.positions);
  const indexes: number[] = [];
  let letter = 0;
  for (let index = 0; index < result.length; index += 1) {
    const code = result.charCodeAt(index);
    if ((code >= 65 && code <= 90) || (code >= 97 && code <= 122)) {
      if (wanted.has(letter)) indexes.push(index);
      letter += 1;
    }
  }
  return indexes;
}

/** Hill analysis: 1-based block/cell of each padding letter (e.g. block 4, cells 2-3). */
export function hillPaddingCells(
  padding: PaddingInfo,
  m: number,
): Array<{ block: number; cell: number }> {
  return padding.positions.map((position) => ({
    block: Math.floor(position / m) + 1,
    cell: (position % m) + 1,
  }));
}

// ---- DES helpers ----

async function readDes(response: Response): Promise<DesResponse> {
  const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";
  if (!contentType.includes("application/json")) throw new ApiError(SYSTEM_ERROR, response.status);
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new ApiError(SYSTEM_ERROR, response.status);
  }
  // DES errors never carry `code`/`details`: show `message` as-is.
  if (isErrorBody(body)) throw new ApiError(body.message, response.status);
  if (response.status !== 200 || !isDesResponse(body)) {
    throw new ApiError(SYSTEM_ERROR, response.status);
  }
  return body;
}

function isDesTraceResponse(value: DesResponse): value is DesTraceResponse {
  const trace = (value as { trace?: unknown }).trace;
  return typeof trace === "object" && trace !== null;
}

function postDesJson(path: string, body: Record<string, string | undefined>): Promise<Response> {
  return fetch(`/api/des/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body), // `undefined` fields are omitted; the server rejects unknown ones.
  });
}

/** Encrypt text (UTF-8 + PKCS#7) or hex blocks. Result is upper-case hex. ~6 s for 5 MiB. */
export async function desEncrypt(request: DesEncryptRequest): Promise<DesResponse> {
  const { text, key, inputFormat, mode, iv } = request;
  return readDes(await postDesJson("encrypt", { text, key, inputFormat, mode, iv }));
}

/**
 * Decrypt hex ciphertext (whitespace/newlines allowed) to text or raw hex.
 * A wrong CBC `iv` is not detected: only the first 8 bytes come out wrong and the
 * response can still be 200, so keep the IV next to the ciphertext.
 */
export async function desDecrypt(request: DesDecryptRequest): Promise<DesResponse> {
  const { text, key, outputFormat, mode, iv } = request;
  return readDes(await postDesJson("decrypt", { text, key, outputFormat, mode, iv }));
}

/** Every intermediate value for exactly one 16-hex block. Not recorded in server history. */
export async function desTrace(request: DesTraceRequest): Promise<DesTraceResponse> {
  const { block, key, operation } = request;
  const body = await readDes(await postDesJson("trace", { block, key, operation }));
  if (!isDesTraceResponse(body)) throw new ApiError(SYSTEM_ERROR, 200);
  return body;
}

function desFileForm(request: DesFileRequest, responseMode: ResponseMode): FormData {
  const data = new FormData();
  data.append("file", request.file);
  data.append("key", request.key);
  data.append("action", request.operation);
  if (request.mode !== undefined) data.append("mode", request.mode);
  if (request.mode === "CBC" && request.iv !== undefined) data.append("iv", request.iv);
  data.append("response_mode", responseMode);
  return data;
}

/** First request for a DES file: preview with warnings. */
export async function desPreviewFile(request: DesFileRequest): Promise<DesResponse> {
  const response = await fetch("/api/des/file", {
    method: "POST",
    body: desFileForm(request, "content"),
  });
  return readDes(response);
}

/** Second request for a DES file: `<name>.encrypted.txt` / `<name>.decrypted.txt`, no warnings. */
export async function desDownloadFile(request: DesFileRequest): Promise<AttachmentResult> {
  const response = await fetch("/api/des/file", {
    method: "POST",
    body: desFileForm(request, "file"),
  });
  return readAttachment(response);
}

/** Save a Blob with the given name (text results or a `downloadFile` attachment). */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** App and database status. Also answers "may I show the server history screen?". */
export async function getHealth(): Promise<Health> {
  const response = await fetch("/api/health");
  // 503 still carries the health body, so read it regardless of status.
  const body = (await response.json()) as { result: Health };
  return body.result;
}

export function canShowServerHistory(health: Health): boolean {
  return health.history === "enabled" && health.database === "ok";
}

/** One page of server history (metadata only). Pass `nextCursor` back verbatim. */
export async function getHistory(query: HistoryQuery = {}): Promise<HistoryPage> {
  const params = new URLSearchParams();
  for (const [name, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") params.set(name, String(value));
  }
  const response = await fetch(`/api/history?${params}`);
  return readResult<HistoryPage>(response);
}

// ---- Personal history on this device (never sent to the server) ----

export interface LocalHistoryEntry {
  at: string;
  cipher: Cipher;
  operation: Operation;
  source: "text" | "file";
  /** Text input, or the file name for `source: "file"`. */
  input: string;
  key:
    | { key: string }
    | { a: string; b: string }
    | HillKeyInput
    | { key: string; mode: DesMode; iv?: string; format: DesFormat };
  /** `null` for files: file contents are never stored. */
  result: string | null;
}

const LOCAL_HISTORY_KEY = "cipher-workbench.history.v1";
const LOCAL_HISTORY_ENABLED_KEY = "cipher-workbench.history.enabled";
const LOCAL_HISTORY_LIMIT = 50;

export function readLocalHistory(): LocalHistoryEntry[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(LOCAL_HISTORY_KEY) ?? "[]");
    return Array.isArray(parsed) ? (parsed as LocalHistoryEntry[]) : [];
  } catch {
    return [];
  }
}

export function isLocalHistoryEnabled(): boolean {
  try {
    return localStorage.getItem(LOCAL_HISTORY_ENABLED_KEY) !== "false";
  } catch {
    return false;
  }
}

export function setLocalHistoryEnabled(enabled: boolean): void {
  try {
    localStorage.setItem(LOCAL_HISTORY_ENABLED_KEY, String(enabled));
  } catch {
    // Storage blocked: the preference simply is not remembered.
  }
}

/** Call after every successful operation; keeps the newest 50 entries. */
export function addLocalHistory(entry: LocalHistoryEntry): void {
  if (!isLocalHistoryEnabled()) return;
  try {
    const next = [entry, ...readLocalHistory()].slice(0, LOCAL_HISTORY_LIMIT);
    localStorage.setItem(LOCAL_HISTORY_KEY, JSON.stringify(next));
  } catch {
    // Storage blocked or full: skip history, never break the cipher flow.
  }
}

export function clearLocalHistory(): void {
  try {
    localStorage.removeItem(LOCAL_HISTORY_KEY);
  } catch {
    // Nothing to clear.
  }
}
