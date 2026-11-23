import type { Company, FiscalYear, ReportRef } from "../types"
import { LAST_FY, rand } from "./generate"

/**
 * Demo company. Fictional on purpose: the statements behind it are generated
 * mock data, so they are never attached to a real listed name.
 */
export const DEMO_COMPANY: Company = {
  symbol: "VARDHANSPL",
  name: "Vardhan Specialty Chemicals Ltd",
  sector: "Specialty Chemicals",
  cap: "Mid cap",
  isDemo: true,
}

/** Real NSE-listed names for search. First report year is indicative. */
const LISTED: Array<[symbol: string, name: string, sector: string, cap: Company["cap"], from: FiscalYear]> = [
  ["AARTIIND", "Aarti Industries Ltd", "Specialty Chemicals", "Mid cap", 2012],
  ["DEEPAKNTR", "Deepak Nitrite Ltd", "Specialty Chemicals", "Mid cap", 2012],
  ["NAVINFLUOR", "Navin Fluorine International Ltd", "Specialty Chemicals", "Mid cap", 2012],
  ["VINATIORGA", "Vinati Organics Ltd", "Specialty Chemicals", "Mid cap", 2012],
  ["PIDILITIND", "Pidilite Industries Ltd", "Chemicals", "Large cap", 2011],
  ["SRF", "SRF Ltd", "Chemicals", "Large cap", 2011],
  ["ASIANPAINT", "Asian Paints Ltd", "Paints", "Large cap", 2011],
  ["ASTRAL", "Astral Ltd", "Building Products", "Mid cap", 2012],
  ["SUPREMEIND", "Supreme Industries Ltd", "Plastics", "Mid cap", 2012],
  ["POLYCAB", "Polycab India Ltd", "Cables & Wires", "Large cap", 2019],
  ["DIXON", "Dixon Technologies (India) Ltd", "Electronics Manufacturing", "Mid cap", 2018],
  ["BALKRISIND", "Balkrishna Industries Ltd", "Tyres", "Mid cap", 2012],
  ["TATAELXSI", "Tata Elxsi Ltd", "IT Services", "Mid cap", 2012],
  ["PERSISTENT", "Persistent Systems Ltd", "IT Services", "Mid cap", 2012],
  ["HCLTECH", "HCL Technologies Ltd", "IT Services", "Large cap", 2011],
  ["TRENT", "Trent Ltd", "Retail", "Large cap", 2012],
  ["INFY", "Infosys Ltd", "IT Services", "Large cap", 2011],
  ["RELIANCE", "Reliance Industries Ltd", "Conglomerate", "Large cap", 2011],
  ["NTPC", "NTPC Ltd", "Power", "Large cap", 2011],
  ["VBL", "Varun Beverages Ltd", "Beverages", "Large cap", 2017],
]

const FIRST_REPORT: Record<string, FiscalYear> = Object.fromEntries(LISTED.map((l) => [l[0], l[4]]))
FIRST_REPORT[DEMO_COMPANY.symbol] = 2010

export const COMPANIES: Company[] = [
  DEMO_COMPANY,
  ...LISTED.map(([symbol, name, sector, cap]) => ({ symbol, name, sector, cap })),
]

export const findCompany = (symbol: string) => COMPANIES.find((c) => c.symbol === symbol)

/** The annual reports a company has on file (what finxl.list_reports returns). */
export function reportsFor(symbol: string): ReportRef[] {
  const first = FIRST_REPORT[symbol] ?? 2012
  const demo = symbol === DEMO_COMPANY.symbol
  const out: ReportRef[] = []
  for (let fy = LAST_FY; fy >= first; fy--) {
    const r = rand(`${symbol}-${fy}`)
    const pages = Math.round(170 + (fy - 2008) * 11 + r * 60)
    out.push({
      fy,
      url: `https://www.bseindia.com/bseplus/AnnualReport/${symbol}_${fy}.pdf`,
      pages,
      sizeMb: Math.round(pages * (0.028 + r * 0.02) * 10) / 10,
      // Older reports are often image scans with no text layer.
      scanned: !demo && fy <= 2013 && r > 0.45,
    })
  }
  return out
}
