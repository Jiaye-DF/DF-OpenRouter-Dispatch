import type { ApiResponse } from "@/types/api";
import { localizeError } from "./error-map";

// API Client：封裝 fetch，統一處理 Cookie、統一回應格式、401 自動 refresh 重試

export class ApiError extends Error {
  readonly status: number;
  readonly code: number;
  readonly detail: string;
  readonly payload: ApiResponse<unknown> | null;

  constructor(
    status: number,
    code: number,
    detail: string,
    payload: ApiResponse<unknown> | null = null
  ) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
    this.payload = payload;
  }

  // 後端錯誤碼經 error-map 中文化後的顯示訊息
  get localizedDetail(): string {
    return localizeError(this.detail);
  }

  // 結構化錯誤酬載(如 sync_throttled.retry_after_seconds、tier_in_use.using_models)
  get data(): unknown {
    return this.payload?.data ?? null;
  }
}

// 取得後端 Base URL；禁止硬編
function getBaseUrl(): string {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!base) {
    // dev 時允許空字串（走相對路徑 / proxy）
    return "";
  }
  return base.replace(/\/$/, "");
}

export interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  query?: Record<string, string | number | boolean | null | undefined>;
  // 預設 true；僅 refresh 端點會關閉以避免遞迴
  autoRefreshOn401?: boolean;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const base = getBaseUrl();
  const url = new URL(
    path.startsWith("http") ? path : `${base}${path}`,
    typeof window === "undefined" ? "http://localhost" : window.location.origin
  );
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null) continue;
      url.searchParams.append(key, String(value));
    }
  }
  if (path.startsWith("http")) return url.toString();
  return `${base}${url.pathname}${url.search}`;
}

// 單一 in-flight refresh Promise，避免瞬間雙重 refresh
let refreshInflight: Promise<boolean> | null = null;

async function refreshToken(): Promise<boolean> {
  if (refreshInflight) return refreshInflight;
  refreshInflight = (async () => {
    try {
      const res = await fetch(`${getBaseUrl()}/api/v1/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      });
      return res.ok;
    } catch {
      return false;
    } finally {
      // 稍延後釋放，避免連續請求打到同一把舊 refresh
      setTimeout(() => {
        refreshInflight = null;
      }, 0);
    }
  })();
  return refreshInflight;
}

async function rawRequest<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { body, query, headers, autoRefreshOn401 = true, ...rest } = options;

  const init: RequestInit = {
    ...rest,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(headers as Record<string, string> | undefined),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  };

  const url = buildUrl(path, query);
  const res = await fetch(url, init);

  // 解析 JSON（容錯：後端可能回非 JSON）
  let payload: ApiResponse<T> | null = null;
  try {
    payload = (await res.json()) as ApiResponse<T>;
  } catch {
    payload = null;
  }

  if (res.status === 401 && autoRefreshOn401 && path !== "/api/v1/auth/refresh") {
    const refreshed = await refreshToken();
    if (refreshed) {
      return rawRequest<T>(path, { ...options, autoRefreshOn401: false });
    }
    throw new ApiError(
      401,
      payload?.code ?? 401,
      payload?.detail ?? "unauthorized",
      payload
    );
  }

  if (!res.ok) {
    throw new ApiError(
      res.status,
      payload?.code ?? res.status,
      payload?.detail ?? `HTTP ${res.status}`,
      payload
    );
  }

  if (!payload) {
    throw new ApiError(res.status, res.status, "invalid_response", null);
  }
  if (!payload.success) {
    throw new ApiError(res.status, payload.code, payload.detail, payload);
  }
  return payload.data as T;
}

export const apiClient = {
  get: <T>(path: string, opts?: RequestOptions) =>
    rawRequest<T>(path, { ...opts, method: "GET" }),
  post: <T>(path: string, body?: unknown, opts?: RequestOptions) =>
    rawRequest<T>(path, { ...opts, method: "POST", body }),
  patch: <T>(path: string, body?: unknown, opts?: RequestOptions) =>
    rawRequest<T>(path, { ...opts, method: "PATCH", body }),
  put: <T>(path: string, body?: unknown, opts?: RequestOptions) =>
    rawRequest<T>(path, { ...opts, method: "PUT", body }),
  delete: <T>(path: string, opts?: RequestOptions) =>
    rawRequest<T>(path, { ...opts, method: "DELETE" }),
};
