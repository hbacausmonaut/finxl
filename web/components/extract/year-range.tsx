"use client"

import * as React from "react"

import { Button } from "@/components/ui/button"
import { Select, Skeleton } from "@/components/ui/controls"
import { fyLabel } from "@/lib/fy"
import type { FiscalYear, ReportRef } from "@/lib/types"
import { cn } from "@/lib/utils"

/**
 * Pick a span from the years that actually have a report on file.
 * Click a start year, then an end year; or use the selects or a preset.
 */
export function YearRange({
  reports,
  from,
  to,
  onChange,
}: {
  reports: ReportRef[] | null
  from: FiscalYear
  to: FiscalYear
  onChange: (from: FiscalYear, to: FiscalYear) => void
}) {
  const [anchor, setAnchor] = React.useState<FiscalYear | null>(null)
  const [hover, setHover] = React.useState<FiscalYear | null>(null)
  const refs = React.useRef(new Map<FiscalYear, HTMLButtonElement>())

  if (!reports) {
    return (
      <div className="space-y-3" aria-busy="true" aria-label="Looking up which reports are on file">
        <div className="flex gap-3">
          <Skeleton className="h-9 w-28" />
          <Skeleton className="h-9 w-28" />
        </div>
        <Skeleton className="h-12 w-full" />
        <p className="text-[13px] text-ink-3">Looking up which annual reports are on file…</p>
      </div>
    )
  }

  const years = reports.map((r) => r.fy).sort((a, b) => a - b)
  const min = years[0]
  const max = years[years.length - 1]
  const scanned = new Set<FiscalYear>()
  const lo = anchor !== null && hover !== null ? Math.min(anchor, hover) : from
  const hi = anchor !== null && hover !== null ? Math.max(anchor, hover) : to

  const click = (fy: FiscalYear) => {
    if (anchor === null) {
      setAnchor(fy)
      setHover(fy)
    } else {
      onChange(Math.min(anchor, fy), Math.max(anchor, fy))
      setAnchor(null)
      setHover(null)
    }
  }
  const onKey = (e: React.KeyboardEvent, fy: FiscalYear) => {
    if (e.key === "Escape" && anchor !== null) {
      setAnchor(null)
      setHover(null)
      return
    }
    const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0
    if (!d) return
    e.preventDefault()
    const next = Math.min(max, Math.max(min, fy + d))
    refs.current.get(next)?.focus()
    if (anchor !== null) setHover(next)
  }

  const opts = [...years].reverse().map((y) => ({ value: String(y), label: `FY ${y}` }))
  const presets: Array<[string, FiscalYear, FiscalYear]> = [
    ...[3, 5, 10].filter((n) => n < years.length).map((n): [string, FiscalYear, FiscalYear] => [`Last ${n}`, max - n + 1, max]),
    [`All ${years.length}`, min, max],
  ]
  const count = to - from + 1

  return (
    <div>
      <div className="flex flex-wrap items-end gap-x-3 gap-y-3">
        <label className="block">
          <span className="mb-1 block text-[12.5px] text-ink-2">From</span>
          <Select label="First fiscal year" value={String(from)} onChange={(v) => onChange(Number(v), Math.max(Number(v), to))} options={opts} className="w-28" />
        </label>
        <label className="block">
          <span className="mb-1 block text-[12.5px] text-ink-2">To</span>
          <Select label="Last fiscal year" value={String(to)} onChange={(v) => onChange(Math.min(from, Number(v)), Number(v))} options={opts} className="w-28" />
        </label>
        <div className="ml-auto flex gap-1">
          {presets.map(([label, f, t]) => (
            <Button key={label} size="sm" variant={from === f && to === t ? "soft" : "ghost"} onClick={() => onChange(f, t)}>
              {label}
            </Button>
          ))}
        </div>
      </div>

      <div
        role="group"
        aria-label={`Years with a report on file, ${fyLabel(min)} to ${fyLabel(max)}. Choose a start year, then an end year.`}
        className="mt-4 flex h-12 overflow-hidden rounded-lg border border-line-2 bg-sunken"
        onMouseLeave={() => anchor !== null && setHover(anchor)}
      >
        {years.map((fy, i) => {
          const inRange = fy >= lo && fy <= hi
          const end = fy === lo || fy === hi
          return (
            <button
              key={fy}
              ref={(el) => {
                if (el) refs.current.set(fy, el)
              }}
              type="button"
              aria-pressed={inRange}
              aria-label={`${fyLabel(fy)}, April ${fy - 1} to March ${fy}${scanned.has(fy) ? ", scanned report" : ""}`}
              title={scanned.has(fy) ? "Scanned report: needs the AI fallback" : `Apr ${fy - 1} – Mar ${fy}`}
              tabIndex={fy === from ? 0 : -1}
              onClick={() => click(fy)}
              onMouseEnter={() => anchor !== null && setHover(fy)}
              onKeyDown={(e) => onKey(e, fy)}
              className={cn(
                "num relative min-w-0 flex-1 border-r border-line text-[12px] font-medium transition-colors last:border-r-0 focus-visible:z-10 focus-visible:outline-offset-[-2px]",
                inRange ? "bg-accent/15 text-ink" : "text-ink-3 hover:bg-ink/[0.05] hover:text-ink",
                end && "bg-accent text-white hover:bg-accent",
                anchor !== null && "cursor-crosshair"
              )}
            >
              <span className={cn(years.length > 12 && i % 2 === 1 && !end && "max-sm:hidden")}>{String(fy % 100).padStart(2, "0")}</span>
              {scanned.has(fy) && <span aria-hidden className={cn("absolute bottom-1.5 left-1/2 size-1 -translate-x-1/2 rounded-full", end ? "bg-white" : "bg-odd")} />}
            </button>
          )
        })}
      </div>

      <p className="mt-2 text-[13px] text-ink-2" aria-live="polite">
        {anchor !== null ? (
          <span className="text-accent-ink">Now choose the last year. Esc cancels.</span>
        ) : (
          <>
            <span className="num font-medium text-ink">{count}</span> {count === 1 ? "report" : "reports"}, April {from - 1} to March {to}
            {scanned.size > 0 && (
              <span className="text-ink-3">
                {" "}
                · <span className="mr-1 inline-block size-1.5 rounded-full bg-odd align-middle" />
                scanned report
              </span>
            )}
          </>
        )}
      </p>
    </div>
  )
}
