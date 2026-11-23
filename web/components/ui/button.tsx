import * as React from "react"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

type Variant = "primary" | "secondary" | "ghost" | "soft" | "danger"
type Size = "sm" | "md" | "lg"

const base =
  "inline-flex shrink-0 select-none items-center justify-center gap-1.5 rounded-md font-medium whitespace-nowrap transition-[background-color,border-color,color,box-shadow,transform] active:scale-[0.98] disabled:pointer-events-none disabled:opacity-45 [&_svg]:shrink-0"

const variants: Record<Variant, string> = {
  primary: "bg-ink text-page shadow-card hover:bg-ink/85",
  secondary: "border border-line-2 bg-surface text-ink shadow-card hover:bg-sunken",
  ghost: "text-ink-2 hover:bg-ink/[0.06] hover:text-ink",
  soft: "bg-accent/10 text-accent-ink hover:bg-accent/[0.16]",
  danger: "text-bad-ink hover:bg-bad/10",
}

const sizes: Record<Size, string> = {
  sm: "h-8 px-2.5 text-[13px] [&_svg]:size-4",
  md: "h-9 px-3.5 text-sm [&_svg]:size-[18px]",
  lg: "h-11 px-5 text-[15px] [&_svg]:size-5",
}
const squares: Record<Size, string> = { sm: "w-8 px-0", md: "w-9 px-0", lg: "w-11 px-0" }

export interface ButtonProps extends React.ComponentProps<"button"> {
  variant?: Variant
  size?: Size
  /** Icon-only: equal width and height. Always pass an aria-label. */
  square?: boolean
  asChild?: boolean
}

export function Button({ variant = "secondary", size = "md", square, asChild, className, type, ...props }: ButtonProps) {
  const Comp = asChild ? Slot.Root : "button"
  return (
    <Comp
      type={asChild ? undefined : (type ?? "button")}
      className={cn(base, variants[variant], sizes[size], square && squares[size], className)}
      {...props}
    />
  )
}
