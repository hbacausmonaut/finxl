"use client"

import * as React from "react"
import { ArrowDownRightIcon, ArrowRightIcon, ArrowUpRightIcon, CheckCircleIcon, WarningIcon } from "@phosphor-icons/react"

import { Columns, Lines, Spark } from "@/components/workbook/charts"
import { useWb } from "@/components/workbook/context"
import { Button } from "@/components/ui/button"
import { Chip, Tip } from "@/components/ui/controls"
import { overallQuality, summaryMetrics, type MetricRow } from "@/lib/compute"
import { formatAmount, formatHeadline, formatPct, formatPerShare, UNITS } from "@/lib/format"
import { fyLabel } from "@/lib/fy"
import { cn } from "@/lib/utils"

/** The workbook's Summary sheet: headline figures, the ratios the engine computes, and how much is confirmed. */
export function SummaryTab() {
  const { views, years, settings, issues, kept, fixed, setPanel, goTo } = useWb()
  const { figures, ratios } = React.useMemo(() => summaryMetrics(views, years), [views, years])
  const q = overallQuality(views, years)
  const pct = q.cells ? q.confirmed / q.cells : 0
  const latest = years[years.length - 1]
  const prev = years[years.length - 2]
  const by = (rows: MetricRow[], id: string) => rows.find((r) => r.id === id)!
  const u = UNITS[settings.unit]

  const tiles: Array<{ row: MetricRow; kind: "amount" | "pct"; color: string }> = [
    { row: by(figures, "rev"), kind: "amount", color: "var(--pl)" },
    { row: by(figures, "pat"), kind: "amount", color: "var(--pl)" },
    { row: by(ratios, "npm"), kind: "pct", color: "var(--pl)" },
    { row: by(ratios, "roe"), kind: "pct", color: "var(--bs)" },
    { row: by(ratios, "cfopat"), kind: "pct", color: "var(--cf)" },
  ]
  const axisAmount = (v: number) => {
    const n = v * u.perLakh
    return Math.abs(n) >= 1000 ? `${(n / 1000).toFixed(n % 1000 === 0 ? 0 : 1)}K` : String(Math.round(n))
  }
  const counts = {
    total: issues.filter((i) => i.kind === "total").length,
    eps: issues.filter((i) => i.kind === "eps").length,
    label: issues.filter((i) => i.kind === "label").length,
  }

  return (
    <div className="space-y-4">
      {/* how much of this workbook has proved itself */}
      <section className="flex flex-col gap-4 rounded-xl border bg-surface p-5 shadow-card md:flex-row md:items-center">
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="display num text-[34px] leading-none font-semibold">{(pct * 100).toFixed(1)}%</span>
            <span className="text-[14px] text-ink-2">of figures confirmed by the reports&rsquo; own totals</span>
          </div>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-ink/[0.07]" role="img" aria-label={`${q.confirmed} of ${q.cells} figures confirmed`}>
            <div className="h-full rounded-full bg-good transition-[width] duration-500" style={{ width: `${pct * 100}%` }} />
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {issues.length === 0 ? (
              <Chip tone="good">
                <CheckCircleIcon weight="fill" /> Every printed total adds up
              </Chip>
            ) : (
              <>
                {counts.total > 0 && (
                  <Chip tone="warn">
                    <WarningIcon weight="fill" /> {counts.total} {counts.total === 1 ? "total doesn't" : "totals don't"} add up
                  </Chip>
                )}
                {counts.eps > 0 && (
                  <Chip tone="warn">
                    <WarningIcon weight="fill" /> {counts.eps} per-share figure looks off
                  </Chip>
                )}
                {counts.label > 0 && (
                  <Chip tone="odd">
                    <WarningIcon weight="fill" /> {counts.label} garbled label
                  </Chip>
                )}
              </>
            )}
            {fixed + kept.length > 0 && <Chip>{fixed + kept.length} dealt with</Chip>}
          </div>
        </div>
        {issues.length > 0 && (
          <Button variant="primary" onClick={() => setPanel("issues")} className="shrink-0">
            Review {issues.length} {issues.length === 1 ? "item" : "items"} <ArrowRightIcon weight="bold" />
          </Button>
        )}
      </section>

      <section aria-label={`Key figures for ${fyLabel(latest)}`} className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        {tiles.map(({ row, kind, color }) => {
          const v = row.values[latest]
          const p = prev === undefined ? undefined : row.values[prev]
          const delta = v === undefined || p === undefined ? undefined : kind === "amount" ? (p ? v / p - 1 : undefined) : v - p
          return (
            <div key={row.id} className="rounded-xl border bg-surface p-4 shadow-card">
              <div className="flex items-center justify-between gap-2 text-[12.5px] text-ink-2">
                <span className="truncate">{row.label.replace(" from operations", "")}</span>
                <span className="num text-ink-3">{fyLabel(latest)}</span>
              </div>
              <div className="display num mt-2 text-[23px] leading-none font-semibold">
                {v === undefined ? "–" : kind === "amount" ? formatHeadline(v, settings) : formatPct(v, settings)}
              </div>
              <div className="mt-2 flex items-end justify-between gap-2">
                {delta === undefined ? (
                  <span />
                ) : (
                  <span className={cn("num flex items-center gap-0.5 text-[12.5px] font-medium", delta >= 0 ? "text-good-ink" : "text-bad-ink")}>
                    {delta >= 0 ? <ArrowUpRightIcon weight="bold" className="size-3.5" /> : <ArrowDownRightIcon weight="bold" className="size-3.5" />}
                    {kind === "amount" ? `${Math.abs(delta * 100).toFixed(1)}%` : `${Math.abs(delta * 100).toFixed(1)} pts`}
                  </span>
                )}
                <Spark values={years.map((y) => row.values[y])} color={color} />
              </div>
            </div>
          )
        })}
      </section>

      <div className="grid gap-3 lg:grid-cols-2">
        <Columns
          title={`Revenue and net profit, ${u.label}`}
          years={years}
          series={[
            { name: "Revenue", color: "var(--pl)", values: years.map((y) => by(figures, "rev").values[y]) },
            { name: "Net profit", color: "var(--sum)", values: years.map((y) => by(figures, "pat").values[y]) },
          ]}
          format={(v) => formatAmount(v, settings)}
          tick={axisAmount}
        />
        <Lines
          title="Margin and return on equity"
          years={years}
          series={[
            { name: "Net profit margin", color: "var(--pl)", values: years.map((y) => by(ratios, "npm").values[y]) },
            { name: "Return on equity", color: "var(--sum)", values: years.map((y) => by(ratios, "roe").values[y]) },
          ]}
          format={(v) => formatPct(v, settings)}
          tick={(v) => `${Math.round(v * 100)}%`}
        />
      </div>

      <section className="thin-scroll overflow-x-auto rounded-xl border bg-surface shadow-card">
        <table className="w-full border-separate border-spacing-0 text-[13px]">
          <thead>
            <tr>
              <th scope="col" className="sticky left-0 z-10 w-[170px] min-w-[170px] border-r border-b bg-surface px-3 py-2 text-left text-[12px] font-medium text-ink-3 md:w-[300px] md:min-w-[300px]">
                Key metrics, {u.label}
              </th>
              {years.map((y) => (
                <th key={y} scope="col" className="num min-w-[92px] border-b px-3 py-2 text-right font-semibold">
                  {fyLabel(y)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[...figures, ...ratios].map((row, i) => (
              <tr key={row.id} className="group/row">
                <th scope="row" className={cn("sticky left-0 z-10 h-9 border-r border-b bg-surface px-3 text-left font-normal group-hover/row:bg-sunken", i === figures.length && "border-t border-t-line-2")}>
                  {row.source ? (
                    <button type="button" onClick={() => goTo(row.source!)} className="flex w-full items-center gap-1.5 text-left hover:text-accent-ink" title="Open this line in its statement">
                      <span className="truncate">{row.label}</span>
                      <ArrowRightIcon className="size-3.5 shrink-0 opacity-0 transition-opacity group-hover/row:opacity-100" />
                    </button>
                  ) : (
                    <Tip text={row.formula} side="right">
                      <span className="cursor-help underline decoration-line-2 decoration-dotted underline-offset-4">{row.label}</span>
                    </Tip>
                  )}
                </th>
                {years.map((y) => {
                  const v = row.values[y]
                  return (
                    <td key={y} className={cn("num border-b px-3 text-right whitespace-nowrap group-hover/row:bg-sunken", i === figures.length && "border-t border-t-line-2")}>
                      {row.format === "pct" ? formatPct(v, settings) : row.format === "per-share" ? formatPerShare(v, settings) : formatAmount(v, settings)}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <p className="text-[12.5px] text-ink-3">
        The same rows as the Summary sheet in the Excel file, where they are live formulas. Hover a ratio to see how it is worked out.
      </p>
    </div>
  )
}
