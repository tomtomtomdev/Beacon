import type { CompanyHealth } from './types'

// GET /companies/health — the source-health view (DESIGN §3): per-company health + summary.
export async function fetchCompanyHealth(): Promise<CompanyHealth> {
  const response = await fetch('/companies/health')
  if (!response.ok) {
    throw new Error(`GET /companies/health failed: ${response.status}`)
  }
  return (await response.json()) as CompanyHealth
}
