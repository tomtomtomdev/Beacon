// Hand-mirrored from backend/beacon/api DTOs — the single place API shapes live.

export type SponsorTier = 'explicit_yes' | 'registry_inferred' | 'unknown' | 'explicit_no'

// The per-job daily-scan lifecycle: new → seen → starred/hidden (see PATCH /jobs/{id}/status).
export type UserStatus = 'new' | 'seen' | 'hidden' | 'starred'

export interface Job {
  id: number
  title: string
  company: string
  url: string
  location: string
  country: string | null
  city: string | null
  categories: string[]
  level: string | null
  posted_at: string | null
  sponsor_tier: SponsorTier
  user_status: UserStatus
}

export interface JobsPageResponse {
  jobs: Job[]
  total: number
}

// One underlying posting behind a canonical job — where the same role was found.
export interface DuplicateSource {
  source: string
  company: string
  url: string
}

// GET /jobs/{id}: the canonical job plus every source it appears on. The detail
// drawer that consumes this lands in slice 10 (per DESIGN.md); the contract lives here now.
export interface JobDetail extends Job {
  description: string
  duplicate_sources: DuplicateSource[]
}
