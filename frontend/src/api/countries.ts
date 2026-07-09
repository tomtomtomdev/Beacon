import type { Country } from './types'

// GET /countries — the visa reference cards (SPEC §4). Seeded server-side; served whole.
export async function fetchCountries(): Promise<Country[]> {
  const response = await fetch('/countries')
  if (!response.ok) {
    throw new Error(`GET /countries failed: ${response.status}`)
  }
  return (await response.json()) as Country[]
}
