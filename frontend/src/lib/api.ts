import type {
  AlertItem,
  ListingCard,
  ListingDetail,
  Meta,
  ModelOverview,
  SavedSearch,
  SearchFilters,
  SearchResponse,
  Tco,
  Vehicle,
  WatchItem,
  Weights,
  Issue,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* not json */
    }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

const post = <T,>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
const put = <T,>(path: string, body: unknown) => request<T>(path, { method: "PUT", body: JSON.stringify(body) });
const del = <T,>(path: string) => request<T>(path, { method: "DELETE" });

export interface SearchRequest {
  filters: SearchFilters;
  sort: string;
  weights?: Weights;
  page?: number;
  page_size?: number;
  profile_id?: number | null;
}

export const api = {
  meta: () => request<Meta>("/api/meta"),
  search: (req: SearchRequest) => post<SearchResponse>("/api/search", req),
  exportCsv: async (req: SearchRequest) => {
    const res = await fetch("/api/search/export.csv", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "autozoeker-export.csv";
    a.click();
    URL.revokeObjectURL(url);
  },
  listing: (id: number, profileId?: number | null) =>
    request<ListingDetail>(`/api/listings/${id}${profileId ? `?profile_id=${profileId}` : ""}`),
  checklist: (id: number) =>
    request<{
      listing: ListingCard;
      sections: { title: string; items: string[] }[];
      model_issues: {
        title: string;
        severity: string;
        certainty: string;
        recall_status: string | null;
        questions: string[];
        verify: string[];
        test_drive: string[];
      }[];
    }>(`/api/listings/${id}/checklist`),
  tco: (id: number, input: Record<string, unknown>, profileId?: number | null) =>
    post<Tco>(`/api/listings/${id}/tco${profileId ? `?profile_id=${profileId}` : ""}`, input),
  feedback: (id: number, profileId: number, value: number) =>
    post<{ ok: boolean; learned_weights: Weights }>(`/api/listings/${id}/feedback`, { profile_id: profileId, value }),
  adScan: (id: number, force = false) =>
    post<{
      summary: string;
      flags: { title: string; severity: string; detail: string }[];
      questions: string[];
      positives: string[];
      cost_usd: number | null;
    }>(`/api/listings/${id}/ad-scan${force ? "?force=true" : ""}`),
  compare: (ids: number[], profileId?: number | null, kmPerYear = 13000) =>
    post<{ items: (ListingCard & { vehicle: Vehicle | null; issues: Issue[]; tco: Tco; ev: unknown })[] }>(
      "/api/compare",
      { ids, profile_id: profileId, km_per_year: kmPerYear },
    ),
  importUrl: (url: string) => post<{ id: number }>("/api/import", { url }),
  kenteken: (plate: string, refresh = false) =>
    request<{ kenteken: string; vehicle: Vehicle | null; available: boolean; listings: (ListingCard & { price_history: { date: string; price: number }[] })[]; issues: Issue[] }>(
      `/api/kenteken/${encodeURIComponent(plate)}${refresh ? "?refresh_data=true" : ""}`,
    ),
  parseSearch: (text: string) =>
    post<{ filters: SearchFilters; explanation: string; sort: string; engine: string }>("/api/ai/parse-search", { text }),
  issues: () =>
    request<{
      curated: Meta["issue_coverage"];
      ai: { key: string; make: string; model: string; title: string; created_at: string; cost_usd: number }[];
    }>("/api/issues"),
  issuesForModel: (make: string, model: string) =>
    request<{
      make: string;
      model: string;
      title: string;
      overview: ModelOverview | null;
      ai_research: { created_at: string; cost_usd: number; model: string } | null;
      ai_available: boolean;
    }>(`/api/issues/${make}/${model}`),
  research: (make: string, model: string, force = false) =>
    post<{ cost_usd: number; web_searches: number }>(`/api/issues/${make}/${model}/research${force ? "?force=true" : ""}`),
  insights: (make: string, model?: string, fuel?: string) => {
    const p = new URLSearchParams();
    if (model) p.set("model", model);
    if (fuel) p.set("fuel", fuel);
    return request<Record<string, any>>(`/api/insights/${make}?${p.toString()}`);
  },
  deals: () => request<{ items: ListingCard[] }>("/api/insights/deals"),
  savedSearches: (profileId: number) => request<SavedSearch[]>(`/api/saved-searches?profile_id=${profileId}`),
  createSavedSearch: (body: Partial<SavedSearch> & { profile_id: number; name: string; filters: SearchFilters }) =>
    post<SavedSearch>("/api/saved-searches", body),
  updateSavedSearch: (id: number, body: Partial<SavedSearch>) => put<SavedSearch>(`/api/saved-searches/${id}`, body),
  deleteSavedSearch: (id: number) => del<{ ok: boolean }>(`/api/saved-searches/${id}`),
  watchlist: () => request<{ statuses: string[]; items: WatchItem[] }>("/api/watchlist"),
  addWatch: (listingId: number, profileId?: number | null) =>
    post<{ id: number }>("/api/watchlist", { listing_id: listingId, profile_id: profileId }),
  updateWatch: (id: number, body: { status?: string; notes?: string; checklist_state?: Record<string, boolean> }) =>
    put<{ ok: boolean }>(`/api/watchlist/${id}`, body),
  deleteWatch: (id: number) => del<{ ok: boolean }>(`/api/watchlist/${id}`),
  feed: (profileId: number, days = 7) => request<{ items: ListingCard[] }>(`/api/feed?profile_id=${profileId}&days=${days}`),
  alerts: (profileId: number) => request<{ unseen: number; items: AlertItem[] }>(`/api/alerts?profile_id=${profileId}`),
  markAlertsSeen: (profileId: number) => post<{ ok: boolean }>(`/api/alerts/seen?profile_id=${profileId}`),
  profiles: () =>
    request<{ id: number; name: string; home_postcode: string | null; ntfy_topic: string | null; weights: Weights; learned_weights: Weights }[]>(
      "/api/profiles",
    ),
  updateProfile: (id: number, body: { home_postcode?: string | null; ntfy_topic?: string | null; weights?: Weights }) =>
    put<{ ok: boolean }>(`/api/profiles/${id}`, body),
  testPush: (id: number) => post<{ ok: boolean }>(`/api/profiles/${id}/test-push`),
  status: () => request<Record<string, any>>("/api/status"),
  crawlNow: () => post<{ started: boolean }>("/api/admin/crawl"),
  retrain: () => post<{ started: boolean }>("/api/admin/retrain"),
};
