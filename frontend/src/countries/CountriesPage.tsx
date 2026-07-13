import { useQuery } from '@tanstack/react-query'
import { Globe as GlobeIcon } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { fetchCountries } from '../api/countries'
import type { Country } from '../api/types'
import { JobsPane } from '../jobs/JobsPane'
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

  // The selected country is a URL param (?focus=CODE) — shareable, and the pivot that decides
  // globe auto-focus + whether the side panel shows the jobs pane (set) or the card stack (unset).
  const [searchParams, setSearchParams] = useSearchParams()
  const focus = searchParams.get('focus')
  const selectedCountry = focus ? countries?.find((c) => c.code === focus) : undefined

  // Selecting a country seeds the country filter + opens the jobs pane on the "All" status view;
  // clearing (ocean tap, back button) returns to the card stack.
  const setFocus = (code: string | null) =>
    setSearchParams(
      (params) => {
        params.delete('country')
        params.delete('status')
        params.delete('focus')
        if (code) {
          params.set('focus', code)
          params.append('country', code)
          params.set('status', 'all')
        }
        return params
      },
      { replace: true },
    )

  return (
    <main className={styles.main}>
      <header className={styles.header}>
        <h1 className={styles.h1}>Country &amp; visa reference</h1>
        <p className={styles.subtitle}>
          As-known Jan 2026 — thresholds and timelines change. Tap a beacon to inspect that market
          and its live postings in the panel beside the globe.
        </p>
      </header>

      {isError && <p className={styles.state}>Could not reach the Beacon API.</p>}
      {isPending && <p className={styles.state}>Loading…</p>}

      {countries && (
        <div className={styles.row}>
          <section className={styles.geoPanel}>
            <Globe countries={countries} selectedCode={focus} onSelect={setFocus} />
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
            <div className={styles.geoCaption}>live beacon field · {countries.length} markets</div>
            <SourceHealth />
          </section>

          <aside className={`${styles.sidePanel} bk-scroll`}>
            {focus ? (
              <JobsPane country={selectedCountry} onBack={() => setFocus(null)} />
            ) : (
              <div className={styles.markets}>
                <div className={styles.marketsCaption}>
                  {countries.length} markets · tap a beacon or a card
                </div>
                <div className={styles.cardStack}>
                  {countries.map((country) => (
                    <CountryCard
                      key={country.code}
                      country={country}
                      onSelect={() => setFocus(country.code)}
                    />
                  ))}
                </div>
              </div>
            )}
          </aside>
        </div>
      )}
    </main>
  )
}

// Static source-health summary folded into the globe legend (Beacon-2: "static summary widget").
// TODO: wire live counts + last-poll time from GET /companies/health rollup.
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

// Compact country card in the narrow side panel (Beacon-2 §1): name + tier, Work visa + PR path
// blocks (Citizenship moves to the reference legend on selection), registry note + verified date.
function CountryCard({ country, onSelect }: { country: Country; onSelect: () => void }) {
  return (
    <button
      type="button"
      className={styles.card}
      aria-label={`${country.name} details`}
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
      </div>
      <div className={styles.cardFooter}>
        <span className={styles.registryNote}>{country.registry_name}</span>
        <span className={styles.verified}>✓ {country.verified_at}</span>
      </div>
    </button>
  )
}
