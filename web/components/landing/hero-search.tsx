"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"

import { CompanyCombobox } from "@/components/extract/company-combobox"

/** The landing page's one job: get a company chosen. */
export function HeroSearch() {
  const router = useRouter()
  return (
    <div className="w-full max-w-xl">
      <CompanyCombobox size="lg" placeholder="Search a company, e.g. Pidilite or HCLTECH" onPick={(c) => router.push(`/new?c=${c.symbol}`)} />
      <p className="mt-3 text-[13.5px] text-ink-2">
        Or open a{" "}
        <Link href="/w/s_vardhan" className="font-medium text-ink underline decoration-line-2 underline-offset-4 transition-colors hover:decoration-ink">
          finished sample workbook
        </Link>{" "}
        to see what you get.
      </p>
    </div>
  )
}
