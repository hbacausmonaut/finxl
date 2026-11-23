"use client"

import * as React from "react"

import { fyLabel } from "@/lib/fy"
import { useWidth } from "@/lib/hooks"
import type { FiscalYear } from "@/lib/types"

export interface Series {
  name: string
  /** A CSS colour. Series take the chart palette in fixed order. */
  color: string
  values: Array<number | undefined>
}

const H = 190
const PAD = { top: 12, right: 8, bottom: 24, left: 44 }

function niceMax(v: number) {
  if (v <= 0) return 1
  const p = 10 ** Math.floor(Math.log10(v))
  const n = v / p
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p
}

function Frame({
  title,
  series,
  children,
}: {
  title: string
  series: Series[]
  children: React.ReactNode
}) {
  return (
    <figure className="rounded-xl border bg-surface p-4 shadow-card">
      <figcaption className="mb-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
        <span className="text-[13.5px] font-semibold">{title}</span>
        {series.length > 1 && (
          <span className="flex gap-3 text-[12.5px] text-ink-2">
            {series.map((s) => (
              <span key={s.name} className="flex items-center gap-1.5">
                <span aria-hidden className="size-2.5 rounded-[3px]" style={{ background: s.color }} />
                {s.name}
              </span>
            ))}
          </span>
        )}
      </figcaption>
      {children}
    </figure>
  )
}

function Tooltip({ x, width, year, series, i, format }: { x: number; width: number; year: FiscalYear; series: Series[]; i: number; format: (v: number) => string }) {
  const left = Math.min(Math.max(x, 70), width - 70)
  return (
    <div className="pointer-events-none absolute top-0 z-10 -translate-x-1/2 rounded-lg border border-line-2 bg-raised px-2.5 py-1.5 text-[12.5px] shadow-pop" style={{ left }}>
      <div className="num mb-0.5 font-semibold">{fyLabel(year)}</div>
      {series.map((s) => (
        <div key={s.name} className="flex items-center gap-1.5 whitespace-nowrap text-ink-2">
          <span aria-hidden className="size-2 rounded-[2px]" style={{ background: s.color }} />
          {s.name}
          <span className="num ml-2 font-medium text-ink">{s.values[i] === undefined ? "–" : format(s.values[i]!)}</span>
        </div>
      ))}
    </div>
  )
}

function Axis({ max, min, y, w, tick }: { max: number; min: number; y: (v: number) => number; w: number; tick: (v: number) => string }) {
  const ticks = [min, min + (max - min) / 2, max]
  return (
    <g>
      {ticks.map((t) => (
        <g key={t}>
          <line x1={PAD.left} x2={w - PAD.right} y1={y(t)} y2={y(t)} stroke={t === 0 ? "var(--line-2)" : "var(--line)"} />
          <text x={PAD.left - 8} y={y(t)} dy="0.32em" textAnchor="end" fontSize="11" fill="var(--ink-3)" className="num">
            {tick(t)}
          </text>
        </g>
      ))}
    </g>
  )
}

/** Grouped columns for amounts on one shared axis. */
export function Columns({ title, years, series, format, tick }: { title: string; years: FiscalYear[]; series: Series[]; format: (v: number) => string; tick: (v: number) => string }) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const [hover, setHover] = React.useState<number | null>(null)
  const all = series.flatMap((s) => s.values.filter((v): v is number => v !== undefined))
  const max = niceMax(Math.max(...all, 0))
  const min = Math.min(0, ...all) < 0 ? -niceMax(-Math.min(...all)) : 0
  const innerW = Math.max(0, w - PAD.left - PAD.right)
  const band = innerW / years.length
  const y = (v: number) => PAD.top + (1 - (v - min) / (max - min)) * (H - PAD.top - PAD.bottom)
  const bar = Math.max(4, Math.min(22, (band - 10) / series.length - 2))
  const group = series.length * bar + (series.length - 1) * 2

  return (
    <Frame title={title} series={series}>
      <div ref={ref} className="relative" onMouseLeave={() => setHover(null)}>
        {hover !== null && <Tooltip x={PAD.left + band * (hover + 0.5)} width={w} year={years[hover]} series={series} i={hover} format={format} />}
        {w > 0 && (
          <svg width={w} height={H} role="img" aria-label={`${title}: ${series.map((s) => s.name).join(" and ")} by year`}>
            <Axis max={max} min={min} y={y} w={w} tick={tick} />
            {years.map((fy, i) => {
              const x0 = PAD.left + band * i + (band - group) / 2
              return (
                <g key={fy}>
                  {hover === i && <rect x={PAD.left + band * i + 2} y={PAD.top} width={band - 4} height={H - PAD.top - PAD.bottom} rx="6" fill="var(--ink)" opacity="0.045" />}
                  {series.map((s, k) => {
                    const v = s.values[i]
                    if (v === undefined) return null
                    const top = Math.min(y(v), y(0))
                    const h = Math.max(1, Math.abs(y(v) - y(0)))
                    const r = Math.min(4, bar / 2, h)
                    const x = x0 + k * (bar + 2)
                    // rounded at the data end, square at the baseline
                    const d =
                      v >= 0
                        ? `M${x},${top + h}V${top + r}Q${x},${top} ${x + r},${top}H${x + bar - r}Q${x + bar},${top} ${x + bar},${top + r}V${top + h}Z`
                        : `M${x},${top}V${top + h - r}Q${x},${top + h} ${x + r},${top + h}H${x + bar - r}Q${x + bar},${top + h} ${x + bar},${top + h - r}V${top}Z`
                    return <path key={s.name} d={d} fill={s.color} />
                  })}
                  <text x={PAD.left + band * (i + 0.5)} y={H - 6} textAnchor="middle" fontSize="11" fill="var(--ink-3)" className="num">
                    {String(fy % 100).padStart(2, "0")}
                  </text>
                  <rect x={PAD.left + band * i} y={0} width={band} height={H} fill="transparent" onMouseEnter={() => setHover(i)} />
                </g>
              )
            })}
          </svg>
        )}
      </div>
    </Frame>
  )
}

/** Lines for ratios on one shared axis, labelled at the line ends. */
export function Lines({ title, years, series, format, tick }: { title: string; years: FiscalYear[]; series: Series[]; format: (v: number) => string; tick: (v: number) => string }) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const [hover, setHover] = React.useState<number | null>(null)
  const all = series.flatMap((s) => s.values.filter((v): v is number => v !== undefined))
  const max = niceMax(Math.max(...all, 0))
  const min = Math.min(0, ...all) < 0 ? -niceMax(-Math.min(...all)) : 0
  const right = 8
  const innerW = Math.max(0, w - PAD.left - right)
  const step = years.length > 1 ? innerW / (years.length - 1) : 0
  const x = (i: number) => PAD.left + step * i
  const y = (v: number) => PAD.top + (1 - (v - min) / (max - min)) * (H - PAD.top - PAD.bottom)

  return (
    <Frame title={title} series={series}>
      <div
        ref={ref}
        className="relative"
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          if (!step) return
          const box = e.currentTarget.getBoundingClientRect()
          setHover(Math.max(0, Math.min(years.length - 1, Math.round((e.clientX - box.left - PAD.left) / step))))
        }}
      >
        {hover !== null && <Tooltip x={x(hover)} width={w} year={years[hover]} series={series} i={hover} format={format} />}
        {w > 0 && (
          <svg width={w} height={H} role="img" aria-label={`${title}: ${series.map((s) => s.name).join(" and ")} by year`}>
            <Axis max={max} min={min} y={y} w={w + PAD.right - right} tick={tick} />
            {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={H - PAD.bottom} stroke="var(--line-2)" />}
            {series.map((s) => {
              const pts = s.values.map((v, i) => (v === undefined ? null : ([x(i), y(v)] as const)))
              // a gap in the data lifts the pen
              const d = pts.map((p, i) => (p ? `${i > 0 && pts[i - 1] ? "L" : "M"}${p[0]},${p[1]}` : "")).join("")
              const last = [...pts].reverse().find(Boolean)
              return (
                <g key={s.name}>
                  <path d={d} fill="none" stroke={s.color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
                  {last && <circle cx={last[0]} cy={last[1]} r="4" fill={s.color} stroke="var(--surface)" strokeWidth="2" />}
                  {hover !== null && pts[hover] && <circle cx={pts[hover]![0]} cy={pts[hover]![1]} r="4" fill={s.color} stroke="var(--surface)" strokeWidth="2" />}
                </g>
              )
            })}
            {years.map((fy, i) => (
              <text key={fy} x={x(i)} y={H - 6} textAnchor={i === 0 ? "start" : i === years.length - 1 ? "end" : "middle"} fontSize="11" fill="var(--ink-3)" className="num">
                {String(fy % 100).padStart(2, "0")}
              </text>
            ))}
          </svg>
        )}
      </div>
    </Frame>
  )
}

/** A trend in a tile: shape only, no axes. */
export function Spark({ values, color = "var(--ink-3)" }: { values: Array<number | undefined>; color?: string }) {
  const pts = values.filter((v): v is number => v !== undefined)
  if (pts.length < 2) return null
  const w = 72, h = 24
  const min = Math.min(...pts), max = Math.max(...pts)
  const span = max - min || 1
  const xy = pts.map((v, i) => [(i / (pts.length - 1)) * (w - 6) + 3, h - 4 - ((v - min) / span) * (h - 8)] as const)
  return (
    <svg width={w} height={h} aria-hidden>
      <path d={xy.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join("")} fill="none" stroke={color} strokeWidth="1.75" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={xy[xy.length - 1][0]} cy={xy[xy.length - 1][1]} r="2.5" fill={color} />
    </svg>
  )
}
