"use client"

import * as React from "react"
import { ThemeProvider, useTheme } from "next-themes"
import { Tooltip } from "radix-ui"
import { Toaster } from "sonner"

import { CommandPalette } from "@/components/shell/command-palette"
import { useSettings } from "@/lib/store"

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    // Light is the designed-for theme; dark and "match my device" live in Settings.
    <ThemeProvider attribute="class" defaultTheme="light" enableSystem storageKey="finxl-theme-v3" disableTransitionOnChange>
      <Tooltip.Provider delayDuration={350} skipDelayDuration={200}>
        <MotionPreference />
        {children}
        <CommandPalette />
        <Toasts />
      </Tooltip.Provider>
    </ThemeProvider>
  )
}

/** Applies the "Reduce motion" setting to the whole document. */
function MotionPreference() {
  const [settings] = useSettings()
  React.useEffect(() => {
    document.documentElement.classList.toggle("calm", settings.reduceMotion)
  }, [settings.reduceMotion])
  return null
}

function Toasts() {
  const { resolvedTheme } = useTheme()
  return (
    <Toaster
      theme={resolvedTheme === "dark" ? "dark" : "light"}
      position="bottom-center"
      gap={8}
      toastOptions={{
        style: {
          fontFamily: "var(--font-sans)",
          fontSize: 13.5,
          borderRadius: 12,
          border: "1px solid var(--line-2)",
          background: "var(--raised)",
          color: "var(--ink)",
          boxShadow: "var(--shadow-pop)",
        },
      }}
    />
  )
}
