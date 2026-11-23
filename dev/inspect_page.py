"""
inspect_page.py
A small diagnostic tool - run this and send Claude the output.
It saves the raw HTML structure around the Concalls and Annual Reports
sections so we can see exactly what tags/classes screener.in is using,
instead of guessing.
"""
import os as _os, sys as _sys  # FinXL engine path
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', "engine"))
import sys
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

ticker = sys.argv[1].upper() if len(sys.argv) > 1 else "INFY"
url = f"https://www.screener.in/company/{ticker}/consolidated/"
resp = requests.get(url, headers=HEADERS, timeout=15)
soup = BeautifulSoup(resp.text, "html.parser")

with open("page_structure_debug.txt", "w", encoding="utf-8") as f:
    # Find the Documents section and dump its raw HTML
    header = soup.find(lambda tag: tag.name in ("h3", "h2") and "Concall" in tag.get_text())
    if header:
        f.write("=== FOUND 'Concall' HEADER, TAG: " + header.name + " ===\n")
        f.write(str(header) + "\n\n")
        container = header.find_next(["ul", "div"])
        f.write("=== NEXT CONTAINER TAG: " + (container.name if container else "NONE") + " ===\n")
        if container:
            # only first 3000 chars so file isn't huge
            f.write(str(container)[:4000] + "\n")
    else:
        f.write("Could not find a 'Concall' header at all.\n")
        # dump a bit of the whole page so we can see structure
        f.write("\n\n=== FIRST 3000 CHARS OF WHOLE PAGE ===\n")
        f.write(resp.text[:3000])

print("Saved to page_structure_debug.txt - open it and send Claude the contents.")
