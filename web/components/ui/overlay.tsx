"use client"

import * as React from "react"
import { XIcon } from "@phosphor-icons/react"
import { Dialog as RDialog, DropdownMenu, Popover as RPopover } from "radix-ui"

import { cn } from "@/lib/utils"

const overlay = "fixed inset-0 z-50 animate-fade bg-[rgb(20_20_28/0.28)] dark:bg-[rgb(0_0_0/0.55)]"

/** Centred dialog for a short, focused task. */
export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  className,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  title: string
  description?: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <RDialog.Root open={open} onOpenChange={onOpenChange}>
      <RDialog.Portal>
        <RDialog.Overlay className={overlay} />
        <RDialog.Content
          className={cn(
            "fixed top-[12%] left-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 animate-pop rounded-xl border border-line-2 bg-raised p-5 shadow-pop outline-none",
            className
          )}
        >
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <RDialog.Title className="display text-lg font-semibold">{title}</RDialog.Title>
              {description && <RDialog.Description className="mt-0.5 text-[13px] text-ink-2">{description}</RDialog.Description>}
            </div>
            <RDialog.Close aria-label="Close" className="-mt-1 -mr-1 grid size-8 place-items-center rounded-md text-ink-3 hover:bg-ink/[0.06] hover:text-ink">
              <XIcon className="size-4" />
            </RDialog.Close>
          </div>
          {children}
        </RDialog.Content>
      </RDialog.Portal>
    </RDialog.Root>
  )
}

/** Bottom sheet on phones, side panel on wider screens. Used where a docked panel doesn't fit. */
export function Sheet({
  open,
  onOpenChange,
  title,
  children,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  title: string
  children: React.ReactNode
}) {
  return (
    <RDialog.Root open={open} onOpenChange={onOpenChange}>
      <RDialog.Portal>
        <RDialog.Overlay className={overlay} />
        <RDialog.Content
          aria-describedby={undefined}
          className="fixed inset-x-0 bottom-0 z-50 flex max-h-[86dvh] animate-sheet flex-col rounded-t-2xl border border-line-2 bg-raised shadow-pop outline-none sm:inset-y-0 sm:right-0 sm:left-auto sm:max-h-none sm:w-[400px] sm:animate-panel sm:rounded-none sm:border-y-0 sm:border-r-0"
        >
          <RDialog.Title className="sr-only">{title}</RDialog.Title>
          <div aria-hidden className="mx-auto mt-2 h-1 w-9 shrink-0 rounded-full bg-ink/15 sm:hidden" />
          {children}
        </RDialog.Content>
      </RDialog.Portal>
    </RDialog.Root>
  )
}

export function Popover({
  trigger,
  children,
  align = "end",
  className,
  open,
  onOpenChange,
}: {
  trigger: React.ReactElement
  children: React.ReactNode
  align?: "start" | "center" | "end"
  className?: string
  open?: boolean
  onOpenChange?: (o: boolean) => void
}) {
  return (
    <RPopover.Root open={open} onOpenChange={onOpenChange}>
      <RPopover.Trigger asChild>{trigger}</RPopover.Trigger>
      <RPopover.Portal>
        <RPopover.Content
          align={align}
          sideOffset={8}
          collisionPadding={12}
          className={cn("z-50 w-80 animate-pop rounded-xl border border-line-2 bg-raised p-4 shadow-pop outline-none", className)}
        >
          {children}
        </RPopover.Content>
      </RPopover.Portal>
    </RPopover.Root>
  )
}

export function Menu({ trigger, children, align = "end" }: { trigger: React.ReactElement; children: React.ReactNode; align?: "start" | "end" }) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>{trigger}</DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content align={align} sideOffset={6} className="z-50 min-w-44 animate-pop rounded-lg border border-line-2 bg-raised p-1 shadow-pop">
          {children}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}

export function MenuItem({
  children,
  onSelect,
  danger,
  icon,
}: {
  children: React.ReactNode
  onSelect: () => void
  danger?: boolean
  icon?: React.ReactNode
}) {
  return (
    <DropdownMenu.Item
      onSelect={onSelect}
      className={cn(
        "flex h-8 cursor-pointer items-center gap-2 rounded-md px-2.5 text-[13px] outline-none select-none data-[highlighted]:bg-ink/[0.06] [&_svg]:size-4 [&_svg]:text-ink-3",
        danger && "text-bad-ink [&_svg]:text-bad-ink"
      )}
    >
      {icon}
      {children}
    </DropdownMenu.Item>
  )
}
