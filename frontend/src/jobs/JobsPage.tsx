import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { fetchJobs, type SortBy } from '../api/jobs'
import type { SponsorTier } from '../api/types'
import { FilterBar } from './FilterBar'
import { JobTable } from './JobTable'
import styles from './JobsPage.module.css'

export function JobsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const q = searchParams.get('q') ?? ''
  const countries = searchParams.getAll('country')
  const tiers = searchParams.getAll('sponsor_tier') as SponsorTier[]
  const sort: SortBy = searchParams.get('sort') === 'date' ? 'date' : 'tier'

  const setQ = (value: string) => {
    setSearchParams(
      (params) => {
        if (value) params.set('q', value)
        else params.delete('q')
        return params
      },
      { replace: true },
    )
  }

  const toggleCountry = (code: string) => {
    setSearchParams(
      (params) => {
        const selected = new Set(params.getAll('country'))
        if (selected.has(code)) selected.delete(code)
        else selected.add(code)
        params.delete('country')
        for (const country of selected) params.append('country', country)
        return params
      },
      { replace: true },
    )
  }

  const toggleTier = (tier: SponsorTier) => {
    setSearchParams(
      (params) => {
        const selected = new Set(params.getAll('sponsor_tier'))
        if (selected.has(tier)) selected.delete(tier)
        else selected.add(tier)
        params.delete('sponsor_tier')
        for (const value of selected) params.append('sponsor_tier', value)
        return params
      },
      { replace: true },
    )
  }

  const setSort = (value: SortBy) => {
    setSearchParams(
      (params) => {
        if (value === 'date') params.set('sort', 'date')
        else params.delete('sort')
        return params
      },
      { replace: true },
    )
  }

  const { data, isPending, isError } = useQuery({
    queryKey: ['jobs', q, countries, tiers, sort],
    queryFn: () => fetchJobs({ q, countries, tiers, sort }),
  })

  return (
    <main className={styles.main}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.h1}>Jobs</h1>
          <p className={styles.subtitle}>
            {data ? `${data.total} postings · sorted by sponsor tier` : 'Loading…'}
          </p>
        </div>
        <div className={styles.legend}>
          <span className={styles.legendItem}>
            <span className={`${styles.legendDot} ${styles.dotYes}`} /> Sponsors
          </span>
          <span className={styles.legendItem}>
            <span className={`${styles.legendDot} ${styles.dotRegistry}`} /> Registry
          </span>
          <span className={styles.legendItem}>
            <span className={`${styles.legendDot} ${styles.dotUnknown}`} /> Unknown
          </span>
          <span className={styles.legendItem}>
            <span className={`${styles.legendDot} ${styles.dotNo}`} /> No
          </span>
        </div>
      </header>

      <FilterBar
        q={q}
        countries={countries}
        tiers={tiers}
        sort={sort}
        onQChange={setQ}
        onToggleCountry={toggleCountry}
        onToggleTier={toggleTier}
        onSortChange={setSort}
      />

      {isError && <p className={styles.stateText}>Could not reach the Beacon API.</p>}
      {!isError && !isPending && data && data.jobs.length === 0 && (
        <div className={styles.empty}>
          <p className={styles.emptyTitle}>No postings match these filters</p>
          <p className={styles.stateText}>Clear the keyword or country filters to browse more.</p>
        </div>
      )}
      {data && data.jobs.length > 0 && <JobTable jobs={data.jobs} />}
    </main>
  )
}
