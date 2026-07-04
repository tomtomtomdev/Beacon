import type { JobsPageResponse } from './types'

export interface JobsQuery {
  q: string
  countries: string[]
}

export async function fetchJobs({ q, countries }: JobsQuery): Promise<JobsPageResponse> {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  for (const country of countries) params.append('country', country)
  const qs = params.toString()

  const response = await fetch(qs ? `/jobs?${qs}` : '/jobs')
  if (!response.ok) {
    throw new Error(`GET /jobs failed: ${response.status}`)
  }
  return (await response.json()) as JobsPageResponse
}
