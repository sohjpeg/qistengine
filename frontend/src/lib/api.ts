/** Typed fetch client. 30s timeout via AbortController, one retry on network failure. */
import type {
  ApplicationDetail,
  MetricsResponse,
  ModelInfoResponse,
  MockProfile,
  PaginatedApplications,
  ParseBillResponse,
  ParseTransactionsResponse,
  ScoreResponse,
} from "./types";

const BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: string;
  offline: boolean;
  constructor(message: string, status: number, detail: string, offline = false) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.offline = offline;
  }
}

const OFFLINE_MESSAGE =
  "The demo server is waking up (free instance, sleeps after 15 min idle). Give it ~40s and retry.";

// The hosted backend is a free instance that cold-starts in 30–50s. Render holds
// the request open while it boots, so a long timeout usually lets the first call
// succeed on its own; the retry only covers a genuine transient blip.
async function request<T>(
  path: string,
  init?: RequestInit & { retries?: number },
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 55_000);
  const retries = init?.retries ?? 1;
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...init?.headers,
      },
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      } catch {
        /* keep statusText */
      }
      throw new ApiError(`Request failed (${res.status})`, res.status, detail);
    }
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (retries > 0) {
      await new Promise((r) => setTimeout(r, 1500));
      return request<T>(path, { ...init, retries: retries - 1 });
    }
    throw new ApiError(OFFLINE_MESSAGE, 0, OFFLINE_MESSAGE, true);
  } finally {
    clearTimeout(timeout);
  }
}

export const api = {
  health: () =>
    request<{ status: string; model_loaded: boolean; model_version: string | null; model_error: string | null }>(
      "/health",
    ),

  modelInfo: () => request<ModelInfoResponse>("/api/v1/model/info"),

  score: (payload: {
    features?: Record<string, number>;
    bill_fields?: Record<string, unknown>;
    transaction_aggregates?: Record<string, unknown>;
    archetype_hint?: string;
    tenor_months?: number;
    applicant_id?: string;
  }) =>
    request<ScoreResponse>("/api/v1/score", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  mockProfiles: () => request<MockProfile[]>("/api/v1/mock/profiles"),

  parseBill: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<ParseBillResponse>("/api/v1/parse-bill", { method: "POST", body: fd });
  },

  /** Several monthly exports aggregate into one ledger server-side. */
  parseTransactions: (files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    return request<ParseTransactionsResponse>("/api/v1/parse-transactions", {
      method: "POST",
      body: fd,
    });
  },

  createApplication: (payload: unknown) =>
    request<ApplicationDetail>("/api/v1/applications", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listApplications: (params: Record<string, string | number | undefined> = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "") q.set(k, String(v));
    });
    const qs = q.toString();
    return request<PaginatedApplications>(`/api/v1/applications${qs ? `?${qs}` : ""}`);
  },

  getApplication: (id: string) => request<ApplicationDetail>(`/api/v1/applications/${id}`),

  recordDecision: (id: string, payload: unknown) =>
    request<ApplicationDetail>(`/api/v1/applications/${id}/decision`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  metrics: () => request<MetricsResponse>("/api/v1/metrics"),
};

export { BASE as API_BASE };
