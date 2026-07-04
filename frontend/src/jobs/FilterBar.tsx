import { ChevronDown, Search } from 'lucide-react'
import { useState } from 'react'
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

interface FilterBarProps {
  q: string
  countries: string[]
  onQChange: (q: string) => void
  onToggleCountry: (code: string) => void
}

export function FilterBar({ q, countries, onQChange, onToggleCountry }: FilterBarProps) {
  const [menuOpen, setMenuOpen] = useState(false)
  const countryLabel = countries.length > 0 ? `Country · ${countries.length}` : 'Country'

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

      <div className={styles.dropdown}>
        <button
          type="button"
          className={countries.length > 0 ? styles.pillButtonActive : styles.pillButton}
          onClick={() => setMenuOpen((open) => !open)}
        >
          {countryLabel}
          <ChevronDown size={14} aria-hidden />
        </button>
        {menuOpen && (
          <>
            <div className={styles.clickAway} onClick={() => setMenuOpen(false)} />
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
    </div>
  )
}
