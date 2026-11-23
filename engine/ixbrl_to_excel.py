"""
ixbrl_to_excel.py  v3
---------------------
Fetches an NSE iXBRL filing viewer page and exports a clean Excel workbook.

The NSE viewer page is plain HTML with <table> elements — no raw XBRL tags.
This script reads those tables directly and maps them to formatted sheets.

Sheets produced:
  Company Info | P&L Statement | Balance Sheet | Cash Flow Statement

Usage:
    python ixbrl_to_excel.py <URL>

Example:
    python ixbrl_to_excel.py https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_152277_23042026125728_iXBRL_WEB.html
"""

import sys, re, os
import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

SCRIPT_VERSION = "v3"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer":    "https://www.nseindia.com/",
    "Accept":     "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── Colours ───────────────────────────────────────────────────────────────────
NAVY  = "1B3A6B"
TEAL  = "1F6B75"
LGREY = "F2F2F2"
DGREY = "D9D9D9"

def _fill(c): return PatternFill("solid", fgColor=c)
def _font(bold=False, color="000000", size=10):
    return Font(bold=bold, color=color, size=size, name="Calibri")
def _border():
    s = Side(border_style="thin", color="CCCCCC")
    return Border(left=s, right=s, top=s, bottom=s)

TOTAL_KW = ["total", "net profit", "net loss", "profit before",
            "net cash", "cash at end", "comprehensive income",
            "total assets", "total liabilities", "total equity"]

def is_total(label):
    return any(k in str(label).lower() for k in TOTAL_KW)


# ── Fetch ─────────────────────────────────────────────────────────────────────
def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


# ── Number cleaning ───────────────────────────────────────────────────────────
def to_num(s):
    """Convert '12,89,000.00' or '(90,000.00)' or '-' to float or None."""
    if not s:
        return None
    s = s.strip().replace(",", "").replace("\xa0", "").replace(" ", "")
    if s in ("-", "--", "NA", "N/A", ""):
        return None
    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        v = float(s)
        return -v if negative else v
    except ValueError:
        return None


# ── Table extraction ──────────────────────────────────────────────────────────
def extract_tables(html):
    """
    Parse all <table> elements from the page.
    Returns list of tables, each table = list of rows, each row = list of cell texts.
    """
    soup = BeautifulSoup(html, "lxml")
    tables = []
    for tbl in soup.find_all("table"):
        rows = []
        for tr in tbl.find_all("tr"):
            cells = [td.get_text(separator=" ", strip=True)
                     for td in tr.find_all(["td", "th"])]
            if any(c for c in cells):   # skip fully empty rows
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


def find_section_table(tables, *keywords):
    """
    Find the table whose first few rows contain ALL of the given keywords.
    Case-insensitive. Returns (table_index, rows) or (None, None).
    """
    kw_lower = [k.lower() for k in keywords]
    for i, tbl in enumerate(tables):
        # Search header rows (first 5)
        header_text = " ".join(
            " ".join(r) for r in tbl[:5]
        ).lower()
        if all(k in header_text for k in kw_lower):
            return i, tbl
    return None, None


def table_to_rows(tbl, label_col=0, val_cols=None):
    """
    Convert a raw table (list of lists) into structured (label, [values]) rows.
    Skips header rows and rows with no numeric content.
    val_cols: list of column indices to use as value columns. If None, auto-detect.
    """
    if not tbl:
        return [], []

    # Auto-detect value columns: last N columns that contain numbers
    if val_cols is None:
        # Scan data rows to find columns that have numbers
        num_col_hits = {}
        for row in tbl[2:]:  # skip first 2 header rows
            for ci, cell in enumerate(row):
                if ci == label_col:
                    continue
                if to_num(cell) is not None:
                    num_col_hits[ci] = num_col_hits.get(ci, 0) + 1
        # Keep columns with at least 2 numeric values
        val_cols = sorted(ci for ci, hits in num_col_hits.items() if hits >= 2)

    # Pull column headers from first 2 rows
    col_headers = []
    for ci in val_cols:
        h = ""
        for row in tbl[:3]:
            if ci < len(row) and row[ci].strip():
                h = row[ci].strip()
                break
        col_headers.append(h)

    structured = []
    for row in tbl:
        if len(row) <= label_col:
            continue
        label = row[label_col].strip()
        if not label:
            continue

        # Skip rows that are purely header-like (contain "particulars", "amount", etc.)
        label_lower = label.lower()
        if any(x in label_lower for x in ["particulars", "amount in", "sr.no", "s.no"]):
            continue

        # Strip leading numbers like "1 ", "1.1 ", "a " from labels
        label = re.sub(r"^\d+\.?\d*\s+", "", label).strip()
        label = re.sub(r"^[a-zA-Z]\.\s+", "", label).strip()

        vals = []
        for ci in val_cols:
            v = row[ci].strip() if ci < len(row) else ""
            vals.append(to_num(v))

        structured.append((label, vals))

    return structured, col_headers


# ── Company info ──────────────────────────────────────────────────────────────
def extract_company_info(html):
    """
    Extract company/filing metadata from the top info table on the page.
    Returns dict of {field: value}.
    """
    soup = BeautifulSoup(html, "lxml")
    info = {}

    # The info section is usually in the first few tables with 2 columns
    for tbl in soup.find_all("table")[:8]:
        rows = tbl.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True)
                val = cells[1].get_text(strip=True)
                if key and val and len(key) < 80:
                    info[key] = val

    # Also try regex on raw text for key fields in case table structure differs
    text = soup.get_text(separator="\n")
    fallbacks = {
        "NSE Symbol":  r"NSE Symbol\s*\n?\s*([A-Z0-9&]+)",
        "ISIN":        r"ISIN\s*\n?\s*(IN[A-Z0-9]+)",
        "Scrip Code":  r"Scrip Code\s*\n?\s*(\d{4,6})",
    }
    for key, pat in fallbacks.items():
        if key not in info:
            m = re.search(pat, text)
            if m:
                info[key] = m.group(1).strip()

    return info


# ── Excel helpers ─────────────────────────────────────────────────────────────
def hdr(ws, row, ncols, text):
    ws.merge_cells(start_row=row, start_column=1,
                   end_row=row,   end_column=max(ncols, 1))
    c = ws.cell(row=row, column=1, value=text)
    c.font      = _font(bold=True, color="FFFFFF", size=12)
    c.fill      = _fill(NAVY)
    c.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[row].height = 22

def col_hdr(ws, row, labels):
    for i, lbl in enumerate(labels, 1):
        c = ws.cell(row=row, column=i, value=lbl)
        c.font      = _font(bold=True, color="FFFFFF", size=10)
        c.fill      = _fill(TEAL)
        c.alignment = Alignment(horizontal="center" if i > 1 else "left",
                                vertical="center", wrap_text=True)
        c.border    = _border()
    ws.row_dimensions[row].height = 28

def data_row_ws(ws, row, label, vals, is_sec=False):
    lc = ws.cell(row=row, column=1, value=label)
    lc.border    = _border()
    lc.alignment = Alignment(vertical="center", indent=0 if is_sec else 1)

    if is_sec:
        lc.font = _font(bold=True, color=NAVY, size=10)
        lc.fill = _fill(LGREY)
    elif is_total(label):
        lc.font = _font(bold=True, color=NAVY)
        lc.fill = _fill(DGREY)
    else:
        lc.font = _font()

    for i, v in enumerate(vals, 2):
        c = ws.cell(row=row, column=i, value=v)
        c.border    = _border()
        c.alignment = Alignment(horizontal="right", vertical="center")
        if v is not None:
            c.number_format = '#,##0.00;(#,##0.00);"-"'
        if is_sec:
            c.fill = _fill(LGREY)
            c.font = _font(bold=True, color=NAVY)
        elif is_total(label):
            c.fill = _fill(DGREY)
            c.font = _font(bold=True, color=NAVY)

    ws.row_dimensions[row].height = 16

def set_cols(ws, widths):
    ws.freeze_panes = ws.cell(row=3, column=2)
    ws.sheet_view.showGridLines = False
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


# ── Sheet builders ────────────────────────────────────────────────────────────
def build_info_sheet(wb, info):
    ws = wb.create_sheet("Company Info")
    ws.sheet_view.showGridLines = False
    hdr(ws, 1, 2, "Company & Filing Information")
    ws.column_dimensions["A"].width = 45
    ws.column_dimensions["B"].width = 55
    for r, (k, v) in enumerate(info.items(), 2):
        kc = ws.cell(row=r, column=1, value=k)
        kc.font = _font(bold=True, color=NAVY)
        kc.fill = _fill(LGREY)
        kc.border = _border()
        vc = ws.cell(row=r, column=2, value=v)
        vc.font = _font()
        vc.border = _border()
        ws.row_dimensions[r].height = 18
    note = ws.cell(row=len(info)+3, column=1,
                   value="All financial values in INR Lakhs unless stated. Source: NSE iXBRL Filing.")
    note.font = Font(italic=True, size=9, color="888888", name="Calibri")


def build_financial_sheet(wb, sheet_name, title, rows, col_headers):
    ws = wb.create_sheet(sheet_name)
    ncols = 1 + len(col_headers)
    hdr(ws, 1, ncols, title)
    col_hdr(ws, 2, ["Particulars"] + col_headers)

    # Column widths: label col wide, value cols fixed
    ws.column_dimensions["A"].width = 52
    for i in range(1, len(col_headers) + 1):
        ws.column_dimensions[get_column_letter(i + 1)].width = 22

    r = 3
    for label, vals in rows:
        # Pad vals to match col_headers length
        while len(vals) < len(col_headers):
            vals.append(None)
        data_row_ws(ws, r, label, vals[:len(col_headers)])
        r += 1

    note = ws.cell(row=r+1, column=1,
                   value="Source: NSE iXBRL Filing | Amounts in INR Lakhs")
    note.font = Font(italic=True, size=9, color="888888", name="Calibri")
    ws.freeze_panes = ws.cell(row=3, column=2)
    ws.sheet_view.showGridLines = False


# ── Section keyword maps ──────────────────────────────────────────────────────
# Each section: (search_keywords, sheet_name, title_suffix)
SECTIONS = [
    (["Financial Results", "Revenue from operations"],
     "P&L Statement", "Profit & Loss Statement"),

    (["Asset", "Liabilities"],
     "Balance Sheet", "Balance Sheet"),

    (["Cash flow", "operating activities"],
     "Cash Flow", "Cash Flow Statement"),
]


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\n[ixbrl_to_excel.py {SCRIPT_VERSION}]")

    url = sys.argv[1].strip() if len(sys.argv) > 1 else input("Paste NSE iXBRL URL: ").strip()
    if not url.startswith("http"):
        print("Error: URL must start with http"); sys.exit(1)

    print("\nStep 1/4  Fetching filing from NSE...")
    html = fetch(url)
    print(f"  Downloaded {len(html):,} characters")

    print("Step 2/4  Parsing tables...")
    tables = extract_tables(html)
    print(f"  Found {len(tables)} tables in the page")

    print("Step 3/4  Extracting company info...")
    info = extract_company_info(html)
    company = (info.get("Name of company") or
               info.get("Name Of Company") or
               info.get("NameOfCompany") or "Company")
    symbol  = (info.get("NSE Symbol") or
               info.get("NseSymbol") or "UNKNOWN")
    period  = (info.get("Date of end of financial year") or
               info.get("DateOfEndOfFinancialYear") or "")
    print(f"  Company : {company}")
    print(f"  Symbol  : {symbol}")
    print(f"  Period  : {period}")

    print("Step 4/4  Building Excel workbook...")
    wb = Workbook()
    wb.remove(wb.active)
    build_info_sheet(wb, info)

    sheets_built = 0
    for keywords, sheet_name, title_suffix in SECTIONS:
        _, tbl = find_section_table(tables, *keywords)
        if tbl:
            rows, col_headers = table_to_rows(tbl)
            if rows:
                title = f"{title_suffix} — {company}"
                build_financial_sheet(wb, sheet_name, title, rows, col_headers)
                print(f"  ✓ {sheet_name}: {len(rows)} rows, {len(col_headers)} value column(s)")
                sheets_built += 1
            else:
                print(f"  ✗ {sheet_name}: table found but no data rows extracted")
        else:
            print(f"  ✗ {sheet_name}: section table not found")

    if sheets_built == 0:
        print("\n  No financial sheets built. Run diagnose.py to inspect table structure.")
        sys.exit(1)

    # Save
    safe   = re.sub(r"[^\w]", "_", symbol)
    per    = re.sub(r"[^\w]", "_", period) if period else "filing"
    fname  = f"{safe}_financials_{per}.xlsx"
    wb.save(fname)
    print(f"\n  Saved : {os.path.abspath(fname)}")
    print(f"  Sheets: {wb.sheetnames}")
    print("\nDone!")


if __name__ == "__main__":
    main()
