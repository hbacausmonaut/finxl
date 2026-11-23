/**
 * Deterministic generator for the demo company's statements.
 *
 * Everything is integer ₹ lakh. The balance sheet balances by construction
 * (short-term borrowings / cash are the plug) and every cash-flow line is
 * derived from balance-sheet movements, so closing cash always equals BS cash.
 * Deliberate extraction errors are applied afterwards in `workbook.ts`.
 */
import type { FiscalYear, Scope } from "../types"

export const FIRST_FY = 2006
export const LAST_FY = 2026

/** Small deterministic PRNG keyed by a string. */
export function rand(key: string) {
  let h = 2166136261
  for (let i = 0; i < key.length; i++) {
    h ^= key.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  h ^= h >>> 13
  h = Math.imul(h, 0x5bd1e995)
  h ^= h >>> 15
  return (h >>> 0) / 4294967296
}

const r = Math.round

/** Revenue growth by fiscal year (FY06 … FY25). FY21 = Covid dip, FY22 = rebound. */
const GROWTH: Record<number, number> = {
  2006: 0.14, 2007: 0.17, 2008: 0.19, 2009: 0.03, 2010: 0.13, 2011: 0.21, 2012: 0.15,
  2013: 0.08, 2014: 0.11, 2015: 0.07, 2016: 0.05, 2017: 0.12, 2018: 0.16, 2019: 0.18,
  2020: 0.03, 2021: -0.06, 2022: 0.32, 2023: 0.17, 2024: 0.02, 2025: 0.09, 2026: 0.12,
}

/** Capex intensity (% of revenue) — an expansion cycle in FY18–FY20 and FY23. */
const CAPEX: Record<number, number> = {
  2009: 0.13, 2012: 0.12, 2018: 0.16, 2019: 0.19, 2020: 0.14, 2023: 0.15, 2024: 0.12,
}

export interface YearTruth {
  fy: FiscalYear
  // P&L
  rev: number; oi: number; mat: number; chinv: number; emp: number; fin: number
  dep: number; oth: number; pbt: number; ctax: number; dtax: number; pat: number; eps: number
  // BS
  ppe: number; cwip: number; intang: number; ncinv: number; onca: number
  inv: number; rec: number; cash: number; ob: number; oca: number
  sc: number; oe: number; ltb: number; dtl: number; oncl: number
  stb: number; tp: number; ocl: number; prov: number
  // CF
  c_pbt: number; c_dep: number; c_fin: number; c_oi: number; c_inv: number; c_rec: number
  c_oa: number; c_tp: number; c_ol: number; c_tax: number
  c_capex: number; c_oir: number; c_invest: number; c_ob: number
  c_ltb: number; c_stb: number; c_finp: number; c_div: number; c_open: number
  // notes
  n_rm: number; n_wip: number; n_fg: number; n_st: number
  n_lt_sec: number; n_lt_uns: number; n_st_wc: number; n_st_pc: number
  n_gross: number; n_accd: number; n_add: number
  n_ctax: number; n_cgst: number; n_cbg: number
  /** export incentives later reclassified into revenue (for the FY20 restatement) */
  reclass: number
}

const cache = new Map<Scope, Map<FiscalYear, YearTruth>>()

export function generateTruth(basis: Scope): Map<FiscalYear, YearTruth> {
  const hit = cache.get(basis)
  if (hit) return hit

  // FY16 revenue anchors the series: ₹1,452 cr standalone; consolidated ~9% larger.
  const anchor = basis === "standalone" ? 145_200 : 158_400
  const revenue = new Map<number, number>()
  revenue.set(2016, anchor)
  for (let y = 2017; y <= LAST_FY; y++) revenue.set(y, r(revenue.get(y - 1)! * (1 + GROWTH[y])))
  for (let y = 2015; y >= FIRST_FY - 1; y--) revenue.set(y, r(revenue.get(y + 1)! / (1 + GROWTH[y + 1])))

  const k = basis === "standalone" ? 0 : 1
  const SHARES_LAKH = 1120 // 11.2 crore shares of ₹2 → EPS(₹) = PAT(lakh) / 1120

  // ── FY05 opening balance sheet ──
  const R0 = revenue.get(FIRST_FY - 1)!
  let prev = {
    ppe: r(0.55 * R0), cwip: r(0.02 * R0), intang: r(0.015 * R0), ncinv: r(0.03 * R0),
    onca: r(0.02 * R0), inv: r((72 / 365) * R0), rec: r((62 / 365) * R0), cash: r(0.025 * R0),
    ob: r(0.008 * R0), oca: r(0.04 * R0), sc: 2240, oe: 0, ltb: r(0.18 * R0), dtl: r(0.02 * R0),
    oncl: r(0.012 * R0), stb: r(0.08 * R0), tp: r(0.56 * (75 / 365) * R0), ocl: r(0.05 * R0),
    prov: r(0.01 * R0), pat: r(0.09 * R0), accd: r(0.45 * 0.565 * R0),
  }
  const assets0 = prev.ppe + prev.cwip + prev.intang + prev.ncinv + prev.onca + prev.inv + prev.rec + prev.cash + prev.ob + prev.oca
  prev.oe = assets0 - (prev.sc + prev.ltb + prev.dtl + prev.oncl + prev.stb + prev.tp + prev.ocl + prev.prov)

  const out = new Map<FiscalYear, YearTruth>()

  for (let fy = FIRST_FY; fy <= LAST_FY; fy++) {
    const rev = revenue.get(fy)!
    const t = fy - 2000
    const matPct = 0.555 + 0.025 * Math.sin(t * 1.3) + (fy === 2022 ? 0.03 : 0) + k * 0.01
    const empPct = 0.071 + 0.004 * Math.cos(t * 0.9)
    const othPct = 0.166 + 0.008 * Math.sin(t * 0.7)
    const taxRate = fy >= 2020 ? 0.252 : 0.31

    // working capital & other balances
    const inv = r(((53 + 5 * Math.sin(t * 0.8)) / 365) * rev)
    const rec = r(((61 + 7 * Math.cos(t * 0.6)) / 365) * rev)
    const tp = r(matPct * ((74 + 5 * Math.sin(t)) / 365) * rev)
    const oca = r(0.041 * rev)
    const onca = r(0.021 * rev)
    const ocl = r(0.052 * rev)
    const prov = r(0.011 * rev)
    const oncl = r(0.012 * rev)
    let ncinv = prev.ncinv + r(0.004 * rev)
    const ob = r(0.008 * rev)

    // fixed assets
    const capex = r((CAPEX[fy] ?? 0.092) * rev)
    const dep = r(0.074 * (prev.ppe + prev.intang))
    const cwip = r(0.26 * capex)
    const intang = r(0.015 * rev)
    const ppe = prev.ppe + capex - dep - (cwip - prev.cwip) - (intang - prev.intang)

    // borrowings (long-term follow capex), finance costs on opening debt
    const ltb = Math.max(0, r(prev.ltb * 0.82 + 0.42 * capex))
    const fin = r(0.092 * (prev.ltb + prev.stb) + 0.0025 * rev)
    const oi = r(0.009 * rev + 0.05 * (prev.ncinv + prev.ob))

    // P&L
    const chinv = -r(0.5 * (inv - prev.inv))
    const mat = r(matPct * rev) - chinv
    const emp = r(empPct * rev)
    const oth = r(othPct * rev)
    const pbt = rev + oi - (mat + chinv + emp + fin + dep + oth)
    const tax = r(taxRate * pbt)
    const dtax = r(0.08 * tax)
    const ctax = tax - dtax
    const pat = pbt - tax
    const eps = Math.round((pat / SHARES_LAKH) * 100) / 100

    // equity
    const div = r(0.3 * prev.pat)
    const sc = 2240
    const oe = prev.oe + pat - div
    const dtl = prev.dtl + dtax

    // funding plug: short-term borrowings if short, otherwise surplus cash
    // (working-capital lines are always drawn, plus surplus parked in treasury investments)
    const fundingExStb = sc + oe + ltb + dtl + oncl + tp + ocl + prov
    const targetCash = r(0.022 * rev)
    const wcLine = r(0.045 * rev)
    let gap = ppe + cwip + intang + ncinv + onca + inv + rec + ob + oca + targetCash - fundingExStb
    if (gap < -wcLine) {
      // surplus beyond keeping the WC line: 70% to investments, rest stays as cash
      const surplus = -gap - wcLine
      ncinv += r(0.7 * surplus)
      gap = ppe + cwip + intang + ncinv + onca + inv + rec + ob + oca + targetCash - fundingExStb
    }
    const stb = Math.max(gap, wcLine)
    const cash = stb - gap + targetCash

    // cash flow derived from BS movements
    const c_inv = -(inv - prev.inv)
    const c_rec = -(rec - prev.rec)
    const c_oa = -(oca - prev.oca + (onca - prev.onca))
    const c_tp = tp - prev.tp
    const c_ol = ocl - prev.ocl + (prov - prev.prov) + (oncl - prev.oncl)
    const c_tax = -ctax
    const c_capex = -capex
    const c_invest = -(ncinv - prev.ncinv)
    const c_ob = -(ob - prev.ob)
    const c_ltb = ltb - prev.ltb
    const c_stb = stb - prev.stb

    const cfo = pbt + dep + fin - oi + c_inv + c_rec + c_oa + c_tp + c_ol + c_tax
    const cfi = c_capex + oi + c_invest + c_ob
    const cff = c_ltb + c_stb - fin - div
    if (prev.cash + cfo + cfi + cff !== cash && process.env.NODE_ENV !== "production") {
      console.error(`[mock] cash flow does not reconcile in FY${fy}`)
    }

    // notes
    const accd = prev.accd + dep
    const gross = ppe + intang + accd
    const prevGross = prev.ppe + prev.intang + prev.accd
    const n_rm = r(0.43 * inv)
    const n_wip = r(0.18 * inv)
    const n_fg = r(0.31 * inv)
    const n_lt_sec = r(0.86 * ltb)
    const n_st_wc = r(0.68 * stb)

    out.set(fy, {
      fy, rev, oi, mat, chinv, emp, fin, dep, oth, pbt, ctax, dtax, pat, eps,
      ppe, cwip, intang, ncinv, onca, inv, rec, cash, ob, oca,
      sc, oe, ltb, dtl, oncl, stb, tp, ocl, prov,
      c_pbt: pbt, c_dep: dep, c_fin: fin, c_oi: -oi, c_inv, c_rec, c_oa, c_tp, c_ol, c_tax,
      c_capex, c_oir: oi, c_invest, c_ob, c_ltb, c_stb, c_finp: -fin, c_div: -div, c_open: prev.cash,
      n_rm, n_wip, n_fg, n_st: inv - n_rm - n_wip - n_fg,
      n_lt_sec, n_lt_uns: ltb - n_lt_sec, n_st_wc, n_st_pc: stb - n_st_wc,
      n_gross: gross, n_accd: accd, n_add: gross - prevGross,
      n_ctax: r(rev * (0.006 + 0.004 * rand(`ct${fy}${basis}`))),
      n_cgst: r(rev * (0.003 + 0.003 * rand(`cg${fy}${basis}`))),
      n_cbg: r(rev * (0.01 + 0.006 * rand(`bg${fy}${basis}`))),
      reclass: r(0.012 * rev),
    })

    prev = { ppe, cwip, intang, ncinv, onca, inv, rec, cash, ob, oca, sc, oe, ltb, dtl, oncl, stb, tp, ocl, prov, pat, accd }
  }

  cache.set(basis, out)
  return out
}
