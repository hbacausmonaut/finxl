import type { Metadata, Viewport } from "next"
import { Bricolage_Grotesque, Figtree } from "next/font/google"

import "./globals.css"
import { Providers } from "@/components/shell/providers"

// latin-ext carries the ₹ sign.
const display = Bricolage_Grotesque({ subsets: ["latin", "latin-ext"], variable: "--font-bricolage", display: "swap" })
const text = Figtree({ subsets: ["latin", "latin-ext"], variable: "--font-figtree", display: "swap" })

export const metadata: Metadata = {
  title: { default: "FinXL — annual reports to Excel", template: "%s · FinXL" },
  description:
    "Pick an Indian listed company and a span of years. FinXL reads each annual report and lines up the full Balance Sheet, P&L and Cash Flow in one Excel file.",
}

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f7f6f2" },
    { media: "(prefers-color-scheme: dark)", color: "#111114" },
  ],
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en-IN" suppressHydrationWarning className={`${display.variable} ${text.variable}`}>
      <body className="min-h-dvh">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
