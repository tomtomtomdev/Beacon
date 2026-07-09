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
  // The sentence that decided an explicit_yes/explicit_no tier; null for
  // registry_inferred/unknown. The drawer highlights it (slice 10, per DESIGN.md).
  sponsor_evidence: string | null
  // Behind a registry_inferred tier: which registers the company matched (e.g. ['UK','NL'])
  // and the fuzzy-match confidence. Empty / null when no register matched.
  registries: string[]
  match_confidence: number | null
  duplicate_sources: DuplicateSource[]
}

// The matchable criteria of a saved search — the subset of the Jobs filter bar that
// gets serialized (no sort/status/pagination). Mirrors domain SearchFilters.
export interface SearchFilters {
  q: string | null
  countries: string[]
  categories: string[]
  levels: string[]
  tiers: SponsorTier[]
}

// GET/POST /searches. new_count = matching jobs the user hasn't triaged yet (user_status='new').
export interface SavedSearch {
  id: number
  name: string
  filters: SearchFilters
  notify_channel: string
  last_run_at: string | null
  new_count: number
}

// GET /settings/telegram. The bot token is write-only — the API returns only whether
// one is set (bot_token_set), never the token itself.
export interface TelegramSettings {
  chat_id: string | null
  bot_token_set: boolean
}

// PUT /settings/telegram. bot_token: null → keep the stored token (don't re-send the
// secret on a chat_id-only save); '' → clear it; a value → set it.
export interface TelegramSettingsUpdate {
  chat_id: string | null
  bot_token: string | null
}

// POST /settings/telegram/test. channel is 'telegram' when creds resolved, else 'stdout'.
export interface TestResult {
  ok: boolean
  channel: string
}

// Target-geography weighting (SPEC §3) — drives the Countries-view legend and map pins.
export type PriorityTier = 'primary' | 'nice_to_have'

// GET /countries: one country's relocation reference card (SPEC §4). Figures are as-known;
// verified_at + source_url let the UI show a "verified as of" date and a re-verify link.
export interface Country {
  code: string
  name: string
  visa_summary: string
  pr_summary: string
  citizenship_summary: string
  registry_name: string
  priority_tier: PriorityTier
  verified_at: string
  source_url: string
}
