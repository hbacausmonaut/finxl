"use client"

import * as React from "react"
import Link from "next/link"
import {
  CheckCircleIcon,
  CheckIcon,
  CopyIcon,
  DownloadSimpleIcon,
  FileCsvIcon,
  ListChecksIcon,
  MagnifyingGlassIcon,
  MicrosoftExcelLogoIcon,
  RowsIcon,
  WarningIcon,
  XIcon,
} from "@phosphor-icons/react"
import { Tabs } from "radix-ui"
import { toast } from "sonner"

import { TAB_TINT, WorkbookProvider, useWb, type PanelMode, type TabId, type WorkbookContext } from "@/components/workbook/context"
import { Inspector } from "@/components/workbook/inspector"
import { SourcesTab } from "@/components/workbook/sources-tab"
import { StatementTable } from "@/components/workbook/statement-table"
import { SummaryTab } from "@/components/workbook/summary-tab"
import { Button } from "@/components/ui/button"
import { Chip, Segmented, Select, Tip, useSlide } from "@/components/ui/controls"
import { Popover, Sheet } from "@/components/ui/overlay"
import { downloadExcel, getWorkbook } from "@/lib/api"
import { COMMON_BASE, computeAll, findIssues, issueCell, type StatementView, type ViewMode } from "@/lib/compute"
import { timeAgo, UNITS } from "@/lib/format"
import { fyLabel } from "@/lib/fy"
import { useMediaQuery } from "@/lib/hooks"
import { fileName } from "@/lib/run"
import { SHEETS } from "@/lib/sheets"
import { useReview, useSettings } from "@/lib/store"
import { cellKey, EMPTY_REVIEW, type CellRef, type FiguresMode, type FiscalYear, type RunRecord, type Scope, type StatementKind, type Unit } from "@/lib/types"
import { cn } from "@/lib/utils"

const TABS: Array<{ id: TabId; label: string }> = [
  { id: "summary", label: "Summary" },
  { id: "pl", label: "P&L" },
  { id: "bs", label: "Balance Sheet" },
  { id: "cf", label: "Cash Flow" },
  { id: "sources", label: "Sources" },
]
const isStatement = (t: TabId): t is StatementKind => t === "pl" || t === "bs" || t === "cf"

export function WorkbookView({ run }: { run: RunRecord }) {
  const wb = React.useMemo(() => getWorkbook(run), [run])
  const [settings, setSettings] = useSettings()
  const [review, reviewApi] = useReview(run.id)
  const wide = useMediaQuery("(min-width: 1180px)")

  const [scope, setScope] = React.useState<Scope>(wb.scopes[0])
  const [tab, setTab] = React.useState<TabId>("summary")
  const [figures, setFigures] = React.useState<FiguresMode>(run.request.figures)
  const [mode, setMode] = React.useState<ViewMode>("values")
  const [query, setQuery] = React.useState("")
  const [collapsed, setCollapsed] = React.useState<Set<string>>(new Set())
  const [selected, setSelected] = React.useState<CellRef | null>(null)
  const [panel, setPanelState] = React.useState<PanelMode>(null)
  const [tabsRef, tabBox] = useSlide(tab)

  const book = wb.books[scope]!
  const years = wb.years
  const views = React.useMemo(() => computeAll(book, years, figures, review), [book, years, figures, review])
  const flagged = React.useMemo(() => findIssues(book, views, years, review), [book, views, years, review])
  const baseline = React.useMemo(() => findIssues(book, computeAll(book, years, figures, EMPTY_REVIEW), years, EMPTY_REVIEW).length, [book, years, figures])
  const issues = flagged.filter((i) => !review.kept.includes(i.id))
  const kept = flagged.filter((i) => review.kept.includes(i.id))
  const fixed = Math.max(0, baseline - flagged.length)

  const setPanel = React.useCallback((p: PanelMode) => {
    setPanelState(p)
    if (p === null) setSelected(null)
  }, [])
  const select = React.useCallback((cell: CellRef | null) => {
    setSelected(cell)
    if (cell) setPanelState("source")
  }, [])

  const goTo = React.useCallback(
    (target: { sheet: StatementKind; row: string; fy?: FiscalYear }) => {
      const cell: CellRef = { scope, sheet: target.sheet, row: target.row, fy: target.fy ?? years[years.length - 1] }
      const section = SHEETS[target.sheet].rows.find((r) => r.id === target.row)?.section
      setTab(target.sheet)
      setMode("values")
      setQuery("")
      if (section) setCollapsed((c) => new Set([...c].filter((x) => x !== section)))
      setSelected(cell)
      // On a narrow screen the panel covers the table, so step aside and point at the figure.
      setPanelState(wide ? "source" : null)
      // Once the statement has painted, bring the figure into view and mark it briefly.
      setTimeout(() => {
        const el = document.querySelector<HTMLElement>(`[data-cell="${cellKey(cell)}"]`)
        if (!el) return
        el.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" })
        el.animate([{ background: "color-mix(in oklab, var(--tint) 45%, transparent)" }, { background: "transparent" }], { duration: 1500, easing: "ease-out" })
      }, 80)
    },
    [scope, years, wide]
  )

  const sourceReport = React.useCallback(
    (fy: FiscalYear) => (figures === "restated" ? Math.min(fy + 1, run.request.to) : Math.max(fy, run.request.from)),
    [figures, run.request.from, run.request.to]
  )

  // Say so when a correction makes a total tie: the reader's edit worked.
  const lastFixed = React.useRef(fixed)
  React.useEffect(() => {
    if (fixed > lastFixed.current) toast.success("That now adds up", { description: "The total ties to its line items with your correction." })
    lastFixed.current = fixed
  }, [fixed])

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement
      if (e.metaKey || e.ctrlKey || e.altKey || t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return
      if (e.key === "i") setPanelState((p) => (p === "issues" ? null : "issues"))
      if (e.key === "t") setSettings({ showTicks: !settings.showTicks })
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [settings.showTicks, setSettings])

  const ctx: WorkbookContext = {
    run, wb, scope, book, years, views, figures, settings, review, reviewApi, issues, kept, fixed, selected, panel, select, setPanel, goTo, sourceReport,
  }
  const hasRestatements = Object.keys(book.restatements).length > 0
  const sectionIds = isStatement(tab) ? SHEETS[tab].rows.filter((r) => r.kind === "header" && r.level === 1).map((r) => r.id) : []
  const condensed = sectionIds.length > 0 && sectionIds.every((s) => collapsed.has(s))
  const issueCount = (id: TabId) => (isStatement(id) ? issues.filter((i) => issueCell(i).sheet === id).length : 0)

  return (
    <WorkbookProvider value={ctx}>
      <div className="[transition:--tint_500ms_ease]" style={{ ["--tint" as string]: TAB_TINT[tab] }}>
        <Tabs.Root value={tab} onValueChange={(v) => setTab(v as TabId)}>
          <div className="wash border-b">
            <div className="mx-auto max-w-[1440px] px-4 pt-6 sm:px-6">
              <p className="text-[13.5px] text-ink-2">
                <Link href="/library" className="hover:text-ink">
                  Library
                </Link>{" "}
                / {run.request.symbol}
              </p>
              <div className="mt-1.5 flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
                <div className="min-w-0">
                  <h1 className="text-[28px] leading-tight font-semibold sm:text-[34px]">{wb.company.name}</h1>
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-2 text-[13.5px] text-ink-2">
                    <span className="num">
                      {fyLabel(years[0])}–{fyLabel(years[years.length - 1])}
                    </span>
                    <span aria-hidden>·</span>
                    {wb.scopes.length > 1 ? (
                      <Segmented
                        size="sm"
                        label="Statements shown"
                        value={scope}
                        onChange={(s) => {
                          setScope(s)
                          setSelected(null)
                        }}
                        options={[
                          { value: "consolidated", label: "Consolidated" },
                          { value: "standalone", label: "Standalone" },
                        ]}
                      />
                    ) : (
                      <span className="capitalize">{scope}</span>
                    )}
                    <span aria-hidden>·</span>
                    <span>
                      {wb.reports.length} reports, extracted {timeAgo(run.startedAt)}
                    </span>
                    {!wb.company.isDemo && <Chip>Sample data</Chip>}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button onClick={() => setPanel(panel === "issues" ? null : "issues")} aria-pressed={panel === "issues"}>
                    {issues.length > 0 ? <WarningIcon weight="fill" className="text-warn" /> : <CheckCircleIcon weight="fill" className="text-good" />}
                    {issues.length > 0 ? `Review ${issues.length}` : "All checked"}
                  </Button>
                  <Popover
                    trigger={
                      <Button variant="primary">
                        <DownloadSimpleIcon weight="bold" /> Download
                      </Button>
                    }
                  >
                    <DownloadPanel tab={tab} />
                  </Popover>
                </div>
              </div>

              <Tabs.List ref={tabsRef} aria-label="Sheets" className="no-scroll relative mt-5 flex gap-1 overflow-x-auto">
                {tabBox && (
                  <span
                    aria-hidden
                    className={cn("absolute bottom-0 left-0 h-[3px] rounded-t-full bg-tint", tabBox.ready && "transition-[transform,width] duration-250")}
                    style={{ width: tabBox.w, transform: `translateX(${tabBox.x}px)` }}
                  />
                )}
                {TABS.map((t) => (
                  <Tabs.Trigger
                    key={t.id}
                    value={t.id}
                    data-active={t.id === tab}
                    className="flex h-10 shrink-0 items-center gap-2 rounded-t-md px-3 text-[14px] font-medium text-ink-2 transition-colors hover:text-ink data-[active=true]:text-ink"
                  >
                    <span aria-hidden className="size-2 rounded-full" style={{ background: TAB_TINT[t.id] }} />
                    {t.label}
                    {issueCount(t.id) > 0 && (
                      <span className="num rounded-full bg-warn/30 px-1.5 text-[11.5px] font-semibold text-warn-ink" aria-label={`${issueCount(t.id)} to review`}>
                        {issueCount(t.id)}
                      </span>
                    )}
                  </Tabs.Trigger>
                ))}
              </Tabs.List>
            </div>
          </div>

          <div className="mx-auto max-w-[1440px] px-4 py-5 sm:px-6">
            <div className={cn("grid items-start gap-4", wide && panel && "grid-cols-[minmax(0,1fr)_384px]")}>
              <div className="min-w-0">
                <Tabs.Content value="summary" className="animate-enter outline-none">
                  <SummaryTab />
                </Tabs.Content>
                {(["pl", "bs", "cf"] as const).map((s) => (
                  <Tabs.Content key={s} value={s} className="animate-enter outline-none">
                    <div className="mb-3 flex flex-wrap items-center gap-2">
                      <label className="relative">
                        <span className="sr-only">Find a line item</span>
                        <MagnifyingGlassIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-ink-3" />
                        <input
                          value={query}
                          onChange={(e) => setQuery(e.target.value)}
                          placeholder="Find a line"
                          className="h-8 w-40 rounded-md border border-line-2 bg-surface pr-7 pl-8 text-[13px] shadow-card outline-none placeholder:text-ink-3 focus:border-accent focus:ring-2 focus:ring-accent/20 sm:w-48"
                        />
                        {query && (
                          <button type="button" aria-label="Clear" onClick={() => setQuery("")} className="absolute top-1/2 right-1.5 grid size-5 -translate-y-1/2 place-items-center rounded text-ink-3 hover:text-ink">
                            <XIcon className="size-3.5" />
                          </button>
                        )}
                      </label>
                      <Segmented
                        size="sm"
                        label="Show figures as"
                        value={mode === "common" && !COMMON_BASE[s] ? "values" : mode}
                        onChange={setMode}
                        options={[
                          { value: "values", label: "Values" },
                          { value: "common", label: "Common size", disabled: !COMMON_BASE[s], hint: COMMON_BASE[s] ? `Each line as a share of ${COMMON_BASE[s]!.label}` : "Not meaningful for cash flows" },
                          { value: "yoy", label: "Growth", hint: "Change on the year before" },
                        ]}
                      />
                      {hasRestatements && (
                        <Segmented
                          size="sm"
                          label="Restated years"
                          value={figures}
                          onChange={setFigures}
                          options={[
                            { value: "restated", label: "Latest figures", hint: "Each year from the newest report that shows it" },
                            { value: "as-reported", label: "As first reported", hint: "Each year from its own report" },
                          ]}
                        />
                      )}
                      <div className="ml-auto flex items-center gap-1.5">
                        <Tip text={<>Tick figures the report&rsquo;s totals confirm (T)</>}>
                          <Button size="sm" variant={settings.showTicks ? "soft" : "ghost"} aria-pressed={settings.showTicks} onClick={() => setSettings({ showTicks: !settings.showTicks })}>
                            <CheckIcon weight="bold" /> Ticks
                          </Button>
                        </Tip>
                        <Tip text={condensed ? "Show every line" : "Show totals only"}>
                          <Button
                            size="sm"
                            variant={condensed ? "soft" : "ghost"}
                            aria-pressed={condensed}
                            onClick={() => setCollapsed(condensed ? new Set() : new Set(sectionIds))}
                          >
                            <RowsIcon /> Totals only
                          </Button>
                        </Tip>
                        <Select
                          label="Unit"
                          value={settings.unit}
                          onChange={(unit: Unit) => setSettings({ unit })}
                          options={(Object.keys(UNITS) as Unit[]).map((u) => ({ value: u, label: UNITS[u].label }))}
                          className="h-8 text-[13px]"
                        />
                        <Tip text="Copy this table, ready to paste into Excel">
                          <Button size="sm" variant="ghost" square aria-label="Copy table" onClick={() => copyTable(views[s], years, settings.unit, collapsed)}>
                            <CopyIcon />
                          </Button>
                        </Tip>
                      </div>
                    </div>
                    <StatementTable
                      sheet={s}
                      mode={mode === "common" && !COMMON_BASE[s] ? "values" : mode}
                      query={query}
                      collapsed={collapsed}
                      onToggle={(id) =>
                        setCollapsed((c) => {
                          const n = new Set(c)
                          if (n.has(id)) n.delete(id)
                          else n.add(id)
                          return n
                        })
                      }
                    />
                    <Legend />
                  </Tabs.Content>
                ))}
                <Tabs.Content value="sources" className="animate-enter outline-none">
                  <SourcesTab />
                </Tabs.Content>
              </div>

              {wide && panel && (
                <aside aria-label={panel === "issues" ? "Review" : "Source"} className="sticky top-[4.5rem] h-[calc(100dvh-5.75rem)] animate-panel overflow-hidden rounded-xl border bg-surface shadow-card">
                  <Inspector />
                </aside>
              )}
            </div>
          </div>
        </Tabs.Root>

        {!wide && (
          <Sheet open={panel !== null} onOpenChange={(o) => !o && setPanel(null)} title={panel === "issues" ? "Review" : "Source"}>
            <Inspector />
          </Sheet>
        )}
      </div>
    </WorkbookProvider>
  )
}

function Legend() {
  const { settings, book } = useWb()
  return (
    <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12.5px] text-ink-3">
      <span>Select any figure to see where it came from.</span>
      {settings.showTicks && (
        <span className="flex items-center gap-1">
          <CheckIcon weight="bold" className="size-3 text-good" /> confirmed by a total
        </span>
      )}
      <span className="flex items-center gap-1">
        <span className="grid size-4 place-items-center rounded-[3px] bg-warn/30">
          <WarningIcon weight="fill" className="size-2.5 text-warn-ink" />
        </span>
        total doesn&rsquo;t add up
      </span>
      {Object.keys(book.restatements).length > 0 && (
        <span>
          <sup className="mr-0.5 text-[9px] font-semibold text-src">r</sup> restated by a later report
        </span>
      )}
      <span className="flex items-center gap-1">
        <span className="size-1.5 rounded-full bg-accent" /> corrected by you
      </span>
    </div>
  )
}

/** Tab-separated rows with plain numbers, so a paste into Excel lands in cells. */
function tableText(view: StatementView, years: FiscalYear[], unit: Unit, collapsed: Set<string>, sep: string) {
  const u = UNITS[unit]
  const q = (s: string) => (sep === "," && /[",]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s)
  const lines = [[`${SHEETS[view.sheet].title} (${u.label})`, ...years.map(fyLabel)].map(q).join(sep)]
  for (const r of view.rows) {
    if (r.kind === "item" && r.section && collapsed.has(r.section)) continue
    const cells = years.map((fy) => {
      const v = view.values[r.id]?.[fy]
      return v === undefined ? "" : r.perShare ? v.toFixed(2) : (v * u.perLakh).toFixed(u.decimals)
    })
    lines.push([q(r.label), ...cells].join(sep))
  }
  return lines
}

function copyTable(view: StatementView, years: FiscalYear[], unit: Unit, collapsed: Set<string>) {
  const lines = tableText(view, years, unit, collapsed, "\t")
  void navigator.clipboard?.writeText(lines.join("\n"))
  toast.success("Table copied", { description: `${lines.length - 1} rows × ${years.length} years. Paste it into Excel or Sheets.` })
}

function DownloadPanel({ tab }: { tab: TabId }) {
  const { wb, run, review, issues, views, years, settings } = useWb()
  const [busy, setBusy] = React.useState(false)
  const name = fileName(run.request, years)
  const edits = Object.keys(review.edits).length + Object.keys(review.labels).length
  const sheets: Array<[string, string]> = [
    ["Summary", "var(--sum)"],
    ...wb.scopes.flatMap((s): Array<[string, string]> => {
      const p = wb.scopes.length > 1 ? (s === "consolidated" ? "Consol " : "Standalone ") : ""
      return [
        [`${p}P&L`, "var(--pl)"],
        [`${p}Balance Sheet`, "var(--bs)"],
        [`${p}Cash Flow`, "var(--cf)"],
      ]
    }),
    ["Sources", "var(--src)"],
    ["Quality", "var(--ink-3)"],
  ]

  const excel = async () => {
    setBusy(true)
    const res = await downloadExcel(wb, review)
    setBusy(false)
    toast.success(res.filename, { description: "Preview build: the live app saves this Excel file to your downloads." })
  }
  const csv = () => {
    if (!isStatement(tab)) return
    const blob = new Blob([tableText(views[tab], years, settings.unit, new Set(), ",").join("\r\n")], { type: "text/csv;charset=utf-8" })
    const a = document.createElement("a")
    a.href = URL.createObjectURL(blob)
    a.download = name.replace(".xlsx", `_${tab.toUpperCase()}.csv`)
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <div>
      <div className="flex items-center gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-good/10 text-good-ink">
          <MicrosoftExcelLogoIcon weight="fill" className="size-5" />
        </span>
        <div className="min-w-0">
          <div className="truncate text-[13.5px] font-semibold" title={name}>
            {name}
          </div>
          <div className="num text-[12.5px] text-ink-3">
            {sheets.length} sheets · {years.length} years · ₹ crore
          </div>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-1">
        {sheets.map(([s, hue]) => (
          <span key={s} className="flex items-center gap-1.5 rounded-md bg-sunken px-2 py-0.5 text-[12px] text-ink-2">
            <span aria-hidden className="size-1.5 rounded-full" style={{ background: hue }} />
            {s}
          </span>
        ))}
      </div>
      <p className={cn("mt-3 flex gap-2 rounded-lg px-3 py-2 text-[13px] leading-snug", issues.length ? "bg-warn/20 text-warn-ink" : "bg-good/10 text-good-ink")}>
        {issues.length ? <ListChecksIcon className="mt-px size-4 shrink-0" /> : <CheckCircleIcon weight="fill" className="mt-px size-4 shrink-0" />}
        <span>
          {issues.length ? `${issues.length} ${issues.length === 1 ? "item is" : "items are"} still flagged. They are highlighted in the file.` : "Every total adds up."}
          {edits > 0 && ` Your ${edits} ${edits === 1 ? "correction is" : "corrections are"} included.`}
        </span>
      </p>
      <Button variant="primary" className="mt-3 w-full" onClick={excel} disabled={busy}>
        <DownloadSimpleIcon weight="bold" /> {busy ? "Building the file…" : "Download Excel"}
      </Button>
      {isStatement(tab) && (
        <Button variant="ghost" size="sm" className="mt-1.5 w-full" onClick={csv}>
          <FileCsvIcon /> This sheet as CSV
        </Button>
      )}
    </div>
  )
}
