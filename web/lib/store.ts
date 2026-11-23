"use client"

import * as React from "react"

import { getReview, getRun, listRuns, putReview, removeRun, startRun } from "./api"
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

// ─── Library (the server files runs per visitor) ──────────────────────────────

interface LibraryState {
  runs: RunRecord[]
  loaded: boolean
  error?: string
}
const libraryStore = createStore<LibraryState>("finxl.library.v4", { runs: [], loaded: false })
let inflight: Promise<void> | null = null

function refresh() {
  inflight ??= listRuns()
    .then((runs) => libraryStore.set({ runs, loaded: true }))
    .catch((e: Error) => libraryStore.set((s) => ({ ...s, loaded: true, error: e.message })))
    .finally(() => (inflight = null))
  return inflight
}

/** The visitor's runs, newest first. Refreshes on mount, and every few seconds while one is queued or running. */
export function useLibrary() {
  const lib = useStore(libraryStore)
  const hydrated = useHydrated()
  const busy = lib.runs.some((r) => r.status === "queued" || r.status === "running")
  React.useEffect(() => {
    void refresh()
  }, [])
  React.useEffect(() => {
    if (!busy) return
    const id = setInterval(() => void refresh(), 4000)
    return () => clearInterval(id)
  }, [busy])
  return { runs: hydrated ? lib.runs : [], hydrated: hydrated && lib.loaded, error: lib.error }
}

export const library = {
  /** Starts a run (or finds the same finished one). Returns the server's run record. */
  start: async (request: ExtractionRequest) => {
    const run = await startRun(request)
    libraryStore.set((s) => ({ ...s, runs: [run, ...s.runs.filter((r) => r.id !== run.id)] }))
    return run
  },
  refresh,
  /** Fetches one run (a shared link) and files it. */
  fetch: async (id: string) => {
    const run = await getRun(id)
    libraryStore.set((s) => ({ ...s, runs: s.runs.some((r) => r.id === id) ? s.runs.map((r) => (r.id === id ? run : r)) : [run, ...s.runs] }))
    return run
  },
  patch: (id: string, patch: Partial<RunRecord>) =>
    libraryStore.set((s) => ({ ...s, runs: s.runs.map((r) => (r.id === id ? { ...r, ...patch } : r)) })),
  remove: (id: string) => {
    libraryStore.set((s) => ({ ...s, runs: s.runs.filter((r) => r.id !== id) }))
    return removeRun(id).catch(() => refresh())
  },
}

// ─── Review edits, per workbook ───────────────────────────────────────────────

const reviewStore = createStore<Record<string, ReviewState>>("finxl.review.v3", {})

const timers = new Map<string, ReturnType<typeof setTimeout>>()
const pulled = new Set<string>()
const isEmpty = (r?: ReviewState) => !r || (!Object.keys(r.edits).length && !Object.keys(r.labels).length && !r.kept.length)

/** A reader's corrections: kept in this browser at once, saved to the server a moment later (the Excel uses them). */
export function useReview(runId: string) {
  const all = useStore(reviewStore)
  const review = all[runId] ?? EMPTY_REVIEW
  React.useEffect(() => {
    if (pulled.has(runId)) return
    pulled.add(runId)
    getReview(runId)
      .then((server) => {
        if (!isEmpty(server) && isEmpty(reviewStore.get()[runId])) reviewStore.set((s) => ({ ...s, [runId]: server }))
      })
      .catch(() => {})
  }, [runId])
  const api = React.useMemo(() => {
    const patch = (f: (r: ReviewState) => ReviewState) => {
      reviewStore.set((s) => ({ ...s, [runId]: f(s[runId] ?? EMPTY_REVIEW) }))
      clearTimeout(timers.get(runId))
      timers.set(runId, setTimeout(() => void putReview(runId, reviewStore.get()[runId] ?? EMPTY_REVIEW).catch(() => {}), 600))
    }
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

/** Saves a run's corrections now (before a download, so the Excel has them). */
export async function flushReview(runId: string) {
  clearTimeout(timers.get(runId))
  await putReview(runId, reviewStore.get()[runId] ?? EMPTY_REVIEW).catch(() => {})
}
