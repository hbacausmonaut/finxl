/**
 * The seam between the UI and the FinXL API (api/main.py). Every call sends the
 * browser's anonymous visitor id, which is how the server files runs and
 * corrections per reader without accounts.
 */
import { toWorkbook, type ApiRun } from "./adapter"
import type { Company, CrossCheckRow, ExtractionRequest, ReportRef, ReviewState, RunRecord, Workbook } from "./types"

/** Same origin in production (FastAPI serves the app); `next dev` proxies /api to the local server. */
const BASE = process.env.NEXT_PUBLIC_API_BASE ?? ""

let visitor: string | null = null
export function visitorId(): string {
  if (visitor) return visitor
  try {
    visitor = window.localStorage.getItem("finxl.visitor")
    if (!visitor) {
      visitor = crypto.randomUUID()
      window.localStorage.setItem("finxl.visitor", visitor)
    }
  } catch {
    visitor ??= `v-${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`
  }
  return visitor
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message)
  }
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "X-Visitor": visitorId(), ...(init.body ? { "Content-Type": "application/json" } : {}), ...init.headers },
    })
  } catch {
    throw new ApiError("Can't reach the FinXL server. Check your connection and try again.", 0)
  }
  if (!res.ok) {
    let msg = `The server answered ${res.status}.`
    try {
      const body = await res.json()
      msg = body.error ?? body.detail ?? msg
      if (Array.isArray(msg)) msg = "That request wasn't valid."
    } catch {
      /* not JSON */
    }
    throw new ApiError(String(msg), res.status)
  }
  return res.json() as Promise<T>
}

// ─── Config ───────────────────────────────────────────────────────────────────

export interface ServerConfig {
  version: string
  ai: { available: boolean; model: string }
  limits: { maxYears: number; runsPerDay: number | null }
}
let configPromise: Promise<ServerConfig> | null = null
export const getConfig = () => (configPromise ??= call<ServerConfig>("/api/config").catch((e) => {
  configPromise = null
  throw e
}))

// ─── Companies ────────────────────────────────────────────────────────────────

/** NSE's equity list, bundled with the app (dev/scripts/build_companies.py), so typing stays instant. */
let companies: Company[] = []
let companiesPromise: Promise<Company[]> | null = null
export function loadCompanies(): Promise<Company[]> {
  companiesPromise ??= fetch("/companies.json")
    .then((r) => (r.ok ? r.json() : []))
    .then((list: Array<[string, string]>) => (companies = list.map(([symbol, name]) => ({ symbol, name }))))
    .catch(() => (companies = []))
  return companiesPromise
}

export function searchCompanies(q: string, limit = 8): Company[] {
  const s = q.trim().toLowerCase()
  if (!s) return []
  const score = (c: Company) => {
    const sym = c.symbol.toLowerCase(), name = c.name.toLowerCase()
    return sym === s ? 0 : sym.startsWith(s) ? 1 : name.startsWith(s) ? 2 : name.split(/\s+/).some((w) => w.startsWith(s)) ? 3 : sym.includes(s) || name.includes(s) ? 4 : 9
  }
  const out: Array<[number, Company]> = []
  for (const c of companies) {
    const n = score(c)
    if (n < 9) out.push([n, c])
  }
  return out.sort((a, b) => a[0] - b[0] || a[1].symbol.length - b[1].symbol.length).slice(0, limit).map(([, c]) => c)
}

export const getCompany = (symbol: string): Company | undefined => companies.find((c) => c.symbol === symbol.toUpperCase())

export const isTicker = (s: string) => /^[A-Z0-9&_-]{1,20}$/.test(s.trim().toUpperCase())

/** finxl.list_reports(ticker): the annual reports on Screener. One page fetch, cached a day on the server. */
export const listReports = (symbol: string) =>
  call<{ symbol: string; name: string; url: string; reports: ReportRef[] }>(`/api/companies/${encodeURIComponent(symbol.toUpperCase())}/reports`)

// ─── Runs ─────────────────────────────────────────────────────────────────────

export const startRun = (req: ExtractionRequest) => call<RunRecord>("/api/runs", { method: "POST", body: JSON.stringify(req) })
export const listRuns = () => call<RunRecord[]>("/api/runs")
export const getRun = (id: string) => call<RunRecord>(`/api/runs/${id}`)
export const removeRun = (id: string) => call<{ ok: boolean }>(`/api/runs/${id}`, { method: "DELETE" })
/** `next dev` buffers proxied event streams, so in development the stream comes straight from the API. */
const EVENTS_BASE = process.env.NODE_ENV === "development" ? (process.env.NEXT_PUBLIC_DEV_API ?? "http://127.0.0.1:8000") : BASE
export const eventsUrl = (id: string) => `${EVENTS_BASE}/api/runs/${id}/events`

const workbooks = new Map<string, Promise<Workbook>>()
export function getWorkbook(id: string): Promise<Workbook> {
  let p = workbooks.get(id)
  if (!p) {
    p = call<ApiRun>(`/api/runs/${id}/workbook`).then(toWorkbook)
    p.catch(() => workbooks.delete(id))
    workbooks.set(id, p)
  }
  return p
}

export const getReview = (id: string) => call<ReviewState>(`/api/runs/${id}/review`)
export const putReview = (id: string, review: ReviewState) => call<{ ok: boolean }>(`/api/runs/${id}/review`, { method: "PUT", body: JSON.stringify(review) })

/** write_workbook with the reader's corrections marked. A plain link, so the browser downloads it. */
export const xlsxUrl = (id: string) => `${BASE}/api/runs/${id}/xlsx?visitor=${encodeURIComponent(visitorId())}`

export async function crossCheck(id: string): Promise<{ rows: CrossCheckRow[]; perSource: Record<string, { checked: number; match: number }> }> {
  const data = await call<{ results: Array<Omit<CrossCheckRow, "fy"> & { year: number }>; perSource: Record<string, { checked: number; match: number }> }>(`/api/runs/${id}/crosscheck`)
  return { rows: data.results.map(({ year, ...r }) => ({ ...r, fy: year })), perSource: data.perSource }
}

// ─── Report pages ─────────────────────────────────────────────────────────────

export const pdfUrl = (symbol: string, fy: number) => `${BASE}/api/pdf/${symbol}/${fy}.pdf`

/** One report page as an image, with the figure (or its label) highlighted. */
export function pageImageUrl(symbol: string, fy: number, page: string, find?: { value?: number; label?: string }) {
  const q = new URLSearchParams()
  if (find?.value !== undefined) q.set("value", String(find.value))
  if (find?.label) q.set("label", find.label)
  const qs = q.toString()
  return `${BASE}/api/pdf/${symbol}/${fy}/page/${encodeURIComponent(page)}.png${qs ? `?${qs}` : ""}`
}

// ─── AI ───────────────────────────────────────────────────────────────────────

/** llm_extract.check_backend, with the server's key. */
export const testAiConnection = () => call<{ ok: boolean; message: string }>("/api/ai/test", { method: "POST" })
