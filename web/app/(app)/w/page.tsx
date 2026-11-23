"use client"

import * as React from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { ArrowCounterClockwiseIcon, WarningCircleIcon } from "@phosphor-icons/react"
import { toast } from "sonner"

import { ProgressView } from "@/components/run/progress-view"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/controls"
import { WorkbookView } from "@/components/workbook/workbook-view"
import { ApiError, getWorkbook } from "@/lib/api"
import { library } from "@/lib/store"
import type { RunRecord, Workbook } from "@/lib/types"

/** One address per extraction (/w?id=…): progress while it runs, the workbook once done. */
export default function WorkbookPage() {
  return (
    <React.Suspense fallback={<Loading />}>
      <ById />
    </React.Suspense>
  )
}

function ById() {
  const id = useSearchParams().get("id") ?? ""
  return <Run key={id} id={id} />
}

function Run({ id }: { id: string }) {
  const router = useRouter()
  const [run, setRun] = React.useState<RunRecord | null>(null)
  const [wb, setWb] = React.useState<Workbook | null>(null)
  const [error, setError] = React.useState<{ status: number; message: string } | null>(null)

  React.useEffect(() => {
    let live = true
    library
      .fetch(id)
      .then((r) => live && setRun(r))
      .catch((e: ApiError) => live && setError({ status: e.status, message: e.message }))
    return () => {
      live = false
    }
  }, [id])

  React.useEffect(() => {
    if (run?.status !== "done" || wb) return
    let live = true
    getWorkbook(id)
      .then((w) => live && setWb(w))
      .catch((e: ApiError) => live && setError({ status: e.status, message: e.message }))
    return () => {
      live = false
    }
  }, [id, run?.status, wb])

  if (error) {
    return (
      <Message
        title={error.status === 404 ? "This workbook doesn't exist" : "Couldn't open this workbook"}
        body={error.status === 404 ? "The link may be wrong, or the run was removed from the server." : error.message}
      >
        <Button asChild variant="primary">
          <Link href="/library">Go to Library</Link>
        </Button>
      </Message>
    )
  }
  if (!run) return <Loading />

  if (run.status === "failed") {
    const again = () =>
      library
        .start(run.request)
        .then((r) => router.push(`/w?id=${r.id}`))
        .catch((e: Error) => toast.error("Couldn't start the run", { description: e.message }))
    return (
      <Message title={`${run.companyName}: the run didn't finish`} body={run.error ?? "Something went wrong while reading the reports."} tone="bad">
        <Button variant="primary" onClick={again}>
          <ArrowCounterClockwiseIcon /> Run again
        </Button>
        <Button asChild>
          <Link href="/new">Change the request</Link>
        </Button>
      </Message>
    )
  }

  if (run.status !== "done") return <ProgressView run={run} onFinish={(r) => setRun(r)} />
  return wb ? <WorkbookView key={run.id} run={run} wb={wb} /> : <Loading />
}

function Loading() {
  return (
    <div className="mx-auto max-w-[1440px] px-4 py-10 sm:px-6">
      <Skeleton className="h-9 w-80" />
      <Skeleton className="mt-3 h-5 w-64" />
      <Skeleton className="mt-8 h-[420px] w-full rounded-xl" />
    </div>
  )
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
