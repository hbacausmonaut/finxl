"use client"

import * as React from "react"

import { newRunId, sampleRuns } from "./api"
import { cellKey, DEFAULT_SETTINGS, EMPTY_REVIEW, rowKey, type CellRef, type ExtractionRequest, type ReviewState, type RunRecord, type Settings } from "./types"

/**
 * Small localStorage-backed stores read through useSyncExternalStore.
 * The server (and the first client paint) sees the defaults; saved state
 * arrives right after hydration, so nothing mismatches.
 */
function createStore<T>(key: string, initial: T) {
  let state = initial
  let loaded = false
  const listeners = new Set<() => void>()
  const load = () => {
    if (loaded || typeof window === "undefined") return
    loaded = true
    try {
      const raw = window.localStorage.getItem(key)
      if (raw) state = typeof initial === "object" && !Array.isArray(initial) ? { ...initial, ...JSON.parse(raw) } : JSON.parse(raw)
    } catch {
      /* unreadable or blocked storage: keep defaults */
    }
  }
  return {
    get: () => {
      load()
      return state
    },
    getServer: () => initial,
    set: (next: T | ((s: T) => T)) => {
      load()
      state = typeof next === "function" ? (next as (s: T) => T)(state) : next
      try {
        window.localStorage.setItem(key, JSON.stringify(state))
      } catch {
        /* storage full or blocked: state still lives for this visit */
      }
      listeners.forEach((l) => l())
    },
    subscribe: (l: () => void) => {
      listeners.add(l)
      return () => listeners.delete(l)
    },
  }
}

function useStore<T>(store: ReturnType<typeof createStore<T>>) {
  return React.useSyncExternalStore(store.subscribe, store.get, store.getServer)
}

/** True once the client has hydrated (saved state is available). */
export function useHydrated() {
  return React.useSyncExternalStore(
    () => () => {},
    () => true,
    () => false
  )
}

// ─── Settings ─────────────────────────────────────────────────────────────────

const settingsStore = createStore<Settings>("finxl.settings.v3", DEFAULT_SETTINGS)

export function useSettings() {
  const settings = useStore(settingsStore)
  const update = React.useCallback((patch: Partial<Settings>) => settingsStore.set((s) => ({ ...s, ...patch })), [])
  return [settings, update] as const
}
export const resetSettings = () => settingsStore.set(DEFAULT_SETTINGS)

// ─── Library ──────────────────────────────────────────────────────────────────

interface LibraryState {
  runs: RunRecord[]
  /** Sample rows the reader removed. */
  hidden: string[]
}
const libraryStore = createStore<LibraryState>("finxl.library.v3", { runs: [], hidden: [] })
let samples: RunRecord[] | null = null

export function useLibrary() {
  const lib = useStore(libraryStore)
  const hydrated = useHydrated()
  const runs = React.useMemo(() => {
    if (!hydrated) return []
    samples ??= sampleRuns()
    return [...lib.runs, ...samples.filter((s) => !lib.hidden.includes(s.id))].sort((a, b) => b.startedAt - a.startedAt)
  }, [lib, hydrated])
  return { runs, hydrated }
}

export const library = {
  /** Starts a run (finxl.run) and files it. Returns its id. */
  start: (request: ExtractionRequest, companyName: string) => {
    const id = newRunId()
    libraryStore.set((s) => ({ ...s, runs: [{ id, request, companyName, startedAt: Date.now(), status: "running" as const }, ...s.runs].slice(0, 40) }))
    return id
  },
  add: (run: RunRecord) => libraryStore.set((s) => ({ ...s, runs: [run, ...s.runs].slice(0, 40) })),
  patch: (id: string, patch: Partial<RunRecord>) =>
    libraryStore.set((s) => ({ ...s, runs: s.runs.map((r) => (r.id === id ? { ...r, ...patch } : r)) })),
  remove: (id: string) =>
    libraryStore.set((s) => ({ runs: s.runs.filter((r) => r.id !== id), hidden: id.startsWith("s_") ? [...s.hidden, id] : s.hidden })),
  clear: () => libraryStore.set({ runs: [], hidden: [] }),
}

// ─── Review edits, per workbook ───────────────────────────────────────────────

const reviewStore = createStore<Record<string, ReviewState>>("finxl.review.v3", {})

export function useReview(runId: string) {
  const all = useStore(reviewStore)
  const review = all[runId] ?? EMPTY_REVIEW
  const api = React.useMemo(() => {
    const patch = (f: (r: ReviewState) => ReviewState) => reviewStore.set((s) => ({ ...s, [runId]: f(s[runId] ?? EMPTY_REVIEW) }))
    return {
      edit: (cell: CellRef, value: number) => patch((r) => ({ ...r, edits: { ...r.edits, [cellKey(cell)]: value } })),
      clearEdit: (cell: CellRef) =>
        patch((r) => {
          const edits = { ...r.edits }
          delete edits[cellKey(cell)]
          return { ...r, edits }
        }),
      rename: (row: Pick<CellRef, "scope" | "sheet" | "row">, label: string) =>
        patch((r) => ({ ...r, labels: { ...r.labels, [rowKey(row)]: label } })),
      clearRename: (row: Pick<CellRef, "scope" | "sheet" | "row">) =>
        patch((r) => {
          const labels = { ...r.labels }
          delete labels[rowKey(row)]
          return { ...r, labels }
        }),
      keep: (issueId: string) => patch((r) => ({ ...r, kept: [...r.kept.filter((k) => k !== issueId), issueId] })),
      unkeep: (issueId: string) => patch((r) => ({ ...r, kept: r.kept.filter((k) => k !== issueId) })),
      reset: () => patch(() => EMPTY_REVIEW),
    }
  }, [runId])
  return [review, api] as const
}

// ─── Recent companies ─────────────────────────────────────────────────────────

const recentStore = createStore<string[]>("finxl.recent.v3", [])
export const useRecents = () => useStore(recentStore)
export const pushRecent = (symbol: string) => recentStore.set((s) => [symbol, ...s.filter((x) => x !== symbol)].slice(0, 6))
