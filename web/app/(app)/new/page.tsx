"use client"

import * as React from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { ArrowRightIcon, CaretRightIcon, CircleNotchIcon, InfoIcon, WarningCircleIcon } from "@phosphor-icons/react"
import { toast } from "sonner"

import { CompanyCombobox, CompanyMark } from "@/components/extract/company-combobox"
import { YearRange } from "@/components/extract/year-range"
import { Button } from "@/components/ui/button"
import { Segmented } from "@/components/ui/controls"
import { getCompany, getConfig, listReports, loadCompanies } from "@/lib/api"
import { timeAgo } from "@/lib/format"
import { fyLabel } from "@/lib/fy"
import { library, pushRecent, useLibrary, useRecents, useSettings } from "@/lib/store"
import type { Company, FiguresMode, ReportRef, ScopeChoice } from "@/lib/types"

export default function NewPage() {
  return (
    <React.Suspense fallback={null}>
      <Extract />
    </React.Suspense>
  )
}

/** Re-mounts the form when the company in the URL changes (e.g. picked from search). */
function Extract() {
  const symbol = useSearchParams().get("c") ?? ""
  return <Form key={symbol} initial={symbol} />
}

function Form({ initial }: { initial: string }) {
  const router = useRouter()
  const [settings] = useSettings()
  const recents = useRecents()
  const { runs } = useLibrary()

  const [company, setCompany] = React.useState<Company | null>(() => (initial ? (getCompany(initial) ?? { symbol: initial.toUpperCase(), name: initial.toUpperCase() }) : null))
  const [reports, setReports] = React.useState<ReportRef[] | null>(null)
  const [lookupError, setLookupError] = React.useState<string | null>(null)
  const [starting, setStarting] = React.useState(false)
  const [aiAvailable, setAiAvailable] = React.useState(false)
  const [maxYears, setMaxYears] = React.useState(12)
  React.useEffect(() => {
    void loadCompanies()
    getConfig()
      .then((c) => {
        setAiAvailable(c.ai.available)
        setMaxYears(c.limits.maxYears)
      })
      .catch(() => {})
  }, [])
  const [range, setRange] = React.useState<[number, number] | null>(null)
  const [scope, setScope] = React.useState<ScopeChoice | null>(null)
  const [figures, setFigures] = React.useState<FiguresMode | null>(null)
  const scopeValue = scope ?? settings.defaultScope
  const figuresValue = figures ?? settings.defaultFigures
  const ai = aiAvailable && settings.aiEngine !== "off" ? settings.aiMode : "off"

  // Which years exist is one lookup per company, so it loads after the pick.
  React.useEffect(() => {
    if (!company) return
    let live = true
    setLookupError(null)
    listReports(company.symbol)
      .then((res) => {
        if (!live) return
        const r = [...res.reports].sort((a, b) => b.fy - a.fy)
        if (!r.length) {
          setLookupError(`Screener lists no annual reports for ${company.symbol}.`)
          return
        }
        if (res.name && res.name !== company.name) setCompany((c) => (c && c.symbol === res.symbol ? { ...c, name: res.name } : c))
        setReports(r)
        const max = r[0].fy
        const min = r[r.length - 1].fy
        setRange([Math.max(min, max - settings.defaultSpan + 1), max])
      })
      .catch((e: Error) => live && setLookupError(e.message))
    return () => {
      live = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- the default span only seeds the first range
  }, [company?.symbol])

  const pick = (c: Company | null) => {
    setCompany(c)
    setReports(null)
    setRange(null)
  }

  const chosen = reports && range ? reports.filter((r) => r.fy >= range[0] && r.fy <= range[1]) : []
  const tooMany = range ? range[1] - range[0] + 1 > maxYears : false
  const same =
    company && range
      ? runs.find((r) => r.status === "done" && r.request.symbol === company.symbol && r.request.from === range[0] && r.request.to === range[1] && r.request.scope === scopeValue)
      : undefined

  const start = async () => {
    if (!company || !range || tooMany) return
    setStarting(true)
    try {
      const run = await library.start({ symbol: company.symbol, from: range[0], to: range[1], scope: scopeValue, figures: figuresValue, ai })
      pushRecent(company.symbol)
      router.push(`/w?id=${run.id}`)
    } catch (e) {
      toast.error("Couldn't start the extraction", { description: (e as Error).message })
      setStarting(false)
    }
  }

  const suggestions = [...recents, "PIDILITIND", "HCLTECH", "INFY", "TITAN"].filter((s, i, a) => a.indexOf(s) === i).slice(0, 5)

  return (
    <div className="wash" style={{ ["--tint" as string]: "var(--pl)" }}>
      <div className="mx-auto max-w-3xl px-4 pt-10 pb-16 sm:px-6 sm:pt-14">
        <h1 className="text-[32px] leading-tight font-semibold sm:text-[38px]">Extract statements</h1>
        <p className="mt-2 text-[15.5px] text-ink-2">Choose a company and the years you need. You get one Excel file with every year side by side.</p>

        <div className="mt-8 space-y-4">
          <Card step={1} title="Company">
            {company ? (
              <div className="flex items-center gap-3">
                <CompanyMark symbol={company.symbol} className="size-11 text-[15px]" />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[16px] font-semibold">{company.name}</div>
                  <div className="text-[13px] text-ink-2">{company.symbol} · NSE</div>
                </div>
                <Button variant="ghost" size="sm" onClick={() => pick(null)}>
                  Change
                </Button>
              </div>
            ) : (
              <>
                <CompanyCombobox onPick={pick} autoFocus />
                <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[13px] text-ink-3">
                  {recents.length > 0 ? "Recent:" : "Try:"}
                  {suggestions.map((s) => {
                    const c = getCompany(s) ?? { symbol: s, name: s }
                    return c ? (
                      <button key={s} type="button" onClick={() => pick(c)} className="rounded-full border border-line-2 bg-surface px-2.5 py-0.5 text-[12.5px] font-medium text-ink-2 transition-colors hover:border-ink-3 hover:text-ink">
                        {s}
                      </button>
                    ) : null
                  })}
                </div>
              </>
            )}

          </Card>

          <Card step={2} title="Years" muted={!company}>
            {company && lookupError ? (
              <p className="flex gap-2 rounded-lg bg-bad/10 px-3 py-2.5 text-[13.5px] text-bad-ink">
                <WarningCircleIcon weight="fill" className="mt-0.5 size-4 shrink-0" />
                <span>
                  {lookupError} Check the NSE symbol and try again.
                </span>
              </p>
            ) : company ? (
              <YearRange reports={reports} from={range?.[0] ?? 0} to={range?.[1] ?? 0} onChange={(f, t) => setRange([f, t])} />
            ) : (
              <p className="text-[14px] text-ink-3">Pick a company to see which annual reports are on file.</p>
            )}
            {tooMany && (
              <p className="mt-3 flex gap-2 rounded-lg bg-warn/20 px-3 py-2 text-[13px] text-warn-ink">
                <WarningCircleIcon className="mt-0.5 size-4 shrink-0" />
                This beta reads up to {maxYears} years at a time. Narrow the range.
              </p>
            )}
          </Card>

          <Card step={3} title="Statements" muted={!company}>
            <Segmented
              label="Which statements"
              value={scopeValue}
              onChange={setScope}
              options={[
                { value: "consolidated", label: "Consolidated" },
                { value: "standalone", label: "Standalone" },
                { value: "both", label: "Both" },
              ]}
            />
            <p className="mt-2 text-[13px] text-ink-2">
              {scopeValue === "consolidated"
                ? "The group, including subsidiaries. The usual choice for valuation."
                : scopeValue === "standalone"
                  ? "The listed company on its own."
                  : "Two sets of sheets in the same file. Takes about twice as long."}
            </p>

            <details className="group mt-4 border-t pt-3">
              <summary className="flex list-none items-center gap-1 text-[13.5px] font-medium text-ink-2 hover:text-ink [&::-webkit-details-marker]:hidden">
                <CaretRightIcon weight="bold" className="size-3.5 transition-transform group-open:rotate-90" />
                More options
              </summary>
              <div className="mt-4 space-y-4">
                <div>
                  <div className="mb-1.5 text-[13px] font-medium">When a later report restates a year</div>
                  <Segmented
                    label="Restated figures"
                    value={figuresValue}
                    onChange={setFigures}
                    options={[
                      { value: "restated", label: "Use the latest figure" },
                      { value: "as-reported", label: "Keep as first reported" },
                    ]}
                  />
                  <p className="mt-1.5 text-[13px] text-ink-2">
                    {figuresValue === "restated"
                      ? "Best for comparing years, and what Screener shows. You can switch inside the workbook."
                      : "Each year exactly as its own report printed it."}
                  </p>
                </div>
                {aiAvailable && (
                  <div className="flex items-center justify-between gap-4 rounded-lg bg-sunken px-3 py-2.5 text-[13px]">
                    <span className="text-ink-2">
                      AI fallback: <span className="font-medium text-ink">{ai === "off" ? "Off" : ai === "fallback" ? "Only when the parser fails" : "Every statement"}</span>
                    </span>
                    <Link href="/settings#ai" className="font-medium text-accent-ink hover:underline">
                      Change
                    </Link>
                  </div>
                )}
              </div>
            </details>
          </Card>
        </div>

        {same && (
          <p className="mt-4 flex items-center gap-2 rounded-lg border border-line-2 bg-surface px-4 py-3 text-[13.5px]">
            <InfoIcon className="size-4 shrink-0 text-accent-ink" />
            <span className="flex-1">You extracted exactly this {timeAgo(same.startedAt ?? same.createdAt)}.</span>
            <Link href={`/w?id=${same.id}`} className="font-medium text-accent-ink hover:underline">
              Open it
            </Link>
          </p>
        )}

        <div className="mt-6 flex flex-col-reverse items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="num text-[13.5px] text-ink-2">
            {company && range ? (
              <>
                {company.symbol} · {fyLabel(range[0])}–{fyLabel(range[1])} · about {Math.max(1, Math.round((chosen.length * (scopeValue === "both" ? 2 : 1)) / 5))} min
              </>
            ) : (
              "Nothing is downloaded until you start."
            )}
          </p>
          <Button variant="primary" size="lg" disabled={!company || !range || tooMany || starting} onClick={start}>
            {starting && <CircleNotchIcon className="animate-spin" />}
            {range ? `Extract ${range[1] - range[0] + 1} ${range[1] === range[0] ? "year" : "years"}` : "Extract"}
            <ArrowRightIcon weight="bold" />
          </Button>
        </div>
      </div>
    </div>
  )
}

function Card({ step, title, muted, children }: { step: number; title: string; muted?: boolean; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border bg-surface p-5 shadow-card sm:p-6">
      <h2 className="mb-4 flex items-center gap-2.5 font-sans text-[15px] font-semibold tracking-normal">
        <span className={`num grid size-6 place-items-center rounded-full text-[12px] ${muted ? "bg-ink/[0.07] text-ink-3" : "bg-ink text-page"}`}>{step}</span>
        {title}
      </h2>
      {children}
    </section>
  )
}
