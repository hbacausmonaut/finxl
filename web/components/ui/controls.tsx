"use client"

import * as React from "react"
import { CaretDownIcon, CheckIcon } from "@phosphor-icons/react"
import { Select as RSelect, Switch as RSwitch, ToggleGroup, Tooltip } from "radix-ui"

import { cn } from "@/lib/utils"

/**
 * Tracks the active child of a strip so a thumb or underline can slide to it.
 * The movement shows which way you went; it is skipped on first paint.
 */
export function useSlide(value: string) {
  const ref = React.useRef<HTMLDivElement>(null)
  const [box, setBox] = React.useState<{ x: number; w: number; ready: boolean } | null>(null)
  React.useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const measure = () => {
      const a = el.querySelector<HTMLElement>('[data-active="true"]')
      if (a) setBox((b) => ({ x: a.offsetLeft, w: a.offsetWidth, ready: b !== null }))
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [value])
  return [ref, box] as const
}

export interface Option<T extends string> {
  value: T
  label: React.ReactNode
  hint?: string
  disabled?: boolean
}

/** A small either/or control. The thumb slides to the chosen option. */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
  size = "md",
  className,
}: {
  value: T
  onChange: (v: T) => void
  options: Option<T>[]
  label: string
  size?: "sm" | "md"
  className?: string
}) {
  const [ref, box] = useSlide(value)
  return (
    <ToggleGroup.Root
      ref={ref}
      type="single"
      value={value}
      onValueChange={(v) => v && onChange(v as T)}
      aria-label={label}
      className={cn("relative inline-flex rounded-md bg-ink/[0.06] p-0.5", className)}
    >
      {box && (
        <span
          aria-hidden
          className={cn("absolute inset-y-0.5 left-0 rounded-[6px] bg-surface shadow-card", box.ready && "transition-[transform,width] duration-200")}
          style={{ width: box.w, transform: `translateX(${box.x}px)` }}
        />
      )}
      {options.map((o) => (
        <ToggleGroup.Item
          key={o.value}
          value={o.value}
          disabled={o.disabled}
          title={o.hint}
          data-active={o.value === value}
          className={cn(
            "relative z-[1] rounded-[6px] font-medium whitespace-nowrap text-ink-2 transition-colors hover:text-ink disabled:opacity-40 data-[active=true]:text-ink",
            size === "sm" ? "h-7 px-2.5 text-[12.5px]" : "h-8 px-3 text-[13px]"
          )}
        >
          {o.label}
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  )
}

export function Switch({ checked, onChange, label, id }: { checked: boolean; onChange: (v: boolean) => void; label: string; id?: string }) {
  return (
    <RSwitch.Root
      id={id}
      checked={checked}
      onCheckedChange={onChange}
      aria-label={label}
      className="relative h-6 w-10 shrink-0 rounded-full bg-ink/15 transition-colors data-[state=checked]:bg-accent"
    >
      <RSwitch.Thumb className="block size-5 translate-x-0.5 rounded-full bg-white shadow-card transition-transform duration-200 data-[state=checked]:translate-x-[18px]" />
    </RSwitch.Root>
  )
}

export function Select<T extends string>({
  value,
  onChange,
  options,
  label,
  className,
}: {
  value: T
  onChange: (v: T) => void
  options: Option<T>[]
  label: string
  className?: string
}) {
  return (
    <RSelect.Root value={value} onValueChange={(v) => onChange(v as T)}>
      <RSelect.Trigger
        aria-label={label}
        className={cn(
          "inline-flex h-9 items-center justify-between gap-2 rounded-md border border-line-2 bg-surface px-3 text-sm shadow-card transition-colors hover:bg-sunken",
          className
        )}
      >
        <RSelect.Value />
        <RSelect.Icon>
          <CaretDownIcon className="size-3.5 text-ink-3" />
        </RSelect.Icon>
      </RSelect.Trigger>
      <RSelect.Portal>
        <RSelect.Content
          position="popper"
          sideOffset={6}
          className="z-50 max-h-72 min-w-[var(--radix-select-trigger-width)] animate-pop overflow-hidden rounded-lg border border-line-2 bg-raised p-1 shadow-pop"
        >
          <RSelect.Viewport>
            {options.map((o) => (
              <RSelect.Item
                key={o.value}
                value={o.value}
                disabled={o.disabled}
                className="flex h-8 cursor-pointer items-center justify-between gap-6 rounded-md px-2.5 text-sm outline-none select-none data-[disabled]:opacity-40 data-[highlighted]:bg-ink/[0.06]"
              >
                <RSelect.ItemText>{o.label}</RSelect.ItemText>
                <RSelect.ItemIndicator>
                  <CheckIcon weight="bold" className="size-3.5 text-accent-ink" />
                </RSelect.ItemIndicator>
              </RSelect.Item>
            ))}
          </RSelect.Viewport>
        </RSelect.Content>
      </RSelect.Portal>
    </RSelect.Root>
  )
}

export function Tip({ children, text, side = "top" }: { children: React.ReactElement; text: React.ReactNode; side?: "top" | "bottom" | "left" | "right" }) {
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>{children}</Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side={side}
          sideOffset={6}
          className="z-[60] max-w-64 animate-fade rounded-md bg-ink px-2 py-1 text-[12px] leading-snug text-page shadow-pop"
        >
          {text}
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  )
}

export function Kbd({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <kbd className={cn("inline-flex h-5 min-w-5 items-center justify-center rounded-[5px] border border-line-2 bg-surface px-1 font-sans text-[11px] font-medium text-ink-2", className)}>
      {children}
    </kbd>
  )
}

export function Skeleton({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return <div aria-hidden className={cn("skeleton", className)} style={style} />
}

type Tone = "neutral" | "good" | "warn" | "odd" | "bad" | "accent"
const tones: Record<Tone, string> = {
  neutral: "bg-ink/[0.06] text-ink-2",
  good: "bg-good/10 text-good-ink",
  warn: "bg-warn/20 text-warn-ink",
  odd: "bg-odd/15 text-odd-ink",
  bad: "bg-bad/10 text-bad-ink",
  accent: "bg-accent/10 text-accent-ink",
}

/** A status label. Always carries an icon or text, never colour alone. */
export function Chip({ tone = "neutral", children, className }: { tone?: Tone; children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex h-6 items-center gap-1 rounded-full px-2 text-[12px] font-medium whitespace-nowrap [&_svg]:size-3.5", tones[tone], className)}>
      {children}
    </span>
  )
}

/** "⌘" on Apple devices, "Ctrl" elsewhere. */
export function useModKey() {
  return React.useSyncExternalStore(
    () => () => {},
    () => (/Mac|iPhone|iPad/.test(navigator.platform) ? "⌘" : "Ctrl"),
    () => "Ctrl"
  )
}
