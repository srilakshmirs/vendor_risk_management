import type {
  EvalReport,
  LLMInfo,
  ScoredVendor,
  VendorDetail,
  VendorListParams,
  VendorListResponse,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown, message?: string) {
    super(message ?? `API ${status}`);
    this.status = status;
    this.body = body;
  }
}

async function request<T>(path: string, init?: RequestInit & { isFormData?: boolean }): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!init?.isFormData) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      body = await res.text().catch(() => null);
    }
    throw new ApiError(res.status, body, `${init?.method ?? "GET"} ${path} → ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function qs(params: Record<string, unknown>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    sp.append(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

// ── Endpoint wrappers ─────────────────────────────────────────────
export const api = {
  health: () => request<{ status: string; environment: string; version: string }>("/healthz"),

  llmInfo: () => request<LLMInfo>("/llm/info"),

  listVendors: (params: VendorListParams = {}) =>
    request<VendorListResponse>(`/vendors${qs(params as Record<string, unknown>)}`),

  getVendor: (vendorId: string) =>
    request<VendorDetail>(`/vendors/${encodeURIComponent(vendorId)}`),

  scoreVendor: (vendorId: string, persist = true) =>
    request<ScoredVendor>(
      `/risk/score/${encodeURIComponent(vendorId)}${qs({ persist })}`,
      { method: "POST" },
    ),

  latestRisk: (vendorId: string) =>
    request<ScoredVendor | null>(
      `/risk/score/${encodeURIComponent(vendorId)}/latest`,
    ),

  scoreAll: () =>
    request<{ status: string; vendors: number; assessments_written: number }>(
      "/risk/score-all",
      { method: "POST" },
    ),

  eval: () => request<EvalReport>("/risk/eval"),

  extractContract: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<any>("/contracts/extract", {
      method: "POST",
      body: formData,
      isFormData: true,
    });
  },
};

export { ApiError };
