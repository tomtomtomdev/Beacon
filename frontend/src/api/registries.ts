import type { RegistryCoverage } from './types'

// GET /registries — sponsor-registry coverage (DESIGN §1): snapshot age, rows and matches
// per register, including the ones that have never been ingested here.
export async function fetchRegistryCoverage(): Promise<RegistryCoverage> {
  const response = await fetch('/registries')
  if (!response.ok) {
    throw new Error(`GET /registries failed: ${response.status}`)
  }
  return (await response.json()) as RegistryCoverage
}
