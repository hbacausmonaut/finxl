import Link from "next/link"

import { cn } from "@/lib/utils"

/** Three sheets, fanned: reports in, one workbook out. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 28 28" className={cn("size-7", className)} aria-hidden>
      <rect x="10.5" y="2.5" width="14" height="18" rx="3.2" fill="var(--sum)" transform="rotate(12 17.5 11.5)" />
      <rect x="7" y="4.5" width="14" height="18" rx="3.2" fill="var(--bs)" transform="rotate(3 14 13.5)" />
      <rect x="3.5" y="7" width="14" height="18" rx="3.2" fill="var(--pl)" transform="rotate(-6 10.5 16)" />
      <g transform="rotate(-6 10.5 16)" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" opacity="0.92">
        <path d="M6.8 12.2h7.4M6.8 16h7.4M6.8 19.8h4.6" />
      </g>
    </svg>
  )
}

export function Logo({ href = "/", className }: { href?: string; className?: string }) {
  return (
    <Link href={href} aria-label="FinXL home" className={cn("inline-flex items-center gap-2 rounded-md", className)}>
      <LogoMark />
      <span className="display text-[19px] leading-none font-bold">FinXL</span>
      <span className="rounded-full border border-accent/30 bg-accent/10 px-1.5 py-[1px] text-[10.5px] leading-[14px] font-semibold tracking-wide text-accent-ink uppercase">Beta</span>
    </Link>
  )
}
