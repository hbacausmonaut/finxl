import { fyRange } from "../fy"
import { componentsOf, KINDS, SHEETS } from "../sheets"
import {
  cellKey,
  type ExtractionRequest,
  type FiscalYear,
  type Restatement,
  type Scope,
  type ScopeBook,
  type SecondReading,
  type SourceEntry,
  type StatementKind,
  type Workbook,
} from "../types"
import { DEMO_COMPANY, findCompany, reportsFor } from "./companies"
import { FIRST_FY, generateTruth, type YearTruth } from "./generate"

/**
 * Misreads planted in the demo data. Each one makes exactly one printed total
 * stop adding up, which is how the engine's footing check (quality.py) would
 * catch it. The second reading is what an AI re-read of the page returns.
 */
const MISREADS: Array<{ sheet: StatementKind; row: string; fy: FiscalYear; delta: number; note: string }> = [
  { sheet: "bs", row: "ocl", fy: 2022, delta: 420, note: "Faint print: one digit reads as either 4 or 0." },
  { sheet: "cf", row: "c_tp", fy: 2024, delta: 180, note: "The figure wraps onto a second line in the PDF." },
  { sheet: "pl", row: "oth", fy: 2025, delta: 500, note: "The units digit is ambiguous (3 or 8)." },
]

/** EPS read 10× too small in one year: the per-share sanity check flags it. */
const EPS_SLIP: FiscalYear = 2023

/** A row whose label came out of a shifted-font PDF as gibberish. */
const GARBLED = { sheet: "bs" as const, row: "onca", label: "2WKHU QRQ-FXUUHQW DVVHWV" }

/** PDF page positions of each statement in a given year's report. */
export function pagesFor(reportFy: FiscalYear, scope: Scope, sheet: StatementKind): number[] {
  const base = 96 + (reportFy - 2008) * 7 + (scope === "consolidated" ? 74 : 0)
  if (sheet === "bs") return [base]
  if (sheet === "pl") return [base + 1]
  return [base + 3, base + 4]
}

function printedValues(t: YearTruth) {
  const out: Record<StatementKind, Record<string, number>> = { pl: {}, bs: {}, cf: {} }
  const truth = t as unknown as Record<string, number>
  for (const sheet of KINDS) {
    const rows = SHEETS[sheet].rows
    for (const r of rows) if (r.kind === "item") out[sheet][r.id] = truth[r.id]
    for (const r of rows)
      if (r.kind === "total") out[sheet][r.id] = componentsOf(sheet, r).reduce((s, [id]) => s + out[sheet][id], 0)
    for (const r of rows)
      if (r.kind === "calc") out[sheet][r.id] = componentsOf(sheet, r).reduce((s, [id, sign]) => s + sign * out[sheet][id], 0)
  }
  return out
}

function buildScope(scope: Scope, req: ExtractionRequest, years: FiscalYear[]): ScopeBook {
  const truth = generateTruth(scope)
  const values: ScopeBook["values"] = { pl: {}, bs: {}, cf: {} }
  const labels: ScopeBook["labels"] = { pl: {}, bs: {}, cf: {} }
  const restatements: Record<string, Restatement> = {}
  const secondReadings: SecondReading[] = []
  const epsExpected: Record<FiscalYear, number> = {}

  for (const sheet of KINDS) for (const r of SHEETS[sheet].rows) labels[sheet][r.id] = r.label

  for (const fy of years) {
    const t = truth.get(fy)
    if (!t) continue
    const printed = printedValues(t)
    for (const sheet of KINDS)
      for (const [row, v] of Object.entries(printed[sheet])) (values[sheet][row] ??= {})[fy] = v
    epsExpected[fy] = t.eps
  }

  for (const m of MISREADS) {
    const right = values[m.sheet][m.row]?.[m.fy]
    if (right === undefined) continue
    values[m.sheet][m.row][m.fy] = right + m.delta
    secondReadings.push({ cell: { scope, sheet: m.sheet, row: m.row, fy: m.fy }, value: right, note: m.note })
  }

  if (values.pl.eps?.[EPS_SLIP] !== undefined) values.pl.eps[EPS_SLIP] = Math.round(values.pl.eps[EPS_SLIP] * 10) / 100

  const garbled: ScopeBook["garbled"] = []
  if (values[GARBLED.sheet][GARBLED.row]) {
    garbled.push({ ...GARBLED, suggestion: labels[GARBLED.sheet][GARBLED.row] })
    labels[GARBLED.sheet][GARBLED.row] = GARBLED.label
  }

  // Restatements: what each year's own report said before a later report changed it.
  const restate = (sheet: StatementKind, row: string, fy: FiscalYear, delta: number, reason: string) => {
    const v = values[sheet][row]?.[fy]
    if (v === undefined || !years.includes(fy + 1) || fy < req.from) return
    restatements[cellKey({ scope, sheet, row, fy })] = { asReported: v + delta, restatedIn: fy + 1, reason }
  }
  const t23 = truth.get(2023)
  if (t23) {
    const why = "Export incentives were moved from Other income into Revenue from operations."
    restate("pl", "rev", 2023, -t23.reclass, why)
    restate("pl", "oi", 2023, t23.reclass, why)
  }
  const t25 = truth.get(2025)
  if (t25) {
    const d = Math.round(t25.inv * 0.021)
    const why = "Stores and spares were re-costed after a change in accounting policy."
    for (const row of ["inv", "ca", "ta", "oe", "eq", "tel"]) restate("bs", row, 2025, d, why)
  }

  const reports = reportsFor(req.symbol)
  const urlOf = (fy: FiscalYear) => reports.find((r) => r.fy === fy)?.url ?? "#"
  const sources: SourceEntry[] = []
  for (const fy of fyRange(req.from, req.to))
    for (const sheet of KINDS)
      sources.push({
        fy,
        scope,
        sheet,
        pages: pagesFor(fy, scope, sheet),
        method: "parser",
        check: "OK",
        checkNote:
          sheet === "bs"
            ? "balance sheet ties"
            : sheet === "pl"
              ? "revenue and profit rows found"
              : "operating cash flow row found",
        url: urlOf(fy),
      })

  return { scope, values, labels, restatements, secondReadings, garbled, epsExpected, sources }
}

const cache = new Map<string, Workbook>()

/** The engine's result for a request. The mock always serves the demo dataset. */
export function buildWorkbook(id: string, req: ExtractionRequest): Workbook {
  const key = `${id}|${req.symbol}|${req.from}|${req.to}|${req.scope}`
  const hit = cache.get(key)
  if (hit) return hit

  // Comparative columns reach one year before the first report (as finxl.run does).
  const years = fyRange(Math.max(FIRST_FY + 1, req.from - 1), req.to)
  const scopes: Scope[] = req.scope === "both" ? ["consolidated", "standalone"] : [req.scope]
  const wb: Workbook = {
    id,
    request: req,
    company: findCompany(req.symbol) ?? DEMO_COMPANY,
    years,
    scopes,
    books: {
      consolidated: scopes.includes("consolidated") ? buildScope("consolidated", req, years) : undefined,
      standalone: scopes.includes("standalone") ? buildScope("standalone", req, years) : undefined,
    },
    reports: reportsFor(req.symbol).filter((r) => r.fy >= req.from && r.fy <= req.to),
  }
  cache.set(key, wb)
  return wb
}

/**
 * Headline figures from outside sources (accuracy_check.py). NSE filings carry
 * each year as originally reported; Screener shows the latest restated figure.
 */
export function outsideFigures(scope: Scope, fy: FiscalYear) {
  const t = generateTruth(scope).get(fy)
  if (!t) return undefined
  const p = printedValues(t)
  return {
    restated: { Revenue: p.pl.rev, "Net profit": p.pl.pat, "Total assets": p.bs.ta, "Cash from operations": p.cf.cfo },
    reclass: t.reclass,
    invRestate: Math.round(t.inv * 0.021),
  }
}
