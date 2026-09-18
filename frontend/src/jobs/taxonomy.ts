import type { Country, PriorityTier, SponsorTier } from '../api/types'

// Category/level display taxonomy — shared by the FilterBar pills and the saved-search
// summary so a code always renders the same label. Values are the API codes; labels are §2.

// Sponsor-tier chip labels — shared by the JobList card chip and the drawer chip row.
export const TIER_LABEL: Record<SponsorTier, string> = {
  explicit_yes: 'Sponsors',
  not_required: 'No visa needed',
  registry_inferred: 'Registry',
  unknown: 'Unknown',
  explicit_no: 'No sponsor',
}

// Country priority tiers (SPEC §3/§4) — the Countries card pill and the Jobs reference
// legend both label them, and they must not drift: one table, imported by both.
export const PRIORITY_TIER_LABEL: Record<PriorityTier, string> = {
  home: 'Home',
  primary: 'Primary',
  nice_to_have: 'Nice-to-have',
}

export const CATEGORY_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: 'ios', label: 'iOS' },
  { value: 'backend', label: 'Backend' },
  { value: 'ai-ml', label: 'AI/ML' },
  { value: 'android', label: 'Android' },
  { value: 'flutter', label: 'Flutter' },
  { value: 'fullstack', label: 'Fullstack' },
  { value: 'frontend', label: 'Frontend' },
]

// DESIGN.md §2 surfaces only the three target-profile levels as filter pills.
export const LEVEL_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: 'senior', label: 'Senior' },
  { value: 'staff', label: 'Staff' },
  { value: 'lead', label: 'Lead' },
]

const CATEGORY_LABELS = new Map(CATEGORY_OPTIONS.map(({ value, label }) => [value, label]))

// Unknown codes (e.g. a new backend category not yet in the table) fall back to the raw code.
export const categoryLabel = (value: string): string => CATEGORY_LABELS.get(value) ?? value

// Names come from /countries — the seeded projection of domain/visa.py's COUNTRY_REFERENCE —
// so the frontend keeps no second copy of the country table. A market added to the backend
// reaches the filter menu and this heading with no edit here, which is the whole point: the
// hardcoded array this replaced is why GB had 480 reachable jobs and no checkbox.
// A code the reference has no row for falls back to the browser's own ISO-3166 table: slice 17
// opened the corpus to countries §4 never assessed, and 47 of them hold open jobs today. A
// code→name table here would be a second source of truth for something every browser ships.
export const countryName = (code: string, markets: readonly Country[]): string =>
  markets.find((market) => market.code === code)?.name ?? regionName(code)

const REGION_NAMES = new Intl.DisplayNames(['en'], { type: 'region' })

// `of` throws RangeError on a structurally invalid code and returns undefined for an unknown
// one; both mean "no name to show", and the bare code is the honest rendering of that.
export const regionName = (code: string): string => {
  try {
    return REGION_NAMES.of(code) ?? code
  } catch {
    return code
  }
}
