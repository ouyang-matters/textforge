/** Thin wrapper around backend API calls — works both via Tauri invoke and direct fetch. */

const API_BASE = "http://127.0.0.1:18157";

let tauriInvoke: ((cmd: string, args?: Record<string, unknown>) => Promise<string>) | null = null;

try {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const tauri = (window as any).__TAURI__;
  if (tauri?.invoke) {
    tauriInvoke = tauri.invoke;
  }
} catch {
  // running outside Tauri (dev mode in browser)
}

async function post<T = any>(path: string, body: unknown): Promise<T> {
  if (tauriInvoke) {
    const raw = await tauriInvoke("invoke_api", { path, body: JSON.stringify(body) });
    return JSON.parse(raw);
  }
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error (${res.status}): ${text}`);
  }
  return res.json();
}

async function get<T = any>(path: string): Promise<T> {
  if (tauriInvoke) {
    const raw = await tauriInvoke("get_api", { path });
    return JSON.parse(raw);
  }
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API error (${res.status})`);
  return res.json();
}

/* ---- Typed API calls ---- */

export interface RewriteResult {
  artifact_id: string;
  text: string;
  original_text: string;
  metrics: Record<string, number | string | null>;
  validation: { passed: boolean; issues: string[] };
}

export interface CompareResult {
  metrics: Record<string, number>;
  quality: { passed: boolean; issues: string[] };
  number_preservation: { passed: boolean; missing: string[]; added: string[] };
  entity_preservation: { score: number; missing: string[]; added: string[] };
}

export interface ChatResponse {
  role: string;
  content: string;
  rewritten_content: string | null;
  artifact_id: string | null;
  metrics: Record<string, number | string | null>;
}

export const api = {
  health: () => get<{ status: string; provider_configured: boolean; chat_configured: boolean }>("/health"),

  rewrite: (body: {
    text: string;
    strength: string;
    style: string;
    preserve_meaning?: boolean;
    preserve_numbers?: boolean;
    preserve_formulas?: boolean;
    preserve_citations?: boolean;
    preserve_names?: boolean;
    preserve_technical?: boolean;
    locked_spans?: { start: number; end: number }[];
  }) => post<RewriteResult>("/api/rewrite", body),

  compare: (original: string, rewritten: string) =>
    post<CompareResult>("/api/compare", { original, rewritten }),

  chat: (body: {
    messages: { role: string; content: string }[];
    model?: string;
    max_tokens?: number;
    temperature?: number | null;
    system_prompt?: string | null;
    auto_rewrite?: boolean;
    rewrite_strength?: string;
    rewrite_style?: string;
    display_mode?: string;
    stream?: boolean;
  }) => post<ChatResponse>("/api/chat", { ...body, stream: false }),

  configureProvider: (api_key: string, model?: string) =>
    post<{ ok: boolean }>("/api/provider/configure", { api_key, model }),

  testProvider: (api_key: string) =>
    post<{ ok: boolean; error?: string; model?: string }>("/api/provider/test", { api_key }),

  getSettings: () => get<Record<string, any>>("/api/settings"),
};

/* ---- Tauri key storage ---- */

export async function setApiKey(key: string): Promise<void> {
  if (tauriInvoke) {
    await tauriInvoke("set_api_key", { service: "anthropic", key });
  } else {
    localStorage.setItem("tf_api_key", key);
  }
}

export async function getApiKey(): Promise<string | null> {
  if (tauriInvoke) {
    try {
      return await tauriInvoke("get_api_key", { service: "anthropic" }) as unknown as string;
    } catch {
      return null;
    }
  }
  return localStorage.getItem("tf_api_key");
}
