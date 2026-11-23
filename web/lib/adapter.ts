/**
 * run.json (api/serialize.py) → the Workbook the app draws.
 * Years arrive as string keys; rows are lists whose index is the row id.
 * Money stays in ₹ crore, as the engine writes it.
 */
import {
  cellKey,
  type CellStatus,
  type FiscalYear,
  type Group,
  type RowDef,
  type Scope,
  type ScopeBook,
  type SecondReading,
  type SheetData,
  type SourceEntry,
  type StatementKind,
  type SummaryPick,
  type Workbook,
} from "./types"

type YearMap<T> = Record<string, T>

export interface ApiRow {
  label: string
  level: number
  header: boolean
  total: boolean
  values: YearMap<number>
  status: YearMap<"ok" | "fail" | null>
  src: YearMap<number>
  group: YearMap<{ ok: boolean; members: Array<[number, number]>; signed?: boolean }>
  labelOk: boolean
  junk?: string
  restated?: YearMap<{ own: number; newest: number; newestFy: number }>
  epsFlag?: YearMap<string>
  epsExpect?: YearMap<number>
}

export interface ApiRun {
  id: string
  request: Workbook["request"]
  company: { symbol: string; name: string; url?: string }
  years: number[]
  columns: YearMap<string>
  scopes: Scope[]
  books: Partial<Record<Scope, { statements: Partial<Record<StatementKind, { title: string; rows: ApiRow[] }>>; summary: Array<{ label: string; kind: StatementKind; rows: YearMap<number>; values: YearMap<number> }> }>>
  sources: Array<{ fy: number; scope: Scope; kind: StatementKind; pages: string[]; method: string; check: string; url: string; quality?: SourceEntry["quality"] }>
  reports: Array<{ fy: number; url: string; label?: string }>
  secondReadings: Array<{ scope: Scope; kind: StatementKind; year: number; reportFy: number; totalRow: number; row: number; value: number; printed?: string; page: string; note: string }>
  createdAt: number
}

export const KIND_ORDER: StatementKind[] = ["pl", "bs", "cf", "ra"]
export const SHORT_TITLE: Record<StatementKind, string> = { pl: "P&L", bs: "Balance Sheet", cf: "Cash Flow", ra: "Revenue Account" }

const PER_SHARE = /per (equity )?share|\beps\b|^\s*(\(?[a-z0-9]\)?\s*)?(basic|diluted)\b/i

const byYear = <A, B>(m: YearMap<A> | undefined, f: (v: A) => B): Record<FiscalYear, B> => {
  const out: Record<FiscalYear, B> = {}
  for (const [y, v] of Object.entries(m ?? {})) if (v !== null && v !== undefined) out[Number(y)] = f(v)
  return out
}

function scopeBook(run: ApiRun, scope: Scope): ScopeBook {
  const src = run.books[scope]!
  const book: ScopeBook = {
    scope,
    sheets: {},
    values: {},
    status: {},
    groups: {},
    src: {},
    restatements: {},
    secondReadings: [],
    garbled: [],
    epsExpected: {},
    sources: [],
    summary: [],
  }
  for (const kind of KIND_ORDER) {
    const st = src.statements[kind]
    if (!st) continue
    const rows: RowDef[] = []
    const values: Record<string, Record<FiscalYear, number>> = {}
    const status: Record<string, Record<FiscalYear, CellStatus>> = {}
    const groups: Record<string, Record<FiscalYear, Group>> = {}
    const srcs: Record<string, Record<FiscalYear, FiscalYear>> = {}
    let underEps = false
    let section: string | undefined
    st.rows.forEach((r, i) => {
      const id = String(i)
      if (r.header) {
        underEps = /per (equity )?share|\beps\b/i.test(r.label)
        section = id
      }
      const perShare = !r.header && (PER_SHARE.test(r.label) || (underEps && Object.values(r.values).every((v) => Math.abs(v) < 5000)))
      rows.push({
        id,
        label: r.label,
        kind: r.header ? "header" : r.total ? "total" : "item",
        level: r.level ?? 0,
        section: r.header ? undefined : section,
        perShare: perShare || undefined,
        strong: r.total && (r.level ?? 0) === 0 ? true : undefined,
        junk: r.junk,
      })
      if (r.header) return
      values[id] = byYear(r.values, (v) => v)
      status[id] = byYear(r.status, (v) => v as CellStatus)
      groups[id] = byYear(r.group, (g) => ({ ok: g.ok, members: g.members.map(([m, s]) => [String(m), s < 0 ? -1 : 1] as [string, 1 | -1]) }))
      srcs[id] = byYear(r.src, (v) => v)
      for (const [y, x] of Object.entries(r.restated ?? {}))
        book.restatements[cellKey({ scope, sheet: kind, row: id, fy: Number(y) })] = { asReported: x.own, latest: x.newest, restatedIn: x.newestFy }
      for (const [y, e] of Object.entries(r.epsExpect ?? {}))
        if (r.epsFlag?.[y]) book.epsExpected[cellKey({ scope, sheet: kind, row: id, fy: Number(y) })] = e
      if (!r.labelOk) book.garbled.push({ sheet: kind, row: id, label: r.label, suggestion: "" })
    })
    book.sheets[kind] = { kind, title: st.title, rows } satisfies SheetData
    book.values[kind] = values
    book.status[kind] = status
    book.groups[kind] = groups
    book.src[kind] = srcs
  }
  book.secondReadings = run.secondReadings
    .filter((s) => s.scope === scope)
    .map(
      (s): SecondReading => ({
        cell: { scope, sheet: s.kind, row: String(s.row), fy: s.year },
        totalRow: String(s.totalRow),
        value: s.value,
        note: s.note,
        printed: s.printed,
        page: String(s.page),
        reportFy: s.reportFy,
      })
    )
  book.sources = run.sources
    .filter((s) => s.scope === scope)
    .map((s) => {
      const m = /^\s*(OK|CHECK|MISSING|N\/A)\b[:\s-]*(.*)$/i.exec(s.check ?? "")
      return {
        fy: s.fy,
        scope,
        sheet: s.kind,
        pages: s.pages,
        method: s.method ?? "",
        check: ((m?.[1] ?? "CHECK").toUpperCase() as SourceEntry["check"]),
        checkNote: m?.[2] ?? s.check ?? "",
        url: s.url,
        quality: s.quality,
      }
    })
  book.summary = src.summary.map(
    (m): SummaryPick => ({ label: m.label, sheet: m.kind, rows: byYear(m.rows, (r) => String(r)), values: byYear(m.values, (v) => v) })
  )
  return book
}

export function toWorkbook(run: ApiRun): Workbook {
  const scopes = run.scopes.filter((s) => run.books[s])
  return {
    id: run.id,
    request: run.request,
    company: { symbol: run.company.symbol, name: run.company.name, url: run.company.url },
    years: [...run.years].sort((a, b) => a - b),
    columns: byYear(run.columns, (c) => c),
    scopes,
    books: Object.fromEntries(scopes.map((s) => [s, scopeBook(run, s)])),
    reports: run.reports.map((r) => ({ fy: r.fy, url: r.url, label: r.label })),
  }
}

/** Statements present in a scope, in reading order. */
export const kindsOf = (book: ScopeBook): StatementKind[] => KIND_ORDER.filter((k) => book.sheets[k])
