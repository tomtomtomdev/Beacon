import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Globe as GlobeIcon } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { fetchCountries } from '../api/countries'
import type { Country } from '../api/types'
import { JobsPane } from '../jobs/JobsPane'
import { PRIORITY_TIER_LABEL } from '../jobs/taxonomy'
import styles from './CountriesPage.module.css'
import { Globe } from './Globe'
import { PanelTabs, type Panel } from './PanelTabs'
import { SourceHealth } from './SourceHealth'
import { useIdleTour } from './useIdleTour'

export function CountriesPage() {
  const { data: countries, isPending, isError } = useQuery({
    queryKey: ['countries'],
    queryFn: fetchCountries,
  })

  // The selected country is a URL param (?focus=CODE) — shareable, and now a *filter* rather
  // than a gate: it seeds the country filter and the relocation legend, and no longer decides
  // what kind of thing the side panel is. That is ?panel=, below.
  const [searchParams, setSearchParams] = useSearchParams()
  const focus = searchParams.get('focus')
  const selectedCountry = focus ? countries?.find((c) => c.code === focus) : undefined
  const panel: Panel = searchParams.get('panel') === 'markets' ? 'markets' : 'jobs'

  const setPanel = (next: Panel) =>
    setSearchParams(
      (params) => {
        // Jobs is the default, so it is the absent value — a shared URL stays clean.
        if (next === 'markets') params.set('panel', 'markets')
        else params.delete('panel')
        return params
      },
      { replace: true },
    )

  // Selecting a country seeds the country filter and shows that market's jobs. It deliberately
  // does **not** touch ?status= any more: forcing status=all moved the list out from under the
  // reader on every beacon tap. Selection is purely additive; clearing drops the filter only.
  const setFocus = (code: string | null) =>
    setSearchParams(
      (params) => {
        params.delete('country')
        params.delete('focus')
        if (code) {
          params.set('focus', code)
          params.append('country', code)
          // Picking a market is a request to see its jobs, wherever the pick came from.
          params.delete('panel')
        }
        return params
      },
      { replace: true },
    )

  // Left alone, the page walks the markets by itself — a lit beacon field rather than a dead
  // screen. Any pointer, key or scroll hands control straight back (see useIdleTour).
  //
  // The tour drives the *globe* and nothing else. It used to write ?focus=, which was harmless
  // while the panel showed visa cards and intolerable now the panel shows the job list: it
  // would take the list away from a reader every 9s and never return to the unfiltered view.
  const codes = useMemo(() => countries?.map((c) => c.code) ?? [], [countries])
  const [touredCode, setTouredCode] = useState<string | null>(null)
  const touring = useIdleTour({
    // Resume from wherever the user left off, then from wherever the tour got to.
    current: touredCode ?? focus,
    codes,
    onAdvance: setTouredCode,
  })
  // What is *lit* and what is *filtered* stop being the same fact.
  const highlight = touring ? touredCode : focus

  const selectCountry = (code: string | null) => {
    // A real selection re-seeds the rotation, so the tour does not resume from a stale market.
    setTouredCode(null)
    setFocus(code)
  }

  return (
    <main className={styles.main}>
      <header className={styles.header}>
        <h1 className={styles.h1}>Open roles &amp; target markets</h1>
        <p className={styles.subtitle}>
          Every market&rsquo;s live postings, sponsor-tier first. Tap a beacon to narrow to one
          market; Markets holds the visa reference, as-known Jan 2026 — thresholds and timelines
          change.
        </p>
      </header>

      {isError && <p className={styles.state}>Could not reach the Beacon API.</p>}
      {isPending && <p className={styles.state}>Loading…</p>}

      {countries && (
        <div className={styles.row}>
          <section className={styles.geoPanel}>
            <Globe
              countries={countries}
              selectedCode={focus}
              highlightCode={highlight}
              onSelect={selectCountry}
            />
            <div className={styles.geoTop}>
              <div className={styles.geoTitleGroup}>
                <GlobeIcon size={18} aria-hidden />
                <span className={styles.geoTitle}>Target geography</span>
                <span className={styles.geoHint}>drag to rotate · tap a beacon</span>
              </div>
              {/* The origin pin is amber while every other pin is teal or grey, so the legend
                  names all three — a colour on the globe that the legend does not explain is a
                  colour the viewer has to guess at. Home leads, as it does in the card stack. */}
              <div className={styles.legend} data-testid="globe-legend">
                <span className={styles.legendItem}>
                  <span className={`${styles.legendDot} ${styles.dotHome}`} /> Home
                </span>
                <span className={styles.legendItem}>
                  <span className={`${styles.legendDot} ${styles.dotPrimary}`} /> Primary target
                </span>
                <span className={styles.legendItem}>
                  <span className={`${styles.legendDot} ${styles.dotNice}`} /> Nice-to-have
                </span>
              </div>
            </div>
            <div className={styles.geoCaption}>
              live beacon field · {countries.length} markets
              {touring && <span className={styles.touring}>· auto-touring — move to take over</span>}
            </div>
            <SourceHealth />
          </section>

          <aside className={`${styles.sidePanel} bk-scroll`}>
            <PanelTabs panel={panel} onPanelChange={setPanel} />
            {panel === 'jobs' ? (
              <JobsPane country={selectedCountry} onBack={() => selectCountry(null)} />
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
                      onSelect={() => selectCountry(country.code)}
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

// Keyed off the tier rather than a ternary, so a third value cannot silently fall through to
// the "nice-to-have" branch the way 'home' did before it had a class of its own.
const TIER_PILL_CLASS: Record<Country['priority_tier'], string> = {
  home: styles.tierHome,
  primary: styles.tierPrimary,
  nice_to_have: styles.tierNice,
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
        <span className={`${styles.tierPill} ${TIER_PILL_CLASS[country.priority_tier]}`}>
          {PRIORITY_TIER_LABEL[country.priority_tier]}
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
