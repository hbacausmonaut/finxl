"""
dump_tables.py
--------------
Fetches the NSE iXBRL page and prints the first 3 rows of every table
so we can identify which tables contain P&L, Balance Sheet, Cash Flow.

Run:
    python dump_tables.py <URL>
"""

import os as _os, sys as _sys  # FinXL engine path
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', "engine"))
import sys, requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.nseindia.com/",
}

url = sys.argv[1] if len(sys.argv) > 1 else input("URL: ").strip()
print(f"Fetching {url} ...")
html = requests.get(url, headers=HEADERS, timeout=30).text
print(f"Downloaded {len(html):,} chars\n")

soup = BeautifulSoup(html, "lxml")
tables = soup.find_all("table")
print(f"Total tables found: {len(tables)}\n")

for i, tbl in enumerate(tables):
    rows = tbl.find_all("tr")
    if not rows:
        continue

    # Get first 3 rows of each table
    preview = []
    for row in rows[:3]:
        cells = [td.get_text(strip=True)[:40] for td in row.find_all(["td","th"])]
        if any(cells):
            preview.append(cells)

    # Get total row count and whether it has numbers
    all_text = tbl.get_text()
    has_numbers = any(c.isdigit() for c in all_text)
    total_rows = len(rows)

    print(f"TABLE {i:03d} | rows={total_rows} | has_numbers={has_numbers}")
    for r in preview:
        print(f"  {r}")
    print()
