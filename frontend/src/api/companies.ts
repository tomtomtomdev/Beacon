import type { CompanyHealth } from './types'

// GET /companies/health — the source-health view (DESIGN §3): per-company health + summary.
export async function fetchCompanyHealth(): Promise<CompanyHealth> {
  const response = await fetch('/companies/health')
  if (!response.ok) {
    throw new Error(`GET /companies/health failed: ${response.status}`)
  }
  return (await response.json()) as CompanyHealth
}

// Shared by the globe widget and the icon-rail's live tag. It lives here, rather than as an
// inline key at each call site the way ['countries'] does, because the two read it at different
// moments: the rail mounts immediately and the widget only once /countries resolves. With the
// default staleTime of 0 the cache is already stale by then and the second mount refetches the
// same rollup. The rollup only moves when a poll runs (every 4–6h), so a minute of freshness is
// conservative — and it makes the two surfaces genuinely cost one request.
export const companyHealthQuery = {
  queryKey: ['companyHealth'] as const,
  queryFn: fetchCompanyHealth,
  staleTime: 60_000,
}
