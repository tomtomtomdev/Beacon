import type { MarketCoverage } from './types'

// GET /markets — open-job counts per country, split into the markets SPEC §4 assessed and the
// ones it never did. Separate from /countries on purpose: that resource is the seeded visa
// reference, and hanging a live job count off it would make a reference change every poll.
export async function fetchMarkets(): Promise<MarketCoverage> {
  const response = await fetch('/markets')
  if (!response.ok) {
    throw new Error(`GET /markets failed: ${response.status}`)
  }
  return (await response.json()) as MarketCoverage
}
