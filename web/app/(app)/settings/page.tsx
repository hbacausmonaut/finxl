"use client"

import * as React from "react"
import { useTheme } from "next-themes"
import { DesktopIcon, MoonIcon, SunIcon } from "@phosphor-icons/react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Kbd, Segmented, Select, Switch, useModKey } from "@/components/ui/controls"
import { getConfig, testAiConnection } from "@/lib/api"
import { formatAmount, formatPct, UNITS } from "@/lib/format"
import { resetSettings, useHydrated, useSettings } from "@/lib/store"
import type { Unit } from "@/lib/types"
import { cn } from "@/lib/utils"

const SECTIONS = [
  ["appearance", "Appearance"],
  ["numbers", "Numbers"],
  ["defaults", "New extractions"],
  ["ai", "AI fallback"],
  ["shortcuts", "Shortcuts"],
  ["data", "Your data"],
] as const

export default function SettingsPage() {
  const [s, set] = useSettings()
  const { theme, setTheme } = useTheme()
  const hydrated = useHydrated()
  const mod = useModKey()
  const [testing, setTesting] = React.useState(false)
  const [ai, setAi] = React.useState<{ available: boolean; model: string } | null>(null)
  React.useEffect(() => {
    getConfig()
      .then((c) => setAi(c.ai))
      .catch(() => setAi({ available: false, model: "" }))
  }, [])
  const sample = 123456.7 // ₹ crore

  return (
    <div className="wash" style={{ ["--tint" as string]: "var(--sum)" }}>
      <div className="mx-auto grid max-w-5xl gap-10 px-4 pt-10 pb-20 sm:px-6 sm:pt-14 lg:grid-cols-[180px_1fr]">
        <div>
          <h1 className="text-[32px] leading-tight font-semibold sm:text-[38px]">Settings</h1>
          <nav aria-label="Settings sections" className="mt-6 hidden flex-col gap-0.5 lg:sticky lg:top-24 lg:flex">
            {SECTIONS.filter(([id]) => id !== "ai" || ai?.available).map(([id, label]) => (
              <a key={id} href={`#${id}`} className="rounded-md px-2.5 py-1.5 text-[14px] text-ink-2 transition-colors hover:bg-ink/[0.05] hover:text-ink">
                {label}
              </a>
            ))}
          </nav>
        </div>

        <div className="space-y-5">
          <Section id="appearance" title="Appearance">
            <Row label="Theme" hint="Light is the default. Dark is easier on the eyes at night.">
              <div role="radiogroup" aria-label="Theme" className="grid grid-cols-3 gap-2">
                {(
                  [
                    ["light", "Light", SunIcon],
                    ["dark", "Dark", MoonIcon],
                    ["system", "Match device", DesktopIcon],
                  ] as const
                ).map(([value, label, Icon]) => {
                  const on = hydrated && theme === value
                  return (
                    <button
                      key={value}
                      type="button"
                      role="radio"
                      aria-checked={on}
                      onClick={() => setTheme(value)}
                      className={cn(
                        "flex flex-col items-center gap-1.5 rounded-lg border px-3 py-2.5 text-[13px] font-medium transition-colors",
                        on ? "border-accent bg-accent/[0.07] text-ink ring-1 ring-accent" : "border-line-2 text-ink-2 hover:bg-sunken"
                      )}
                    >
                      <Icon weight={on ? "fill" : "regular"} className="size-5" />
                      {label}
                    </button>
                  )
                })}
              </div>
            </Row>
            <Row label="Row height" hint="Compact fits more lines of a statement on screen.">
              <Segmented
                label="Row height"
                value={s.density}
                onChange={(density) => set({ density })}
                options={[
                  { value: "comfortable", label: "Comfortable" },
                  { value: "compact", label: "Compact" },
                ]}
              />
            </Row>
            <Row label="Reduce motion" hint="Turns off slides and fades. Your device's own setting is always respected." htmlFor="set-motion">
              <Switch id="set-motion" label="Reduce motion" checked={s.reduceMotion} onChange={(reduceMotion) => set({ reduceMotion })} />
            </Row>
          </Section>

          <Section id="numbers" title="Numbers" note="How figures are shown on screen. The Excel file is always written in ₹ crore.">
            <Row label="Unit">
              <Select label="Unit" value={s.unit} onChange={(unit: Unit) => set({ unit })} options={(Object.keys(UNITS) as Unit[]).map((u) => ({ value: u, label: UNITS[u].label }))} className="w-40" />
            </Row>
            <Row label="Digit grouping" hint="Indian groups in lakhs and crores. International groups in thousands.">
              <Segmented
                label="Digit grouping"
                value={s.grouping}
                onChange={(grouping) => set({ grouping })}
                options={[
                  { value: "indian", label: "1,23,45,678" },
                  { value: "international", label: "12,345,678" },
                ]}
              />
            </Row>
            <Row label="Negative figures">
              <Segmented
                label="Negative figures"
                value={s.negatives}
                onChange={(negatives) => set({ negatives })}
                options={[
                  { value: "parentheses", label: "(1,234.50)" },
                  { value: "minus", label: "−1,234.50" },
                ]}
              />
            </Row>
            <Row label="Tick confirmed figures" hint="Marks every figure that sits inside a printed total which adds up." htmlFor="set-ticks">
              <Switch id="set-ticks" label="Tick confirmed figures" checked={s.showTicks} onChange={(showTicks) => set({ showTicks })} />
            </Row>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-1 rounded-lg bg-sunken px-4 py-3 text-[13px] text-ink-2">
              <span>Preview</span>
              <span className="num text-[15px] font-medium text-ink">{formatAmount(sample, s)}</span>
              <span className="num text-[15px] font-medium text-ink">{formatAmount(-sample / 40, s)}</span>
              <span className="num text-[15px] font-medium text-ink">{formatPct(-0.0312, s)}</span>
              <span className="text-ink-3">{UNITS[s.unit].label}</span>
            </div>
          </Section>

          <Section id="defaults" title="New extractions" note="What the Extract form starts with. You can change any of it per run.">
            <Row label="Statements">
              <Segmented
                label="Default statements"
                value={s.defaultScope}
                onChange={(defaultScope) => set({ defaultScope })}
                options={[
                  { value: "consolidated", label: "Consolidated" },
                  { value: "standalone", label: "Standalone" },
                  { value: "both", label: "Both" },
                ]}
              />
            </Row>
            <Row label="Years to start with" hint="Counted back from the newest report.">
              <Select
                label="Default number of years"
                value={String(s.defaultSpan)}
                onChange={(v) => set({ defaultSpan: Number(v) })}
                options={[3, 5, 6, 7, 10].map((n) => ({ value: String(n), label: `${n} years` }))}
                className="w-32"
              />
            </Row>
            <Row label="Restated years" hint="Latest figures compare best across years. As first reported keeps each year as its own report printed it.">
              <Segmented
                label="Restated years"
                value={s.defaultFigures}
                onChange={(defaultFigures) => set({ defaultFigures })}
                options={[
                  { value: "restated", label: "Latest figures" },
                  { value: "as-reported", label: "As first reported" },
                ]}
              />
            </Row>
          </Section>

          {ai?.available && (
          <Section
            id="ai"
            title="AI fallback"
            note="The built-in parser reads most reports exactly and needs no AI. A fallback helps only with scanned reports and statements that fail their checks. It uses this server's Gemini key."
          >
            <Row label="AI fallback" hint={`Model: ${ai.model}. Backup models are tried when the free tier is busy.`}>
              <Segmented
                label="AI fallback"
                value={s.aiEngine === "off" ? "off" : "gemini"}
                onChange={(aiEngine) => set({ aiEngine })}
                options={[
                  { value: "off", label: "Off" },
                  { value: "gemini", label: "On" },
                ]}
              />
            </Row>
            {s.aiEngine !== "off" && (
              <div className="animate-fade space-y-5">
                <Row label="Use it">
                  <Segmented
                    label="When to use AI"
                    value={s.aiMode}
                    onChange={(aiMode) => set({ aiMode })}
                    options={[
                      { value: "fallback", label: "Only when the parser fails" },
                      { value: "always", label: "Every statement" },
                    ]}
                  />
                </Row>
                <Button
                  disabled={testing}
                  onClick={async () => {
                    setTesting(true)
                    try {
                      const r = await testAiConnection()
                      if (r.ok) toast.success(r.message || "Gemini answered.")
                      else toast.error(r.message)
                    } catch (e) {
                      toast.error((e as Error).message)
                    } finally {
                      setTesting(false)
                    }
                  }}
                >
                  {testing ? "Testing…" : "Test connection"}
                </Button>
              </div>
            )}
          </Section>
          )}

          <Section id="shortcuts" title="Shortcuts">
            <dl className="grid gap-x-8 gap-y-2.5 text-[14px] sm:grid-cols-2">
              {(
                [
                  ["Search companies and workbooks", [mod, "K"]],
                  ["Search, from anywhere", ["/"]],
                  ["Move between figures", ["↑", "↓", "←", "→"]],
                  ["Open a figure's source", ["Enter"]],
                  ["Open or close the review list", ["I"]],
                  ["Show or hide ticks", ["T"]],
                  ["Close a panel", ["Esc"]],
                ] as const
              ).map(([what, keys]) => (
                <div key={what} className="flex items-center justify-between gap-4">
                  <dt className="text-ink-2">{what}</dt>
                  <dd className="flex gap-1">
                    {keys.map((k) => (
                      <Kbd key={k}>{k}</Kbd>
                    ))}
                  </dd>
                </div>
              ))}
            </dl>
          </Section>

          <Section id="data" title="Your data" note="Settings live in this browser. Your library and corrections are kept on the server under an anonymous id stored in this browser; there are no accounts in the beta.">
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={() => {
                  resetSettings()
                  setTheme("light")
                  toast("Settings are back to their defaults")
                }}
              >
                Reset settings
              </Button>
            </div>
          </Section>
        </div>
      </div>
    </div>
  )
}

function Section({ id, title, note, children }: { id: string; title: string; note?: string; children: React.ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="scroll-mt-24 rounded-xl border bg-surface p-5 shadow-card sm:p-6">
      <h2 id={`${id}-h`} className="font-sans text-[17px] font-semibold tracking-normal">
        {title}
      </h2>
      {note && <p className="mt-1 max-w-2xl text-[13.5px] text-ink-2">{note}</p>}
      <div className="mt-5 space-y-5">{children}</div>
    </section>
  )
}

function Row({ label, hint, htmlFor, children }: { label: string; hint?: string; htmlFor?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center sm:justify-between sm:gap-8">
      <div className="min-w-0">
        {htmlFor ? (
          <label htmlFor={htmlFor} className="text-[14px] font-medium">
            {label}
          </label>
        ) : (
          <div className="text-[14px] font-medium">{label}</div>
        )}
        {hint && <p className="mt-0.5 max-w-md text-[13px] text-ink-2">{hint}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  )
}
