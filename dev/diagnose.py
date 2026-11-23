"""
diagnose.py
-----------
Fetches the NSE iXBRL page and shows exactly what tags and structure
are present, so we can fix the main parser.

Run:
    python diagnose.py <URL>
"""

import os as _os, sys as _sys  # FinXL engine path
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', "engine"))
import sys
import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.nseindia.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

url = sys.argv[1] if len(sys.argv) > 1 else input("URL: ").strip()

print("Fetching...")
resp = requests.get(url, headers=HEADERS, timeout=30)
html = resp.text
print(f"Downloaded {len(html):,} chars\n")

# ── 1. Show first 2000 chars raw ──────────────────────────────────────────────
print("=" * 60)
print("RAW FIRST 1500 CHARS:")
print("=" * 60)
print(html[:1500])

# ── 2. Try ALL parsers ────────────────────────────────────────────────────────
for parser in ["lxml", "html.parser", "lxml-xml", "xml"]:
    try:
        soup = BeautifulSoup(html, parser)
        all_tags = [t.name for t in soup.find_all() if t.name]
        unique = sorted(set(all_tags))
        ix_tags = [t for t in unique if t and "ix" in t.lower()]
        xbrl_tags = [t for t in unique if t and ("xbrl" in t.lower() or ":" in str(t))]
        print(f"\n[Parser: {parser}]")
        print(f"  Total tags: {len(all_tags)}, Unique: {len(unique)}")
        print(f"  ix-related tags: {ix_tags[:20]}")
        print(f"  xbrl-related tags: {xbrl_tags[:20]}")
        print(f"  First 30 unique tags: {unique[:30]}")
    except Exception as e:
        print(f"\n[Parser: {parser}] FAILED: {e}")

# ── 3. Search raw HTML for ix: patterns ──────────────────────────────────────
print("\n" + "=" * 60)
print("SEARCHING RAW HTML FOR KEY PATTERNS:")
print("=" * 60)

patterns = {
    "ix:nonFraction":   r'ix:nonFraction',
    "ix:nonfraction":   r'ix:nonfraction',
    "<ix:":             r'<ix:',
    "nonFraction":      r'nonFraction',
    "contextRef":       r'contextRef',
    "unitRef":          r'unitRef',
    "xmlns:ix":         r'xmlns:ix',
    "RevenueFromOps":   r'RevenueFromOperations',
    "in-gaap":          r'in-gaap:',
    "ind-as":           r'ind.as',
}

for label, pattern in patterns.items():
    count = len(re.findall(pattern, html, re.IGNORECASE))
    if count > 0:
        # Show first occurrence with context
        m = re.search(pattern, html, re.IGNORECASE)
        start = max(0, m.start() - 30)
        snippet = html[start:m.start()+120].replace('\n', ' ')
        print(f"\n  ✓ '{label}' found {count} times")
        print(f"    First: ...{snippet}...")
    else:
        print(f"  ✗ '{label}' NOT FOUND")

# ── 4. Sample 500 chars from middle of file ───────────────────────────────────
mid = len(html) // 2
print("\n" + "=" * 60)
print("500 CHARS FROM MIDDLE OF FILE:")
print("=" * 60)
print(html[mid:mid+500])
