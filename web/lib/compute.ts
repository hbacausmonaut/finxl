import { kindsOf } from "./adapter"
import {
  cellKey,
  rowKey,
  type CellStatus,
  type FiguresMode,
  type FiscalYear,
  type Group,
  type Issue,
  type ReviewState,
  type RowDef,
  type ScopeBook,
  type StatementKind,
} from "./types"

type Grid<T> = Record<string, Record<FiscalYear, T>>

export interface StatementView {
  sheet: StatementKind
  title: string
  rows: RowDef[]
  /** Figure shown for each row and year (printed value, with review edits applied). */
  values: Grid<number>
  /** What the items of a total add up to, where the report's own footing found them. */
  sums: Grid<number>
  status: Grid<CellStatus>
  groups: Grid<Group>
  /** Rows whose label failed the dictionary check and hasn't been renamed. */
  garbled: Set<string>
}

/** quality.py _tolerance: printed figures are rounded, so a total can be off by a unit or two. */
function tolerance(n: number, integer: boolean) {
  return (integer ? 1 : 0.01) * (1.05 + 0.1 * n)
}

/**
 * Applies the figures mode and the reader's edits, then re-checks the totals the
 * engine checked: the engine's status stands unless a figure in that total
 * changed, in which case the total is added up again from the same items.
 */
export function computeStatement(
  book: ScopeBook,
  sheet: StatementKind,
  years: FiscalYear[],
  mode: FiguresMode,
  review: ReviewState
): StatementView {
  const def = book.sheets[sheet]!
  const scope = book.scope
  const base = book.values[sheet] ?? {}
  const serverStatus = book.status[sheet] ?? {}
  const groups = book.groups[sheet] ?? {}
  const values: Grid<number> = {}
  const status: Grid<CellStatus> = {}
  const sums: Grid<number> = {}
  const changed = new Set<string>()

  for (const r of def.rows) {
    if (r.kind === "header") continue
    values[r.id] = {}
    status[r.id] = {}
    for (const fy of years) {
      const key = cellKey({ scope, sheet, row: r.id, fy })
      let v: number | undefined = base[r.id]?.[fy]
      const re = book.restatements[key]
      if (re) {
        const want = mode === "as-reported" ? re.asReported : re.latest
        if (v !== want) changed.add(`${r.id}:${fy}`)
        v = want
      }
      if (review.edits[key] !== undefined) {
        v = review.edits[key]
        changed.add(`${r.id}:${fy}`)
      }
      if (v !== undefined) {
        values[r.id][fy] = v
        status[r.id][fy] = serverStatus[r.id]?.[fy] ?? null
      }
    }
  }

  for (const r of def.rows) {
    const g = groups[r.id]
    if (!g) continue
    sums[r.id] = {}
    for (const fy of years) {
      const grp = g[fy]
      const printed = values[r.id]?.[fy]
      if (!grp || printed === undefined) continue
      const vals = grp.members.map(([id, sign]) => sign * (values[id]?.[fy] ?? 0))
      const sum = vals.reduce((a, b) => a + b, 0)
      sums[r.id][fy] = sum
      const touched = changed.has(`${r.id}:${fy}`) || grp.members.some(([id]) => changed.has(`${id}:${fy}`))
      if (!touched) continue
      const integer = [printed, ...vals].every((v) => Math.abs(v - Math.round(v)) < 1e-9)
      const ok = Math.abs(sum - printed) <= tolerance(grp.members.length, integer)
      status[r.id][fy] = ok ? "ok" : "fail"
      for (const [id] of grp.members) {
        if (values[id]?.[fy] === undefined || status[id][fy] === "fail") continue
        if (ok) status[id][fy] = "ok"
        else if (changed.has(`${id}:${fy}`)) status[id][fy] = null
      }
    }
  }

  const garbled = new Set(
    book.garbled.filter((g) => g.sheet === sheet && !review.labels[rowKey({ scope, sheet, row: g.row })]).map((g) => g.row)
  )
  const rows = def.rows.map((r) => ({ ...r, label: review.labels[rowKey({ scope, sheet, row: r.id })] ?? r.label }))

  return { sheet, title: def.title, rows, values, sums, status, groups, garbled }
}

export type Views = Partial<Record<StatementKind, StatementView>>

export function computeAll(book: ScopeBook, years: FiscalYear[], mode: FiguresMode, review: ReviewState): Views {
  return Object.fromEntries(kindsOf(book).map((k) => [k, computeStatement(book, k, years, mode, review)]))
}

/** The total a row feeds into in that year, from the report's own footing. */
export function parentOf(view: StatementView, row: string, fy: FiscalYear): RowDef | undefined {
  return view.rows.find((r) => view.groups[r.id]?.[fy]?.members.some(([id]) => id === row))
}

// ─── Issues ───────────────────────────────────────────────────────────────────

/** Everything the checks flag for one scope, given the current edits. */
export function findIssues(book: ScopeBook, views: Views, years: FiscalYear[], review: ReviewState): Issue[] {
  const out: Issue[] = []
  const scope = book.scope
  for (const sheet of kindsOf(book)) {
    const v = views[sheet]!
    for (const r of v.rows) {
      if (r.kind === "header") continue
      for (const fy of years) {
        if (v.status[r.id]?.[fy] !== "fail") continue
        const suspect = book.secondReadings.find(
          (s) => s.cell.sheet === sheet && s.cell.fy === fy && s.totalRow === r.id && review.edits[cellKey(s.cell)] === undefined
        )
        const cell = { scope, sheet, row: r.id, fy }
        out.push({ id: `total:${cellKey(cell)}`, kind: "total", cell, printed: v.values[r.id][fy], sum: v.sums[r.id]?.[fy] ?? NaN, suspect })
      }
    }
  }
  for (const [key, expected] of Object.entries(book.epsExpected)) {
    const [, sheet, row, fy] = key.split(":")
    const value = views[sheet as StatementKind]?.values[row]?.[Number(fy)]
    if (value === undefined || !expected) continue
    if (review.edits[key] !== undefined && Math.abs(value / expected - 1) <= 0.05) continue
    const cell = { scope, sheet: sheet as StatementKind, row, fy: Number(fy) }
    out.push({ id: `eps:${key}`, kind: "eps", cell, value, expected })
  }
  for (const g of book.garbled) {
    if (review.labels[rowKey({ scope, sheet: g.sheet, row: g.row })]) continue
    out.push({ id: `label:${rowKey({ scope, sheet: g.sheet, row: g.row })}`, kind: "label", scope, sheet: g.sheet, row: g.row, label: g.label })
  }
  return out
}

export const issueCell = (i: Issue) => (i.kind === "label" ? { scope: i.scope, sheet: i.sheet, row: i.row } : i.cell)

// ─── Quality (the engine's Quality sheet) ─────────────────────────────────────

export interface Quality {
  cells: number
  confirmed: number
  totals: number
  failedTotals: number
}

export function qualityOf(view: StatementView | undefined, fy: FiscalYear): Quality {
  const q: Quality = { cells: 0, confirmed: 0, totals: 0, failedTotals: 0 }
  if (!view) return q
  for (const r of view.rows) {
    if (r.kind === "header" || view.values[r.id]?.[fy] === undefined) continue
    q.cells++
    const s = view.status[r.id][fy]
    if (s === "ok") q.confirmed++
    if (view.groups[r.id]?.[fy]) {
      q.totals++
      if (s === "fail") q.failedTotals++
    }
  }
  return q
}

export function overallQuality(views: Views, years: FiscalYear[]): Quality {
  const sum: Quality = { cells: 0, confirmed: 0, totals: 0, failedTotals: 0 }
  for (const view of Object.values(views))
    for (const fy of years) {
      const q = qualityOf(view, fy)
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
  /** Where the figure comes from each year, so the row can link to its statement. */
  source?: { sheet: StatementKind; rows: Record<FiscalYear, string> }
  formula?: string
  values: Record<FiscalYear, number | undefined>
}

const pickByLabel = (book: ScopeBook, label: string) => book.summary.find((m) => m.label === label)

export function summaryMetrics(book: ScopeBook, views: Views, years: FiscalYear[]): { figures: MetricRow[]; ratios: MetricRow[] } {
  const series = (label: string) => {
    const p = pickByLabel(book, label)
    return (fy: FiscalYear) => {
      const row = p?.rows[fy]
      return p && row !== undefined ? views[p.sheet]?.values[row]?.[fy] : undefined
    }
  }
  const figures: MetricRow[] = book.summary.map((p, i) => ({
    id: `m${i}`,
    label: p.label,
    format: /eps/i.test(p.label) ? "per-share" : "amount",
    source: { sheet: p.sheet, rows: p.rows },
    values: Object.fromEntries(years.map((fy) => [fy, series(p.label)(fy)])),
  }))
  const rev = series("Revenue from operations"), pat = series("Net profit"), eq = series("Total equity"), ta = series("Total assets"), cfo = series("Cash from operations")
  const div = (a?: number, b?: number) => (a === undefined || !b ? undefined : a / b)
  const ratio = (id: string, label: string, formula: string, f: (fy: FiscalYear, i: number) => number | undefined): MetricRow => ({
    id, label, format: "pct", formula, values: Object.fromEntries(years.map((fy, i) => [fy, f(fy, i)])),
  })
  return {
    figures,
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

/** Within 0.5%, the engine's tolerance for outside sources. */
export const agrees = (a: number, b: number | undefined | null) => b !== undefined && b !== null && Math.abs(a - b) <= Math.abs(b) * 0.005

// ─── Display transforms ───────────────────────────────────────────────────────

export type ViewMode = "values" | "common" | "yoy"

/** Base row for common-size statements: the Summary's revenue and total-assets picks. */
export function commonBase(book: ScopeBook, sheet: StatementKind): { label: string; rows: Record<FiscalYear, string> } | null {
  const label = sheet === "pl" ? "Revenue from operations" : sheet === "bs" ? "Total assets" : null
  const p = label ? pickByLabel(book, label) : undefined
  return p && p.sheet === sheet ? { label: sheet === "bs" ? "total assets" : "revenue", rows: p.rows } : null
}

export function transform(
  view: StatementView,
  mode: ViewMode,
  row: string,
  fy: FiscalYear,
  years: FiscalYear[],
  base: ReturnType<typeof commonBase>
): number | undefined {
  const v = view.values[row]?.[fy]
  if (v === undefined || mode === "values") return v
  if (mode === "common") {
    const r = base?.rows[fy]
    const b = r !== undefined ? view.values[r]?.[fy] : undefined
    return b ? v / b : undefined
  }
  const i = years.indexOf(fy)
  const prev = i > 0 ? view.values[row]?.[years[i - 1]] : undefined
  return prev ? v / prev - 1 : undefined
}
