"use client"

import * as React from "react"
import { Command } from "cmdk"
import { ArrowRightIcon, MagnifyingGlassIcon } from "@phosphor-icons/react"

import { searchCompanies } from "@/lib/api"
import type { Company } from "@/lib/types"
import { cn } from "@/lib/utils"

/** Type-ahead over the bundled company list. Arrow keys move, Enter picks. */
export function CompanyCombobox({
  onPick,
  size = "md",
  autoFocus,
  placeholder = "Company name or NSE symbol",
  action,
}: {
  onPick: (c: Company) => void
  size?: "md" | "lg"
  autoFocus?: boolean
  placeholder?: string
  /** Shown at the right edge of the field (e.g. a submit button). */
  action?: React.ReactNode
}) {
  const [q, setQ] = React.useState("")
  const [open, setOpen] = React.useState(false)
  const results = React.useMemo(() => searchCompanies(q, 7), [q])
  const lg = size === "lg"

  return (
    <Command
      shouldFilter={false}
      loop
      label="Company search"
      className="relative"
      onKeyDown={(e) => {
        if (e.key === "Escape") setOpen(false)
      }}
    >
      <div
        className={cn(
          "flex items-center gap-2.5 border border-line-2 bg-surface shadow-lift transition-shadow focus-within:border-accent focus-within:ring-4 focus-within:ring-accent/15",
          lg ? "h-14 rounded-xl pr-2 pl-4" : "h-12 rounded-lg pr-1.5 pl-3.5"
        )}
      >
        <MagnifyingGlassIcon className={cn("shrink-0 text-ink-3", lg ? "size-5" : "size-[18px]")} />
        <Command.Input
          value={q}
          onValueChange={(v) => {
            setQ(v)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          autoFocus={autoFocus}
          placeholder={placeholder}
          className={cn("h-full min-w-0 flex-1 bg-transparent outline-none placeholder:text-ink-3", lg ? "text-[16px]" : "text-[15px]")}
        />
        {action}
      </div>

      {open && (
        <Command.List
          // keep focus in the field so a click on a row still registers
          onMouseDown={(e) => e.preventDefault()}
          className="thin-scroll absolute top-full right-0 left-0 z-30 mt-2 max-h-80 animate-pop overflow-y-auto rounded-xl border border-line-2 bg-raised p-1.5 text-left shadow-pop"
        >
          <Command.Empty className="px-3 py-5 text-[13.5px] text-ink-2">
            No company matches “{q}”. Try the NSE symbol, such as HCLTECH or PIDILITIND.
          </Command.Empty>
          {results.map((c) => (
            <Command.Item
              key={c.symbol}
              value={c.symbol}
              onSelect={() => {
                onPick(c)
                setOpen(false)
                setQ("")
              }}
              className="group flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 outline-none select-none data-[selected=true]:bg-ink/[0.06]"
            >
              <CompanyMark symbol={c.symbol} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[14px] font-medium">{c.name}</span>
                <span className="block truncate text-[12.5px] text-ink-3">
                  {c.symbol} · {c.sector}
                </span>
              </span>
              {c.isDemo && <span className="rounded-full bg-accent/10 px-2 py-0.5 text-[11.5px] font-medium text-accent-ink">Sample data</span>}
              <ArrowRightIcon className="size-4 text-ink-3 opacity-0 transition-opacity group-data-[selected=true]:opacity-100" />
            </Command.Item>
          ))}
        </Command.List>
      )}
    </Command>
  )
}

const HUES = ["var(--pl)", "var(--bs)", "var(--cf)", "var(--sum)", "var(--src)"]

/** A coloured initial, so companies are easy to tell apart in lists. */
export function CompanyMark({ symbol, className }: { symbol: string; className?: string }) {
  const hue = HUES[[...symbol].reduce((s, ch) => s + ch.charCodeAt(0), 0) % HUES.length]
  return (
    <span
      aria-hidden
      className={cn("grid size-9 shrink-0 place-items-center rounded-lg text-[13px] font-semibold", className)}
      style={{ background: `color-mix(in oklab, ${hue} 14%, var(--surface))`, color: `color-mix(in oklab, ${hue} 70%, var(--ink))` }}
    >
      {symbol.slice(0, 2)}
    </span>
  )
}
