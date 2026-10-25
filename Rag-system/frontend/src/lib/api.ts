// One place that talks to the backend: adds the token, renews it when it
// expires, and turns every failure into an ApiError the UI can translate.

export class ApiError extends Error {
  status: number;
  code: string;
  retryAfter?: number;

  constructor(status: number, code: string, message: string, retryAfter?: number) {
    super(message);
    this.status = status;
    this.code = code;
    this.retryAfter = retryAfter;
  }
}

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "";
const REFRESH_KEY = "rag.refresh_token";

export interface User {
  id: string;
  email: string | null;
  phone: string | null;
  name: string | null;
  role: "user" | "admin";
  email_verified: boolean;
  phone_verified: boolean;
  is_active: boolean;
  created_at: number;
}

export interface Tokens {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  refresh_token: string;
  user: User;
}

// the access token lives in memory only; the refresh token survives a reload
let accessToken: string | null = null;
let onSessionLost: (() => void) | null = null;
let refreshing: Promise<boolean> | null = null;

export const session = {
  getRefreshToken: () => localStorage.getItem(REFRESH_KEY),
  set(tokens: Tokens) {
    accessToken = tokens.access_token;
    localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
  },
  clear() {
    accessToken = null;
    localStorage.removeItem(REFRESH_KEY);
  },
  onLost(handler: () => void) {
    onSessionLost = handler;
  },
};

async function parseError(response: Response): Promise<ApiError> {
  let code = "http_" + response.status;
  let message = response.statusText || "Request failed";

  try {
    const data = await response.json();
    const detail = data?.detail;

    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      code = detail.code ?? code;
      message = detail.message ?? message;
    } else if (Array.isArray(detail)) {
      code = "validation";
      message = detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ") || message;
    } else if (typeof detail === "string") {
      message = detail;
    } else if (data?.signal) {
      code = String(data.signal);
    }
  } catch {
    /* body was not JSON */
  }

  const retry = Number(response.headers.get("Retry-After"));
  return new ApiError(response.status, code, message, Number.isFinite(retry) && retry > 0 ? retry : undefined);
}

async function rawFetch(path: string, init: RequestInit, auth: boolean): Promise<Response> {
  const headers = new Headers(init.headers);

  if (auth && accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  try {
    return await fetch(BASE + path, { ...init, headers });
  } catch {
    throw new ApiError(0, "network_error", "Cannot reach the server.");
  }
}

/** Gets a new access token with the refresh token. Many calls share one request. */
export function refreshSession(): Promise<boolean> {
  if (refreshing) return refreshing;

  const token = session.getRefreshToken();
  if (!token) return Promise.resolve(false);

  refreshing = (async () => {
    try {
      const response = await rawFetch("/api/v1/auth/refresh", { method: "POST", body: JSON.stringify({ refresh_token: token }) }, false);
      if (!response.ok) return false;
      session.set((await response.json()) as Tokens);
      return true;
    } catch {
      return false;
    } finally {
      refreshing = null;
    }
  })();

  return refreshing;
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean;
  signal?: AbortSignal;
}

export async function api<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = options.body !== undefined ? "POST" : "GET", body, auth = true, signal } = options;

  const init: RequestInit = {
    method,
    signal,
    body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
  };

  let response = await rawFetch(path, init, auth);

  // an expired access token is renewed once, silently
  if (auth && response.status === 401) {
    const error = await parseError(response.clone());

    if (["token_expired", "invalid_token", "missing_token"].includes(error.code) && (await refreshSession())) {
      response = await rawFetch(path, init, auth);
    }

    if (response.status === 401) {
      session.clear();
      onSessionLost?.();
    }
  }

  if (!response.ok) throw await parseError(response);

  if (response.status === 204) return undefined as T;

  return (await response.json()) as T;
}
