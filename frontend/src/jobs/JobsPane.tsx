import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { fetchJobs, patchJobStatus, type SortBy, type StatusView } from '../api/jobs'
import type { SponsorTier, UserStatus } from '../api/types'
import { FilterBar } from './FilterBar'
import { JobDrawer } from './JobDrawer'
import styles from './JobsPage.module.css'
import { JobTable } from './JobTable'
import { StatusTabs } from './StatusTabs'
import { countryName } from './taxonomy'

const STATUS_VIEWS: readonly StatusView[] = ['new', 'starred', 'all', 'hidden']

// Per-view empty states (DESIGN §2 jobs pane).
const EMPTY_TEXT: Record<StatusView, { title: string; subtitle: string }> = {
  new: {
    title: "You're all caught up",
    subtitle: 'No new postings under these filters. Switch to All to browse everything.',
  },
  starred: { title: 'No starred postings yet', subtitle: 'Star a job to keep it here.' },
  all: {
    title: 'No postings match these filters',
    subtitle: 'Clear the keyword or country filters to browse more.',
  },
  hidden: { title: 'Nothing hidden', subtitle: 'Jobs you hide land here, recoverable anytime.' },
}

// The Jobs list is not its own route — it renders inside the Countries view, below the globe,
// once a country is selected. `onBack` clears the selection and returns to the card grid.
export function JobsPane({ onBack }: { onBack: () => void }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const q = searchParams.get('q') ?? ''
  const countries = searchParams.getAll('country')
  const categories = searchParams.getAll('category')
  const levels = searchParams.getAll('level')
  const tiers = searchParams.getAll('sponsor_tier') as SponsorTier[]
  const sort: SortBy = searchParams.get('sort') === 'date' ? 'date' : 'tier'
  // Selecting a country opens this pane with status=all (browse everything for that country).
  const statusParam = searchParams.get('status')
  const view: StatusView =
    statusParam && STATUS_VIEWS.includes(statusParam as StatusView)
      ? (statusParam as StatusView)
      : 'new'

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

  // One toggle for every repeated multi-select param (country/category/level/sponsor_tier).
  const toggleParam = (param: string, value: string) => {
    setSearchParams(
      (params) => {
        const selected = new Set(params.getAll(param))
        if (selected.has(value)) selected.delete(value)
        else selected.add(value)
        params.delete(param)
        for (const item of selected) params.append(param, item)
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

  const setView = (value: StatusView) => {
    setSearchParams(
      (params) => {
        if (value === 'new') params.delete('status')
        else params.set('status', value)
        return params
      },
      { replace: true },
    )
  }

  // The open drawer is a URL param (?job=id) so a deep-linked job is shareable and the
  // browser Back button closes it — same rationale as the filter/view params.
  const jobParam = searchParams.get('job')
  const openJobId = jobParam ? Number(jobParam) : null

  const queryClient = useQueryClient()
  const { data, isPending, isError } = useQuery({
    queryKey: ['jobs', q, countries, categories, levels, tiers, sort, view],
    queryFn: () => fetchJobs({ q, countries, categories, levels, tiers, sort, status: view }),
  })

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: UserStatus }) => patchJobStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['job'] })
    },
  })

  const openJob = (id: number) => {
    setSearchParams(
      (params) => {
        params.set('job', String(id))
        return params
      },
      { replace: true },
    )
    // Opening a `new` job marks it seen (DESIGN §2 status workflow).
    const job = data?.jobs.find((candidate) => candidate.id === id)
    if (job?.user_status === 'new') statusMutation.mutate({ id, status: 'seen' })
  }

  const closeJob = () => {
    setSearchParams(
      (params) => {
        params.delete('job')
        return params
      },
      { replace: true },
    )
  }

  const heading = countries.length === 1 ? `Jobs · ${countryName(countries[0])}` : 'Jobs'
  const resultLabel = data
    ? `${view === 'all' ? '' : `${view[0].toUpperCase()}${view.slice(1)} · `}${data.jobs.length}` +
      `${data.jobs.length === 1 ? ' posting' : ' postings'} · sorted by ` +
      (sort === 'tier' ? 'sponsor tier' : 'date')
    : 'Loading…'

  return (
    <section className={styles.pane}>
      <header className={styles.header}>
        <div>
          <button type="button" className={styles.back} onClick={onBack}>
            <ChevronLeft size={14} aria-hidden />
            All countries
          </button>
          <h1 className={styles.h1}>{heading}</h1>
          <p className={styles.subtitle}>{resultLabel}</p>
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

      <div className={styles.filterBar}>
        <div className={styles.toolbar}>
          <StatusTabs view={view} onViewChange={setView} />
        </div>

        <FilterBar
          q={q}
          countries={countries}
          categories={categories}
          levels={levels}
          tiers={tiers}
          sort={sort}
          onQChange={setQ}
          onToggleCountry={(code) => toggleParam('country', code)}
          onToggleCategory={(value) => toggleParam('category', value)}
          onToggleLevel={(value) => toggleParam('level', value)}
          onToggleTier={(tier) => toggleParam('sponsor_tier', tier)}
          onSortChange={setSort}
        />
      </div>

      {isError && <p className={styles.stateText}>Could not reach the Beacon API.</p>}
      {!isError && !isPending && data && data.jobs.length === 0 && (
        <div className={styles.empty}>
          <p className={styles.emptyTitle}>{EMPTY_TEXT[view].title}</p>
          <p className={styles.stateText}>{EMPTY_TEXT[view].subtitle}</p>
        </div>
      )}
      {data && data.jobs.length > 0 && (
        <JobTable
          jobs={data.jobs}
          onOpen={openJob}
          onSetStatus={(id, status) => statusMutation.mutate({ id, status })}
        />
      )}

      {openJobId !== null && (
        <JobDrawer
          jobId={openJobId}
          onClose={closeJob}
          onSetStatus={(id, status) => statusMutation.mutate({ id, status })}
        />
      )}
    </section>
  )
}
