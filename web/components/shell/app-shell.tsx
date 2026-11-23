"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { BooksIcon, GearSixIcon, MagnifyingGlassIcon, PlusCircleIcon } from "@phosphor-icons/react"

import { Logo } from "@/components/shell/logo"
import { openPalette } from "@/components/shell/command-palette"
import { Kbd, useModKey, useSlide } from "@/components/ui/controls"
import { cn } from "@/lib/utils"

const NAV = [
  { href: "/new", label: "Extract", icon: PlusCircleIcon, match: (p: string) => p.startsWith("/new") },
  { href: "/library", label: "Library", icon: BooksIcon, match: (p: string) => p.startsWith("/library") || p.startsWith("/w/") },
  { href: "/settings", label: "Settings", icon: GearSixIcon, match: (p: string) => p.startsWith("/settings") },
]

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const active = NAV.find((n) => n.match(pathname))?.href ?? ""
  const [ref, box] = useSlide(active)
  const mod = useModKey()

  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[70] focus:rounded-md focus:bg-surface focus:px-3 focus:py-2 focus:shadow-pop">
        Skip to content
      </a>

      <header className="sticky top-0 z-40 border-b bg-page/85 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-[1440px] items-center gap-6 px-4 sm:px-6">
          <Logo href="/" />

          <nav ref={ref} aria-label="Main" className="relative hidden items-center md:flex">
            {box && (
              <span
                aria-hidden
                className={cn("absolute top-1/2 left-0 h-8 rounded-md bg-ink/[0.07]", box.ready && "transition-[transform,width] duration-200")}
                style={{ width: box.w, transform: `translate(${box.x}px, -50%)` }}
              />
            )}
            {NAV.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                data-active={n.href === active}
                aria-current={n.href === active ? "page" : undefined}
                className="relative z-[1] rounded-md px-3 py-1.5 text-sm font-medium text-ink-2 transition-colors hover:text-ink data-[active=true]:text-ink"
              >
                {n.label}
              </Link>
            ))}
          </nav>

          <button
            type="button"
            onClick={openPalette}
            className="ml-auto hidden h-9 w-64 items-center gap-2 rounded-md border border-line-2 bg-surface px-2.5 text-left text-[13px] text-ink-3 shadow-card transition-colors hover:text-ink-2 md:flex"
          >
            <MagnifyingGlassIcon className="size-4" />
            <span className="truncate">Search companies, workbooks</span>
            <span className="ml-auto flex gap-0.5">
              <Kbd>{mod}</Kbd>
              <Kbd>K</Kbd>
            </span>
          </button>
          <button
            type="button"
            onClick={openPalette}
            aria-label="Search"
            className="ml-auto grid size-9 place-items-center rounded-md text-ink-2 hover:bg-ink/[0.06] md:hidden"
          >
            <MagnifyingGlassIcon className="size-5" />
          </button>
        </div>
      </header>

      <main id="main" key={active || pathname} className="flex-1 animate-enter pb-20 md:pb-0">
        {children}
      </main>

      {/* Phones: the three tabs sit under the thumb. */}
      <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-3 border-t bg-page/92 pb-[env(safe-area-inset-bottom)] backdrop-blur-md md:hidden">
        {NAV.map((n) => {
          const on = n.href === active
          return (
            <Link
              key={n.href}
              href={n.href}
              aria-current={on ? "page" : undefined}
              className={cn("flex flex-col items-center gap-0.5 py-2 text-[11px] font-medium transition-colors", on ? "text-ink" : "text-ink-3")}
            >
              <n.icon weight={on ? "fill" : "regular"} className="size-[22px]" />
              {n.label}
            </Link>
          )
        })}
      </nav>
    </div>
  )
}
