"""
Second reading on real pages: take a statement that reads correctly, corrupt one
figure the way a misread would (a wrong digit), and check that the page re-read
proposes the printed figure, and nothing else.

Needs the PIDILITIND FY2021 annual report in the PDF cache (downloaded on first run).
Run: .venv/Scripts/python -m pytest dev/tests/test_second_reading.py -q
"""

import copy
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "engine"))

import fitz  # noqa: E402
import pytest  # noqa: E402

import finxl  # noqa: E402
import pdfview  # noqa: E402
import second_reading  # noqa: E402

TICKER, FY = "PIDILITIND", 2021


@pytest.fixture(scope="module")
def statement():
    out = finxl.run(TICKER, FY, FY, "consolidated", out_dir=tempfile.mkdtemp(), log=lambda m: None)
    _, merged, sources, years, _ = out
    rows = merged[("consolidated", "pl")]
    src = next(s for s in sources if s["fy"] == FY and s["scope"] == "consolidated" and s["statement"] == "Profit & Loss")
    doc = fitz.open(pdfview.pdf_path(None, TICKER, FY))
    yield rows, pdfview.parse_pages(src["pages"].split(",")), doc
    doc.close()


def _total_with_members(rows, year, min_members=3):
    for i, r in enumerate(rows):
        g = r.get("group", {}).get(year)
        if g and g["ok"] and len(g["members"]) >= min_members and r["status"].get(year) == "ok":
            return i, g
    raise AssertionError("no confirmed total with enough members")


def test_finds_a_misread_item(statement):
    rows, pages, doc = statement
    ti, g = _total_with_members(rows, FY)
    target = next(r for r, _ in g["members"] if abs(rows[r]["values"][FY]) > 10)
    right = rows[target]["values"][FY]
    bad = copy.deepcopy(rows)
    bad[target]["values"][FY] = round(right + 0.30, 2)  # e.g. 1,254.56 read as 1,254.86
    found = second_reading.for_statement(doc, pages, bad, FY, ti, g)
    assert len(found) == 1, found
    assert found[0]["row"] == target
    assert abs(found[0]["value"] - right) <= 0.011
    assert found[0]["printed"]  # the proposal is a number printed on the page


def test_nothing_when_total_ties(statement):
    rows, pages, doc = statement
    ti, g = _total_with_members(rows, FY)
    assert second_reading.for_statement(doc, pages, rows, FY, ti, g) == []
