"use client"

import * as React from "react"

import type { Views } from "@/lib/compute"
import type { useReview } from "@/lib/store"
import type { CellRef, FiguresMode, FiscalYear, Issue, ReviewState, RunRecord, Scope, ScopeBook, Settings, StatementKind, Workbook } from "@/lib/types"

export type TabId = "summary" | StatementKind | "sources"
export type PanelMode = "source" | "issues" | null

/** The tab colours, as spreadsheet tabs have them. */
export const TAB_TINT: Record<TabId, string> = {
  summary: "var(--sum)",
  pl: "var(--pl)",
  bs: "var(--bs)",
  cf: "var(--cf)",
  ra: "var(--pl)",
  sources: "var(--src)",
}

export interface WorkbookContext {
  run: RunRecord
  wb: Workbook
  scope: Scope
  book: ScopeBook
  years: FiscalYear[]
  views: Views
  figures: FiguresMode
  settings: Settings
  review: ReviewState
  reviewApi: ReturnType<typeof useReview>[1]
  /** Flagged and not yet dealt with. */
  issues: Issue[]
  /** Flagged, looked at, kept as printed. */
  kept: Issue[]
  /** How many flagged items an edit has resolved. */
  fixed: number
  selected: CellRef | null
  panel: PanelMode
  select: (cell: CellRef | null) => void
  setPanel: (p: PanelMode) => void
  /** Open a statement at a row (and year), and point at it. */
  goTo: (target: { sheet: StatementKind; row: string; fy?: FiscalYear }) => void
  /** The annual report a figure was read from (a statement's usual one for that year when no row is given). */
  sourceReport: (fy: FiscalYear, sheet?: StatementKind, row?: string) => FiscalYear
}

const Ctx = React.createContext<WorkbookContext | null>(null)
export const WorkbookProvider = Ctx.Provider

export function useWb() {
  const c = React.useContext(Ctx)
  if (!c) throw new Error("useWb must be used inside a workbook")
  return c
}
