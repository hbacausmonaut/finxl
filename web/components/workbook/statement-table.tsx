"use client"

import * as React from "react"
import { CaretRightIcon, CheckIcon, WarningIcon } from "@phosphor-icons/react"

import { useWb } from "@/components/workbook/context"
import { commonBase, transform, type ViewMode } from "@/lib/compute"
import { formatAmount, formatPct, formatPerShare, UNITS } from "@/lib/format"
import { fyLabel } from "@/lib/fy"
import { cellKey, type CellRef, type StatementKind } from "@/lib/types"
import { cn } from "@/lib/utils"

/**
 * One statement, every year side by side.
 * The label column and the year header stay put while the figures scroll.
 * Arrow keys move between figures; Enter (or a click) opens the source.
 */
export function StatementTable({
  sheet,
  mode,
  query,
  collapsed,
  onToggle,
}: {
  sheet: StatementKind
  mode: ViewMode
  query: string
  collapsed: Set<string>
  onToggle: (section: string) => void
}) {
  const { views, years, scope, book, settings, review, selected, select, panel, figures, sourceReport, run, wb } = useWb()
  const view = views[sheet]!
  const base = React.useMemo(() => commonBase(book, sheet), [book, sheet])
  const compact = settings.density === "compact"
  const q = query.trim().toLowerCase()

  const rows = view.rows.filter((r) => {
    if (q) {
      if (r.kind === "header") return view.rows.some((x) => x.section === r.id && x.label.toLowerCase().includes(q))
      return r.label.toLowerCase().includes(q)
    }
    return !(r.kind === "item" && r.section && collapsed.has(r.section))
  })
  const figureRows = rows.filter((r) => r.kind !== "header")
  const scroller = React.useRef<HTMLDivElement>(null)
  const [focus, setFocus] = React.useState<{ r: number; c: number }>({ r: 0, c: years.length - 1 })

  const move = (r: number, c: number) => {
    const rr = Math.max(0, Math.min(figureRows.length - 1, r))
    const cc = Math.max(0, Math.min(years.length - 1, c))
    scroller.current?.querySelector<HTMLElement>(`[data-r="${rr}"][data-c="${cc}"]`)?.focus()
  }
  const onKeyDown = (e: React.KeyboardEvent) => {
    const t = e.target as HTMLElement
    if (t.dataset.r === undefined) return
    const r = Number(t.dataset.r)
    const c = Number(t.dataset.c)
    const to: Record<string, [number, number]> = {
      ArrowUp: [r - 1, c],
      ArrowDown: [r + 1, c],
      ArrowLeft: [r, c - 1],
      ArrowRight: [r, c + 1],
      Home: [r, 0],
      End: [r, years.length - 1],
      PageUp: [r - 8, c],
      PageDown: [r + 8, c],
    }
    if (to[e.key]) {
      e.preventDefault()
      move(...to[e.key])
    }
  }

  const rowH = compact ? "h-7" : "h-9"
  const unitLabel = mode === "values" ? UNITS[settings.unit].label : mode === "common" ? "% of base" : "% change"
  let ri = -1

  return (
    <div ref={scroller} className="thin-scroll max-h-[calc(100dvh-13.5rem)] min-h-64 overflow-auto overscroll-x-contain rounded-xl border bg-surface shadow-card">
      <table role="grid" aria-label={`${view.title}, ${scope}`} onKeyDown={onKeyDown} className="w-full border-separate border-spacing-0 text-[13px]">
        <thead>
          <tr>
            <th scope="col" className="sticky top-0 left-0 z-30 w-[150px] min-w-[150px] border-r border-b bg-surface px-3 py-2 text-left align-bottom text-[12px] font-medium text-ink-3 md:w-[300px] md:min-w-[300px]">
              {unitLabel}
            </th>
            {years.map((fy) => {
              const from = sourceReport(fy, sheet)
              const comparative = fy < run.request.from
              return (
                <th
                  key={fy}
                  scope="col"
                  title={comparative ? `Comparative column of the ${fyLabel(from)} report` : from === fy ? `From the ${fyLabel(fy)} annual report` : `As shown in the ${fyLabel(from)} annual report`}
                  className={cn("sticky top-0 z-20 min-w-[92px] border-b bg-surface px-3 py-2 text-right align-bottom", compact && "min-w-[84px]")}
                >
                  <span className="num block text-[13px] font-semibold">{fyLabel(fy)}</span>
                  {!compact && <span className="num block text-[11px] font-normal text-ink-3">{wb.columns[fy] ?? `Mar ${fy}`}</span>}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            if (row.kind === "header") {
              const open = !collapsed.has(row.id) || Boolean(q)
              return (
                <tr key={row.id}>
                  <th scope="rowgroup" className={cn("sticky left-0 z-10 border-r border-b bg-surface px-1.5 text-left", rowH)}>
                    <button
                      type="button"
                      onClick={() => onToggle(row.id)}
                      aria-expanded={open}
                      className="flex h-full w-full items-center gap-1 rounded-md px-1.5 text-[12.5px] font-semibold text-ink-2 hover:text-ink"
                    >
                      <CaretRightIcon weight="bold" className={cn("size-3 shrink-0 transition-transform", open && "rotate-90")} />
                      <span className="truncate" style={{ paddingLeft: row.level * 12 }}>{row.label}</span>
                    </button>
                  </th>
                  <td colSpan={years.length} className="border-b" />
                </tr>
              )
            }
            ri++
            const r = ri
            const total = row.kind === "total"
            const garbled = view.garbled.has(row.id)
            return (
              <tr key={row.id} className={cn("group/row animate-row", row.strong && "[&>*]:bg-[color-mix(in_oklab,var(--sunken)_55%,var(--surface))]")}>
                <th
                  scope="row"
                  title={row.label}
                  className={cn(
                    "sticky left-0 z-10 border-r border-b bg-surface px-3 text-left font-normal group-hover/row:bg-sunken",
                    rowH,
                    total && "font-medium",
                    row.strong && "font-semibold",
                    total && "border-t border-t-line-2"
                  )}
                  style={{ paddingLeft: 12 + row.level * 14 + (row.section ? 12 : 0) }}
                >
                  <span className={cn("flex items-center gap-1.5", garbled && "text-odd-ink")}>
                    {garbled && <WarningIcon weight="fill" className="size-3.5 shrink-0 text-odd" aria-label="Label looks garbled" />}
                    <span className="truncate">{row.label}</span>
                    {row.junk && <span className="shrink-0 rounded bg-odd/15 px-1 text-[10.5px] text-odd-ink" title={row.junk}>page text?</span>}
                  </span>
                </th>
                {years.map((fy, c) => {
                  const cell: CellRef = { scope, sheet, row: row.id, fy }
                  const key = cellKey(cell)
                  const value = transform(view, mode, row.id, fy, years, base)
                  const text =
                    mode === "values" ? (row.perShare ? formatPerShare(value, settings) : formatAmount(value, settings)) : row.perShare ? "" : formatPct(value, settings)
                  const status = view.status[row.id]?.[fy]
                  const restated = book.restatements[key]
                  const edited = review.edits[key] !== undefined
                  const isSel = selected !== null && cellKey(selected) === key
                  const label = `${row.label}, ${fyLabel(fy)}: ${text || "blank"}${status === "fail" ? ", total does not add up" : status === "ok" ? ", confirmed" : ""}${restated ? ", restated" : ""}${edited ? ", edited" : ""}`
                  return (
                    <td key={fy} role="gridcell" className={cn("border-b p-0", total && "border-t border-t-line-2")}>
                      <button
                        type="button"
                        data-r={r}
                        data-c={c}
                        data-cell={key}
                        tabIndex={focus.r === r && focus.c === c ? 0 : -1}
                        aria-label={label}
                        aria-pressed={isSel}
                        onFocus={() => {
                          setFocus({ r, c })
                          if (panel === "source") select(cell)
                        }}
                        onClick={() => select(cell)}
                        className={cn(
                          "num relative flex w-full items-center justify-end px-3 whitespace-nowrap outline-none transition-colors",
                          rowH,
                          total && "font-medium",
                          row.strong && "font-semibold",
                          "hover:bg-ink/[0.045] focus-visible:shadow-[inset_0_0_0_2px_var(--tint)]",
                          status === "fail" && "bg-warn/25 hover:bg-warn/35",
                          isSel && "bg-tint/10 shadow-[inset_0_0_0_2px_var(--tint)]",
                          figures === "as-reported" && restated && "text-src"
                        )}
                      >
                        {settings.showTicks && status === "ok" && mode === "values" && (
                          <CheckIcon weight="bold" aria-hidden className="absolute top-1/2 left-1.5 size-2.5 -translate-y-1/2 text-good" />
                        )}
                        {status === "fail" && <WarningIcon weight="fill" aria-hidden className="absolute top-1/2 left-1.5 size-3 -translate-y-1/2 text-warn-ink" />}
                        {text}
                        {restated && (
                          <sup aria-hidden className="-mr-1.5 ml-0.5 text-[9px] font-semibold text-src">
                            r
                          </sup>
                        )}
                        {edited && <span aria-hidden className="absolute top-1 right-1 size-1.5 rounded-full bg-accent" />}
                      </button>
                    </td>
                  )
                })}
              </tr>
            )
          })}
          {rows.length === 0 && (
            <tr>
              <td colSpan={years.length + 1} className="px-4 py-10 text-center text-[14px] text-ink-3">
                No line item matches “{query}”.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
