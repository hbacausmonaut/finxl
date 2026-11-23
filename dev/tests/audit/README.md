# Sampling audit (CHAT_HANDOFF item 4)

Files here:

| File | Written by | What |
|---|---|---|
| `sample.json` | `python audit.py sample` | The 100 sampled figures (fixed seed 20261104) plus how many figures each group has in all the Excels. Drawn once; re-drawing needs `--force`. |
| `progress.json` | the audit screen | Harsh's answers, saved after every click (`correct` / `wrong` + reason / `cant_tell`). |
| `report.md`, `report.json` | "Write report" button, or `python audit.py report` | Accuracy overall and per group with 95% ranges, errors by reason, and every error. |

## Steps (on the laptop, after session A's 100-company work is merged)

1. Draw the sample. It re-runs the normal pipeline (no AI, same settings as `tests/regression.py`) on every
   company in `tests/companies.json`, because the group of each figure (confirmed / can't be checked /
   flagged) isn't stored in the Excel. PDFs are cached, so this takes about as long as the regression suite.

   ```
   python audit.py sample --workers 3
   ```

2. Open the app (`python -m streamlit run app.py`), pick **🔍 Sampling audit** in the sidebar.
   One figure at a time: company, statement, year, label and our value, next to the PDF page with the
   number boxed in red and its line in yellow. Click ✅ / ❌ (then a reason) / ?. Stop any time; it
   resumes at the next unchecked figure.
3. Click **📄 Write report** (or run `python audit.py report`).

## How the sample is drawn

- Groups (from `quality.py`): **confirmed** (part of a total that adds up in the report), **unchecked**
  (not part of any total: EPS, memo lines, ...) and **flagged** (a total that doesn't add up).
- Quotas: 50% confirmed, 30% unchecked, 20% flagged (flagged figures are rare, so they're over-sampled;
  a shortfall is filled from the other groups).
- Within a group, picks go round-robin over companies, and each pick prefers the statement type,
  scope (consolidated/standalone) and year used least so far. The final order is shuffled, and the
  screen doesn't show the group, so it can't bias the answer.
- Because of the quotas, the report gives the plain sample accuracy and an overall accuracy weighted by
  each group's real share of all figures. "Can't tell" answers are left out of the accuracy.
