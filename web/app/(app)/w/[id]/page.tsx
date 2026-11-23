"use client"

import * as React from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ArrowCounterClockwiseIcon, WarningCircleIcon } from "@phosphor-icons/react"

import { ProgressView } from "@/components/run/progress-view"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/controls"
import { WorkbookView } from "@/components/workbook/workbook-view"
import { library, useLibrary } from "@/lib/store"

/** One address per extraction: it shows progress while running and the workbook once done. */
export default function WorkbookPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = React.use(params)
  const { runs, hydrated } = useLibrary()
  const router = useRouter()
  const run = runs.find((r) => r.id === id)

  if (!hydrated) {
    return (
      <div className="mx-auto max-w-[1440px] px-4 py-10 sm:px-6">
        <Skeleton className="h-9 w-80" />
        <Skeleton className="mt-3 h-5 w-64" />
        <Skeleton className="mt-8 h-[420px] w-full rounded-xl" />
      </div>
    )
  }

  if (!run) {
    return (
      <Message title="This workbook isn't in your library" body="It may have been removed, or the link is from another device. Workbooks are kept in this browser for now.">
        <Button asChild variant="primary">
          <Link href="/library">Go to Library</Link>
        </Button>
      </Message>
    )
  }

  if (run.status === "failed") {
    const again = () => {
      router.push(`/w/${library.start(run.request, run.companyName)}`)
    }
    return (
      <Message title={`${run.companyName}: the run didn't finish`} body={run.error ?? "Something went wrong while reading the reports."} tone="bad">
        <Button variant="primary" onClick={again}>
          <ArrowCounterClockwiseIcon /> Run again
        </Button>
        <Button asChild>
          <Link href="/settings#ai">AI fallback settings</Link>
        </Button>
      </Message>
    )
  }

  return run.status === "running" ? <ProgressView run={run} /> : <WorkbookView key={run.id} run={run} />
}

function Message({ title, body, tone, children }: { title: string; body: string; tone?: "bad"; children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-lg px-4 py-24 text-center">
      {tone === "bad" && <WarningCircleIcon weight="duotone" className="mx-auto mb-4 size-10 text-bad" />}
      <h1 className="text-[26px] font-semibold">{title}</h1>
      <p className="mt-2 text-[15px] text-ink-2">{body}</p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">{children}</div>
    </div>
  )
}
