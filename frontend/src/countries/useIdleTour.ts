import { useEffect, useRef, useState, useSyncExternalStore } from 'react'

/** Events that mean a human is present. `pointermove` is filtered separately (see MOVE_SLOP). */
const ACTIVITY_EVENTS = ['pointerdown', 'keydown', 'wheel', 'touchstart', 'scroll'] as const

/** Layout shifting under a still cursor can emit a pointermove; ignore sub-pixel-ish jitter. */
const MOVE_SLOP = 2

const REDUCED_MOTION = '(prefers-reduced-motion: reduce)'

/** Long enough that reading a card never triggers it; short enough to feel alive on a wall screen. */
export const TOUR_IDLE_MS = 45_000
/** One market per dwell — enough to read the visa blocks and let its jobs land. */
export const TOUR_DWELL_MS = 9_000

export type IdleTourOptions = {
  /** Rotation order. Fewer than two entries means there is nothing to tour. */
  codes: readonly string[]
  /** The market currently selected — the tour resumes from wherever the user left off. */
  current: string | null
  onAdvance: (code: string) => void
  enabled?: boolean
  idleDelayMs?: number
  dwellMs?: number
}

/**
 * Calls `onActivity` on any sign of a human at the keyboard or pointer. A `pointermove` only
 * counts once the cursor has actually travelled — layout shifting under a still cursor emits
 * one, and that would cancel the tour it just triggered.
 */
function subscribeActivity(onActivity: () => void): () => void {
  let lastX = Number.NaN
  let lastY = Number.NaN
  const onPointerMove = (event: PointerEvent) => {
    if (Math.abs(event.clientX - lastX) + Math.abs(event.clientY - lastY) <= MOVE_SLOP) return
    lastX = event.clientX
    lastY = event.clientY
    onActivity()
  }
  for (const event of ACTIVITY_EVENTS) window.addEventListener(event, onActivity, { passive: true })
  window.addEventListener('pointermove', onPointerMove, { passive: true })
  return () => {
    for (const event of ACTIVITY_EVENTS) window.removeEventListener(event, onActivity)
    window.removeEventListener('pointermove', onPointerMove)
  }
}

function subscribeReducedMotion(onChange: () => void): () => void {
  const query = window.matchMedia?.(REDUCED_MOTION)
  query?.addEventListener('change', onChange)
  return () => query?.removeEventListener('change', onChange)
}

function reducedMotionSnapshot(): boolean {
  return window.matchMedia?.(REDUCED_MOTION).matches ?? false
}

/**
 * Rotates the selection through `codes` once the page has been untouched for `idleDelayMs`,
 * one market per `dwellMs`. Any sign of a human — pointer, key, wheel, touch, scroll — hands
 * control straight back, leaving the market the tour landed on selected, and restarts the
 * countdown. Returns whether the tour is currently driving, so the UI can say so.
 */
export function useIdleTour({
  codes,
  current,
  onAdvance,
  enabled = true,
  idleDelayMs = TOUR_IDLE_MS,
  dwellMs = TOUR_DWELL_MS,
}: IdleTourOptions): boolean {
  const [idle, setIdle] = useState(false)
  const reducedMotion = useSyncExternalStore(subscribeReducedMotion, reducedMotionSnapshot, () => false)
  const active = enabled && codes.length > 1 && !reducedMotion
  // Derived, not stored: switching the tour off never needs a state write of its own.
  const touring = active && idle

  // The rotation timer reads the newest props without being torn down on every advance.
  const latest = useRef({ codes, current, onAdvance })
  useEffect(() => {
    latest.current = { codes, current, onAdvance }
  })

  // Idle detection is a subscription to the document, so it lives in an effect.
  useEffect(() => {
    if (!active) return
    let timer = 0
    const arm = () => {
      window.clearTimeout(timer)
      timer = window.setTimeout(() => setIdle(true), idleDelayMs)
    }
    const onActivity = () => {
      setIdle(false)
      arm()
    }
    // A hidden tab is idle, but touring it would waste fetches — pause until it is back.
    const onVisibility = () => {
      if (document.hidden) {
        window.clearTimeout(timer)
        setIdle(false)
      } else {
        arm()
      }
    }
    const unsubscribe = subscribeActivity(onActivity)
    document.addEventListener('visibilitychange', onVisibility)
    arm()
    return () => {
      window.clearTimeout(timer)
      unsubscribe()
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [active, idleDelayMs])

  useEffect(() => {
    if (!touring) return
    const advance = () => {
      const { codes: order, current: at, onAdvance: select } = latest.current
      const next = order[(order.indexOf(at ?? '') + 1) % order.length]
      select(next)
    }
    advance()
    const ticker = window.setInterval(advance, dwellMs)
    return () => window.clearInterval(ticker)
  }, [touring, dwellMs])

  return touring
}
