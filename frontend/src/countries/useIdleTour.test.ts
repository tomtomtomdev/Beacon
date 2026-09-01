import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useIdleTour } from './useIdleTour'

const CODES = ['NL', 'SE', 'DE'] as const
const IDLE_MS = 1_000
const DWELL_MS = 500

type Harness = { current: string | null; onAdvance: (code: string) => void }

function renderTour(overrides: Partial<Parameters<typeof useIdleTour>[0]> = {}) {
  const onAdvance = vi.fn<Harness['onAdvance']>()
  const view = renderHook(
    (props: { current: string | null }) =>
      useIdleTour({
        codes: [...CODES],
        current: props.current,
        onAdvance,
        idleDelayMs: IDLE_MS,
        dwellMs: DWELL_MS,
        ...overrides,
      }),
    { initialProps: { current: null as string | null } },
  )
  return { ...view, onAdvance }
}

function pointerMove(x: number, y: number) {
  act(() => {
    window.dispatchEvent(new MouseEvent('pointermove', { clientX: x, clientY: y }))
  })
}

function elapse(ms: number) {
  act(() => {
    vi.advanceTimersByTime(ms)
  })
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('useIdleTour', () => {
  it('stays quiet until the idle delay has elapsed', () => {
    const { result, onAdvance } = renderTour()

    elapse(IDLE_MS - 1)

    expect(onAdvance).not.toHaveBeenCalled()
    expect(result.current).toBe(false)
  })

  it('selects the first market once idle, then rotates one market per dwell', () => {
    const { result, onAdvance, rerender } = renderTour()

    elapse(IDLE_MS)
    expect(result.current).toBe(true)
    expect(onAdvance).toHaveBeenLastCalledWith('NL')

    // The page feeds the new selection back in; the tour advances from wherever it is.
    rerender({ current: 'NL' })
    elapse(DWELL_MS)
    expect(onAdvance).toHaveBeenLastCalledWith('SE')

    rerender({ current: 'DE' })
    elapse(DWELL_MS)
    expect(onAdvance).toHaveBeenLastCalledWith('NL')
  })

  it('starts the rotation after the market the user last picked', () => {
    const { onAdvance, rerender } = renderTour()
    rerender({ current: 'SE' })

    elapse(IDLE_MS)

    expect(onAdvance).toHaveBeenCalledExactlyOnceWith('DE')
  })

  it('hands control back on activity and restarts the idle countdown', () => {
    const { result, onAdvance } = renderTour()
    elapse(IDLE_MS)
    expect(onAdvance).toHaveBeenCalledTimes(1)

    pointerMove(120, 90)
    expect(result.current).toBe(false)

    elapse(IDLE_MS - 1)
    expect(onAdvance).toHaveBeenCalledTimes(1)
    elapse(1)
    expect(onAdvance).toHaveBeenCalledTimes(2)
  })

  it('ignores a pointermove that did not actually move (layout shifting under the cursor)', () => {
    const { result } = renderTour()
    pointerMove(120, 90)

    elapse(IDLE_MS)
    expect(result.current).toBe(true)

    pointerMove(120, 90)
    expect(result.current).toBe(true)
  })

  it('pauses while the tab is hidden and re-arms when it comes back', () => {
    const { result, onAdvance } = renderTour()
    elapse(IDLE_MS)
    expect(onAdvance).toHaveBeenCalledTimes(1)

    const hidden = vi.spyOn(document, 'hidden', 'get').mockReturnValue(true)
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'))
    })
    expect(result.current).toBe(false)

    elapse(IDLE_MS * 3)
    expect(onAdvance).toHaveBeenCalledTimes(1)

    hidden.mockReturnValue(false)
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'))
    })
    elapse(IDLE_MS)
    expect(onAdvance).toHaveBeenCalledTimes(2)
  })

  it('never runs when disabled, when there is nowhere to rotate, or under reduced motion', () => {
    const { result: disabled, onAdvance: a } = renderTour({ enabled: false })
    const { result: single, onAdvance: b } = renderTour({ codes: ['NL'] })
    // jsdom ships no matchMedia, so the reduced-motion probe is stubbed wholesale.
    vi.stubGlobal('matchMedia', () => ({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }))
    const { result: reduced, onAdvance: c } = renderTour()

    elapse(IDLE_MS * 4)

    expect([disabled.current, single.current, reduced.current]).toEqual([false, false, false])
    expect([a, b, c].every((fn) => fn.mock.calls.length === 0)).toBe(true)
  })
})
