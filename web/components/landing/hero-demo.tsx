"use client"

import * as React from "react"

import { computeStatement } from "@/lib/compute"
import { formatAmount } from "@/lib/format"
import { fyLabel } from "@/lib/fy"
import { usePrefersCalm } from "@/lib/hooks"
import { buildWorkbook } from "@/lib/mock/workbook"
import { EMPTY_REVIEW } from "@/lib/types"
import { cn } from "@/lib/utils"

const ROWS: Array<[id: string, label: string, strong?: boolean]> = [
  ["rev", "Revenue from operations"],
  ["oi", "Other income"],
  ["ti", "Total income", true],
  ["texp", "Total expenses"],
  ["pbt", "Profit before tax", true],
  ["tax", "Total tax expense"],
  ["pat", "Profit for the year", true],
]
const PREFS = { unit: "crore", grouping: "indian", negatives: "parentheses" } as const
const TARGET = 2026

/**
 * The product in one picture: a line is marked on the report page and its
 * figure lands in the newest column of the workbook. Runs only while on
 * screen; shows the finished state when motion is reduced.
 */
export function HeroDemo() {
  const { years, values } = React.useMemo(() => {
    const wb = buildWorkbook("hero", { symbol: "VARDHANSPL", from: 2023, to: 2026, scope: "consolidated", figures: "restated", ai: "off" })
    const v = computeStatement(wb.books.consolidated!, "pl", wb.years, "restated", EMPTY_REVIEW)
    return { years: wb.years.slice(-4), values: v.values }
  }, [])

  const ref = React.useRef<HTMLDivElement>(null)
  const calm = usePrefersCalm()
  const [seen, setSeen] = React.useState(false)
  const [tick, setTick] = React.useState(0)

  React.useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(([e]) => setSeen(e.isIntersecting), { threshold: 0.35 })
    io.observe(el)
    return () => io.disconnect()
  }, [])

  React.useEffect(() => {
    if (!seen || calm) return
    const done = tick >= ROWS.length
    const t = setTimeout(() => setTick((s) => (s >= ROWS.length ? 0 : s + 1)), done ? 4200 : tick === 0 ? 900 : 620)
    return () => clearTimeout(t)
  }, [tick, seen, calm])

  const step = calm ? ROWS.length : tick
  const amt = (id: string, fy: number) => formatAmount(values[id]?.[fy], PREFS)

  return (
    <div ref={ref} role="img" aria-label="A profit and loss statement being read from an annual report into a multi-year workbook" className="relative mx-auto w-full max-w-[640px] select-none">
      {/* the report page */}
      <div className="relative z-[1] w-[66%] -rotate-2 rounded-lg border border-line-2 bg-[#fffdf8] p-4 pb-28 text-[#23211c] shadow-lift sm:p-5 sm:pb-32 dark:bg-[#f3efe6]">
        <div className="text-[9px] font-medium tracking-[0.14em] uppercase opacity-55">Annual Report 2025–26</div>
        <div className="display mt-1 text-[13px] leading-tight font-semibold sm:text-[15px]">Statement of Profit and Loss</div>
        <div className="mt-3 flex border-b border-[#23211c]/25 pb-1 text-[8.5px] opacity-60 sm:text-[9.5px]">
          <span className="flex-1">Particulars (₹ crore)</span>
          <span className="w-[26%] text-right">31 Mar 2026</span>
          <span className="hidden w-[26%] text-right sm:block">31 Mar 2025</span>
        </div>
        <div className="mt-1">
          {ROWS.map(([id, label, strong], i) => (
            <div key={id} className={cn("relative flex h-[22px] items-center text-[9px] sm:h-6 sm:text-[10.5px]", strong && "font-semibold")}>
              {/* the marker stroke */}
              <span
                aria-hidden
                className="absolute inset-x-[-4px] inset-y-[3px] origin-left rounded-[3px] transition-transform duration-500"
                style={{
                  background: "color-mix(in oklab, var(--pl) 26%, transparent)",
                  transform: `scaleX(${i < step ? 1 : 0})`,
                  transitionTimingFunction: "var(--ease-out)",
                }}
              />
              <span className="relative flex-1 truncate pr-2">{label}</span>
              <span className="num relative w-[26%] text-right">{amt(id, TARGET)}</span>
              <span className="num relative hidden w-[26%] text-right opacity-55 sm:block">{amt(id, TARGET - 1)}</span>
            </div>
          ))}
        </div>
        <div className="mt-3 space-y-1.5 opacity-20" aria-hidden>
          <div className="h-1 w-4/5 rounded-full bg-current" />
          <div className="h-1 w-3/5 rounded-full bg-current" />
        </div>
      </div>

      {/* the workbook */}
      <div className="relative z-[2] -mt-24 ml-[14%] rotate-1 overflow-hidden rounded-xl border border-line-2 bg-surface shadow-pop sm:-mt-28 sm:ml-[20%]">
        <div className="flex items-center gap-2 border-b px-3 py-2">
          <span className="size-2 rounded-full bg-pl" />
          <span className="truncate text-[11px] font-medium text-ink-2">VARDHANSPL_Financials_FY2023-FY2026.xlsx</span>
        </div>
        <table className="w-full border-collapse text-[9.5px] sm:text-[11px]">
          <thead>
            <tr className="text-ink-3">
              <th className="py-1.5 pl-3 text-left font-medium">₹ crore</th>
              {years.map((y) => (
                <th key={y} className={cn("num px-2 py-1.5 text-right font-medium", y === TARGET && "text-ink", y < TARGET - 1 && "hidden sm:table-cell")}>
                  {fyLabel(y)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map(([id, label, strong], i) => (
              <tr key={id} className={cn("border-t", strong && "font-semibold")}>
                <td className="w-[42%] max-w-0 truncate py-[5px] pl-3 sm:py-1.5">{label}</td>
                {years.map((y) => (
                  <td key={y} className={cn("num px-2 text-right", y < TARGET - 1 && "hidden sm:table-cell", y < TARGET && "text-ink-2")}>
                    {y < TARGET ? (
                      amt(id, y)
                    ) : (
                      <span
                        className="inline-block rounded-[3px] px-1 transition-[opacity,background-color] duration-500"
                        style={{
                          opacity: i < step ? 1 : 0,
                          background: i === step - 1 && step < ROWS.length ? "color-mix(in oklab, var(--pl) 22%, transparent)" : "transparent",
                        }}
                      >
                        {amt(id, y)}
                      </span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        <div className="flex gap-1 border-t bg-sunken px-2 pt-1.5 text-[9.5px] font-medium sm:text-[10.5px]">
          {[
            ["Summary", "var(--sum)"],
            ["P&L", "var(--pl)"],
            ["Balance Sheet", "var(--bs)"],
            ["Cash Flow", "var(--cf)"],
            ["Sources", "var(--src)"],
          ].map(([name, hue], i) => (
            <span
              key={name}
              className={cn("rounded-t-md border border-b-0 px-2 py-1", i === 1 ? "bg-surface text-ink" : "border-transparent text-ink-3", i > 3 && "hidden sm:block")}
              style={{ boxShadow: i === 1 ? `inset 0 2px 0 ${hue}` : undefined }}
            >
              {name}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
