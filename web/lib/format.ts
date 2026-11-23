import type { Settings, Unit } from "./types"

export type NumberPrefs = Pick<Settings, "unit" | "grouping" | "negatives">

/** Values arrive as ₹ lakh. 1 crore = 100 lakh = 10 million. */
export const UNITS: Record<Unit, { label: string; short: string; perLakh: number; decimals: number }> = {
  crore: { label: "₹ crore", short: "cr", perLakh: 0.01, decimals: 2 },
  lakh: { label: "₹ lakh", short: "lakh", perLakh: 1, decimals: 0 },
  million: { label: "₹ million", short: "mn", perLakh: 0.1, decimals: 1 },
}

const cache = new Map<string, Intl.NumberFormat>()
function nf(grouping: Settings["grouping"], decimals: number) {
  const key = `${grouping}:${decimals}`
  let f = cache.get(key)
  if (!f) {
    f = new Intl.NumberFormat(grouping === "indian" ? "en-IN" : "en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })
    cache.set(key, f)
  }
  return f
}

function signed(v: number, body: string, negatives: Settings["negatives"]) {
  if (v >= 0) return body
  return negatives === "parentheses" ? `(${body})` : `−${body}`
}

/** A statement amount in the reader's unit. Blank stays blank, zero prints as a dash. */
export function formatAmount(lakh: number | undefined, p: NumberPrefs, decimals?: number): string {
  if (lakh === undefined || Number.isNaN(lakh)) return ""
  const u = UNITS[p.unit]
  const d = decimals ?? u.decimals
  const v = lakh * u.perLakh
  if (Math.abs(v) < 0.5 * 10 ** -d) return "–"
  return signed(v, nf(p.grouping, d).format(Math.abs(v)), p.negatives)
}

export function formatPerShare(v: number | undefined, p: NumberPrefs): string {
  if (v === undefined) return ""
  return signed(v, nf(p.grouping, 2).format(Math.abs(v)), p.negatives)
}

export function formatPct(v: number | undefined, p: Pick<Settings, "negatives">, decimals = 1): string {
  if (v === undefined || !Number.isFinite(v)) return ""
  return signed(v, `${(Math.abs(v) * 100).toFixed(decimals)}%`, p.negatives)
}

/** Headline figure for tiles and prose: "₹3,701 cr". */
export function formatHeadline(lakh: number, p: NumberPrefs): string {
  const u = UNITS[p.unit]
  const v = lakh * u.perLakh
  const d = Math.abs(v) >= 1000 ? 0 : Math.abs(v) >= 100 ? 1 : u.decimals
  return signed(v, `₹${nf(p.grouping, d).format(Math.abs(v))} ${u.short}`, p.negatives)
}

/** Parses what a reader types into an edit box, in their unit, back to ₹ lakh. */
export function parseAmount(text: string, unit: Unit): number | null {
  const neg = /^\s*[(−-]/.test(text)
  const n = Number(text.replace(/[^\d.]/g, ""))
  if (!text.trim() || !Number.isFinite(n)) return null
  return Math.round(((neg ? -n : n) / UNITS[unit].perLakh) * 100) / 100
}

export function formatDuration(sec: number) {
  if (sec < 60) return `${Math.round(sec)}s`
  return `${Math.floor(sec / 60)}m ${Math.round(sec % 60)}s`
}

export function timeAgo(ts: number, now = Date.now()) {
  const d = (now - ts) / 1000
  if (d < 60) return "just now"
  if (d < 3600) return `${Math.floor(d / 60)} min ago`
  if (d < 86400) return `${Math.floor(d / 3600)} h ago`
  const days = Math.floor(d / 86400)
  if (days < 7) return `${days} d ago`
  return new Date(ts).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })
}
