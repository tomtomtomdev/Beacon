import type { SponsorTier } from '../api/types'

// Category/level display taxonomy — shared by the FilterBar pills and the saved-search
// summary so a code always renders the same label. Values are the API codes; labels are §2.

// Sponsor-tier chip labels — shared by the JobList card chip and the drawer chip row.
export const TIER_LABEL: Record<SponsorTier, string> = {
  explicit_yes: 'Sponsors',
  registry_inferred: 'Registry',
  unknown: 'Unknown',
  explicit_no: 'No sponsor',
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

// The 11 target markets (SPEC §3) — shared by the FilterBar country dropdown and the
// "Jobs · {Country}" heading. Codes are the /jobs `country[]` param; tier drives the P/☆ badge.
export const COUNTRY_OPTIONS: ReadonlyArray<{
  code: string
  name: string
  tier: 'primary' | 'nice_to_have'
}> = [
  { code: 'SG', name: 'Singapore', tier: 'primary' },
  { code: 'AU', name: 'Australia', tier: 'primary' },
  { code: 'JP', name: 'Japan', tier: 'primary' },
  { code: 'NL', name: 'Netherlands', tier: 'primary' },
  { code: 'US', name: 'United States', tier: 'primary' },
  { code: 'CA', name: 'Canada', tier: 'primary' },
  { code: 'IE', name: 'Ireland', tier: 'primary' },
  { code: 'SE', name: 'Sweden', tier: 'nice_to_have' },
  { code: 'NO', name: 'Norway', tier: 'nice_to_have' },
  { code: 'DK', name: 'Denmark', tier: 'nice_to_have' },
  { code: 'CH', name: 'Switzerland', tier: 'nice_to_have' },
]

const COUNTRY_NAMES = new Map(COUNTRY_OPTIONS.map(({ code, name }) => [code, name]))

export const countryName = (code: string): string => COUNTRY_NAMES.get(code) ?? code
