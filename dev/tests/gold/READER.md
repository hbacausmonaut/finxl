# Instructions for the second reader (Claude)

You are reading ONE financial statement from an Indian annual report, from page images only.
Your reading is compared row by row with an automatic parser, so it must be **independent**:

- Do **not** open anything under `tests/gold/parser/`, `tests/gold/silver/`, `tests/gold/disagreements_*`,
  any `.xlsx`, or the PDF's text layer. Use only the PNG page images you are given.
- Do not run the parser or any Python that extracts text from the PDF.

## What to write

One JSON file per statement, `tests/gold/reading/<TICKER>_<FY>_<kind>.json` (kind: `pl`, `bs`, `cf`):

```json
{
  "ticker": "SBIN", "fy": 2026, "statement": "pl", "scope": "consolidated",
  "reader": "claude", "read_at": "2026-11-04 12:00 UTC",
  "unit": "thousand",
  "years": [2026, 2025],
  "rows": [
    {"label": "INCOME", "values": [null, null], "page": 313},
    {"label": "Interest earned", "values": [5149325904, 4903126989], "page": 313}
  ],
  "notes": "anything odd: statement continues on a page you were not given, unreadable cells, etc."
}
```

- `unit`: the unit the amounts are printed in: `crore`, `lakh`, `million`, `thousand` ("000s omitted", "₹ '000"), or `null` for plain rupees.
- `years`: the fiscal year of each amount column, current year first (year ended 31 March 2026 → 2026). One entry per year, even if a year has inner/outer sub-columns.
- `page`: the 0-based PDF page index. Image file names carry the 1-based page number (`p314_s1.png` = page index 313; `p126L` / `p126R` = left/right half of page index 125).

## Which rows

Include, **in printed order**, every line of the statement body between the column headings and the end of the statement:
- every line item, sub-item, **section heading** (e.g. "INCOME", "ASSETS", "Cash flow from operating activities") with `null` values, every **total and sub-total**, EPS lines, and memo lines inside the statement.
- if the statement runs across several pages, all of them, once. Skip lines repeated as "carried forward / brought forward" headers only if they carry no amounts.

Do **not** include:
- page furniture: navigation strips ("Company Overview | Governance | …"), page numbers, running headers/footers, the company name, the statement title ("Consolidated Balance Sheet as at …"), the unit line ("₹ in crore", "(000s omitted)")
- column headings ("Note", "Schedule No.", "As at 31.03.2026", "(Current Year)", "₹")
- anything after the statement's last line (closing cash and cash equivalents / total / EPS): "Notes:" blocks, the "Components of cash and cash equivalents" breakdown, financing-liability reconciliations, income-tax-paid memos, even when they sit inside the same box or on a page that repeats the title,
- footnotes and explanatory notes after the statement, reconciliation tables printed below it, "Significant accounting policies…" lines, "The accompanying notes form…", signature blocks, auditors' names, dates and places.
- the images named `*-next_*` show the page AFTER the statement: use them only if the statement clearly continues there.

## Labels

- As printed, with wrapped lines joined into one label ("Net Profit for the year (before adjustment for Share in Profit of Associates and Minority Interest)").
- Drop serial markers at the start (`I.`, `II.`, `(a)`, `(i)`, `A.`, `1.`) and the note / schedule number column.
- Keep everything else, including "Less:", "Add:", "(Increase)/Decrease in …", "(in ₹)". Write the rupee sign as `₹`.

## Values

- Copy every amount exactly. Write it as a plain number with no separators, in the printed unit: `514932,59,04` → `5149325904`; `1,23,456.78` → `123456.78`.
- Brackets or a leading minus mean negative: `(1,234.50)` → `-1234.5`.
- `-`, `–`, `—`, `Nil` or an empty cell → `null`.
- A row whose amount sits in a sub-total column still has one value per year: the number printed on that line under that year.
- If a line prints BOTH its own amount and, in the outer column, the sub-total of the block it closes, record the line's own amount and mention the sub-total in `notes` (don't add a row for it).
- Never compute, round or "correct" a number. If a cell is genuinely unreadable, write `null` and say so in `notes`.
- Be careful with digits that look alike (3/8, 1/7, 5/6, 0/8) and with the number of digits: zoom into the image again if unsure.

## Checks before you save

- If the first image does not begin with the statement's title, or the last statement page ends mid-table and the `-next` page doesn't continue it, say so in `notes` (the statement may start or end on a page you were not given).
- Re-read every total line and make sure the digits you typed are the ones printed (do not "fix" them so totals add up).
- The JSON must be valid (no comments, no trailing commas).
