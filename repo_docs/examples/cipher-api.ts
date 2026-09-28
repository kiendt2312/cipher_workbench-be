/**
 * Framework-neutral API client for the cipher backend.
 *
 * Copy this file into the FE project. It only uses `fetch`, `FormData`, `Blob`
 * and `localStorage`, calls relative `/api/...` URLs (same origin or dev proxy)
 * and follows repo_docs/frontend-integration.md. Results always come from the server.
 */

export type Cipher = "caesar" | "vigenere" | "playfair" | "affine" | "columnar";
export type Operation = "encrypt" | "decrypt";
export type ResponseMode = "content" | "file";

/** Raw UI values: keep them as strings; never parse integer keys through `number`. */
export type KeyInput =
  | { cipher: "caesar"; key: string }
  | { cipher: "vigenere" | "playfair" | "columnar"; key: string }
  | { cipher: "affine"; a: string; b: string };

export type TextRequest = KeyInput & { operation: Operation; text: string };
export type FileRequest = KeyInput & { operation: Operation; file: File };

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
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

function isErrorBody(value: unknown): value is { success: false; message: string } {
  if (typeof value !== "object" || value === null) return false;
  const body = value as Record<string, unknown>;
  return body.success === false && typeof body.message === "string";
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
  if (isErrorBody(body)) throw new ApiError(body.message, response.status);
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

/** Encrypt or decrypt text. Returns the server `result`. */
export async function transformText(request: TextRequest): Promise<string> {
  const response = await fetch(`/api/${request.cipher}/${request.operation}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: textBody(request),
  });
  return readResult<string>(response);
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
  return data; // Never set Content-Type yourself; the browser adds the boundary.
}

/** First request for a file: returns the transformed text for preview. */
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

/** Second request for a file: the official attachment with the server's filename and BOM. */
export async function downloadFile(request: FileRequest): Promise<AttachmentResult> {
  const response = await fetch(`/api/${request.cipher}/file`, {
    method: "POST",
    body: fileForm(request, "file"),
  });
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
  key: Record<string, string>;
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
