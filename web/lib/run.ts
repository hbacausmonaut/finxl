import { computeAll, qualityOf } from "./compute"
import { fyLabel, fyRange } from "./fy"
import { reportsFor } from "./mock/companies"
import { rand } from "./mock/generate"
import { buildWorkbook, pagesFor } from "./mock/workbook"
import { KINDS, SHEETS } from "./sheets"
import { EMPTY_REVIEW, type ExtractionRequest, type FiscalYear, type RunEvent, type RunRecord, type StageId } from "./types"

/** The five things finxl.run does, in order. */
export const STAGES: Array<{ id: StageId; title: string; doing: string }> = [
  { id: "lookup", title: "Find reports", doing: "Looking up the annual reports on file" },
  { id: "download", title: "Download PDFs", doing: "Downloading each year's report" },
  { id: "read", title: "Read statements", doing: "Finding and reading the statements in each report" },
  { id: "merge", title: "Line up years", doing: "Matching line items across years and checking totals" },
  { id: "write", title: "Write Excel", doing: "Building the workbook" },
]

export interface Timeline {
  events: RunEvent[]
  total: number
}

const cache = new Map<string, Timeline>()

/**
 * A run as a list of timed events. Real progress will arrive from the engine
 * (its `log` and `progress` callbacks); here the schedule is fixed by the
 * request, so reloading the page mid-run picks up where it should be.
 */
export function buildTimeline(run: RunRecord): Timeline {
  const hit = cache.get(run.id)
  if (hit) return hit
  const req: ExtractionRequest = run.request
  const events: RunEvent[] = []
  const years = fyRange(req.from, req.to).reverse()
  const j = (k: string, base: number) => base * (0.8 + 0.4 * rand(`${run.id}${k}`))
  let t = 0
  const log = (stage: StageId, text: string, level: RunEvent["level"] = "info") => events.push({ t, stage, type: "log", text, level })

  events.push({ t, stage: "lookup", type: "start" })
  log("lookup", `Looking up ${req.symbol} on screener.in …`)
  t += j("l", 800)
  log("lookup", `${run.companyName}: ${years.length} annual report(s): ${years.join(", ")}`, "ok")
  events.push({ t, stage: "lookup", type: "end" })

  events.push({ t, stage: "download", type: "start" })
  log("download", "Downloading PDFs (cached after the first run) …")
  const reports = reportsFor(req.symbol)
  const start = t
  years.forEach((fy, i) => {
    // four downloads at a time
    t = start + (Math.floor(i / 4) + 1) * j(`d${fy}`, 520) + (i % 4) * 90
    const r = reports.find((x) => x.fy === fy)
    events.push({ t, stage: "download", type: "year", fy })
    log("download", `FY${fy}: ${req.symbol}_AR_${fy}.pdf (${r?.sizeMb.toFixed(1) ?? "8.0"} MB)`)
  })
  t += 150
  events.push({ t, stage: "download", type: "end" })

  events.push({ t, stage: "read", type: "start" })
  log("read", "Reading financial statements from each report …")
  const wb = buildWorkbook(run.id, req)
  for (const fy of years) {
    for (const scope of wb.scopes) {
      const views = computeAll(wb.books[scope]!, wb.years, "restated", EMPTY_REVIEW)
      for (const sheet of KINDS) {
        t += j(`r${fy}${scope}${sheet}`, 430)
        const q = qualityOf(views[sheet], fy)
        const pages = pagesFor(fy, scope, sheet).join(", ")
        const bad = q.failedTotals ? `; ${q.failedTotals} total doesn't add up` : ""
        log(
          "read",
          `FY${fy} ${scope} ${SHEETS[sheet].title}: OK pages ${pages}, ${q.cells} figures via parser; ${q.confirmed}/${q.cells} confirmed by the report's totals${bad}`,
          q.failedTotals ? "warn" : "info"
        )
      }
    }
    events.push({ t, stage: "read", type: "year", fy })
  }
  events.push({ t, stage: "read", type: "end" })

  events.push({ t, stage: "merge", type: "start" })
  log("merge", `Lining up ${wb.years.length} years (${req.figures === "restated" ? "latest restated figures" : "as originally reported"})`)
  t += j("m1", 500)
  log("merge", `${fyLabel(wb.years[0])} comes from the comparative column of the ${fyLabel(req.from)} report`)
  t += j("m2", 450)
  if (wb.years.includes(2023)) log("merge", "consolidated FY2023: EPS check: reported 2.26, profit ÷ shares gives 22.58", "warn")
  events.push({ t, stage: "merge", type: "end" })

  events.push({ t, stage: "write", type: "start" })
  t += j("w", 700)
  log("write", `Saved: ${fileName(req, wb.years)}`, "ok")
  events.push({ t, stage: "write", type: "end" })

  const tl = { events, total: t }
  cache.set(run.id, tl)
  return tl
}

export const fileName = (req: ExtractionRequest, years: FiscalYear[]) =>
  `${req.symbol}_Financials_FY${years[0]}-FY${years[years.length - 1]}.xlsx`

export interface StageProgress {
  status: "pending" | "running" | "done"
  startedAt?: number
  endedAt?: number
  years: FiscalYear[]
}

export interface RunProgress {
  stages: Record<StageId, StageProgress>
  logs: RunEvent[]
  /** 0–1, weighted the way the engine reports it. */
  fraction: number
  current?: StageId
  done: boolean
}

const WEIGHT: Record<StageId, [from: number, to: number]> = {
  lookup: [0, 0.05],
  download: [0.05, 0.3],
  read: [0.3, 0.9],
  merge: [0.9, 0.96],
  write: [0.96, 1],
}

export function progressAt(tl: Timeline, elapsed: number, yearCount: number): RunProgress {
  const stages = Object.fromEntries(STAGES.map((s) => [s.id, { status: "pending", years: [] }])) as unknown as RunProgress["stages"]
  const logs: RunEvent[] = []
  for (const e of tl.events) {
    if (e.t > elapsed) break
    const s = stages[e.stage]
    if (e.type === "start") Object.assign(s, { status: "running", startedAt: e.t })
    else if (e.type === "end") Object.assign(s, { status: "done", endedAt: e.t })
    else if (e.type === "year" && e.fy) s.years.push(e.fy)
    else if (e.type === "log") logs.push(e)
  }
  const done = elapsed >= tl.total
  const current = STAGES.find((s) => stages[s.id].status === "running")?.id
  let fraction = done ? 1 : 0
  if (!done)
    for (const s of STAGES) {
      const st = stages[s.id]
      const [a, b] = WEIGHT[s.id]
      if (st.status === "done") fraction = b
      else if (st.status === "running") {
        const within =
          s.id === "download" || s.id === "read"
            ? st.years.length / yearCount
            : Math.min(1, (elapsed - (st.startedAt ?? 0)) / 800)
        fraction = a + (b - a) * within
      }
    }
  return { stages, logs, fraction, current, done }
}
