import type { JobDetail, JobsPageResponse, SponsorTier, UserStatus } from './types'

export type SortBy = 'tier' | 'date'

// The status segmented control (DESIGN.md §2). 'all' shows everything except hidden
// (the API's param-less default), so it maps to omitting the status param entirely.
export type StatusView = 'new' | 'starred' | 'all' | 'hidden'

export interface JobsQuery {
  q: string
  countries: string[]
  categories: string[]
  levels: string[]
  tiers: SponsorTier[]
  sort: SortBy
  status: StatusView
}

export async function fetchJobs({
  q,
  countries,
  categories,
  levels,
  tiers,
  sort,
  status,
}: JobsQuery): Promise<JobsPageResponse> {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  for (const country of countries) params.append('country', country)
  for (const category of categories) params.append('category', category)
  for (const level of levels) params.append('level', level)
  for (const tier of tiers) params.append('sponsor_tier', tier)
  // 'tier' is the API default — omit it so shared URLs stay clean.
  if (sort === 'date') params.set('sort', 'date')
  // 'all' = the API's param-less default (everything but hidden); the rest filter to one status.
  if (status !== 'all') params.set('status', status)
  const qs = params.toString()

  const response = await fetch(qs ? `/jobs?${qs}` : '/jobs')
  if (!response.ok) {
    throw new Error(`GET /jobs failed: ${response.status}`)
  }
  return (await response.json()) as JobsPageResponse
}

// GET /jobs/{id} — the canonical job, its sponsorship evidence, and every source it was
// found on. Feeds the detail drawer (DESIGN.md §2).
export async function fetchJobDetail(id: number): Promise<JobDetail> {
  const response = await fetch(`/jobs/${id}`)
  if (!response.ok) {
    throw new Error(`GET /jobs/${id} failed: ${response.status}`)
  }
  return (await response.json()) as JobDetail
}

export async function patchJobStatus(id: number, status: UserStatus): Promise<void> {
  const response = await fetch(`/jobs/${id}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  })
  if (!response.ok) {
    throw new Error(`PATCH /jobs/${id}/status failed: ${response.status}`)
  }
}
