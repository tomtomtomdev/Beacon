// Hand-mirrored from backend/beacon/api DTOs — the single place API shapes live.

export type SponsorTier = 'explicit_yes' | 'registry_inferred' | 'unknown' | 'explicit_no'

export interface Job {
  id: number
  title: string
  company: string
  url: string
  location: string
  country: string | null
  city: string | null
  posted_at: string | null
  sponsor_tier: SponsorTier
}

export interface JobsPageResponse {
  jobs: Job[]
  total: number
}
