"use client"

import * as React from "react"

export function useMediaQuery(query: string) {
  const subscribe = React.useCallback(
    (cb: () => void) => {
      const mql = window.matchMedia(query)
      mql.addEventListener("change", cb)
      return () => mql.removeEventListener("change", cb)
    },
    [query]
  )
  return React.useSyncExternalStore(subscribe, () => window.matchMedia(query).matches, () => false)
}

/** Width of an element, for charts that draw to the pixel. */
export function useWidth<T extends HTMLElement>() {
  const ref = React.useRef<T>(null)
  const [width, setWidth] = React.useState(0)
  React.useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setWidth(Math.round(e.contentRect.width)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, width] as const
}

/** A clock that ticks while `active`, for live durations. */
export function useNow(active: boolean, everyMs = 150) {
  const [now, setNow] = React.useState(0)
  React.useEffect(() => {
    const tick = () => setNow(Date.now())
    tick()
    if (!active) return
    const id = setInterval(tick, everyMs)
    return () => clearInterval(id)
  }, [active, everyMs])
  return now
}

/** True when the reader has asked for less motion (device setting or Settings). */
export function usePrefersCalm() {
  const os = useMediaQuery("(prefers-reduced-motion: reduce)")
  const [calm, setCalm] = React.useState(false)
  React.useEffect(() => {
    const el = document.documentElement
    const read = () => setCalm(el.classList.contains("calm"))
    read()
    const mo = new MutationObserver(read)
    mo.observe(el, { attributes: true, attributeFilter: ["class"] })
    return () => mo.disconnect()
  }, [])
  return os || calm
}
