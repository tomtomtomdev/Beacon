import type { JobsPageResponse, SponsorTier } from './types'

export type SortBy = 'tier' | 'date'

export interface JobsQuery {
  q: string
  countries: string[]
  categories: string[]
  levels: string[]
  tiers: SponsorTier[]
  sort: SortBy
}

export async function fetchJobs({
  q,
  countries,
  categories,
  levels,
  tiers,
  sort,
}: JobsQuery): Promise<JobsPageResponse> {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  for (const country of countries) params.append('country', country)
  for (const category of categories) params.append('category', category)
  for (const level of levels) params.append('level', level)
  for (const tier of tiers) params.append('sponsor_tier', tier)
  // 'tier' is the API default — omit it so shared URLs stay clean.
  if (sort === 'date') params.set('sort', 'date')
  const qs = params.toString()

  const response = await fetch(qs ? `/jobs?${qs}` : '/jobs')
  if (!response.ok) {
    throw new Error(`GET /jobs failed: ${response.status}`)
  }
  return (await response.json()) as JobsPageResponse
}
