# tests/gold: file formats

Written by session C (`gold.py`). Session B's review screen reads the `disagreements_*` files
and writes the `resolutions_*` files. Every amount is in the statement's **printed unit**
(`unit`: crore / lakh / million / thousand / null = rupees), exactly as in that one annual report.

## Statement ids

`<TICKER>_<FY>_<kind>`, e.g. `SBIN_2026_pl`. kind: `pl` Profit & Loss, `bs` Balance Sheet, `cf` Cash Flow.
Scope is always consolidated. FY = the report's financial year (year ending March FY).

## `disagreements_<id>.json` (written by `gold.py compare`, read by the review screen)

```json
{
  "format": "docfetcher-gold-disagreements/1",
  "ticker": "SBIN", "fy": 2026, "scope": "consolidated", "statement": "pl", "statement_name": "Profit & Loss",
  "pdf": "SBIN/AnnualReports/Annual Report 2026.pdf",      // relative to $DOCFETCHER_CACHE (~/DocFetcherData)
  "pdf_url": "https://www.bseindia.com/...pdf",              // to download it if the cache is empty
  "pages": [{"page": 313, "name": "314", "clip": [0, 0, 595.3, 841.9]}],   // 0-based page index; clip = PDF points
  "unit": "thousand", "years": [2026, 2025], "reader": "claude",
  "stats": {"rows_parser": 31, "rows_reader": 28, "rows_agreed": 26, "...": "..."},
  "disagreements": [
    {
      "id": "d001",
      "kind": "value",                 // value | label | missing_in_parser | extra_in_parser | unit (whole statement: value_parser/value_reader hold the units)
      "pattern": "value_scale",        // see PATTERNS in gold.py; lets the screen group similar items
      "pattern_text": "Value off by a power of 10 (unit / digits)",
      "year": 2026,                    // value disagreements only, else null
      "label_parser": "Basic (in `)",  "label_reader": "Basic (in ₹)",     // null when that side has no row
      "value_parser": 0.0091, "value_reader": 91.16,                      // value disagreements only
      "values_parser": {"2026": 0.0091, "2025": 0.0087},                  // the whole row, both sides
      "values_reader": {"2026": 91.16, "2025": 86.91},
      "parser_index": 27, "reader_index": 25,   // row positions; keep them, finalize matches on them
      "page": 313,                              // 0-based page to show (the reader's page for that row)
      "search": ["91.16"]                       // strings to highlight; amounts in Indian grouping.
                                                // Match on digits only: SBI prints 514932,59,04.
    }
  ],
  "rows": [ "... every aligned row (parser and reader side by side), for context ..." ]
}
```

`label_reader` can be `""`: a sub-total printed with no label (the parser calls these "Subtotal").

## `resolutions_<id>.json` (written by the review screen)

```json
{
  "format": "docfetcher-gold-resolutions/1",
  "ticker": "SBIN", "fy": 2026, "statement": "pl",
  "resolved_by": "Harsh", "resolved_at": "2026-11-06 10:00",
  "answers": {
    "d001": {"choice": "reader"},
    "d002": {"choice": "parser"},
    "d003": {"choice": "neither", "value": 1234.5},
    "d004": {"choice": "neither", "label": "Basic (₹)"},
    "d005": {"choice": "neither", "label": "Interest earned", "values": {"2026": 1, "2025": 2}}
  }
}
```

- `choice`: `parser` (the parser is right), `reader` (the second reader is right), or `neither`.
  With `neither`, give the correct `value` (value disagreements), `label` (label disagreements),
  or `label` + `values` (a row missing from the parser that should be there with other figures).
- For `extra_in_parser`: `parser` = the row really is in the statement; `reader` = drop it.
- For `missing_in_parser`: `reader` = the row is in the statement (as read); `parser` = it isn't.
- A "resolve the whole pattern at once" button is fine: write one answer per id.

Then `python gold.py finalize <TICKER> <FY>` writes `gold_<id>.json` once every disagreement has an answer.

## `gold_<id>.json` and `silver/<id>.json` (reference copies)

```json
{"format": "docfetcher-gold-copy/1", "level": "gold" | "silver",
 "ticker": "SBIN", "fy": 2026, "scope": "consolidated", "statement": "pl",
 "unit": "thousand", "years": [2026, 2025], "pages": [...], "pdf": "...", "pdf_url": "...",
 "rows": [{"label": "Interest earned", "values": [5149325904, 4903126989],
           "source": "agreed" | "reader" | "harsh"}]}
```

Silver copies also carry `stats` and `mismatches` (same records as `disagreements`).

## Other folders

- `reading/<id>.json`: the second reader's independent reading (format in `READER.md`).
- `parser/<id>.json`: the parser's output at the time of the comparison (same row shape: label + values).
- Page images are rendered to `$DOCFETCHER_CACHE/gold_pages/<id>/` and are not committed.

## The regression check

`gold.gold_check(level="all"|"gold"|"silver", tickers=None)` re-runs the parser on each reference
statement's report and returns `{"failures": [...], "warnings": [...], "totals": {...}, "per_statement": {...}}`.
A difference from a GOLD copy is a failure; from a SILVER copy, a warning. Command line: `python gold.py check`.
