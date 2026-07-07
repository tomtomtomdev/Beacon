import { ChevronDown, Search } from 'lucide-react'
import { useState } from 'react'
import type { SortBy } from '../api/jobs'
import type { SponsorTier } from '../api/types'
import styles from './FilterBar.module.css'

// DESIGN.md §1 country dropdown list; tier P/☆ badges arrive with the countries table (slice 10).
const COUNTRIES: ReadonlyArray<{ code: string; name: string }> = [
  { code: 'SG', name: 'Singapore' },
  { code: 'AU', name: 'Australia' },
  { code: 'JP', name: 'Japan' },
  { code: 'NL', name: 'Netherlands' },
  { code: 'US', name: 'United States' },
  { code: 'CA', name: 'Canada' },
  { code: 'IE', name: 'Ireland' },
  { code: 'SE', name: 'Sweden' },
  { code: 'NO', name: 'Norway' },
  { code: 'DK', name: 'Denmark' },
  { code: 'CH', name: 'Switzerland' },
]

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
  tiers: SponsorTier[]
  sort: SortBy
  onQChange: (q: string) => void
  onToggleCountry: (code: string) => void
  onToggleTier: (tier: SponsorTier) => void
  onSortChange: (sort: SortBy) => void
}

export function FilterBar({
  q,
  countries,
  tiers,
  sort,
  onQChange,
  onToggleCountry,
  onToggleTier,
  onSortChange,
}: FilterBarProps) {
  const [openMenu, setOpenMenu] = useState<OpenMenu>(null)
  const toggleMenu = (menu: 'country' | 'tier') =>
    setOpenMenu((current) => (current === menu ? null : menu))

  const countryLabel = countries.length > 0 ? `Country · ${countries.length}` : 'Country'
  const tierLabel = tiers.length > 0 ? `Tier · ${tiers.length}` : 'Sponsor tier'

  return (
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
              {COUNTRIES.map(({ code, name }) => (
                <label key={code} className={styles.menuRow}>
                  <input
                    type="checkbox"
                    checked={countries.includes(code)}
                    onChange={() => onToggleCountry(code)}
                  />
                  <span>{name}</span>
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
  )
}
