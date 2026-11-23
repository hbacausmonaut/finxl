"use client"

import * as React from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ArrowCounterClockwiseIcon, CheckCircleIcon, CircleNotchIcon, DotsThreeIcon, MagnifyingGlassIcon, PlusIcon, TrashIcon, WarningCircleIcon, WarningIcon } from "@phosphor-icons/react"
import { toast } from "sonner"

import { CompanyMark } from "@/components/extract/company-combobox"
import { Button } from "@/components/ui/button"
import { Chip, Segmented, Skeleton } from "@/components/ui/controls"
import { Menu, MenuItem } from "@/components/ui/overlay"
import { formatDuration, timeAgo } from "@/lib/format"
import { fyLabel } from "@/lib/fy"
import { library, useLibrary } from "@/lib/store"
import type { RunRecord } from "@/lib/types"

type Filter = "all" | "review" | "clean"

export default function LibraryPage() {
  const { runs, hydrated, error } = useLibrary()
  const router = useRouter()
  const [q, setQ] = React.useState("")
  const [filter, setFilter] = React.useState<Filter>("all")

  const shown = runs.filter((r) => {
    const s = q.trim().toLowerCase()
    if (s && !r.companyName.toLowerCase().includes(s) && !r.request.symbol.toLowerCase().includes(s)) return false
    if (filter === "review") return r.status === "done" && (r.issues ?? 0) > 0
    if (filter === "clean") return r.status === "done" && !r.issues
    return true
  })

  const again = (r: RunRecord) => {
    library
      .start(r.request)
      .then((run) => router.push(`/w?id=${run.id}`))
      .catch((e: Error) => toast.error("Couldn't start the run", { description: e.message }))
  }
  const remove = (r: RunRecord) => {
    library.remove(r.id)
    toast(`Removed ${r.request.symbol} from your library`)
  }

  return (
    <div className="wash" style={{ ["--tint" as string]: "var(--bs)" }}>
      <div className="mx-auto max-w-5xl px-4 pt-10 pb-16 sm:px-6 sm:pt-14">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-[32px] leading-tight font-semibold sm:text-[38px]">Library</h1>
            <p className="mt-2 text-[15.5px] text-ink-2">Every workbook you have extracted, ready to open or download again.</p>
          </div>
          <Button asChild variant="primary">
            <Link href="/new">
              <PlusIcon weight="bold" /> New extraction
            </Link>
          </Button>
        </div>

        <div className="mt-7 flex flex-wrap items-center gap-2">
          <label className="relative">
            <span className="sr-only">Filter by company</span>
            <MagnifyingGlassIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-3" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Filter by company"
              className="h-9 w-56 rounded-md border border-line-2 bg-surface pr-3 pl-9 text-[14px] shadow-card outline-none placeholder:text-ink-3 focus:border-accent focus:ring-2 focus:ring-accent/20"
            />
          </label>
          <Segmented
            label="Show"
            value={filter}
            onChange={setFilter}
            options={[
              { value: "all", label: "All" },
              { value: "review", label: "To review" },
              { value: "clean", label: "All checked" },
            ]}
          />
        </div>

        <ul className="mt-4 space-y-2">
          {!hydrated &&
            [0, 1, 2, 3].map((i) => (
              <li key={i}>
                <Skeleton className="h-[72px] w-full rounded-xl" />
              </li>
            ))}
          {shown.map((r) => {
            const running = r.status === "running" || r.status === "queued"
            return (
              <li key={r.id} className="group relative flex items-center gap-3 rounded-xl border bg-surface p-3 shadow-card transition-shadow hover:shadow-lift sm:gap-4 sm:p-4">
                <CompanyMark symbol={r.request.symbol} className="size-10" />
                <div className="min-w-0 flex-1">
                  <Link href={`/w?id=${r.id}`} className="block truncate text-[15px] font-semibold after:absolute after:inset-0 after:rounded-xl">
                    {r.companyName}
                  </Link>
                  <div className="num mt-0.5 flex flex-wrap gap-x-2 text-[13px] text-ink-2">
                    <span>{r.request.symbol}</span>
                    <span aria-hidden>·</span>
                    <span>
                      {fyLabel(r.request.from)}–{fyLabel(r.request.to)}
                    </span>
                    <span aria-hidden>·</span>
                    <span className="capitalize">{r.request.scope === "both" ? "Consolidated + standalone" : r.request.scope}</span>
                    <span className="hidden text-ink-3 sm:inline">· {timeAgo(r.startedAt ?? r.createdAt)}</span>
                  </div>
                  {r.status === "failed" && r.error && <p className="mt-1 line-clamp-1 text-[12.5px] text-bad-ink">{r.error}</p>}
                </div>

                <div className="hidden shrink-0 text-right sm:block">
                  {r.status === "done" && r.confirmedPct != null && (
                    <>
                      <div className="num text-[15px] font-semibold">{r.confirmedPct.toFixed(1)}%</div>
                      <div className="text-[12px] text-ink-3">confirmed</div>
                    </>
                  )}
                  {r.status === "done" && r.durationSec != null && r.confirmedPct == null && <span className="num text-[13px] text-ink-3">{formatDuration(r.durationSec)}</span>}
                </div>

                <div className="shrink-0">
                  {running ? (
                    <Chip tone="accent">
                      <CircleNotchIcon weight="bold" className="animate-spin" /> {r.status === "queued" ? "Waiting" : "Reading"}
                    </Chip>
                  ) : r.status === "failed" ? (
                    <Chip tone="bad">
                      <WarningCircleIcon weight="fill" /> Didn&rsquo;t finish
                    </Chip>
                  ) : r.issues ? (
                    <Chip tone="warn">
                      <WarningIcon weight="fill" /> {r.issues} to review
                    </Chip>
                  ) : (
                    <Chip tone="good">
                      <CheckCircleIcon weight="fill" /> All checked
                    </Chip>
                  )}
                </div>

                <div className="relative z-[1] shrink-0">
                  <Menu
                    trigger={
                      <Button variant="ghost" size="sm" square aria-label={`More for ${r.companyName}`}>
                        <DotsThreeIcon weight="bold" />
                      </Button>
                    }
                  >
                    <MenuItem icon={<ArrowCounterClockwiseIcon />} onSelect={() => again(r)}>
                      Run again
                    </MenuItem>
                    <MenuItem icon={<TrashIcon />} danger onSelect={() => remove(r)}>
                      Remove
                    </MenuItem>
                  </Menu>
                </div>
              </li>
            )
          })}
        </ul>

        {error && runs.length === 0 && <p className="mt-4 rounded-lg bg-bad/10 px-4 py-3 text-[13.5px] text-bad-ink">{error}</p>}
        {hydrated && !error && shown.length === 0 && (
          <div className="mt-4 rounded-xl border border-dashed border-line-2 px-6 py-14 text-center">
            <p className="text-[15px] font-medium">{runs.length === 0 ? "Nothing here yet" : "No workbook matches"}</p>
            <p className="mt-1 text-[14px] text-ink-2">{runs.length === 0 ? "Extract your first company and it will be kept here, in this browser." : "Clear the filter to see everything."}</p>
            {runs.length === 0 && (
              <Button asChild variant="primary" className="mt-5">
                <Link href="/new">Extract statements</Link>
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
