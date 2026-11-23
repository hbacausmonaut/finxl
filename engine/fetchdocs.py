"""
fetchdocs.py
------------
A simple tool that:
1. Looks up a company on screener.in
2. Lists all the documents available (Annual Reports, Concalls, Credit Ratings)
3. Lets you pick what you want and what years
4. Downloads everything in one go, into organized folders

Usage:
    python fetchdocs.py RELIANCE
    (RELIANCE is the screener.in ticker/slug for the company)
"""

import sys
import os
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.screener.in/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SCRIPT_VERSION = "v3"

SCREENER_BASE = "https://www.screener.in/company/{}/consolidated/"
SCREENER_BASE_FALLBACK = "https://www.screener.in/company/{}/"


def fetch_screener_page(ticker):
    """Try to fetch the company's screener.in page (consolidated, then standalone fallback)."""
    for url_template in (SCREENER_BASE, SCREENER_BASE_FALLBACK):
        url = url_template.format(ticker.upper())
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200 and "Documents" in resp.text:
                return resp.text, url
        except requests.RequestException:
            continue
    return None, None


def parse_annual_reports(soup):
    """Find the Annual reports section and extract (year, url) pairs."""
    results = []
    header = soup.find(lambda tag: tag.name in ("h3", "h2") and "Annual report" in tag.get_text())
    if not header:
        return results
    # The list of links usually follows in a <ul> or set of <a> tags after the header
    container = header.find_next(["ul", "div"])
    if not container:
        return results
    for a in container.find_all("a", href=True):
        text = a.get_text(strip=True)
        text = re.sub(r"(\d{4})(from)", r"\1 \2", text)  # "2022from" -> "2022 from"
        match = re.search(r"(\d{4})", text)
        year = match.group(1) if match else "unknown"
        results.append({"year": year, "label": text, "url": a["href"]})
    return results


def parse_concalls(soup):
    """Find the Concalls section and extract date + transcript/ppt links."""
    results = []
    header = soup.find(lambda tag: tag.name in ("h3", "h2") and "Concall" in tag.get_text())
    if not header:
        return results
    container = header.find_next(["ul", "div"])
    if not container:
        return results

    # Concalls are usually list items, each with a date label and a few links
    items = container.find_all("li")
    seen_dates = {}  # tracks how many times we've seen each date, to disambiguate duplicates
    for li in items:
        date_text = li.get_text(strip=True)[:20]  # rough label, e.g. "Apr2026Transcript..."
        date_match = re.search(r"([A-Za-z]{3}\s?\d{4})", li.get_text())
        date_label = date_match.group(1) if date_match else date_text
        date_label = date_label.replace(" ", "_")

        # Some companies have two concalls in the same month -> disambiguate with a counter
        seen_dates[date_label] = seen_dates.get(date_label, 0) + 1
        suffix = f"_{seen_dates[date_label]}" if seen_dates[date_label] > 1 else ""

        for a in li.find_all("a", href=True):
            link_text = a.get_text(strip=True) or a.get("title", "") or "file"
            full_label = f"{date_label}{suffix}_{link_text}"
            results.append({"date": date_label, "label": full_label, "url": a["href"]})
    return results


def parse_credit_ratings(soup):
    results = []
    header = soup.find(lambda tag: tag.name in ("h3", "h2") and "Credit rating" in tag.get_text())
    if not header:
        return results
    container = header.find_next(["ul", "div"])
    if not container:
        return results
    for a in container.find_all("a", href=True):
        text = a.get_text(strip=True)
        results.append({"label": text, "url": a["href"]})
    return results


def filter_by_year_range(items, year_key, start, end):
    if not start and not end:
        return items
    filtered = []
    for item in items:
        y = item.get(year_key, "")
        digits = re.search(r"\d{4}", y)
        if not digits:
            filtered.append(item)  # keep if we can't tell the year, better safe than sorry
            continue
        y_int = int(digits.group())
        if start and y_int < start:
            continue
        if end and y_int > end:
            continue
        filtered.append(item)
    return filtered


def safe_filename(text, fallback="file"):
    text = re.sub(r"[^\w\-. ]", "_", text).strip()
    return text or fallback


def guess_extension(url, content_type, content_bytes=None):
    if url.lower().endswith(".pdf"):
        return ".pdf"
    if url.lower().endswith(".zip"):
        return ".zip"
    if url.lower().endswith((".html", ".htm")):
        return ".html"
    if "pdf" in content_type:
        return ".pdf"
    if "zip" in content_type:
        return ".zip"
    if "html" in content_type:
        return ".html"
    # Last resort: sniff the actual file bytes. PDFs always start with %PDF.
    if content_bytes:
        if content_bytes[:4] == b"%PDF":
            return ".pdf"
        if content_bytes[:2] == b"PK":  # zip files (and some docx) start with PK
            return ".zip"
        if content_bytes[:15].lower().lstrip().startswith(b"<!doctype html") or content_bytes[:5].lower() == b"<html":
            return ".html"
    return ".bin"


def download_one(item, folder, label_key):
    url = item["url"]
    if not url.startswith("http"):
        return f"SKIPPED (no direct link): {item.get(label_key, 'unknown')}"
    if "youtube.com" in url or "youtu.be" in url:
        # Don't download video pages as junk files - just record the link in a text file
        name = safe_filename(item.get(label_key, "recording")) + "_LINK.txt"
        path = os.path.join(folder, name)
        with open(path, "w") as f:
            f.write(url + "\n")
        return f"LINK SAVED (video, not downloaded): {path}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        ext = guess_extension(url, content_type, resp.content)
        name = safe_filename(item.get(label_key, "document")) + ext
        path = os.path.join(folder, name)
        with open(path, "wb") as f:
            f.write(resp.content)
        return f"OK: {path}"
    except requests.RequestException as e:
        return f"FAILED: {item.get(label_key, 'unknown')} ({e})"


def bulk_download(items, folder, label_key):
    os.makedirs(folder, exist_ok=True)
    results = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(download_one, item, folder, label_key) for item in items]
        for future in as_completed(futures):
            result = future.result()
            print("  " + result)
            results.append(result)
    return results


def ask(prompt):
    return input(prompt).strip()


def main():
    if len(sys.argv) < 2:
        print("Usage: python fetchdocs.py TICKER   (e.g. python fetchdocs.py RELIANCE)")
        sys.exit(1)

    ticker = sys.argv[1].upper()
    print(f"[fetchdocs.py {SCRIPT_VERSION}]")
    print(f"\nLooking up '{ticker}' on screener.in ...")
    html, used_url = fetch_screener_page(ticker)

    if not html:
        print(f"Could not find a screener.in page for '{ticker}'. "
              f"Double check the ticker (it should match the symbol used on screener.in, "
              f"e.g. RELIANCE, TCS, INFY).")
        sys.exit(1)

    print(f"Found page: {used_url}")
    soup = BeautifulSoup(html, "html.parser")

    annual_reports = parse_annual_reports(soup)
    concalls = parse_concalls(soup)
    credit_ratings = parse_credit_ratings(soup)

    print(f"\nFound:")
    print(f"  Annual reports : {len(annual_reports)}")
    print(f"  Concall files  : {len(concalls)}")
    print(f"  Credit ratings : {len(credit_ratings)}")

    if not (annual_reports or concalls or credit_ratings):
        print("\nNo documents found. The page structure may have changed, or this company has none listed.")
        sys.exit(0)

    print("\nWhat do you want to download?")
    print("  1. Annual reports")
    print("  2. Concalls (transcripts/PPTs)")
    print("  3. Credit ratings")
    print("  4. All of the above")
    choice = ask("Enter number(s), comma separated (e.g. 1,2): ")
    choices = set(c.strip() for c in choice.split(","))
    want_annual = "1" in choices or "4" in choices
    want_concalls = "2" in choices or "4" in choices
    want_ratings = "3" in choices or "4" in choices

    start_year, end_year = None, None
    if want_annual or want_concalls:
        year_range = ask("Year range (e.g. 2020-2026), or press Enter for all years: ")
        if year_range:
            parts = year_range.split("-")
            if len(parts) == 2:
                start_year = int(parts[0].strip())
                end_year = int(parts[1].strip())

    base_folder = os.path.join(os.getcwd(), ticker)
    os.makedirs(base_folder, exist_ok=True)

    if want_annual:
        filtered = filter_by_year_range(annual_reports, "year", start_year, end_year)
        print(f"\nDownloading {len(filtered)} annual report(s)...")
        bulk_download(filtered, os.path.join(base_folder, "AnnualReports"), "label")

    if want_concalls:
        filtered = filter_by_year_range(concalls, "date", start_year, end_year)
        print(f"\nDownloading {len(filtered)} concall file(s)...")
        bulk_download(filtered, os.path.join(base_folder, "Concalls"), "label")

    if want_ratings:
        print(f"\nDownloading {len(credit_ratings)} credit rating file(s)...")
        bulk_download(credit_ratings, os.path.join(base_folder, "CreditRatings"), "label")

    print(f"\nDone! Check the folder: {base_folder}")


if __name__ == "__main__":
    main()
