import type { SponsorTier } from '../api/types'

// Category/level display taxonomy — shared by the FilterBar pills and the JobTable chips
// so a code always renders the same label. Values are the API codes; labels are DESIGN.md §2.

// Sponsor-tier chip labels — shared by the JobTable row chip and the drawer chip row.
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
