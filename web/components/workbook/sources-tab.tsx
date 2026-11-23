"use client"

import * as React from "react"
import { ArrowSquareOutIcon, CheckIcon, CircleNotchIcon, QuotesIcon, WarningIcon } from "@phosphor-icons/react"
import { toast } from "sonner"

import { useWb } from "@/components/workbook/context"
import { Button } from "@/components/ui/button"
import { Chip, Tip } from "@/components/ui/controls"
import { kindsOf, SHORT_TITLE } from "@/lib/adapter"
import { crossCheck, pdfUrl } from "@/lib/api"
import { qualityOf } from "@/lib/compute"
import { formatAmount } from "@/lib/format"
import { fyLabel } from "@/lib/fy"
import type { CrossCheckRow, FiscalYear } from "@/lib/types"
import { cn } from "@/lib/utils"

const HUE = { pl: "var(--pl)", bs: "var(--bs)", cf: "var(--cf)", ra: "var(--pl)" } as const

/** The workbook's Sources and Quality sheets: which pages, how much is confirmed, and how it compares outside. */
export function SourcesTab() {
  const { wb, scope, book, views, years, settings, goTo, run } = useWb()
  const amt = (v: number | undefined) => formatAmount(v, settings)
  const [check, setCheck] = React.useState<{ state: "idle" | "busy" | "done" | "error"; rows: CrossCheckRow[]; error?: string }>({ state: "idle", rows: [] })
  const cc = check.rows.filter((r) => r.scope === scope)
  const metrics = [...new Set(cc.map((r) => r.metric))]
  const runCheck = () => {
    setCheck({ state: "busy", rows: [] })
    crossCheck(run.id)
      .then((d) => setCheck({ state: "done", rows: d.rows }))
      .catch((e: Error) => setCheck({ state: "error", rows: [], error: e.message }))
  }
  const cite = (fy: FiscalYear) => `${wb.company.name}. (${fy}). Annual Report ${fy - 1}–${String(fy).slice(2)}.`

  return (
    <div className="space-y-8">
      <section>
        <Heading title="Confirmed by each report's own totals" note="Share of figures that sit inside a printed total which adds up. Select a cell to open that statement." />
        <div className="thin-scroll overflow-x-auto rounded-xl border bg-surface shadow-card">
          <table className="w-full border-separate border-spacing-0 text-[13px]">
            <thead>
              <tr>
                <th scope="col" className="sticky left-0 z-10 w-[150px] min-w-[150px] border-r border-b bg-surface px-3 py-2 text-left text-[12px] font-medium text-ink-3">
                  Statement
                </th>
                {years.map((y) => (
                  <th key={y} scope="col" className="num min-w-[84px] border-b px-2 py-2 text-center font-semibold">
                    {fyLabel(y)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {kindsOf(book).map((sheet) => (
                <tr key={sheet}>
                  <th scope="row" className="sticky left-0 z-10 border-r border-b bg-surface px-3 text-left font-medium">
                    <span className="flex items-center gap-2">
                      <span aria-hidden className="size-2 rounded-full" style={{ background: HUE[sheet] }} />
                      {SHORT_TITLE[sheet]}
                    </span>
                  </th>
                  {years.map((fy) => {
                    const q = qualityOf(views[sheet], fy)
                    const pct = q.cells ? q.confirmed / q.cells : 0
                    return (
                      <td key={fy} className="border-b p-1">
                        <button
                          type="button"
                          onClick={() => goTo({ sheet, row: views[sheet]!.rows.find((r) => r.kind !== "header" && views[sheet]!.values[r.id]?.[fy] !== undefined)?.id ?? "0", fy })}
                          title={`${q.confirmed} of ${q.cells} figures confirmed${q.failedTotals ? `; ${q.failedTotals} total doesn't add up` : ""}`}
                          className={cn(
                            "num flex h-8 w-full items-center justify-center gap-1 rounded-md text-[12.5px] font-medium transition-colors hover:ring-2 hover:ring-ink/15",
                            q.failedTotals ? "bg-warn/25 text-warn-ink" : "text-ink"
                          )}
                          // one hue, lighter = less confirmed
                          style={q.failedTotals ? undefined : { background: `color-mix(in oklab, var(--accent) ${Math.round(6 + pct * 16)}%, transparent)` }}
                        >
                          {q.failedTotals > 0 && <WarningIcon weight="fill" className="size-3" />}
                          {Math.round(pct * 100)}%
                        </button>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <Heading
          title="Headline figures against outside sources"
          note="NSE filings carry each year as first reported; Screener shows the latest restated figure. A difference usually means a restatement, not a misread."
        />
        {check.state !== "done" ? (
          <div className="flex flex-wrap items-center gap-3 rounded-xl border bg-surface p-4 shadow-card">
            <p className="min-w-0 flex-1 text-[13.5px] text-ink-2">
              {check.state === "error" ? check.error : "Compares revenue, profit, total assets and operating cash flow with NSE's XBRL filings and Screener. Takes a few seconds."}
            </p>
            <Button onClick={runCheck} disabled={check.state === "busy"}>
              {check.state === "busy" ? <><CircleNotchIcon className="animate-spin" /> Checking…</> : check.state === "error" ? "Try again" : "Run the cross-check"}
            </Button>
          </div>
        ) : metrics.length === 0 ? (
          <p className="rounded-xl border bg-surface p-4 text-[13.5px] text-ink-2 shadow-card">No outside source covers these years for the {scope} statements.</p>
        ) : (
        <div className="thin-scroll overflow-x-auto rounded-xl border bg-surface shadow-card">
          <table className="w-full border-separate border-spacing-0 text-[13px]">
            <thead>
              <tr>
                <th scope="col" className="sticky left-0 z-10 w-[170px] min-w-[170px] border-r border-b bg-surface px-3 py-2 text-left text-[12px] font-medium text-ink-3">
                  Within 0.5% of the outside figure
                </th>
                {years.map((y) => (
                  <th key={y} scope="col" className="num min-w-[84px] border-b px-2 py-2 text-center font-semibold">
                    {fyLabel(y)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {metrics.map((m) => (
                <tr key={m}>
                  <th scope="row" className="sticky left-0 z-10 h-10 border-r border-b bg-surface px-3 text-left font-medium">
                    {m}
                  </th>
                  {years.map((fy) => {
                    const r = cc.find((x) => x.metric === m && x.fy === fy)
                    return (
                      <td key={fy} className="border-b px-2 text-center">
                        {r ? <Agreement row={r} amt={amt} /> : <span className="text-ink-3">–</span>}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        )}
      </section>

      <section>
        <Heading title="Annual reports used" note={`${wb.reports.length} reports, ${scope} statements. Page numbers are positions in the PDF, not the printed folio.`} />
        <ul className="space-y-2">
          {wb.reports.map((rep) => {
            const src = book.sources.filter((s) => s.fy === rep.fy)
            return (
              <li key={rep.fy} className="flex flex-col gap-3 rounded-xl border bg-surface p-4 shadow-card md:flex-row md:items-center">
                <div className="min-w-0 md:w-52">
                  <div className="text-[14.5px] font-semibold">Annual Report {fyLabel(rep.fy)}</div>
                  <div className="num text-[12.5px] text-ink-3">
                    {rep.label ?? "Annual report"}
                    {rep.fy === run.request.from && years[0] < rep.fy ? ` · also gives ${fyLabel(years[0])}` : ""}
                  </div>
                </div>
                <div className="flex min-w-0 flex-1 flex-wrap gap-1.5">
                  {src.map((s) => (
                    <Chip key={s.sheet} className="h-7 gap-1.5 bg-sunken text-ink-2">
                      <span aria-hidden className="size-1.5 rounded-full" style={{ background: HUE[s.sheet] }} />
                      {SHORT_TITLE[s.sheet]}
                      <span className="num text-ink-3">p. {s.pages.join(", ")}</span>
                      {s.check === "OK" ? <CheckIcon weight="bold" className="text-good" aria-label={`Check passed: ${s.checkNote}`} /> : <WarningIcon weight="fill" className="text-warn" aria-label={`Needs checking: ${s.checkNote}`} />}
                    </Chip>
                  ))}
                </div>
                <div className="flex shrink-0 gap-1">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      void navigator.clipboard?.writeText(cite(rep.fy))
                      toast.success("Citation copied", { description: cite(rep.fy) })
                    }}
                  >
                    <QuotesIcon /> Cite
                  </Button>
                  <Button size="sm" asChild>
                    <a href={pdfUrl(wb.company.symbol, rep.fy)} target="_blank" rel="noreferrer">
                      Open PDF <ArrowSquareOutIcon />
                    </a>
                  </Button>
                </div>
              </li>
            )
          })}
        </ul>
      </section>
    </div>
  )
}

function Heading({ title, note }: { title: string; note: string }) {
  return (
    <div className="mb-3">
      <h2 className="font-sans text-[16px] font-semibold tracking-normal">{title}</h2>
      <p className="mt-0.5 max-w-3xl text-[13.5px] text-ink-2">{note}</p>
    </div>
  )
}

function Agreement({ row, amt }: { row: CrossCheckRow; amt: (v: number | undefined) => string }) {
  const ok = row.status === "OK"
  const nse = row.sources["NSE XBRL"]
  const scr = row.sources["Screener"]
  return (
    <Tip
      text={
        <span className="num block space-y-0.5 text-left">
          <span className="block">Workbook: {row.ours === null ? "blank" : amt(row.ours)}</span>
          <span className="block">NSE filing: {nse === undefined || nse === null ? "no filing for this year" : amt(nse)}</span>
          {scr !== undefined && scr !== null && <span className="block">Screener: {amt(scr)}</span>}
          {row.note && <span className="block max-w-64 font-sans">{row.note}</span>}
        </span>
      }
    >
      <span
        tabIndex={0}
        className={cn("inline-flex h-7 min-w-12 cursor-help items-center justify-center gap-1 rounded-md px-2 text-[12.5px] font-medium", ok ? "text-good-ink" : "bg-ink/[0.06] text-ink-2")}
      >
        {ok ? (
          <>
            <CheckIcon weight="bold" className="size-3.5" />
            <span className="sr-only">Agrees</span>
          </>
        ) : (
          <>{row.status === "MISSING" ? "missing" : `≠ ${row.basis === "NSE XBRL" ? "NSE" : "Screener"}`}</>
        )}
      </span>
    </Tip>
  )
}
