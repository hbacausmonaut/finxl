"use client"

import * as React from "react"
import Link from "next/link"
import NumberFlow from "@number-flow/react"
import { CaretRightIcon, CheckIcon, CircleNotchIcon } from "@phosphor-icons/react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { getWorkbook } from "@/lib/api"
import { computeAll, findIssues, overallQuality } from "@/lib/compute"
import { formatDuration } from "@/lib/format"
import { fyLabel, fyRange } from "@/lib/fy"
import { useNow } from "@/lib/hooks"
import { buildTimeline, progressAt, STAGES } from "@/lib/run"
import { library } from "@/lib/store"
import { EMPTY_REVIEW, type RunRecord } from "@/lib/types"
import { cn } from "@/lib/utils"

/** A run in progress: what stage it is on, which years are done, and how long is left. */
export function ProgressView({ run }: { run: RunRecord }) {
  const timeline = React.useMemo(() => buildTimeline(run), [run])
  const now = useNow(true)
  const elapsed = now ? Math.max(0, now - run.startedAt) : 0
  const years = React.useMemo(() => fyRange(run.request.from, run.request.to).reverse(), [run.request.from, run.request.to])
  const p = progressAt(timeline, elapsed, years.length)
  const left = Math.max(0, timeline.total - elapsed) / 1000

  // When the engine reports the last stage done, file the result in the library.
  React.useEffect(() => {
    if (!p.done) return
    const wb = getWorkbook(run)
    let cells = 0, confirmed = 0, issues = 0
    for (const scope of wb.scopes) {
      const book = wb.books[scope]!
      const views = computeAll(book, wb.years, run.request.figures, EMPTY_REVIEW)
      const q = overallQuality(views, wb.years)
      cells += q.cells
      confirmed += q.confirmed
      issues += findIssues(book, views, wb.years, EMPTY_REVIEW).length
    }
    library.patch(run.id, { status: "done", durationSec: Math.round(timeline.total / 1000), confirmedPct: Math.round((1000 * confirmed) / cells) / 10, issues })
    toast.success(`${run.companyName} is ready`, { description: issues ? `${issues} things to look at before you download.` : "Every total adds up." })
  }, [p.done, run, timeline.total])

  return (
    <div className="wash" style={{ ["--tint" as string]: "var(--pl)" }}>
      <div className="mx-auto max-w-3xl px-4 pt-10 pb-16 sm:px-6 sm:pt-14">
        <p className="text-[13.5px] text-ink-2">
          <Link href="/library" className="hover:text-ink">
            Library
          </Link>{" "}
          / {run.request.symbol}
        </p>
        <h1 className="mt-2 text-[30px] leading-tight font-semibold sm:text-[36px]">Reading {run.companyName.replace(/ Ltd$/, "")}</h1>
        <p className="num mt-1.5 text-[15px] text-ink-2">
          {years.length} annual {years.length === 1 ? "report" : "reports"}, {fyLabel(run.request.from)}–{fyLabel(run.request.to)} ·{" "}
          {run.request.scope === "both" ? "consolidated and standalone" : run.request.scope}
        </p>

        <div className="mt-8 rounded-xl border bg-surface p-5 shadow-card sm:p-6">
          <div className="flex items-end justify-between gap-4">
            <div className="display num text-[44px] leading-none font-semibold">
              <NumberFlow value={Math.round(p.fraction * 100)} suffix="%" />
            </div>
            <p className="num pb-1 text-[13.5px] text-ink-2" aria-live="off">
              {p.done ? "Done" : left > 1 ? `about ${formatDuration(left)} left` : "finishing"}
            </p>
          </div>
          <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-ink/[0.07]" role="progressbar" aria-label="Overall progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(p.fraction * 100)}>
            <div className="h-full rounded-full bg-accent transition-[width] duration-300 ease-linear" style={{ width: `${p.fraction * 100}%` }} />
          </div>

          <ol className="mt-6">
            {STAGES.map((s, i) => {
              const st = p.stages[s.id]
              const perYear = s.id === "download" || s.id === "read"
              return (
                <li key={s.id} className="relative flex gap-3.5 pb-5 last:pb-0">
                  {i < STAGES.length - 1 && <span aria-hidden className={cn("absolute top-6 bottom-0 left-[11px] w-px transition-colors duration-300", st.status === "done" ? "bg-good/50" : "bg-line-2")} />}
                  <span
                    className={cn(
                      "relative z-[1] mt-0.5 grid size-[23px] shrink-0 place-items-center rounded-full border transition-colors duration-300",
                      st.status === "done" && "border-good bg-good text-white",
                      st.status === "running" && "border-accent bg-surface text-accent",
                      st.status === "pending" && "border-line-2 bg-surface text-ink-3"
                    )}
                  >
                    {st.status === "done" ? <CheckIcon weight="bold" className="size-3" /> : st.status === "running" ? <CircleNotchIcon weight="bold" className="size-3.5 animate-spin" /> : <span className="num text-[11px]">{i + 1}</span>}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className={cn("text-[15px] font-medium", st.status === "pending" && "text-ink-3")}>{s.title}</span>
                      {st.startedAt !== undefined && (
                        <span className="num text-[12.5px] text-ink-3">{(((st.endedAt ?? elapsed) - st.startedAt) / 1000).toFixed(1)}s</span>
                      )}
                    </div>
                    {st.status === "running" && <p className="text-[13.5px] text-ink-2">{s.doing}</p>}
                    {perYear && st.status !== "pending" && (
                      <div className="mt-2 flex flex-wrap gap-1" aria-label={`${st.years.length} of ${years.length} years done`}>
                        {years.map((fy) => {
                          const done = st.years.includes(fy)
                          return (
                            <span
                              key={fy}
                              className={cn(
                                "num rounded-md px-1.5 py-0.5 text-[11.5px] font-medium transition-colors duration-300",
                                done ? "bg-good/12 text-good-ink" : "bg-ink/[0.05] text-ink-3"
                              )}
                            >
                              {fyLabel(fy)}
                            </span>
                          )
                        })}
                      </div>
                    )}
                  </div>
                </li>
              )
            })}
          </ol>
        </div>

        <Log lines={p.logs} />

        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 text-[13.5px] text-ink-2">
          <p>You can leave this page. The run keeps going and appears in your Library.</p>
          <Button variant="ghost" size="sm" onClick={() => library.patch(run.id, { startedAt: Date.now() - timeline.total - 1 })} title="Preview build only">
            Skip ahead (preview only)
          </Button>
        </div>
      </div>
    </div>
  )
}

function Log({ lines }: { lines: ReturnType<typeof progressAt>["logs"] }) {
  const ref = React.useRef<HTMLDivElement>(null)
  React.useEffect(() => {
    const el = ref.current
    if (el) el.scrollTop = el.scrollHeight
  }, [lines.length])
  return (
    <details className="group mt-4 rounded-xl border bg-surface shadow-card">
      <summary className="flex list-none items-center gap-1.5 px-5 py-3 text-[13.5px] font-medium text-ink-2 hover:text-ink [&::-webkit-details-marker]:hidden">
        <CaretRightIcon weight="bold" className="size-3.5 transition-transform group-open:rotate-90" />
        Run log
        <span className="num ml-auto text-[12.5px] font-normal text-ink-3">{lines.length} lines</span>
      </summary>
      <div ref={ref} role="log" className="thin-scroll max-h-64 overflow-y-auto border-t px-5 py-3 text-[12.5px] leading-relaxed">
        {lines.map((l, i) => (
          <div key={i} className="flex gap-3">
            <span className="num w-10 shrink-0 text-right text-ink-3">{(l.t / 1000).toFixed(1)}s</span>
            <span className={cn("min-w-0", l.level === "warn" ? "text-warn-ink" : l.level === "ok" ? "text-good-ink" : "text-ink-2")}>{l.text}</span>
          </div>
        ))}
      </div>
    </details>
  )
}
