"""
Builds web/public/companies.json, the symbol list the company search uses, from
NSE's public list of equity securities (EQUITY_L.csv). Run it now and then to
pick up new listings:

    python dev/scripts/build_companies.py

Output: [[symbol, name], ...] sorted by symbol (equity series only).
"""

import csv
import io
import json
import os

import requests

URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "web", "public", "companies.json")


def main():
    r = requests.get(URL, timeout=30, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "text/csv,*/*"})
    r.raise_for_status()
    rows = csv.DictReader(io.StringIO(r.content.decode("utf-8-sig")))
    out = []
    for row in rows:
        row = {k.strip(): (v or "").strip() for k, v in row.items()}
        if row.get("SERIES") not in ("EQ", "BE", "BZ", "SM", "ST"):
            continue
        name = row["NAME OF COMPANY"].replace("Limited", "Ltd").replace("LIMITED", "LTD")
        out.append([row["SYMBOL"], name])
    out.sort()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(out)} companies -> {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
