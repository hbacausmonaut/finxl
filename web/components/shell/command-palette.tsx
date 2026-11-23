"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { useTheme } from "next-themes"
import { Command } from "cmdk"
import { BooksIcon, BuildingsIcon, GearSixIcon, MagnifyingGlassIcon, MoonIcon, PlusCircleIcon, SunIcon, TableIcon } from "@phosphor-icons/react"

import { fyLabel } from "@/lib/fy"
import { loadCompanies, searchCompanies } from "@/lib/api"
import { useLibrary } from "@/lib/store"

const EVENT = "finxl:palette"
export const openPalette = () => window.dispatchEvent(new Event(EVENT))

const item =
  "flex cursor-pointer items-center gap-3 rounded-md px-2.5 py-2 text-[13.5px] outline-none select-none data-[selected=true]:bg-ink/[0.06] [&_svg]:size-[18px] [&_svg]:shrink-0 [&_svg]:text-ink-3"
const group = "px-1.5 pb-1.5 [&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:pt-2.5 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:text-[11.5px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-ink-3"

/** One search box for companies, saved workbooks and the few global actions. */
export function CommandPalette() {
  const [open, setOpen] = React.useState(false)
  const router = useRouter()
  const { resolvedTheme, setTheme } = useTheme()
  const { runs } = useLibrary()
  const [search, setSearch] = React.useState("")
  const [, setLoaded] = React.useState(0)
  React.useEffect(() => {
    if (open) void loadCompanies().then((l) => setLoaded(l.length))
  }, [open])
  const companies = searchCompanies(search, 8)

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLElement && (e.target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName))
      if ((e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey)) || (e.key === "/" && !typing)) {
        e.preventDefault()
        setOpen((o) => !o)
      }
    }
    const onOpen = () => setOpen(true)
    window.addEventListener("keydown", onKey)
    window.addEventListener(EVENT, onOpen)
    return () => {
      window.removeEventListener("keydown", onKey)
      window.removeEventListener(EVENT, onOpen)
    }
  }, [])

  const go = (href: string) => {
    setOpen(false)
    router.push(href)
  }
  const done = runs.filter((r) => r.status === "done").slice(0, 6)

  return (
    <Command.Dialog
      open={open}
      onOpenChange={setOpen}
      label="Search"
      overlayClassName="fixed inset-0 z-[60] animate-fade bg-[rgb(20_20_28/0.28)] dark:bg-[rgb(0_0_0/0.55)]"
      contentClassName="fixed top-[14%] left-1/2 z-[60] w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 animate-pop overflow-hidden rounded-xl border border-line-2 bg-raised shadow-pop outline-none"
    >
      <div className="flex items-center gap-2.5 border-b px-4">
        <MagnifyingGlassIcon className="size-[18px] text-ink-3" />
        <Command.Input value={search} onValueChange={setSearch} placeholder="Company, NSE symbol, or a saved workbook" className="h-12 w-full bg-transparent text-[15px] outline-none placeholder:text-ink-3" />
      </div>
      <Command.List className="thin-scroll max-h-[min(420px,56dvh)] overflow-y-auto py-1.5">
        <Command.Empty className="px-4 py-8 text-center text-[13.5px] text-ink-3">Nothing matches. Try an NSE symbol such as HCLTECH.</Command.Empty>

        {done.length > 0 && (
          <Command.Group heading="Your workbooks" className={group}>
            {done.map((r) => (
              <Command.Item key={r.id} value={`workbook ${r.request.symbol} ${r.companyName} ${r.id}`} onSelect={() => go(`/w?id=${r.id}`)} className={item}>
                <TableIcon />
                <span className="truncate">{r.companyName}</span>
                <span className="num ml-auto shrink-0 text-[12px] text-ink-3">
                  {fyLabel(r.request.from)}–{fyLabel(r.request.to)}
                </span>
              </Command.Item>
            ))}
          </Command.Group>
        )}

        <Command.Group heading="Extract a company" className={group}>
          {companies.map((c) => (
            <Command.Item key={c.symbol} value={`${c.symbol} ${c.name}`} onSelect={() => go(`/new?c=${c.symbol}`)} className={item}>
              <BuildingsIcon />
              <span className="truncate">{c.name}</span>
              <span className="num ml-auto shrink-0 text-[12px] text-ink-3">{c.symbol}</span>
            </Command.Item>
          ))}
        </Command.Group>

        <Command.Group heading="Go to" className={group}>
          <Command.Item onSelect={() => go("/new")} className={item}>
            <PlusCircleIcon /> New extraction
          </Command.Item>
          <Command.Item onSelect={() => go("/library")} className={item}>
            <BooksIcon /> Library
          </Command.Item>
          <Command.Item onSelect={() => go("/settings")} className={item}>
            <GearSixIcon /> Settings
          </Command.Item>
          <Command.Item
            value="theme dark light appearance"
            onSelect={() => {
              setTheme(resolvedTheme === "dark" ? "light" : "dark")
              setOpen(false)
            }}
            className={item}
          >
            {resolvedTheme === "dark" ? <SunIcon /> : <MoonIcon />}
            Switch to {resolvedTheme === "dark" ? "light" : "dark"} theme
          </Command.Item>
        </Command.Group>
      </Command.List>
    </Command.Dialog>
  )
}
