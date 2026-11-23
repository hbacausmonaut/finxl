"use client"

import { useWb } from "@/components/workbook/context"
import { formatAmount, formatPerShare } from "@/lib/format"
import { SHEETS } from "@/lib/sheets"
import type { CellRef } from "@/lib/types"
import { cn } from "@/lib/utils"

const PRINT = { unit: "crore", grouping: "indian", negatives: "parentheses" } as const

const TITLES = {
  pl: "Statement of Profit and Loss",
  bs: "Balance Sheet",
  cf: "Statement of Cash Flows",
}

/**
 * Stand-in for the report page a figure was read from: the lines around it,
 * this year and the comparative, with the figure marked. The live app shows
 * the rendered PDF page here (the engine's pdfview does this already).
 */
export function SourcePage({ cell, reportFy, page }: { cell: CellRef; reportFy: number; page: number }) {
  const { book, wb } = useWb()
  const rows = SHEETS[cell.sheet].rows.filter((r) => r.kind !== "header")
  const at = Math.max(0, rows.findIndex((r) => r.id === cell.row))
  const start = Math.max(0, Math.min(at - 3, rows.length - 7))
  const shown = rows.slice(start, start + 7)
  const cols = [reportFy, reportFy - 1]
  // What the page itself prints: where the engine misread a figure, the page still shows the right one.
  const val = (row: string, fy: number) =>
    row === "eps"
      ? book.epsExpected[fy]
      : (book.secondReadings.find((s) => s.cell.sheet === cell.sheet && s.cell.row === row && s.cell.fy === fy)?.value ?? book.values[cell.sheet][row]?.[fy])

  return (
    <figure>
      <div className="relative overflow-hidden rounded-lg border border-line-2 bg-[#fffdf8] px-4 pt-4 pb-6 text-[#23211c] shadow-card dark:bg-[#efeadf]">
        <div className="text-[8.5px] font-medium tracking-[0.14em] uppercase opacity-55">{wb.company.name}</div>
        <div className="display mt-0.5 text-[13px] font-semibold">
          {cell.scope === "consolidated" ? "Consolidated " : ""}
          {TITLES[cell.sheet]}
        </div>
        <div className="mt-2.5 flex border-b border-[#23211c]/25 pb-1 text-[9px] opacity-60">
          <span className="flex-1">Particulars (₹ crore)</span>
          {cols.map((y) => (
            <span key={y} className="w-[27%] text-right">
              31 Mar {y}
            </span>
          ))}
        </div>
        {shown.map((r) => (
          <div key={r.id} className={cn("flex h-[22px] items-center text-[10.5px]", (r.kind === "total" || r.kind === "calc") && "font-semibold")}>
            <span className="flex-1 truncate pr-2">{r.label}</span>
            {cols.map((y) => {
              const hit = r.id === cell.row && y === cell.fy
              const v = val(r.id, y)
              return (
                <span key={y} className={cn("num relative w-[27%] text-right", y !== reportFy && "opacity-60", hit && "opacity-100")}>
                  {hit && <span aria-hidden className="absolute -inset-x-1 -inset-y-0.5 rounded-[3px] border-[1.5px] border-tint bg-tint/20" />}
                  <span className="relative">{r.perShare ? formatPerShare(v, PRINT) : formatAmount(v, PRINT)}</span>
                </span>
              )
            })}
          </div>
        ))}
        <div className="num absolute right-4 bottom-1.5 text-[9px] opacity-45">{page}</div>
      </div>
      <figcaption className="sr-only">Illustration of the report page with the figure marked.</figcaption>
    </figure>
  )
}
