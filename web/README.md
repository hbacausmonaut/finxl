# FinXL: UI concept

A frontend-only concept for **FinXL**, which turns an Indian listed company's annual reports (any span of fiscal years) into one multi-year Excel of P&L, Balance Sheet, Cash Flow and key notes, ready for a three-statement model.

This build is for **UI/UX evaluation**. It does not touch the real backend. Every screen reads from a typed mock API (`lib/api.ts`) backed by deterministic mock data, so it can be wired to the real service later by replacing the function bodies.

> All figures are mock data. The demo company, *Vardhan Specialty Chemicals Ltd (VARDHANSPL)*, is fictional on purpose so that fabricated statements are never attached to a real listed name. The other 19 companies in search are real NSE names; picking one runs against the demo dataset (the UI says so).

---

## Run it

Requires Node 20+ (built and tested on Node 26 LTS, Next.js 16.4, React 19.3, Tailwind 4).

```bash
npm install
npm run dev          # http://localhost:3000
```

Other scripts: `npm run build`, `npm run start`, `npm run typecheck`, `npm run lint`.

Shortcuts: **Ctrl/⌘ K** or **/** opens the command palette. **D** toggles dark mode. In a statement table, the **arrow keys / Home / End / PgUp / PgDn** move between figures and **Enter** opens the source.

---

## Screens

| Route | Screen | What to look at |
|---|---|---|
| `/` | **Landing** | The one-line pitch, the single Aceternity hero moment (a live 10-year P&L tilting flat as you scroll) and the "Try with a company" CTA |
| `/search` | **Company search** | ⌘K palette over NSE companies, recent searches, sector peers, an open-ended **fiscal-year timeline picker** (click a start then an end, or use the From/To selects or presets; no span limit), Standalone vs Consolidated, OCR warning for scanned years |
| `/run` | **Extraction run** | Agent-style step cards: Fetch → Locate → Extract → Reconcile → Build. Each card shows status, live duration, progress, pages found per year and a streaming log. Also a per-year status matrix, a 1×/4× speed toggle, Re-run, and a completion card plus toast. Opening `/run` without `?start=1` replays the last run quickly |
| `/viewer` | **Statement viewer** (core) | NumberFlow KPI strip (Revenue, EBITDA margin, PAT, Net debt, CFO/PAT) with YoY deltas and sparklines, focused on any year you click; tabs for **P&L / Balance Sheet / Cash Flow / Notes / Ratios**; sticky header + sticky first column; smooth horizontal scroll with edge shadows; density toggle; ₹ Cr / ₹ L / ₹ unit toggle; expand/collapse groups; CAGR column |
| `/export` | **Export** | Raw extracted vs model-ready layout (each with a sheet preview), include toggles, unit, a pre-flight summary that warns about unreviewed values and failing checks, mock download with a Sonner toast |
| `/history` | **Run history** | Past runs with company, years, basis, status, accuracy score and duration; filter and search; a table on desktop and cards on mobile; opening a run loads it |

### New features (UI only, mocked)

- **Source traceability**: click any figure. A side Sheet (a Vaul bottom drawer on phones) shows a placeholder annual-report page with the figure boxed, plus page number, report year, the label as printed, read method (text layer vs OCR, with scanned years given a paper texture) and a confidence meter. Computed rows show their formula breakdown instead.
- **Integrity checks**: a panel with a checks × years matrix covering three checks per year:
  - Assets = Equity + Liabilities
  - CF closing cash = BS cash
  - Expense lines = printed total expenses

  Failing cells are highlighted red in the table, year headers get red/green dots, and "Show likely cause" jumps to and flashes the offending cell.
- **Low-confidence review queue**: approval cards (AI Elements `Confirmation`) where you can *Accept extracted*, *Use second reading* or *Edit*, with Undo. Decisions flow straight into the table, KPIs, ratios and checks. Using the second reading on a planted error turns its check green.
- **Restatement flags**: a superscript **R** on restated cells; the source panel shows *as first reported* (struck through) next to *restated*, with the reason.
- **Quick ratios tab**: revenue growth, EBITDA and PAT margins, ROE, ROCE, receivable/inventory/payable days, cash-conversion cycle, net debt/EBITDA, interest coverage and CFO/PAT. All are computed live from the extracted data, including review edits.

---

## Design system

| Token | Choice |
|---|---|
| Feel | Editorial finance terminal: calm, dense, precise |
| UI font | **IBM Plex Sans** |
| Figures | **IBM Plex Mono** with tabular, slashed-zero numerals (`.num` utility); `tabular-nums` is on globally |
| Headings | **Newsreader** (serif, with italics for emphasis) |
| Radius | 5px base, every radius step capped at 6px (shadcn defaults can't go soft) |
| Theme | **Dark by default** (toggle or press D for light; the choice is stored under `finxl-theme`) |
| Palette | Warm paper / ink neutrals, **one cobalt accent**, semantic `positive` / `negative` / `warning`, all as CSS variables with a full `.dark` set (`app/globals.css`) |
| Numbers | Indian grouping (`en-IN`), ₹ crore by default with lakh / absolute toggles, right-aligned, negatives in parentheses, FY labels (`FY16`…`FY25`) |

---

## Libraries, and where each is used

Everything was installed via each library's CLI or shadcn registry, so the source lives in the repo and is editable.

| Library | Install | Used in |
|---|---|---|
| **Next.js 16** (App Router) + TypeScript + Tailwind 4 | `shadcn init -t next -b radix` | Whole app |
| **shadcn/ui on Radix** (restyled) | `shadcn add …` | Buttons, inputs, select, toggle groups, tabs, table, dialog, sheet, tooltip, switch, radio group, progress, skeleton, kbd, collapsible: every screen. Restyled through tokens; `tabs.tsx`, `dialog.tsx`, `sheet.tsx` and `drawer.tsx` were also edited directly |
| **Sonner** | `shadcn add sonner` | Run-complete toast, review edits, export success (`components/ui/sonner.tsx`, themed) |
| **Vaul** | `shadcn add drawer` | Mobile nav menu (`app-shell.tsx`); on phones, the trace, checks and review panels (`components/app/side-panel.tsx`) |
| **cmdk** | `shadcn add command` | ⌘K palette: companies, recents, navigation, unit/density/theme actions (`components/app/command-palette.tsx`) |
| **NumberFlow** | `npm i @number-flow/react` | KPI strip, run progress % and elapsed time, checks count, review progress |
| **Vercel AI Elements** | `shadcn add @ai-elements/{tool,task,confirmation,shimmer,chain-of-thought}` | `Tool` as the collapsible pipeline step card; `Task` / `TaskItemFile` for pages found per report; `Shimmer` for the running-step label; `Confirmation` for review approval cards (`components/run/*`, `components/viewer/review-queue.tsx`) |
| **Magic UI** | `shadcn add @magicui/border-beam @magicui/animated-shiny-text` | `BorderBeam` traces the active step card; `AnimatedShinyText` is the landing eyebrow pill |
| **Aceternity UI** | `shadcn add @aceternity/container-scroll-animation` | **Landing hero only**: a server-rendered 10-year P&L preview that tilts into place on scroll (restyled; respects reduced motion) |
| next-themes, lucide-react, motion | pulled in by the above | Theming, icons, animation runtime |

Not taken from a library: the fiscal-year timeline picker, the statement grid and the source-page placeholder. Nothing on 21st.dev fitted Indian fiscal years or a sticky multi-year financial grid with roving focus, so these are built from shadcn primitives.

---

## Mock data and API

- `lib/mock/generate.ts` generates **FY06–FY25** for a mid-cap specialty-chemicals company (standalone and consolidated) in integer ₹ lakh. Every cash-flow line is derived from balance-sheet movements, so **the balance sheet balances and closing cash ties out by construction**.
- `lib/mock/workbook.ts` then plants **three extraction errors**, each breaking exactly one check:
  - FY19 other current liabilities: BS doesn't balance
  - FY22 trade payables in CF: closing cash ≠ BS cash
  - FY23 other expenses (an OCR 3↔8 misread): expenses ≠ printed total

  It also adds three correct-but-shaky values, plus restatements in FY20 (revenue/other income reclassified in the FY21 report) and FY23 (inventories restated in the FY24 report).
- `lib/api.ts` is the typed contract: `searchCompanies`, `getCompany`, `listRuns`, `getWorkbook`, `streamRun` (simulates an SSE stream of `RunEvent`s) and `exportWorkbook`. Types live in `lib/types.ts`.
- `lib/compute.ts` holds the subtotals, integrity checks, ratios and KPIs, all recomputed live from extracted values plus reviewer overrides.

## Project map

```
app/
  page.tsx                 landing
  (app)/layout.tsx         app shell (top bar, nav, mobile drawer)
  (app)/search|run|viewer|export|history/page.tsx
components/
  app/       shell, command palette, side panel (Sheet ↔ Vaul), year-range picker, workspace state
  run/       step cards, run stream hook
  viewer/    statement table, KPI strip, trace panel, source page, checks panel, review queue
  landing/   hero preview
  ui/, ai-elements/   installed library components (editable)
lib/         types, api, compute, format, fiscal-year helpers, sheet layouts, mock data
```

See `PLAN.md` for the original design plan.

## Motion & polish upgrade (branch `motion-upgrade`)

Every change has an on/off switch in `lib/features.ts`; set a flag to `false` to remove just that change.
The original build is tagged `v1-original` (`git checkout v1-original`, or `git switch master`).
