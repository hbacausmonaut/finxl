import type { RowDef, StatementKind } from "./types"

/**
 * Line-item layout of each statement, in report order: a caption, its items,
 * then the printed total. The engine returns rows "as printed" with an indent
 * level; this is the same shape with stable ids for the demo data.
 */

const h = (id: string, label: string, level: 0 | 1 = 1): RowDef => ({ id, label, kind: "header", level })
const i = (id: string, label: string, section: string, extra: Partial<RowDef> = {}): RowDef => ({
  id, label, kind: "item", level: 2, section, ...extra,
})
const t = (id: string, label: string, section: string, strong = false): RowDef => ({
  id, label, kind: "total", level: 1, section, strong,
})
const c = (id: string, label: string, formula: RowDef["formula"]): RowDef => ({
  id, label, kind: "calc", level: 0, formula, strong: true,
})

const PL: RowDef[] = [
  h("h_inc", "Income"),
  i("rev", "Revenue from operations", "h_inc"),
  i("oi", "Other income", "h_inc"),
  t("ti", "Total income", "h_inc"),
  h("h_exp", "Expenses"),
  i("mat", "Cost of materials consumed", "h_exp"),
  i("chinv", "Changes in inventories of finished goods and work-in-progress", "h_exp"),
  i("emp", "Employee benefits expense", "h_exp"),
  i("fin", "Finance costs", "h_exp"),
  i("dep", "Depreciation and amortisation expense", "h_exp"),
  i("oth", "Other expenses", "h_exp"),
  t("texp", "Total expenses", "h_exp"),
  c("pbt", "Profit before tax", [["ti", 1], ["texp", -1]]),
  h("h_tax", "Tax expense"),
  i("ctax", "Current tax", "h_tax"),
  i("dtax", "Deferred tax", "h_tax"),
  t("tax", "Total tax expense", "h_tax"),
  c("pat", "Profit for the year", [["pbt", 1], ["tax", -1]]),
  h("h_eps", "Earnings per equity share"),
  i("eps", "Basic and diluted (₹)", "h_eps", { perShare: true }),
]

const BS: RowDef[] = [
  h("h_assets", "Assets", 0),
  h("h_nca", "Non-current assets"),
  i("ppe", "Property, plant and equipment", "h_nca"),
  i("cwip", "Capital work-in-progress", "h_nca"),
  i("intang", "Intangible assets", "h_nca"),
  i("ncinv", "Investments", "h_nca"),
  i("onca", "Other non-current assets", "h_nca"),
  t("nca", "Total non-current assets", "h_nca"),
  h("h_ca", "Current assets"),
  i("inv", "Inventories", "h_ca"),
  i("rec", "Trade receivables", "h_ca"),
  i("cash", "Cash and cash equivalents", "h_ca"),
  i("ob", "Bank balances other than cash and cash equivalents", "h_ca"),
  i("oca", "Other current assets", "h_ca"),
  t("ca", "Total current assets", "h_ca"),
  c("ta", "Total assets", [["nca", 1], ["ca", 1]]),
  h("h_el", "Equity and liabilities", 0),
  h("h_eq", "Equity"),
  i("sc", "Equity share capital", "h_eq"),
  i("oe", "Other equity", "h_eq"),
  t("eq", "Total equity", "h_eq"),
  h("h_ncl", "Non-current liabilities"),
  i("ltb", "Borrowings", "h_ncl"),
  i("dtl", "Deferred tax liabilities (net)", "h_ncl"),
  i("oncl", "Other non-current liabilities", "h_ncl"),
  t("ncl", "Total non-current liabilities", "h_ncl"),
  h("h_cl", "Current liabilities"),
  i("stb", "Borrowings", "h_cl"),
  i("tp", "Trade payables", "h_cl"),
  i("ocl", "Other current liabilities", "h_cl"),
  i("prov", "Provisions", "h_cl"),
  t("cl", "Total current liabilities", "h_cl"),
  c("tel", "Total equity and liabilities", [["eq", 1], ["ncl", 1], ["cl", 1]]),
]

const CF: RowDef[] = [
  h("h_cfo", "Cash flows from operating activities"),
  i("c_pbt", "Profit before tax", "h_cfo"),
  i("c_dep", "Depreciation and amortisation expense", "h_cfo"),
  i("c_fin", "Finance costs", "h_cfo"),
  i("c_oi", "Interest and other income", "h_cfo"),
  i("c_inv", "(Increase)/decrease in inventories", "h_cfo"),
  i("c_rec", "(Increase)/decrease in trade receivables", "h_cfo"),
  i("c_oa", "(Increase)/decrease in other assets", "h_cfo"),
  i("c_tp", "Increase/(decrease) in trade payables", "h_cfo"),
  i("c_ol", "Increase/(decrease) in other liabilities and provisions", "h_cfo"),
  i("c_tax", "Income taxes paid (net)", "h_cfo"),
  t("cfo", "Net cash from operating activities", "h_cfo", true),
  h("h_cfi", "Cash flows from investing activities"),
  i("c_capex", "Purchase of property, plant and equipment", "h_cfi"),
  i("c_oir", "Interest and other income received", "h_cfi"),
  i("c_invest", "(Purchase)/sale of investments (net)", "h_cfi"),
  i("c_ob", "Movement in other bank balances", "h_cfi"),
  t("cfi", "Net cash used in investing activities", "h_cfi", true),
  h("h_cff", "Cash flows from financing activities"),
  i("c_ltb", "Proceeds from/(repayment of) long-term borrowings", "h_cff"),
  i("c_stb", "Short-term borrowings (net)", "h_cff"),
  i("c_finp", "Finance costs paid", "h_cff"),
  i("c_div", "Dividends paid", "h_cff"),
  t("cff", "Net cash from/(used in) financing activities", "h_cff", true),
  c("c_net", "Net increase/(decrease) in cash and cash equivalents", [["cfo", 1], ["cfi", 1], ["cff", 1]]),
  { id: "c_open", label: "Cash and cash equivalents at the beginning of the year", kind: "item", level: 0 },
  c("c_close", "Cash and cash equivalents at the end of the year", [["c_net", 1], ["c_open", 1]]),
]

export const SHEETS: Record<StatementKind, { title: string; short: string; rows: RowDef[] }> = {
  pl: { title: "Profit & Loss", short: "P&L", rows: PL },
  bs: { title: "Balance Sheet", short: "Balance Sheet", rows: BS },
  cf: { title: "Cash Flow", short: "Cash Flow", rows: CF },
}

export const KINDS: StatementKind[] = ["pl", "bs", "cf"]

export const rowDef = (sheet: StatementKind, id: string) => SHEETS[sheet].rows.find((r) => r.id === id)

/** Rows a printed total or calculated line is built from, with signs. */
export function componentsOf(sheet: StatementKind, row: RowDef): Array<[string, 1 | -1]> {
  if (row.kind === "calc") return row.formula ?? []
  if (row.kind === "total")
    return SHEETS[sheet].rows.filter((r) => r.kind === "item" && r.section === row.section).map((r) => [r.id, 1])
  return []
}

/** The total or calculated line a row feeds into, if any. */
export function parentOf(sheet: StatementKind, id: string): RowDef | undefined {
  const rows = SHEETS[sheet].rows
  const self = rows.find((r) => r.id === id)
  if (!self) return undefined
  if (self.kind === "item" && self.section) {
    const total = rows.find((r) => r.kind === "total" && r.section === self.section)
    if (total) return total
  }
  return rows.find((r) => r.kind === "calc" && r.formula?.some(([x]) => x === id))
}
