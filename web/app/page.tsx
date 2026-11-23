import Link from "next/link"
import { ArrowRightIcon, CheckIcon } from "@phosphor-icons/react/ssr"

import { HeroDemo } from "@/components/landing/hero-demo"
import { HeroSearch } from "@/components/landing/hero-search"
import { Logo } from "@/components/shell/logo"
import { Button } from "@/components/ui/button"

const SHEETS = [
  ["Summary", "var(--sum)", "Revenue, profit, equity, assets and cash flows as live formulas, with growth, margins, ROE and ROA."],
  ["Profit & Loss", "var(--pl)", "Every line item as the report prints it, one column per year."],
  ["Balance Sheet", "var(--bs)", "Assets, equity and liabilities in full, not the ten-line summary."],
  ["Cash Flow", "var(--cf)", "Operating, investing and financing activities, line by line."],
  ["Sources", "var(--src)", "The PDF pages each statement came from, and a link to the report."],
  ["Quality", "var(--ink-3)", "How many figures the report's own totals confirm, and what doesn't add up."],
] as const

const STEPS = [
  ["Finds the reports", "Every annual report for the years you pick, straight from the company's filings."],
  ["Locates the statements", "The Balance Sheet, P&L and Cash Flow, inside PDFs that run to 150–500 pages."],
  ["Reads and checks each line", "Each total is re-added from its items. Figures that tie are marked confirmed."],
  ["Lines up the years", "Renamed and restated lines are matched, so each item sits in one row."],
] as const

const PEOPLE = [
  ["Students", "var(--pl)", ["Full statements for a valuation assignment, without retyping from PDFs", "Common-size and year-on-year views built in", "Each ratio shows the formula behind it"]],
  ["Researchers", "var(--bs)", ["Consistent multi-year panels, as reported or latest restated", "Page-level sources, with a citation you can copy", "Indian or international number formats"]],
  ["Analysts", "var(--cf)", ["The first tab of a model in minutes, in ₹ crore", "Totals already ticked; exceptions listed for review", "Cross-checked against NSE filings and Screener"]],
] as const

// From the engine's test logs (100 companies, November 2026).
const STATS = [
  ["100", "listed companies in the test set"],
  ["97.9%", "of statements pass their checks"],
  ["95.7%", "of figures tie to the report's own totals"],
  ["95 of 100", "sampled figures matched the PDF by eye"],
] as const

export default function Landing() {
  return (
    <div className="relative overflow-x-clip">
      {/* backdrop: slow colour fields behind the hero */}
      <div aria-hidden className="aurora pointer-events-none absolute inset-x-0 top-0 -z-10 h-[820px] overflow-hidden">
        <i style={{ left: "-12%", top: "-38%", width: "62vw", height: "62vw", background: "radial-gradient(closest-side, color-mix(in oklab, var(--pl) 26%, transparent), transparent)", ["--dx" as string]: "60px", ["--dy" as string]: "40px" }} />
        <i style={{ right: "-14%", top: "-30%", width: "56vw", height: "56vw", background: "radial-gradient(closest-side, color-mix(in oklab, var(--bs) 22%, transparent), transparent)", ["--dx" as string]: "-50px", ["--dy" as string]: "50px", animationDelay: "-8s" }} />
        <i style={{ left: "30%", top: "6%", width: "44vw", height: "44vw", background: "radial-gradient(closest-side, color-mix(in oklab, var(--sum) 16%, transparent), transparent)", ["--dx" as string]: "40px", ["--dy" as string]: "-40px", animationDelay: "-15s" }} />
        <div className="dots absolute inset-0 opacity-60 [mask-image:linear-gradient(to_bottom,black,transparent_75%)]" />
        <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-page to-transparent" />
      </div>

      <header className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-5">
        <Logo />
        <nav className="ml-auto hidden items-center gap-6 text-sm text-ink-2 sm:flex">
          <a href="#workbook" className="transition-colors hover:text-ink">What you get</a>
          <a href="#how" className="transition-colors hover:text-ink">How it works</a>
          <a href="#accuracy" className="transition-colors hover:text-ink">Accuracy</a>
        </nav>
        <Button asChild variant="primary" className="ml-auto sm:ml-0">
          <Link href="/library">Open app</Link>
        </Button>
      </header>

      <section className="mx-auto grid max-w-6xl items-center gap-12 px-5 pt-10 pb-20 lg:grid-cols-[1.02fr_1fr] lg:pt-16 lg:pb-28">
        <div>
          <p className="mb-5 inline-flex items-center gap-2 rounded-full border border-line-2 bg-surface/70 px-3 py-1 text-[13px] text-ink-2 backdrop-blur">
            <span className="size-1.5 rounded-full bg-cf" />
            For students, researchers and analysts
          </p>
          <h1 className="text-[42px] leading-[1.02] font-bold sm:text-[58px]">
            Years of annual reports, one clean Excel.
          </h1>
          <p className="mt-5 max-w-xl text-[17px] leading-relaxed text-ink-2">
            Pick an Indian listed company and a span of years. FinXL reads each annual report and lines up the complete Balance Sheet,
            Profit &amp; Loss and Cash Flow, with every figure checked against the report&rsquo;s own totals.
          </p>
          <div className="mt-8">
            <HeroSearch />
          </div>
        </div>
        <HeroDemo />
      </section>

      <section id="workbook" className="mx-auto max-w-6xl px-5 py-16">
        <h2 className="text-[30px] font-semibold sm:text-[36px]">One file, six sheets</h2>
        <p className="mt-2 max-w-2xl text-[16px] text-ink-2">The same workbook every time, so your model can link to it without rework.</p>
        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {SHEETS.map(([name, hue, body]) => (
            <div key={name} className="relative overflow-hidden rounded-xl border bg-surface p-5 shadow-card">
              <span aria-hidden className="absolute inset-x-0 top-0 h-1" style={{ background: hue }} />
              <h3 className="text-[17px] font-semibold">{name}</h3>
              <p className="mt-1.5 text-[14.5px] leading-relaxed text-ink-2">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="how" className="mx-auto max-w-6xl px-5 py-16">
        <h2 className="text-[30px] font-semibold sm:text-[36px]">How it works</h2>
        <ol className="mt-8 grid gap-x-8 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map(([title, body], i) => (
            <li key={title} className="relative border-t-2 border-ink pt-4">
              <span className="num display text-[13px] font-semibold text-ink-3">Step {i + 1}</span>
              <h3 className="mt-1 text-[18px] font-semibold">{title}</h3>
              <p className="mt-1.5 text-[14.5px] leading-relaxed text-ink-2">{body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="mx-auto max-w-6xl px-5 py-16">
        <h2 className="text-[30px] font-semibold sm:text-[36px]">Made for the people who need the full statements</h2>
        <div className="mt-8 grid gap-3 md:grid-cols-3">
          {PEOPLE.map(([who, hue, points]) => (
            <div key={who} className="rounded-xl border bg-surface p-6 shadow-card">
              <h3 className="flex items-center gap-2.5 text-[19px] font-semibold">
                <span aria-hidden className="h-5 w-1.5 rounded-full" style={{ background: hue }} />
                {who}
              </h3>
              <ul className="mt-4 space-y-2.5 text-[14.5px] text-ink-2">
                {points.map((p) => (
                  <li key={p} className="flex gap-2.5">
                    <CheckIcon weight="bold" className="mt-[3px] size-4 shrink-0 text-ink-3" />
                    {p}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      <section id="accuracy" className="mx-auto max-w-6xl px-5 py-16">
        <div className="rounded-2xl bg-ink px-6 py-10 text-page sm:px-12 sm:py-14">
          <h2 className="max-w-2xl text-[30px] font-semibold sm:text-[36px]">It shows its working</h2>
          <p className="mt-3 max-w-2xl text-[16px] leading-relaxed opacity-75">
            The measure is simple: do our numbers match the annual report? Each total is re-added from its line items. What ties is
            marked confirmed. What doesn&rsquo;t is listed for you to check against the page, not hidden.
          </p>
          <dl className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {STATS.map(([n, label]) => (
              <div key={label}>
                <dt className="sr-only">{label}</dt>
                <dd className="display num text-[38px] leading-none font-semibold">{n}</dd>
                <dd className="mt-2 text-[14px] opacity-70">{label}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-5 pt-10 pb-24 text-center">
        <h2 className="text-[30px] font-semibold sm:text-[36px]">Start with one company</h2>
        <p className="mx-auto mt-2 max-w-md text-[16px] text-ink-2">Six years of statements takes about a minute.</p>
        <Button asChild variant="primary" size="lg" className="mt-7">
          <Link href="/new">
            Extract statements <ArrowRightIcon weight="bold" />
          </Link>
        </Button>
      </section>

      <footer className="border-t">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-5 py-6 text-[13px] text-ink-3">
          <Logo />
          <span>Public beta. Figures come from companies' own annual reports; check anything flagged before relying on it.</span>
          <Link href="/settings" className="ml-auto transition-colors hover:text-ink">
            Settings
          </Link>
        </div>
      </footer>
    </div>
  )
}
