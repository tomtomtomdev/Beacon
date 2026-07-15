import { ChevronDown, Search } from 'lucide-react'
import { useState } from 'react'
import type { SortBy } from '../api/jobs'
import type { SponsorTier } from '../api/types'
import styles from './FilterBar.module.css'
import { CATEGORY_OPTIONS, COUNTRY_OPTIONS, LEVEL_OPTIONS } from './taxonomy'

// DESIGN.md §1 sponsor-tier dropdown; dot colors reuse the tier tokens.
const TIER_OPTIONS: ReadonlyArray<{ value: SponsorTier; label: string; dot: string }> = [
  { value: 'explicit_yes', label: 'Sponsors', dot: styles.dotYes },
  { value: 'registry_inferred', label: 'Registry', dot: styles.dotRegistry },
  { value: 'unknown', label: 'Unknown', dot: styles.dotUnknown },
  { value: 'explicit_no', label: 'No sponsor', dot: styles.dotNo },
]

type OpenMenu = 'country' | 'tier' | null

interface FilterBarProps {
  q: string
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
  onSortChange: (sort: SortBy) => void
  // The Fit sort option only appears once a resume is active (§11 — opt-in, never default).
  showFitSort: boolean
}

export function FilterBar({
  q,
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
  onSortChange,
  showFitSort,
}: FilterBarProps) {
  const [openMenu, setOpenMenu] = useState<OpenMenu>(null)
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
            <div className={styles.menu} role="group" aria-label="Filter by country">
              {COUNTRY_OPTIONS.map(({ code, name, tier }) => (
                <label key={code} className={styles.menuRow}>
                  <input
                    type="checkbox"
                    checked={countries.includes(code)}
                    onChange={() => onToggleCountry(code)}
                  />
                  <span className={styles.menuRowLabel}>{name}</span>
                  <span
                    className={tier === 'primary' ? styles.tierBadgePrimary : styles.tierBadgeNice}
                    aria-hidden
                  >
                    {tier === 'primary' ? 'P' : '☆'}
                  </span>
                </label>
              ))}
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
