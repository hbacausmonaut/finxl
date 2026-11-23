/**
 * Domain types: the shapes the FinXL API returns (api/serialize.py) after the
 * client adapter (lib/adapter.ts) has turned them into lookups.
 *
 * Money is ₹ crore everywhere in the app, as the engine writes it; other units
 * are a display concern. Per-share figures are plain ₹.
 */

export type FiscalYear = number

export type Scope = "consolidated" | "standalone"
export type ScopeChoice = Scope | "both"
/** finxl `restated` flag: newest report showing each year, or each year's own report. */
export type FiguresMode = "restated" | "as-reported"
/** ra = an insurer's Revenue Account. */
export type StatementKind = "pl" | "bs" | "cf" | "ra"
export type AiMode = "off" | "fallback" | "always"

export interface Company {
  symbol: string
  name: string
  sector?: string
  /** The bundled sample workbook. */
  isDemo?: boolean
}

/** One annual report on file for a company (finxl.list_reports). */
export interface ReportRef {
  fy: FiscalYear
  url: string
  label?: string
}

export interface ExtractionRequest {
  symbol: string
  from: FiscalYear
  to: FiscalYear
  scope: ScopeChoice
  figures: FiguresMode
  ai: AiMode
}

// ─── Statements ───────────────────────────────────────────────────────────────

/** header: a caption with no figures; item: a line item; total: a line the report's own totals check. */
export type RowKind = "header" | "item" | "total"

export interface RowDef {
  /** Index of the row in its statement, as a string. */
  id: string
  label: string
  kind: RowKind
  level: number
  /** The caption row this line sits under (for "totals only"). */
  section?: string
  perShare?: boolean
  strong?: boolean
  /** Looks like page text, not a line item (quality.junk_reason). */
  junk?: string
}

export interface CellRef {
  scope: Scope
  sheet: StatementKind
  row: string
  fy: FiscalYear
}
export const cellKey = (c: CellRef) => `${c.scope}:${c.sheet}:${c.row}:${c.fy}`
export const rowKey = (c: Pick<CellRef, "scope" | "sheet" | "row">) => `${c.scope}:${c.sheet}:${c.row}`

/** quality.py status: confirmed by the report's own totals, a total that doesn't add up, or not covered. */
export type CellStatus = "ok" | "fail" | null

/** What a total was checked against in its report (quality.py footing). */
export interface Group {
  ok: boolean
  members: Array<[rowId: string, sign: 1 | -1]>
}

/** One row of the engine's Sources sheet. */
export interface SourceEntry {
  fy: FiscalYear
  scope: Scope
  sheet: StatementKind
  /** PDF page positions, e.g. "212" or "106L" (left half of a two-page spread). */
  pages: string[]
  method: string
  check: "OK" | "CHECK" | "MISSING" | "N/A"
  checkNote: string
  url: string
  quality?: { cells: number; confirmed: number; totals: number; failed_totals: number; bad_labels: number; junk_rows: number }
}

/** A year whose own report printed a different figure from the newest report. */
export interface Restatement {
  asReported: number
  latest: number
  restatedIn: FiscalYear
}

/** A figure re-read from the page when its total didn't add up (engine/second_reading.py). */
export interface SecondReading {
  cell: CellRef
  /** The failing total this reading explains. */
  totalRow: string
  value: number
  note: string
  printed?: string
  page: string
  reportFy: FiscalYear
}

export interface SheetData {
  kind: StatementKind
  title: string
  rows: RowDef[]
}

/** A Summary figure and which row it came from each year (finxl.summary_values). */
export interface SummaryPick {
  label: string
  sheet: StatementKind
  rows: Record<FiscalYear, string>
  values: Record<FiscalYear, number>
}

type Grid<T> = Partial<Record<StatementKind, Record<string, Record<FiscalYear, T>>>>

export interface ScopeBook {
  scope: Scope
  sheets: Partial<Record<StatementKind, SheetData>>
  /** Figures as extracted (₹ crore; per-share rows in ₹): sheet → row → fy. */
  values: Grid<number>
  status: Grid<CellStatus>
  groups: Grid<Group>
  /** The annual report each figure was taken from. */
  src: Grid<FiscalYear>
  restatements: Record<string, Restatement>
  secondReadings: SecondReading[]
  /** Rows whose label failed the dictionary check. */
  garbled: Array<{ sheet: StatementKind; row: string; label: string; suggestion: string }>
  /** Expected EPS (profit ÷ shares) where the per-share check flags a figure, by cellKey. */
  epsExpected: Record<string, number>
  sources: SourceEntry[]
  summary: SummaryPick[]
}

export interface Workbook {
  id: string
  request: ExtractionRequest
  company: Company & { url?: string }
  years: FiscalYear[]
  /** Column headings, e.g. "Mar 2025" or "Dec 2024". */
  columns: Record<FiscalYear, string>
  scopes: Scope[]
  books: Partial<Record<Scope, ScopeBook>>
  reports: ReportRef[]
}

/** accuracy_check.py: headline figures against outside sources. */
export interface CrossCheckRow {
  scope: Scope
  metric: string
  fy: FiscalYear
  ours: number | null
  sources: Record<string, number | null>
  status: "OK" | "DIFF" | "MISSING"
  basis: string
  note: string
}

// ─── Issues & review ──────────────────────────────────────────────────────────

export type Issue =
  | {
      id: string
      kind: "total"
      cell: CellRef
      printed: number
      sum: number
      /** The item most likely misread, with a second reading when one exists. */
      suspect?: SecondReading
    }
  | { id: string; kind: "eps"; cell: CellRef; value: number; expected: number }
  | { id: string; kind: "label"; scope: Scope; sheet: StatementKind; row: string; label: string }

export interface ReviewState {
  /** cellKey → corrected value */
  edits: Record<string, number>
  /** rowKey → corrected label */
  labels: Record<string, string>
  /** issue ids the reader has looked at and chosen to keep as printed */
  kept: string[]
}
export const EMPTY_REVIEW: ReviewState = { edits: {}, labels: {}, kept: [] }

// ─── Runs ─────────────────────────────────────────────────────────────────────

export type StageId = "lookup" | "download" | "read" | "merge" | "write"
export type RunStatus = "queued" | "running" | "done" | "failed"

export interface RunRecord {
  id: string
  request: ExtractionRequest
  companyName: string
  /** Seconds since the epoch (from the server). */
  createdAt: number
  startedAt?: number | null
  status: RunStatus
  durationSec?: number | null
  confirmedPct?: number | null
  issues?: number | null
  error?: string | null
  /** Place in the queue while waiting. */
  position?: number
}

/** One server-sent event from /api/runs/{id}/events. */
export type RunEvent =
  | { seq: number; t: number; type: "queued"; position: number }
  | { seq: number; t: number; type: "start" }
  | { seq: number; t: number; type: "stage"; stage: StageId }
  | { seq: number; t: number; type: "stage-end"; stage: StageId }
  | { seq: number; t: number; type: "progress"; fraction: number }
  | { seq: number; t: number; type: "year"; stage: StageId; fy: FiscalYear }
  | { seq: number; t: number; type: "log"; level: "info" | "warn" | "ok"; text: string }
  | { seq: number; t: number; type: "done"; confirmedPct: number | null; issues: number }
  | { seq: number; t: number; type: "failed"; error: string }

// ─── Settings ─────────────────────────────────────────────────────────────────

export type Unit = "crore" | "lakh" | "million"
export type Grouping = "indian" | "international"
export type Negatives = "parentheses" | "minus"
export type Density = "comfortable" | "compact"

export interface Settings {
  unit: Unit
  grouping: Grouping
  negatives: Negatives
  density: Density
  showTicks: boolean
  defaultScope: ScopeChoice
  defaultFigures: FiguresMode
  defaultSpan: number
  aiEngine: "off" | "gemini" | "ollama"
  aiMode: "fallback" | "always"
  aiModel: string
  reduceMotion: boolean
}

export const DEFAULT_SETTINGS: Settings = {
  unit: "crore",
  grouping: "indian",
  negatives: "parentheses",
  density: "comfortable",
  showTicks: false,
  defaultScope: "consolidated",
  defaultFigures: "restated",
  defaultSpan: 6,
  aiEngine: "off",
  aiMode: "fallback",
  aiModel: "gemini-flash-latest",
  reduceMotion: false,
}
