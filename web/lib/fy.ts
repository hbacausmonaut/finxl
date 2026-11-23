import type { FiscalYear } from "./types"

/** 2025 → "FY25" */
export const fyLabel = (fy: FiscalYear) => `FY${String(fy % 100).padStart(2, "0")}`

/** 2025 → "Apr 2024 – Mar 2025" */
export const fyPeriod = (fy: FiscalYear) => `Apr ${fy - 1} – Mar ${fy}`

export const fyRange = (from: FiscalYear, to: FiscalYear): FiscalYear[] => {
  const out: FiscalYear[] = []
  for (let y = from; y <= to; y++) out.push(y)
  return out
}

export const rangeLabel = (from: FiscalYear, to: FiscalYear) =>
  from === to ? fyLabel(from) : `${fyLabel(from)}–${fyLabel(to)}`
