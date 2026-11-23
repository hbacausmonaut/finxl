import { componentsOf, KINDS, SHEETS } from "./sheets"
import { outsideFigures } from "./mock/workbook"
import {
  cellKey,
  rowKey,
  type CellStatus,
  type CrossCheckRow,
  type FiguresMode,
  type FiscalYear,
  type Issue,
  type ReviewState,
  type RowDef,
  type Scope,
  type ScopeBook,
  type StatementKind,
  type Workbook,
} from "./types"

type Grid<T> = Record<string, Record<FiscalYear, T>>

export interface StatementView {
  sheet: StatementKind
  rows: RowDef[]
  /** Figure shown for each row and year (printed value, with review edits applied). */
  values: Grid<number>
  /** What the components of a total or calculated line add up to. */
  sums: Grid<number>
  status: Grid<CellStatus>
  /** Rows whose label failed the dictionary check and hasn't been renamed. */
  garbled: Set<string>
}

/** Rounding slack in a printed statement: ₹0.01 crore. */
const TOL = 1

/**
 * Applies the figures mode and the reader's edits, then re-runs the footing
 * check the way quality.py does: a total that equals its items confirms every
 * figure in it; a total that doesn't is flagged and its items stay unconfirmed.
 */
export function computeStatement(
  book: ScopeBook,
  sheet: StatementKind,
  years: FiscalYear[],
  mode: FiguresMode,
  review: ReviewState
): StatementView {
  const def = SHEETS[sheet]
  const values: Grid<number> = {}
  const sums: Grid<number> = {}
  const status: Grid<CellStatus> = {}
  const scope = book.scope

  for (const r of def.rows) {
    if (r.kind === "header") continue
    values[r.id] = {}
    status[r.id] = {}
    for (const fy of years) {
      const key = cellKey({ scope, sheet, row: r.id, fy })
      let v: number | undefined = book.values[sheet][r.id]?.[fy]
      if (mode === "as-reported" && book.restatements[key]) v = book.restatements[key].asReported
      if (review.edits[key] !== undefined) v = review.edits[key]
      if (v !== undefined) {
        values[r.id][fy] = v
        status[r.id][fy] = null
      }
    }
  }

  for (const r of def.rows) {
    if (r.kind !== "total" && r.kind !== "calc") continue
    const parts = componentsOf(sheet, r)
    sums[r.id] = {}
    for (const fy of years) {
      const printed = values[r.id][fy]
      if (printed === undefined) continue
      const sum = parts.reduce((s, [id, sign]) => s + sign * (values[id]?.[fy] ?? 0), 0)
      sums[r.id][fy] = sum
      const ok = Math.abs(sum - printed) <= TOL
      status[r.id][fy] = ok ? "ok" : "fail"
      if (ok) for (const [id] of parts) if (status[id][fy] !== "fail") status[id][fy] = "ok"
    }
  }

  const garbled = new Set(
    book.garbled.filter((g) => g.sheet === sheet && !review.labels[rowKey({ scope, sheet, row: g.row })]).map((g) => g.row)
  )
  const rows = def.rows.map((r) => ({
    ...r,
    label: review.labels[rowKey({ scope, sheet, row: r.id })] ?? book.labels[sheet][r.id] ?? r.label,
  }))

  return { sheet, rows, values, sums, status, garbled }
}

export type Views = Record<StatementKind, StatementView>

export function computeAll(book: ScopeBook, years: FiscalYear[], mode: FiguresMode, review: ReviewState): Views {
  return {
    pl: computeStatement(book, "pl", years, mode, review),
    bs: computeStatement(book, "bs", years, mode, review),
    cf: computeStatement(book, "cf", years, mode, review),
  }
}

// ─── Issues ───────────────────────────────────────────────────────────────────

/** Everything the checks flag for one scope, given the current edits. */
export function findIssues(book: ScopeBook, views: Views, years: FiscalYear[], review: ReviewState): Issue[] {
  const out: Issue[] = []
  const scope = book.scope
  for (const sheet of KINDS) {
    const v = views[sheet]
    for (const r of v.rows) {
      if (r.kind !== "total" && r.kind !== "calc") continue
      for (const fy of years) {
        if (v.status[r.id][fy] !== "fail") continue
        const parts = componentsOf(sheet, r).map(([id]) => id)
        const suspect = book.secondReadings.find(
          (s) => s.cell.sheet === sheet && s.cell.fy === fy && parts.includes(s.cell.row) && review.edits[cellKey(s.cell)] === undefined
        )
        const cell = { scope, sheet, row: r.id, fy }
        out.push({ id: `total:${cellKey(cell)}`, kind: "total", cell, printed: v.values[r.id][fy], sum: v.sums[r.id][fy], suspect })
      }
    }
  }
  for (const fy of years) {
    const value = views.pl.values.eps?.[fy]
    const expected = book.epsExpected[fy]
    if (value === undefined || !expected) continue
    const ratio = value / expected
    if (ratio < 0.8 || ratio > 1.25) {
      const cell = { scope, sheet: "pl" as const, row: "eps", fy }
      out.push({ id: `eps:${cellKey(cell)}`, kind: "eps", cell, value, expected })
    }
  }
  for (const g of book.garbled) {
    if (review.labels[rowKey({ scope, sheet: g.sheet, row: g.row })]) continue
    out.push({ id: `label:${rowKey({ scope, sheet: g.sheet, row: g.row })}`, kind: "label", scope, sheet: g.sheet, row: g.row, label: g.label, suggestion: g.suggestion })
  }
  return out
}

export const issueCell = (i: Issue) =>
  i.kind === "label" ? { scope: i.scope, sheet: i.sheet, row: i.row } : i.cell

// ─── Quality (the engine's Quality sheet) ─────────────────────────────────────

export interface Quality {
  cells: number
  confirmed: number
  totals: number
  failedTotals: number
}

export function qualityOf(view: StatementView, fy: FiscalYear): Quality {
  const q: Quality = { cells: 0, confirmed: 0, totals: 0, failedTotals: 0 }
  for (const r of view.rows) {
    if (r.kind === "header" || view.values[r.id]?.[fy] === undefined) continue
    q.cells++
    const s = view.status[r.id][fy]
    if (s === "ok") q.confirmed++
    if (r.kind === "total" || r.kind === "calc") {
      q.totals++
      if (s === "fail") q.failedTotals++
    }
  }
  return q
}

export function overallQuality(views: Views, years: FiscalYear[]): Quality {
  const sum: Quality = { cells: 0, confirmed: 0, totals: 0, failedTotals: 0 }
  for (const sheet of KINDS)
    for (const fy of years) {
      const q = qualityOf(views[sheet], fy)
      sum.cells += q.cells
      sum.confirmed += q.confirmed
      sum.totals += q.totals
      sum.failedTotals += q.failedTotals
    }
  return sum
}

// ─── Summary (the engine's Summary sheet) ─────────────────────────────────────

export interface MetricRow {
  id: string
  label: string
  format: "amount" | "per-share" | "pct"
  /** Where the figure comes from, so the row can link to its statement. */
  source?: { sheet: StatementKind; row: string }
  formula?: string
  values: Record<FiscalYear, number | undefined>
}

export function summaryMetrics(views: Views, years: FiscalYear[]): { figures: MetricRow[]; ratios: MetricRow[] } {
  const pick = (sheet: StatementKind, row: string) => (fy: FiscalYear) => views[sheet].values[row]?.[fy]
  const rev = pick("pl", "rev"), pat = pick("pl", "pat"), eq = pick("bs", "eq"), ta = pick("bs", "ta"), cfo = pick("cf", "cfo")
  const line = (id: string, label: string, sheet: StatementKind, row: string, format: MetricRow["format"] = "amount"): MetricRow => ({
    id, label, format, source: { sheet, row }, values: Object.fromEntries(years.map((fy) => [fy, pick(sheet, row)(fy)])),
  })
  const ratio = (id: string, label: string, formula: string, f: (fy: FiscalYear, i: number) => number | undefined): MetricRow => ({
    id, label, format: "pct", formula, values: Object.fromEntries(years.map((fy, i) => [fy, f(fy, i)])),
  })
  const div = (a?: number, b?: number) => (a === undefined || !b ? undefined : a / b)

  return {
    figures: [
      line("rev", "Revenue from operations", "pl", "rev"),
      line("pbt", "Profit before tax", "pl", "pbt"),
      line("pat", "Net profit", "pl", "pat"),
      line("eps", "Earnings per share (₹)", "pl", "eps", "per-share"),
      line("eq", "Total equity", "bs", "eq"),
      line("ta", "Total assets", "bs", "ta"),
      line("cfo", "Cash from operations", "cf", "cfo"),
      line("cfi", "Cash from investing", "cf", "cfi"),
      line("cff", "Cash from financing", "cf", "cff"),
    ],
    ratios: [
      ratio("growth", "Revenue growth", "Revenue ÷ last year's revenue − 1", (fy, i) => {
        const d = i === 0 ? undefined : div(rev(fy), rev(years[i - 1]))
        return d === undefined ? undefined : d - 1
      }),
      ratio("npm", "Net profit margin", "Net profit ÷ Revenue", (fy) => div(pat(fy), rev(fy))),
      ratio("roe", "Return on equity", "Net profit ÷ Total equity", (fy) => div(pat(fy), eq(fy))),
      ratio("roa", "Return on assets", "Net profit ÷ Total assets", (fy) => div(pat(fy), ta(fy))),
      ratio("cfopat", "CFO ÷ Net profit", "Cash from operations ÷ Net profit", (fy) => div(cfo(fy), pat(fy))),
    ],
  }
}

// ─── Cross-check (accuracy_check.py) ──────────────────────────────────────────

const HEADLINE: Array<[CrossCheckRow["metric"], StatementKind, string]> = [
  ["Revenue", "pl", "rev"],
  ["Net profit", "pl", "pat"],
  ["Total assets", "bs", "ta"],
  ["Cash from operations", "cf", "cfo"],
]

export function crossCheck(wb: Workbook, scope: Scope, views: Views): CrossCheckRow[] {
  const out: CrossCheckRow[] = []
  for (const [metric, sheet, row] of HEADLINE)
    for (const fy of wb.years) {
      const ours = views[sheet].values[row]?.[fy]
      const o = outsideFigures(scope, fy)
      if (ours === undefined || !o) continue
      const restated = o.restated[metric]
      // NSE filings carry the figure as first reported; Screener the latest restated one.
      let nse = restated
      if (metric === "Revenue" && fy === 2023) nse = restated - o.reclass
      if (metric === "Total assets" && fy === 2025) nse = restated + o.invRestate
      out.push({ metric, fy, ours, nse: fy >= wb.request.from ? nse : undefined, screener: restated })
    }
  return out
}

/** Within 0.5%, the engine's tolerance for outside sources. */
export const agrees = (a: number, b: number | undefined) => b !== undefined && Math.abs(a - b) <= Math.abs(b) * 0.005

// ─── Display transforms ───────────────────────────────────────────────────────

export type ViewMode = "values" | "common" | "yoy"

/** Base row for common-size statements. */
export const COMMON_BASE: Record<StatementKind, { row: string; label: string } | null> = {
  pl: { row: "rev", label: "revenue" },
  bs: { row: "ta", label: "total assets" },
  cf: null,
}

export function transform(view: StatementView, mode: ViewMode, row: string, fy: FiscalYear, years: FiscalYear[]): number | undefined {
  const v = view.values[row]?.[fy]
  if (v === undefined || mode === "values") return v
  if (mode === "common") {
    const base = COMMON_BASE[view.sheet]
    const b = base ? view.values[base.row]?.[fy] : undefined
    return b ? v / b : undefined
  }
  const i = years.indexOf(fy)
  const prev = i > 0 ? view.values[row]?.[years[i - 1]] : undefined
  return prev ? v / prev - 1 : undefined
}
