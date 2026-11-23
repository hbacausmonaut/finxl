"use client"

import * as React from "react"
import { ArrowSquareOutIcon, CircleNotchIcon, ImageBrokenIcon } from "@phosphor-icons/react"

import { useWb } from "@/components/workbook/context"
import { pageImageUrl, pdfUrl } from "@/lib/api"
import { cn } from "@/lib/utils"

/**
 * The report page a figure was read from, rendered by the server (pdfview) with
 * the figure, or failing that its line, outlined.
 */
export function SourcePage({ reportFy, pages, value, label }: { reportFy: number; pages: string[]; value?: number; label: string }) {
  const { wb } = useWb()
  const [i, setI] = React.useState(0)
  const page = pages[Math.min(i, pages.length - 1)]
  const src = page ? pageImageUrl(wb.company.symbol, reportFy, page, { value, label }) : null
  const [loaded, setLoaded] = React.useState<string | null>(null)
  const [failed, setFailed] = React.useState<string | null>(null)
  const state = !src ? "none" : failed === src ? "error" : loaded === src ? "ok" : "loading"

  if (!src) return <p className="rounded-lg bg-sunken p-4 text-[13px] text-ink-2">The pages for this statement weren&rsquo;t recorded.</p>

  return (
    <figure>
      <div className="relative min-h-48 overflow-hidden rounded-lg border border-line-2 bg-white shadow-card">
        {state !== "error" && (
          // eslint-disable-next-line @next/next/no-img-element -- rendered on demand by the API, not a static asset
          <img
            key={src}
            src={src}
            alt={`Page ${page} of the ${reportFy} annual report, with ${label} marked`}
            onLoad={() => setLoaded(src)}
            onError={() => setFailed(src)}
            className={cn("block w-full transition-opacity duration-200", state === "loading" && "opacity-0")}
          />
        )}
        {state === "loading" && (
          <div className="absolute inset-0 grid place-items-center text-[13px] text-ink-3">
            <span className="flex items-center gap-2">
              <CircleNotchIcon className="size-4 animate-spin" /> Opening the page…
            </span>
          </div>
        )}
        {state === "error" && (
          <div className="grid min-h-48 place-items-center p-6 text-center text-[13px] text-ink-2">
            <span>
              <ImageBrokenIcon className="mx-auto mb-2 size-6 text-ink-3" />
              This page couldn&rsquo;t be shown. The report may no longer be cached on the server.
            </span>
          </div>
        )}
      </div>
      <figcaption className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[12.5px] text-ink-3">
        <span className="flex items-center gap-1">
          {pages.length > 1 ? (
            pages.map((p, k) => (
              <button
                key={p}
                type="button"
                onClick={() => setI(k)}
                aria-pressed={k === i}
                className={cn("num rounded px-1.5 py-0.5 hover:bg-sunken hover:text-ink", k === i && "bg-sunken font-medium text-ink")}
              >
                p. {p}
              </button>
            ))
          ) : (
            <span className="num">PDF page {page}</span>
          )}
        </span>
        <a href={pdfUrl(wb.company.symbol, reportFy)} target="_blank" rel="noreferrer" className="flex items-center gap-1 hover:text-ink">
          Whole report <ArrowSquareOutIcon />
        </a>
      </figcaption>
    </figure>
  )
}
