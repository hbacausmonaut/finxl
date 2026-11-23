> **Checked by Claude, not by Harsh.** Harsh asked Claude to do this audit on 2026-11-08. Each figure was compared with a picture of its row and column heading from the PDF.

# Sampling audit report

Generated 2026-11-08T00:19:16. Sample of 100 figures (seed 20261104), 100 answered. 95% ranges are Wilson intervals; 'can't tell' answers are left out of the accuracy.

**Overall accuracy (weighted by group size): 97.6%** (95% range 93.1% – 100.0%). Groups with no judged figures yet are left out of the weighting.

Plain sample accuracy: 95.0% (95 of 100 judged; 95% range 88.8% – 97.8%); can't tell: 0, unanswered: 0.

| Group | Figures in all Excels | Sampled | Correct | Wrong | Can't tell | Accuracy | 95% range |
|---|---:|---:|---:|---:|---:|---:|---|
| Confirmed by the report's totals | 174049 | 50 | 49 | 1 | 0 | 98.0% | 89.5% – 99.6% |
| Can't be checked (EPS, memo lines, ...) | 6572 | 30 | 26 | 4 | 0 | 86.7% | 70.3% – 94.7% |
| Flagged (total doesn't add up) | 932 | 20 | 20 | 0 | 0 | 100.0% | 83.9% – 100.0% |

## Errors by reason

| Reason | Count |
|---|---:|
| wrong number | 2 |
| garbled label | 2 |
| wrong unit | 1 |

## Every error

| # | Company | Statement | Year | Label | Our value (₹ cr) | Group | Report / pages | Reason | Note |
|---|---|---|---|---|---:|---|---|---|---|
| a025 | ONGC | standalone Balance Sheet | FY2019 | No. 31, 31, 31, LIABILITIES | 201.9 | unchecked | FY2020 p.223, 224 | wrong number | Checked by Claude from the PDF page, at Harsh's request. Junk row: the column heading '31, 2019' was read as a figure, not a real line item. |
| a026 | SHRIRAMFIN | standalone Cash Flow | FY2022 | Components of cash and cash equivalents March 31, 2026 March | 2022.0 | unchecked | FY2023 p.168, 169 | wrong number | Checked by Claude from the PDF page, at Harsh's request. Junk row: the year 2022 in a table heading was read as a figure. |
| a079 | DIXON | consolidated Profit & Loss | FY2025 | Subtotal | 32.0 | confirmed | FY2026 p.419 | wrong unit | Checked by Claude from the PDF page, at Harsh's request. Report prints 32 in Rs lakh, so 0.32 crore. The Excel shows 32. All DIXON FY2025-26 columns are unconverted. |
| a087 | MASTEK | consolidated Profit & Loss | FY2019 | Basic - I | 42.61 | unchecked | FY2020 p.239 | garbled label | Checked by Claude from the PDF page, at Harsh's request. Figure is right. Label 'Basic - I': the letter I is a rupee sign not mapped back. |
| a090 | IRCTC | consolidated Profit & Loss | FY2023 | (1) Basic (in ₹) (Face value H 2 Per Share) | 12.57 | unchecked | FY2024 p.316 | garbled label | Checked by Claude from the PDF page, at Harsh's request. Figure is right. Label says 'Face value H 2': H is a rupee sign not mapped back. |
