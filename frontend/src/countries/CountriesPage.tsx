import { useQuery } from '@tanstack/react-query'
import { Globe as GlobeIcon } from 'lucide-react'
import { useState } from 'react'
import { fetchCountries } from '../api/countries'
import type { Country } from '../api/types'
import styles from './CountriesPage.module.css'
import { Globe } from './Globe'

const TIER_LABEL: Record<Country['priority_tier'], string> = {
  primary: 'Primary',
  nice_to_have: 'Nice-to-have',
}

export function CountriesPage() {
  const { data: countries, isPending, isError } = useQuery({
    queryKey: ['countries'],
    queryFn: fetchCountries,
  })
  // Which country is highlighted — transient UI state, so local (not a shareable URL param).
  const [selected, setSelected] = useState<string | null>(null)

  return (
    <main className={`${styles.main} bk-scroll`}>
      <header className={styles.header}>
        <h1 className={styles.h1}>Country &amp; visa reference</h1>
        <p className={styles.subtitle}>
          As-known Jan 2026 — thresholds and timelines change. Each row carries a verified date for
          manual re-check. PR and citizenship are distinguished (Indonesia bars adult dual
          citizenship).
        </p>
      </header>

      {isError && <p className={styles.state}>Could not reach the Beacon API.</p>}
      {isPending && <p className={styles.state}>Loading…</p>}

      {countries && (
        <>
          <section className={styles.geoPanel}>
            <Globe countries={countries} selectedCode={selected} onSelect={setSelected} />
            <div className={styles.geoTop}>
              <div className={styles.geoTitleGroup}>
                <GlobeIcon size={18} aria-hidden />
                <span className={styles.geoTitle}>Target geography</span>
                <span className={styles.geoHint}>drag to rotate · tap a beacon</span>
              </div>
              <div className={styles.legend}>
                <span className={styles.legendItem}>
                  <span className={`${styles.legendDot} ${styles.dotPrimary}`} /> Primary target
                </span>
                <span className={styles.legendItem}>
                  <span className={`${styles.legendDot} ${styles.dotNice}`} /> Nice-to-have
                </span>
              </div>
            </div>
            <div className={styles.geoCaption}>live beacon field · 11 markets</div>
            <SourceHealth />
          </section>

          <div className={styles.grid}>
            {countries.map((country) => (
              <CountryCard
                key={country.code}
                country={country}
                selected={selected === country.code}
                onSelect={() => setSelected((cur) => (cur === country.code ? null : country.code))}
              />
            ))}
          </div>
        </>
      )}
    </main>
  )
}

// Static source-health summary folded into the globe legend (DESIGN: "static summary widget").
// TODO: wire live counts + last-poll time from GET /companies health rollup.
function SourceHealth() {
  return (
    <div className={styles.health}>
      <div className={styles.healthHead}>
        <span className={styles.healthLabel}>Source health</span>
        <span className={styles.healthPoll}>poll 07:04</span>
      </div>
      <div className={styles.healthRows}>
        <div className={styles.healthRow}>
          <span className={`${styles.healthDot} ${styles.dotOk}`} />
          <span className={styles.healthCount}>44</span> OK
        </div>
        <div className={styles.healthRow}>
          <span className={`${styles.healthDot} ${styles.dotDegraded}`} />
          <span className={styles.healthCount}>1</span> degraded
        </div>
        <div className={styles.healthRow}>
          <span className={`${styles.healthDot} ${styles.dotQuarantined}`} />
          <span className={styles.healthCount}>2</span> quarantined
        </div>
      </div>
    </div>
  )
}

function CountryCard({
  country,
  selected,
  onSelect,
}: {
  country: Country
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      className={`${styles.card} ${selected ? styles.cardSelected : ''}`}
      aria-label={`${country.name} details`}
      aria-pressed={selected}
      onClick={onSelect}
    >
      <div className={styles.cardHeader}>
        <span className={styles.cardName}>{country.name}</span>
        <span
          className={`${styles.tierPill} ${
            country.priority_tier === 'primary' ? styles.tierPrimary : styles.tierNice
          }`}
        >
          {TIER_LABEL[country.priority_tier]}
        </span>
      </div>
      <div className={styles.blocks}>
        <div>
          <div className={styles.blockLabel}>Work visa</div>
          <div className={styles.blockValue}>{country.visa_summary}</div>
        </div>
        <div>
          <div className={styles.blockLabel}>PR path</div>
          <div className={styles.blockValue}>{country.pr_summary}</div>
        </div>
        <div>
          <div className={styles.blockLabel}>Citizenship</div>
          <div className={styles.blockValue}>{country.citizenship_summary}</div>
        </div>
      </div>
      <div className={styles.cardFooter}>
        <span className={styles.registryNote}>{country.registry_name}</span>
        <span className={styles.verified}>✓ {country.verified_at}</span>
      </div>
    </button>
  )
}
