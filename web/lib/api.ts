/**
 * The seam between the UI and the engine. Each function names the engine call
 * it stands in for; today they answer from mock data, with realistic delays
 * where the real call is slow. Replace the bodies to go live.
 */
import { COMPANIES, findCompany, reportsFor } from "./mock/companies"
import { buildWorkbook } from "./mock/workbook"
import { fileName } from "./run"
import type { Company, ExtractionRequest, ReportRef, ReviewState, RunRecord, Workbook } from "./types"

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

/** A bundled symbol list, so typing stays instant. (Engine: none yet; it takes a ticker as typed.) */
export function searchCompanies(q: string, limit = 8): Company[] {
  const s = q.trim().toLowerCase()
  if (!s) return COMPANIES.slice(0, limit)
  const score = (c: Company) =>
    c.symbol.toLowerCase().startsWith(s) ? 0 : c.name.toLowerCase().startsWith(s) ? 1 : c.symbol.toLowerCase().includes(s) || c.name.toLowerCase().includes(s) ? 2 : c.sector.toLowerCase().includes(s) ? 3 : 9
  return COMPANIES.map((c) => [score(c), c] as const)
    .filter(([n]) => n < 9)
    .sort((a, b) => a[0] - b[0])
    .slice(0, limit)
    .map(([, c]) => c)
}

export const getCompany = (symbol: string) => findCompany(symbol)

/** finxl.list_reports(ticker): one Screener page fetch, so it takes a moment. */
export async function listReports(symbol: string): Promise<ReportRef[]> {
  await sleep(450 + Math.random() * 350)
  return reportsFor(symbol)
}

export const newRunId = () => `r_${Math.random().toString(36).slice(2, 8)}`

/** finxl.run result for a finished run. */
export const getWorkbook = (run: Pick<RunRecord, "id" | "request">): Workbook => buildWorkbook(run.id, run.request)

/** write_workbook: the .xlsx the engine saves. Mocked: nothing is written. */
export async function downloadExcel(wb: Workbook, review: ReviewState) {
  await sleep(700)
  const edits = Object.keys(review.edits).length + Object.keys(review.labels).length
  return { filename: fileName(wb.request, wb.years), edits }
}

/** llm_extract.check_backend */
export async function testAiConnection(engine: "gemini" | "ollama", hasKey: boolean) {
  await sleep(900)
  if (engine === "gemini" && !hasKey) return { ok: false, message: "Enter a Gemini API key first." }
  return { ok: true, message: engine === "gemini" ? "Gemini answered. Free tier: expect waits at busy times." : "Ollama is running locally with this model." }
}

const HOUR = 3600_000
const sample = (
  id: string,
  symbol: string,
  from: number,
  to: number,
  scope: ExtractionRequest["scope"],
  hoursAgo: number,
  extra: Partial<RunRecord> = {}
): RunRecord => ({
  id,
  request: { symbol, from, to, scope, figures: "restated", ai: "off" },
  companyName: findCompany(symbol)?.name ?? symbol,
  startedAt: Date.now() - hoursAgo * HOUR,
  status: "done",
  durationSec: 40 + ((to - from) * 9),
  confirmedPct: 96.4,
  issues: 0,
  sample: true,
  ...extra,
})

/** Example library rows so the demo doesn't open empty. */
export const sampleRuns = (): RunRecord[] => [
  sample("s_vardhan", "VARDHANSPL", 2021, 2026, "consolidated", 3, { confirmedPct: 97.8, issues: 5 }),
  sample("s_pidilite", "PIDILITIND", 2020, 2026, "both", 26, { confirmedPct: 98.9, issues: 1 }),
  sample("s_hcl", "HCLTECH", 2019, 2026, "consolidated", 50, { confirmedPct: 99.2 }),
  sample("s_ntpc", "NTPC", 2022, 2026, "standalone", 98, { confirmedPct: 95.1, issues: 7 }),
  sample("s_vinati", "VINATIORGA", 2021, 2025, "standalone", 170, { confirmedPct: 97.3, issues: 2 }),
  sample("s_supreme", "SUPREMEIND", 2012, 2016, "standalone", 290, {
    status: "failed",
    error: "No financial statements could be extracted: these reports are scans with no text layer. Turn on the AI fallback in Settings and run again.",
    confirmedPct: undefined,
    durationSec: 21,
  }),
]
