import { ChevronDown, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { SortBy } from '../api/jobs'
import type { Country, MarketCoverage, PriorityTier, SponsorTier } from '../api/types'
import styles from './FilterBar.module.css'
import { CATEGORY_OPTIONS, LEVEL_OPTIONS, regionName } from './taxonomy'

// DESIGN.md §1 sponsor-tier dropdown; dot colors reuse the tier tokens.
const TIER_OPTIONS: ReadonlyArray<{ value: SponsorTier; label: string; dot: string }> = [
  { value: 'explicit_yes', label: 'Sponsors', dot: styles.dotYes },
  { value: 'not_required', label: 'No visa needed', dot: styles.dotHome },
  { value: 'registry_inferred', label: 'Registry', dot: styles.dotRegistry },
  { value: 'unknown', label: 'Unknown', dot: styles.dotUnknown },
  { value: 'explicit_no', label: 'No sponsor', dot: styles.dotNo },
]

// Keyed off the tier so a third value cannot fall through to the nice-to-have branch, the way
// a ternary on 'primary' silently would. ⌂ is the home market: not a ranking, a different kind
// of row (DESIGN §1).
const COUNTRY_BADGE: Record<PriorityTier, { className: string; glyph: string }> = {
  home: { className: styles.tierBadgeHome, glyph: '⌂' },
  primary: { className: styles.tierBadgePrimary, glyph: 'P' },
  nice_to_have: { className: styles.tierBadgeNice, glyph: '☆' },
}

type OpenMenu = 'country' | 'tier' | null

interface FilterBarProps {
  q: string
  // The markets /countries serves, in the server's order (home, then primary, then
  // alphabetical within tier) — rendered as served, never re-sorted here.
  markets: readonly Country[]
  // GET /markets: the open-job count per country, and the countries §4 never assessed. Null
  // until it lands — counts are derived or absent, never a placeholder (slice 19's rule).
  coverage: MarketCoverage | null
  countries: string[]
  categories: string[]
  levels: string[]
  tiers: SponsorTier[]
  sort: SortBy
  onQChange: (q: string) => void
  onToggleCountry: (code: string) => void
  onToggleCategory: (value: string) => void
  onToggleLevel: (value: string) => void
  onToggleTier: (tier: SponsorTier) => void
  // Delisted postings are out of the list by default; this brings them back, greyed.
  includeClosed: boolean
  onToggleClosed: () => void
  onSortChange: (sort: SortBy) => void
  // The Fit sort option only appears once a resume is active (§11 — opt-in, never default).
  showFitSort: boolean
}

export function FilterBar({
  q,
  markets,
  coverage,
  countries,
  categories,
  levels,
  tiers,
  sort,
  onQChange,
  onToggleCountry,
  onToggleCategory,
  onToggleLevel,
  onToggleTier,
  includeClosed,
  onToggleClosed,
  onSortChange,
  showFitSort,
}: FilterBarProps) {
  const [openMenu, setOpenMenu] = useState<OpenMenu>(null)
  // Derived during render from the one response — no state, no effect.
  const openJobs = useMemo(
    () => new Map(coverage?.target_markets.map((market) => [market.code, market.open_jobs])),
    [coverage],
  )
  const otherMarkets = coverage?.other_markets ?? []
  const toggleMenu = (menu: 'country' | 'tier') =>
    setOpenMenu((current) => (current === menu ? null : menu))

  const countryLabel = countries.length > 0 ? `Country · ${countries.length}` : 'Country'
  const tierLabel = tiers.length > 0 ? `Tier · ${tiers.length}` : 'Sponsor tier'

  return (
    <div className={styles.filters}>
      <div className={styles.bar}>
        <div className={styles.searchBox}>
        <Search size={16} className={styles.searchIcon} aria-hidden />
        <input
          className={styles.searchInput}
          type="search"
          placeholder="Search title, company, keyword…"
          value={q}
          onChange={(e) => onQChange(e.target.value)}
        />
      </div>

      <div className={styles.sortControl} role="group" aria-label="Sort by">
        <span className={styles.sortLabel}>Sort</span>
        <button
          type="button"
          className={sort === 'tier' ? styles.segmentActive : styles.segment}
          aria-pressed={sort === 'tier'}
          onClick={() => onSortChange('tier')}
        >
          Sponsor tier
        </button>
        <button
          type="button"
          className={sort === 'date' ? styles.segmentActive : styles.segment}
          aria-pressed={sort === 'date'}
          onClick={() => onSortChange('date')}
        >
          Date
        </button>
        {showFitSort && (
          <button
            type="button"
            className={sort === 'match' ? styles.segmentActive : styles.segment}
            aria-pressed={sort === 'match'}
            onClick={() => onSortChange('match')}
          >
            Fit
          </button>
        )}
      </div>

      <div className={styles.dropdown}>
        <button
          type="button"
          className={countries.length > 0 ? styles.pillButtonActive : styles.pillButton}
          onClick={() => toggleMenu('country')}
        >
          {countryLabel}
          <ChevronDown size={14} aria-hidden />
        </button>
        {openMenu === 'country' && (
          <>
            <div className={styles.clickAway} onClick={() => setOpenMenu(null)} />
            <div
              className={`${styles.menu} ${styles.menuScroll}`}
              role="group"
              aria-label="Filter by country"
            >
              <p className={styles.menuNote}>Open postings per market.</p>
              {markets.map(({ code, name, priority_tier }) => (
                <CountryRow
                  key={code}
                  name={name}
                  openJobs={openJobs.get(code)}
                  checked={countries.includes(code)}
                  onToggle={() => onToggleCountry(code)}
                  tier={priority_tier}
                />
              ))}
              {otherMarkets.length > 0 && (
                <>
                  <div className={styles.menuDivider} aria-hidden />
                  <p className={styles.menuHeading}>Other markets</p>
                  <p className={styles.menuNote}>
                    Not relocation targets — no visa reference, no globe pin. Postings only.
                  </p>
                  {otherMarkets.map(({ code, open_jobs }) => (
                    <CountryRow
                      key={code}
                      name={regionName(code)}
                      openJobs={open_jobs}
                      checked={countries.includes(code)}
                      onToggle={() => onToggleCountry(code)}
                      tier={null}
                    />
                  ))}
                </>
              )}
            </div>
          </>
        )}
      </div>

      <div className={styles.dropdown}>
        <button
          type="button"
          aria-label="Filter by sponsor tier"
          className={tiers.length > 0 ? styles.pillButtonActive : styles.pillButton}
          onClick={() => toggleMenu('tier')}
        >
          {tierLabel}
          <ChevronDown size={14} aria-hidden />
        </button>
        {openMenu === 'tier' && (
          <>
            <div className={styles.clickAway} onClick={() => setOpenMenu(null)} />
            <div className={styles.menu} role="group" aria-label="Filter by sponsor tier">
              <p className={styles.menuNote}>Opt-in filter. Off by default — nothing is hidden.</p>
              {TIER_OPTIONS.map(({ value, label, dot }) => (
                <label key={value} className={styles.menuRow}>
                  <input
                    type="checkbox"
                    checked={tiers.includes(value)}
                    onChange={() => onToggleTier(value)}
                  />
                  <span className={`${styles.tierDot} ${dot}`} aria-hidden />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </>
        )}
        </div>

        {/* Opt-in, like the tier filter: closed postings are kept (SPEC §5) and reachable,
            just not carried by default — Sweden is 86% closed and the list was mostly dead
            rows. What comes back is greyed and labelled, never silently mixed in. */}
        <button
          type="button"
          className={includeClosed ? styles.pillButtonActive : styles.pillButton}
          aria-pressed={includeClosed}
          onClick={onToggleClosed}
        >
          Show closed
        </button>
      </div>

      <div className={styles.chipRow}>
        <span className={styles.chipLabel}>Category</span>
        {CATEGORY_OPTIONS.map(({ value, label }) => (
          <button
            key={value}
            type="button"
            className={categories.includes(value) ? styles.chipToggleActive : styles.chipToggle}
            aria-pressed={categories.includes(value)}
            onClick={() => onToggleCategory(value)}
          >
            {label}
          </button>
        ))}
        <span className={styles.chipDivider} aria-hidden />
        <span className={styles.chipLabel}>Level</span>
        {LEVEL_OPTIONS.map(({ value, label }) => (
          <button
            key={value}
            type="button"
            className={levels.includes(value) ? styles.chipToggleActive : styles.chipToggle}
            aria-pressed={levels.includes(value)}
            onClick={() => onToggleLevel(value)}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  )
}

// One row shape for both groups. `tier` is null for an other market: COUNTRY_BADGE is keyed by
// priority_tier, a §4 concept those countries do not have, and a grey "unknown" glyph would
// assert a tier had been assessed and come back empty. The whitespace after the name is
// load-bearing — without it the accessible name concatenates to "Norway0".
function CountryRow({
  name,
  openJobs,
  checked,
  onToggle,
  tier,
}: {
  name: string
  openJobs: number | undefined
  checked: boolean
  onToggle: () => void
  tier: PriorityTier | null
}) {
  const badge = tier ? COUNTRY_BADGE[tier] : null
  return (
    <label className={styles.menuRow}>
      <input type="checkbox" checked={checked} onChange={onToggle} />
      <span className={styles.menuRowLabel}>{name}</span>{' '}
      <MarketCount openJobs={openJobs} />
      {badge && (
        <span className={badge.className} aria-hidden>
          {badge.glyph}
        </span>
      )}
    </label>
  )
}

// A target market keeps its row at zero — it is a reference fact, not a corpus one — so the
// zero renders rather than being hidden: it is what tells you the box will return nothing.
// Absent (the response has not landed) is the one case that renders no number at all.
function MarketCount({ openJobs }: { openJobs: number | undefined }) {
  if (openJobs === undefined) return null
  return <span className={styles.menuCount}>{openJobs.toLocaleString()}</span>
}
