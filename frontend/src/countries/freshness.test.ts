import { describe, expect, it } from 'vitest'
import { ageLabel } from './freshness'

const NOW = new Date('2026-09-15T13:00:00Z')

describe('ageLabel', () => {
  it.each([
    ['2026-09-15T12:59:30Z', 'just now'],
    ['2026-09-15T12:43:00Z', '17m ago'],
    // The boundary that matters: a poll runs every 4–6h, so the minute→hour step has to land
    // where a viewer expects it rather than rounding a 59-minute-old poll up to an hour.
    ['2026-09-15T12:00:00Z', '1h ago'],
    ['2026-09-15T05:00:00Z', '8h ago'],
    ['2026-09-14T13:00:00Z', '1d ago'],
    ['2026-09-04T05:29:57Z', '11d ago'],
    ['2026-07-01T05:29:57Z', '76d ago'],
  ])('renders %s as %s', (iso, expected) => {
    expect(ageLabel(iso, NOW)).toBe(expected)
  })
})
