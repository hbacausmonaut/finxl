/**
 * Domain types. These mirror what the DocFetcher engine produces today
 * (finxl.run → merged rows, sources, quality) so the mock API can be swapped
 * for the real one without reshaping the UI.
 *
 * Money is integer ₹ lakh everywhere (1 crore = 100 lakh); units are a display
 * concern. Per-share figures are plain ₹.
 */

export type FiscalYear = number

export type Scope = "consolidated" | "standalone"
export type ScopeChoice = Scope | "both"
/** finxl `restated` flag: newest report showing each year, or each year's own report. */
export type FiguresMode = "restated" | "as-reported"
export type StatementKind = "pl" | "bs" | "cf"
export type AiMode = "off" | "fallback" | "always"

export interface Company {
  symbol: string
  name: string
  sector: string
  cap: "Large cap" | "Mid cap" | "Small cap"
  /** Only the demo company has its own (fictional) dataset in this build. */
  isDemo?: boolean
}

/** One annual report listed for a company (finxl.list_reports). */
export interface ReportRef {
  fy: FiscalYear
  url: string
  pages: number
  sizeMb: number
  /** No text layer: the parser can't read it without the AI fallback. */
  scanned: boolean
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

/**
 * header: a caption with no figures ("Current assets")
 * item:   a line item
 * total:  a printed total that should equal the items of its section
 * calc:   a printed line that follows from other lines (profit before tax, total assets)
 */
export type RowKind = "header" | "item" | "total" | "calc"

export interface RowDef {
  id: string
  label: string
  kind: RowKind
  level: 0 | 1 | 2
  /** item → the header it sits under; total → the header it closes. */
  section?: string
  /** calc → signed references to other rows. */
  formula?: Array<[rowId: string, sign: 1 | -1]>
  perShare?: boolean
  strong?: boolean
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

/** One row of the engine's Sources sheet. */
export interface SourceEntry {
  fy: FiscalYear
  scope: Scope
  sheet: StatementKind
  /** PDF page positions (not printed page numbers). */
  pages: number[]
  method: "parser" | "ai"
  check: "OK" | "CHECK" | "MISSING"
  checkNote: string
  url: string
}

/** What a later report changed about an earlier year. */
export interface Restatement {
  asReported: number
  restatedIn: FiscalYear
  reason: string
}

/** A second reading of one figure (AI fallback re-reading the page). */
export interface SecondReading {
  cell: CellRef
  value: number
  note: string
}

export interface ScopeBook {
  scope: Scope
  /** Printed value of every row that carries figures: sheet → row → fy. */
  values: Record<StatementKind, Record<string, Record<FiscalYear, number>>>
  /** Row labels as extracted (may be garbled). */
  labels: Record<StatementKind, Record<string, string>>
  restatements: Record<string, Restatement>
  secondReadings: SecondReading[]
  /** Rows whose label failed the dictionary check, with the decoded suggestion. */
  garbled: Array<{ sheet: StatementKind; row: string; label: string; suggestion: string }>
  /** Expected EPS from profit ÷ shares, for the per-share sanity check. */
  epsExpected: Record<FiscalYear, number>
  sources: SourceEntry[]
}

/** accuracy_check.py: headline figures against outside sources. */
export interface CrossCheckRow {
  metric: "Revenue" | "Net profit" | "Total assets" | "Cash from operations"
  fy: FiscalYear
  ours: number
  nse?: number
  screener?: number
}

export interface Workbook {
  id: string
  request: ExtractionRequest
  company: Company
  years: FiscalYear[]
  scopes: Scope[]
  books: Record<Scope, ScopeBook | undefined>
  reports: ReportRef[]
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
  | { id: string; kind: "label"; scope: Scope; sheet: StatementKind; row: string; label: string; suggestion: string }

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
export type RunStatus = "running" | "done" | "failed"

export interface RunRecord {
  id: string
  request: ExtractionRequest
  companyName: string
  startedAt: number
  status: RunStatus
  durationSec?: number
  /** Snapshot for the library list. */
  confirmedPct?: number
  issues?: number
  error?: string
  /** Seeded example rows that ship with the demo. */
  sample?: boolean
}

export interface RunEvent {
  t: number
  stage: StageId
  type: "start" | "year" | "log" | "end"
  fy?: FiscalYear
  level?: "info" | "warn" | "ok"
  text?: string
}

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
