"use client"

import * as React from "react"
import {
  ArrowCounterClockwiseIcon,
  ArrowLeftIcon,
  CheckCircleIcon,
  CheckIcon,
  MinusCircleIcon,
  PencilSimpleIcon,
  WarningIcon,
  XIcon,
} from "@phosphor-icons/react"

import { useWb } from "@/components/workbook/context"
import { SourcePage } from "@/components/workbook/source-page"
import { Button } from "@/components/ui/button"
import { Chip } from "@/components/ui/controls"
import { formatAmount, formatPerShare, parseAmount, UNITS } from "@/lib/format"
import { fyLabel } from "@/lib/fy"
import { glossaryFor } from "@/lib/glossary"
import { parentOf } from "@/lib/compute"
import { SHORT_TITLE } from "@/lib/adapter"
import { cellKey, type CellRef, type Issue } from "@/lib/types"
import { cn } from "@/lib/utils"

/** The panel beside the table: where a figure came from, or what needs a look. */
export function Inspector() {
  const { panel, setPanel, selected, issues } = useWb()
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center gap-1 border-b px-3 py-2">
        {panel === "source" && issues.length > 0 ? (
          <Button variant="ghost" size="sm" onClick={() => setPanel("issues")}>
            <ArrowLeftIcon /> {issues.length} to review
          </Button>
        ) : (
          <span className="px-2 text-[13.5px] font-semibold">{panel === "issues" ? "Review" : "Source"}</span>
        )}
        <Button variant="ghost" size="sm" square aria-label="Close panel" className="ml-auto" onClick={() => setPanel(null)}>
          <XIcon />
        </Button>
      </div>
      <div className="thin-scroll min-h-0 flex-1 overflow-y-auto">
        {panel === "issues" ? <IssueList /> : selected ? <Source key={cellKey(selected)} cell={selected} /> : null}
      </div>
    </div>
  )
}

// ─── Source of one figure ─────────────────────────────────────────────────────

function Source({ cell }: { cell: CellRef }) {
  const { views, book, settings, review, reviewApi, sourceReport, issues } = useWb()
  const view = views[cell.sheet]!
  const row = view.rows.find((r) => r.id === cell.row)!
  const key = cellKey(cell)
  const value = view.values[row.id]?.[cell.fy]
  const status = view.status[row.id]?.[cell.fy]
  const restated = book.restatements[key]
  const edited = review.edits[key] !== undefined
  const second = book.secondReadings.find((s) => cellKey(s.cell) === key)
  const eps = issues.find((i) => i.kind === "eps" && cellKey(i.cell) === key)
  const reportFy = sourceReport(cell.fy, cell.sheet, cell.row)
  const src = book.sources.find((s) => s.fy === reportFy && s.sheet === cell.sheet)
  const [editing, setEditing] = React.useState(false)
  const fmt = (v: number | undefined) => (row.perShare ? formatPerShare(v, settings) : formatAmount(v, settings))

  return (
    <div className="space-y-6 p-4 animate-fade">
      <header>
        <p className="text-[12.5px] text-ink-2">
          {view.title} · {fyLabel(cell.fy)}
        </p>
        <h2 className="mt-0.5 font-sans text-[16px] leading-snug font-semibold tracking-normal">{row.label}</h2>
        <div className="mt-3 flex items-end justify-between gap-3">
          <div>
            <div className="display num text-[32px] leading-none font-semibold">{fmt(value) || "–"}</div>
            <div className="mt-1.5 text-[12.5px] text-ink-3">{row.perShare ? "₹ per share" : UNITS[settings.unit].label}</div>
          </div>
          {!editing && (
            <Button size="sm" onClick={() => setEditing(true)}>
              <PencilSimpleIcon /> Correct
            </Button>
          )}
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5">
          <StatusChip status={status} covered={Boolean(parentOf(view, row.id, cell.fy)) || Boolean(view.groups[row.id]?.[cell.fy])} />
          {edited && <Chip tone="accent">Corrected by you</Chip>}
          {restated && <Chip>Restated</Chip>}
        </div>
      </header>

      {editing && (
        <EditBox
          initial={value}
          perShare={Boolean(row.perShare)}
          onCancel={() => setEditing(false)}
          onSave={(v) => {
            reviewApi.edit(cell, v)
            setEditing(false)
          }}
        />
      )}
      {edited && !editing && (
        <button type="button" onClick={() => reviewApi.clearEdit(cell)} className="flex items-center gap-1.5 text-[13px] font-medium text-accent-ink hover:underline">
          <ArrowCounterClockwiseIcon className="size-4" /> Put back the extracted figure ({fmt(book.values[cell.sheet]?.[row.id]?.[cell.fy])})
        </button>
      )}

      {second && !edited && (
        <Callout tone="warn" title="A second reading disagrees">
          <p>
            Re-reading page {second.page} gives <b className="num font-semibold">{fmt(second.value)}</b>. {second.note}
          </p>
          <Button size="sm" variant="primary" className="mt-2.5" onClick={() => reviewApi.edit(cell, second.value)}>
            Use {fmt(second.value)}
          </Button>
        </Callout>
      )}
      {eps?.kind === "eps" && (
        <Callout tone="warn" title="This per-share figure looks off">
          <p>
            Profit for the year ÷ shares gives about <b className="num font-semibold">{formatPerShare(eps.expected, settings)}</b>. Check it against the page.
          </p>
          <Button size="sm" variant="primary" className="mt-2.5" onClick={() => reviewApi.edit(cell, eps.expected)}>
            Use {formatPerShare(eps.expected, settings)}
          </Button>
        </Callout>
      )}

      <Footing cell={cell} />

      <section>
        <h3 className="mb-2 font-sans text-[13px] font-semibold tracking-normal text-ink-2">Where it was read</h3>
        <SourcePage
          key={`${reportFy}:${cell.sheet}`}
          reportFy={reportFy}
          pages={second && !edited ? [second.page] : (src?.pages ?? [])}
          value={row.perShare ? undefined : value}
          label={row.label}
        />
        <p className="mt-2.5 text-[13px] text-ink-2">
          Annual Report {fyLabel(reportFy)}
          <span className="text-ink-3"> · read by the {/ai|llm|gemini/i.test(src?.method ?? "") ? "AI fallback" : "parser"}</span>
        </p>
        {reportFy !== cell.fy && (
          <p className="mt-1.5 text-[12.5px] text-ink-3">
            {cell.fy < reportFy ? `${fyLabel(cell.fy)} is the comparative column of the ${fyLabel(reportFy)} report, the newest one that shows this year.` : null}
          </p>
        )}
      </section>

      {restated && (
        <section>
          <h3 className="mb-2 font-sans text-[13px] font-semibold tracking-normal text-ink-2">Restated in the {fyLabel(restated.restatedIn)} report</h3>
          <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border bg-line text-[13px]">
            <div className="bg-surface p-3">
              <dt className="text-[12px] text-ink-3">As first reported</dt>
              <dd className="num mt-0.5 text-[15px] font-medium">{fmt(restated.asReported)}</dd>
            </div>
            <div className="bg-surface p-3">
              <dt className="text-[12px] text-ink-3">Latest figure</dt>
              <dd className="num mt-0.5 text-[15px] font-medium">{fmt(restated.latest)}</dd>
            </div>
          </dl>
          <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
            The {fyLabel(cell.fy)} report printed one figure; a later report shows this year differently, usually after a reclassification or an accounting change.
          </p>
        </section>
      )}

      {glossaryFor(row.label) && (
        <section className="rounded-lg bg-sunken p-3">
          <h3 className="font-sans text-[12.5px] font-semibold tracking-normal text-ink-2">What this line means</h3>
          <p className="mt-1 text-[13px] leading-relaxed text-ink-2">{glossaryFor(row.label)}</p>
        </section>
      )}
    </div>
  )
}

function StatusChip({ status, covered }: { status: "ok" | "fail" | null | undefined; covered: boolean }) {
  if (status === "ok")
    return (
      <Chip tone="good">
        <CheckCircleIcon weight="fill" /> Confirmed by the report&rsquo;s totals
      </Chip>
    )
  if (status === "fail")
    return (
      <Chip tone="warn">
        <WarningIcon weight="fill" /> Doesn&rsquo;t add up
      </Chip>
    )
  return (
    <Chip>
      <MinusCircleIcon /> {covered ? "Not confirmed: its total doesn't add up" : "No total covers this line"}
    </Chip>
  )
}

/** The arithmetic behind a tick: the total this figure belongs to, re-added. */
function Footing({ cell }: { cell: CellRef }) {
  const { views, settings } = useWb()
  const view = views[cell.sheet]!
  const self = view.rows.find((r) => r.id === cell.row)!
  const target = view.groups[self.id]?.[cell.fy] ? self : parentOf(view, self.id, cell.fy)
  if (!target) {
    return self.perShare ? null : (
      <section>
        <h3 className="mb-1 font-sans text-[13px] font-semibold tracking-normal text-ink-2">How it&rsquo;s checked</h3>
        <p className="text-[13px] leading-relaxed text-ink-2">No printed total adds this line in, so arithmetic can&rsquo;t confirm it. Compare it with the page below.</p>
      </section>
    )
  }
  const parts = view.groups[target.id]?.[cell.fy]?.members ?? []
  const label = (id: string) => view.rows.find((r) => r.id === id)?.label ?? id
  const sum = view.sums[target.id]?.[cell.fy]
  const printed = view.values[target.id]?.[cell.fy]
  const ok = view.status[target.id]?.[cell.fy] === "ok"
  const amt = (v: number | undefined) => formatAmount(v, settings)

  return (
    <section>
      <h3 className="mb-2 font-sans text-[13px] font-semibold tracking-normal text-ink-2">How it&rsquo;s checked</h3>
      <div className="overflow-hidden rounded-lg border text-[13px]">
        <table className="w-full">
          <tbody>
            {parts.map(([id, sign]) => (
              <tr key={id} className={cn("border-b", id === cell.row && "bg-tint/10 font-medium")}>
                <td className="w-6 py-1.5 pl-3 text-ink-3">{sign < 0 ? "−" : "+"}</td>
                <td className="max-w-0 truncate py-1.5 pr-2" title={label(id)}>
                  {label(id)}
                </td>
                <td className="num py-1.5 pr-3 text-right whitespace-nowrap">{amt(view.values[id]?.[cell.fy])}</td>
              </tr>
            ))}
            <tr className="border-b bg-sunken">
              <td />
              <td className="py-1.5 pr-2 text-ink-2">Adds up to</td>
              <td className="num py-1.5 pr-3 text-right font-medium">{amt(sum)}</td>
            </tr>
            <tr className="bg-sunken">
              <td />
              <td className="max-w-0 truncate py-1.5 pr-2 text-ink-2" title={target.label}>
                Report prints, as {target.label}
              </td>
              <td className="num py-1.5 pr-3 text-right font-medium">{amt(printed)}</td>
            </tr>
          </tbody>
        </table>
        <div className={cn("flex items-center gap-1.5 border-t px-3 py-2 font-medium", ok ? "bg-good/8 text-good-ink" : "bg-warn/20 text-warn-ink")}>
          {ok ? <CheckIcon weight="bold" className="size-3.5" /> : <WarningIcon weight="fill" className="size-3.5" />}
          {ok ? "They match, so every figure in this total is confirmed." : `Off by ${amt(Math.abs((sum ?? 0) - (printed ?? 0)))}. One of these figures was probably misread.`}
        </div>
      </div>
    </section>
  )
}

function EditBox({ initial, perShare, onSave, onCancel }: { initial: number | undefined; perShare: boolean; onSave: (v: number) => void; onCancel: () => void }) {
  const { settings } = useWb()
  const u = UNITS[settings.unit]
  const [text, setText] = React.useState(() => (initial === undefined ? "" : perShare ? initial.toFixed(2) : (initial * u.perCrore).toFixed(u.decimals)))
  const [bad, setBad] = React.useState(false)
  const id = React.useId()
  return (
    <form
      className="rounded-lg border border-accent/40 bg-accent/[0.05] p-3"
      onSubmit={(e) => {
        e.preventDefault()
        const v = perShare ? Number(text.replace(/[^\d.-]/g, "")) : parseAmount(text, settings.unit)
        if (v === null || !Number.isFinite(v) || !text.trim()) return setBad(true)
        onSave(v)
      }}
    >
      <label htmlFor={id} className="text-[12.5px] font-medium text-ink-2">
        Figure as printed on the page ({perShare ? "₹ per share" : u.label})
      </label>
      <input
        id={id}
        autoFocus
        inputMode="decimal"
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          setBad(false)
        }}
        onKeyDown={(e) => e.key === "Escape" && onCancel()}
        aria-invalid={bad}
        className="num mt-1.5 h-9 w-full rounded-md border border-line-2 bg-surface px-3 text-[14px] outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 aria-[invalid=true]:border-bad"
      />
      {bad && <p className="mt-1 text-[12.5px] text-bad-ink">Enter a number, for example 115.75 or (12.40).</p>}
      <div className="mt-2.5 flex justify-end gap-2">
        <Button size="sm" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button size="sm" variant="primary" type="submit">
          Save
        </Button>
      </div>
    </form>
  )
}

function Callout({ tone, title, children }: { tone: "warn"; title: string; children: React.ReactNode }) {
  return (
    <div className={cn("rounded-lg p-3 text-[13px] leading-relaxed", tone === "warn" && "bg-warn/20")}>
      <div className="mb-1 flex items-center gap-1.5 font-semibold text-warn-ink">
        <WarningIcon weight="fill" className="size-4" /> {title}
      </div>
      {children}
    </div>
  )
}

// ─── Review list ──────────────────────────────────────────────────────────────

function IssueList() {
  const { issues, kept, fixed, reviewApi, review, views } = useWb()
  const issueRowLabel = (i: Issue) => (i.kind === "label" ? i.label : views[i.cell.sheet]?.rows.find((r) => r.id === i.cell.row)?.label ?? "")
  const total = issues.length + kept.length + fixed
  if (total === 0)
    return (
      <div className="px-6 py-14 text-center">
        <CheckCircleIcon weight="duotone" className="mx-auto size-10 text-good" />
        <p className="mt-3 text-[15px] font-medium">Nothing to review</p>
        <p className="mt-1 text-[13.5px] text-ink-2">Every printed total adds up and every label reads cleanly.</p>
      </div>
    )
  return (
    <div className="p-4">
      <div className="mb-4">
        <div className="flex items-baseline justify-between text-[13px]">
          <span className="font-medium">
            <span className="num">{total - issues.length}</span> of <span className="num">{total}</span> dealt with
          </span>
          {(Object.keys(review.edits).length > 0 || kept.length > 0 || Object.keys(review.labels).length > 0) && (
            <button type="button" onClick={reviewApi.reset} className="text-[12.5px] text-ink-3 hover:text-ink">
              Undo all
            </button>
          )}
        </div>
        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-ink/[0.07]">
          <div className="h-full rounded-full bg-good transition-[width] duration-300" style={{ width: `${((total - issues.length) / total) * 100}%` }} />
        </div>
      </div>

      {issues.length === 0 && (
        <p className="mb-4 flex items-center gap-2 rounded-lg bg-good/10 px-3 py-2.5 text-[13.5px] font-medium text-good-ink">
          <CheckCircleIcon weight="fill" className="size-4" /> All dealt with. The download includes your corrections.
        </p>
      )}

      <ul className="space-y-2.5">
        {issues.map((i) => (
          <li key={i.id}>
            <IssueCard issue={i} />
          </li>
        ))}
      </ul>

      {kept.length > 0 && (
        <>
          <h3 className="mt-6 mb-2 font-sans text-[12.5px] font-semibold tracking-normal text-ink-3">Kept as printed</h3>
          <ul className="space-y-1.5">
            {kept.map((i) => (
              <li key={i.id} className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2 text-[13px] text-ink-2">
                <span className="truncate">{issueTitle(i, issueRowLabel)}</span>
                <button type="button" onClick={() => reviewApi.unkeep(i.id)} className="shrink-0 text-[12.5px] font-medium text-accent-ink hover:underline">
                  Reopen
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}


function issueTitle(i: Issue, label: (i: Issue) => string) {
  if (i.kind === "total") return `${label(i)} doesn't add up · ${fyLabel(i.cell.fy)}`
  if (i.kind === "eps") return `Earnings per share looks off · ${fyLabel(i.cell.fy)}`
  return `Garbled label · ${SHORT_TITLE[i.sheet]}`
}

function IssueCard({ issue }: { issue: Issue }) {
  const { settings, reviewApi, goTo, views } = useWb()
  const amt = (v: number) => formatAmount(v, settings)
  const show = () =>
    goTo(issue.kind === "label" ? { sheet: issue.sheet, row: issue.row } : issue.kind === "total" && issue.suspect ? { sheet: issue.suspect.cell.sheet, row: issue.suspect.cell.row, fy: issue.suspect.cell.fy } : { sheet: issue.cell.sheet, row: issue.cell.row, fy: issue.cell.fy })
  const rowLabel = (sheet: keyof typeof views, id: string) => views[sheet]?.rows.find((r) => r.id === id)?.label ?? id
  const issueRowLabel = (i: Issue) => (i.kind === "label" ? i.label : rowLabel(i.cell.sheet, i.cell.row))
  const [name, setName] = React.useState("")

  return (
    <article className="rounded-xl border bg-surface p-3.5 shadow-card">
      <div className="flex items-start gap-2">
        <WarningIcon weight="fill" className={cn("mt-0.5 size-4 shrink-0", issue.kind === "label" ? "text-odd" : "text-warn")} />
        <div className="min-w-0 flex-1">
          <h3 className="font-sans text-[13.5px] leading-snug font-semibold tracking-normal">{issueTitle(issue, issueRowLabel)}</h3>
          <p className="mt-1 text-[13px] leading-relaxed text-ink-2">
            {issue.kind === "total" && (
              <>
                Its items add up to <span className="num font-medium text-ink">{amt(issue.sum)}</span>; the report prints{" "}
                <span className="num font-medium text-ink">{amt(issue.printed)}</span>.
                {issue.suspect && (
                  <>
                    {" "}
                    Re-reading <span className="font-medium text-ink">{rowLabel(issue.suspect.cell.sheet, issue.suspect.cell.row)}</span> gives{" "}
                    <span className="num font-medium text-ink">{amt(issue.suspect.value)}</span>, which makes it tie.
                  </>
                )}
              </>
            )}
            {issue.kind === "eps" && (
              <>
                Read as <span className="num font-medium text-ink">{formatPerShare(issue.value, settings)}</span>, but profit ÷ shares gives about{" "}
                <span className="num font-medium text-ink">{formatPerShare(issue.expected, settings)}</span>.
              </>
            )}
            {issue.kind === "label" && (
              <>
                Read as <span className="font-medium text-odd-ink">{issue.label}</span>. The words don&rsquo;t read cleanly; type the label as the page prints it.
              </>
            )}
          </p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-1.5 pl-6">
        {issue.kind === "total" && issue.suspect && (
          <Button size="sm" variant="primary" onClick={() => reviewApi.edit(issue.suspect!.cell, issue.suspect!.value)}>
            Use {amt(issue.suspect.value)}
          </Button>
        )}
        {issue.kind === "eps" && (
          <Button size="sm" variant="primary" onClick={() => reviewApi.edit(issue.cell, issue.expected)}>
            Use {formatPerShare(issue.expected, settings)}
          </Button>
        )}
        {issue.kind === "label" && (
          <form
            className="flex w-full gap-1.5"
            onSubmit={(e) => {
              e.preventDefault()
              if (name.trim()) reviewApi.rename(issue, name.trim())
            }}
          >
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Label as printed"
              aria-label="Corrected label"
              className="h-8 min-w-0 flex-1 rounded-md border border-line-2 bg-surface px-2.5 text-[13px] outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
            />
            <Button size="sm" variant="primary" type="submit" disabled={!name.trim()}>
              Rename
            </Button>
          </form>
        )}
        <Button size="sm" onClick={show}>
          Show
        </Button>
        <Button size="sm" variant="ghost" onClick={() => reviewApi.keep(issue.id)}>
          Keep as printed
        </Button>
      </div>
    </article>
  )
}
