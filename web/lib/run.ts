"use client"

import * as React from "react"

import { eventsUrl } from "./api"
import type { ExtractionRequest, FiscalYear, RunEvent, StageId } from "./types"

/** The five things finxl.run does, in order. */
export const STAGES: Array<{ id: StageId; title: string; doing: string }> = [
  { id: "lookup", title: "Find reports", doing: "Looking up the annual reports on file" },
  { id: "download", title: "Download PDFs", doing: "Downloading each year's report" },
  { id: "read", title: "Read statements", doing: "Finding and reading the statements in each report" },
  { id: "merge", title: "Line up years", doing: "Matching line items across years and checking totals" },
  { id: "write", title: "Write Excel", doing: "Building the workbook" },
]

export const fileName = (req: ExtractionRequest, years: FiscalYear[]) =>
  `${req.symbol}_Financials_FY${years[0]}-FY${years[years.length - 1]}.xlsx`

export interface StageProgress {
  status: "pending" | "running" | "done"
  /** Seconds since the epoch. */
  startedAt?: number
  endedAt?: number
  years: FiscalYear[]
}

export interface RunProgress {
  stages: Record<StageId, StageProgress>
  logs: Array<Extract<RunEvent, { type: "log" }>>
  /** 0–1, as the engine reports it. */
  fraction: number
  current?: StageId
  /** Place in the queue, while waiting for a free reader. */
  queued?: number
  startedAt?: number
  outcome?: { type: "done"; confirmedPct: number | null; issues: number } | { type: "failed"; error: string }
  connected: boolean
}

const fresh = (): RunProgress => ({
  stages: Object.fromEntries(STAGES.map((s) => [s.id, { status: "pending", years: [] }])) as unknown as RunProgress["stages"],
  logs: [],
  fraction: 0,
  connected: false,
})

function apply(p: RunProgress, e: RunEvent): RunProgress {
  const stages = { ...p.stages }
  const set = (id: StageId, patch: Partial<StageProgress>) => (stages[id] = { ...stages[id], ...patch })
  switch (e.type) {
    case "queued":
      return { ...p, queued: e.position }
    case "start":
      return { ...p, queued: undefined, startedAt: e.t }
    case "stage": {
      // A stage starting means the ones before it are over (merge can be skipped).
      const i = STAGES.findIndex((s) => s.id === e.stage)
      STAGES.slice(0, i).forEach((s) => stages[s.id].status !== "done" && set(s.id, { status: "done", endedAt: e.t, startedAt: stages[s.id].startedAt ?? e.t }))
      set(e.stage, { status: "running", startedAt: e.t })
      return { ...p, stages, current: e.stage, queued: undefined }
    }
    case "stage-end":
      set(e.stage, { status: "done", endedAt: e.t })
      return { ...p, stages }
    case "year":
      if (!stages[e.stage].years.includes(e.fy)) set(e.stage, { years: [...stages[e.stage].years, e.fy] })
      return { ...p, stages }
    case "progress":
      return { ...p, fraction: Math.max(p.fraction, e.fraction) }
    case "log":
      return { ...p, logs: [...p.logs, e] }
    case "done":
      STAGES.forEach((s) => stages[s.id].status !== "done" && set(s.id, { status: "done", endedAt: e.t }))
      return { ...p, stages, fraction: 1, current: undefined, outcome: { type: "done", confirmedPct: e.confirmedPct, issues: e.issues } }
    case "failed":
      return { ...p, current: undefined, outcome: { type: "failed", error: e.error } }
  }
  return p
}

/** Live progress of a run from the server's event stream (it replays from the start on connect). */
export function useRunProgress(id: string, active: boolean): RunProgress {
  const [p, setP] = React.useState<RunProgress>(fresh)
  React.useEffect(() => {
    if (!active) return
    setP(fresh())
    const es = new EventSource(eventsUrl(id))
    es.onopen = () => setP((x) => ({ ...x, connected: true }))
    es.onmessage = (m) => {
      try {
        const e = JSON.parse(m.data) as RunEvent
        setP((x) => apply(x, e))
        if (e.type === "done" || e.type === "failed") es.close()
      } catch {
        /* keep-alive or a partial line */
      }
    }
    es.onerror = () => setP((x) => ({ ...x, connected: false }))
    return () => es.close()
  }, [id, active])
  return p
}
