import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft } from 'lucide-react'
import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchJobs, patchJobStatus, type SortBy, type StatusView } from '../api/jobs'
import { fetchCountries } from '../api/countries'
import { fetchMarkets } from '../api/markets'
import { fetchResumes } from '../api/resumes'
import type { Country, SponsorTier, UserStatus } from '../api/types'
import { FilterBar } from './FilterBar'
import { JobDrawer } from './JobDrawer'
import { JobList } from './JobList'
import styles from './JobsPage.module.css'
import { StatusTabs } from './StatusTabs'
import { PRIORITY_TIER_LABEL, countryName } from './taxonomy'

const STATUS_VIEWS: readonly StatusView[] = ['new', 'starred', 'all', 'hidden']

// Per-view empty states (Beacon-2 §2 jobs pane).
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

// The Jobs list is not its own route — it renders inside the Countries side panel, beside the
// globe, once a country is selected. `country` is the selected market (drives the reference
// legend); `onBack` clears the selection and returns to the all-markets card stack.
export function JobsPane({ country, onBack }: { country?: Country; onBack: () => void }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const q = searchParams.get('q') ?? ''
  const countries = searchParams.getAll('country')
  const categories = searchParams.getAll('category')
  const levels = searchParams.getAll('level')
  const tiers = searchParams.getAll('sponsor_tier') as SponsorTier[]
  // The active resume (server-owned singleton) drives ?resume= scoring — a soft, opt-in signal.
  const { data: resumes } = useQuery({ queryKey: ['resumes'], queryFn: fetchResumes })
  // Same ['countries'] key the drawer and the Countries view already use, so the query cache
  // is the sharing mechanism and this costs no extra request.
  const { data: markets } = useQuery({ queryKey: ['countries'], queryFn: fetchCountries })
  // /markets is the live rollup (open jobs per country, split against §4) — deliberately not a
  // field on /countries, which is the seeded visa reference and must not change every poll.
  const { data: coverage } = useQuery({ queryKey: ['markets'], queryFn: fetchMarkets })
  const activeResume = resumes?.find((resume) => resume.active) ?? null
  const resumeId = activeResume?.id ?? null

  // sort=match only means anything with a resume; without one it decays to the default so the
  // control never lies (the Fit segment is hidden anyway when no resume is active).
  const sortParam = searchParams.get('sort')
  const requestedSort: SortBy =
    sortParam === 'date' ? 'date' : sortParam === 'match' ? 'match' : 'tier'
  const sort: SortBy = requestedSort === 'match' && resumeId === null ? 'tier' : requestedSort
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
        // 'tier' is the API default — omit it; 'date'/'match' are explicit.
        if (value === 'tier') params.delete('sort')
        else params.set('sort', value)
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
  // Paged, because the API serves 50 rows and the corpus holds 9,130 open canonical jobs. The
  // offset is the page param, never part of the key — a filter change starts a new list, but
  // paging deeper into the same one must not.
  const { data, isPending, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useInfiniteQuery({
      queryKey: ['jobs', q, countries, categories, levels, tiers, sort, view, resumeId],
      queryFn: ({ pageParam }) =>
        fetchJobs({
          q,
          countries,
          categories,
          levels,
          tiers,
          sort,
          status: view,
          resume: resumeId,
          offset: pageParam,
        }),
      initialPageParam: 0,
      getNextPageParam: (lastPage, pages) => {
        const loaded = pages.reduce((rows, page) => rows + page.jobs.length, 0)
        // A page that came back short of what `total` promised means the corpus moved under
        // us; stopping is the honest response to that, not requesting the same offset forever.
        if (loaded >= lastPage.total || lastPage.jobs.length === 0) return undefined
        return loaded
      },
    })

  // One flattened list feeds the rows, the drawer's lookup and its fit hand-down — three
  // readers that must not disagree about which jobs are on screen.
  const jobs = useMemo(() => data?.pages.flatMap((page) => page.jobs) ?? [], [data])
  // The server's count of everything matching these filters, not the number of rows fetched.
  const total = data?.pages[0]?.total ?? null

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
    // Opening a `new` job marks it seen (Beacon-2 §2 status workflow).
    const job = jobs.find((candidate) => candidate.id === id)
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

  const heading =
    countries.length === 1 ? `Jobs · ${countryName(countries[0], markets ?? [])}` : 'Jobs'
  const sortLabel = sort === 'tier' ? 'sponsor tier' : sort === 'date' ? 'date' : 'fit'
  const resultLabel =
    total === null
      ? 'Loading…'
      : `${view === 'all' ? '' : `${view[0].toUpperCase()}${view.slice(1)} · `}` +
        `${total.toLocaleString()}${total === 1 ? ' posting' : ' postings'} · sorted by ${sortLabel}`

  return (
    <section className={styles.pane}>
      <header className={styles.header}>
        {/* Only when there is a filter to clear. The panel is no longer gated on a selection,
            so on the default view this was a control that undid nothing, sitting above a
            heading that already read "Jobs". */}
        {countries.length > 0 && (
          <button type="button" className={styles.back} onClick={onBack}>
            <ChevronLeft size={14} aria-hidden />
            All markets
          </button>
        )}
        <h1 className={styles.h1}>{heading}</h1>
        <p className={styles.subtitle}>{resultLabel}</p>
      </header>

      {country?.priority_tier === 'home' && <HomeMarketBlock name={country.name} />}

      {country && country.priority_tier !== 'home' && (
        <div className={styles.reference}>
          <div className={styles.refHead}>
            <span className={styles.refTitle}>{country.name} — relocation reference</span>
            <span
              className={`${styles.tierPill} ${
                country.priority_tier === 'primary' ? styles.tierPrimary : styles.tierNice
              }`}
            >
              {PRIORITY_TIER_LABEL[country.priority_tier]}
            </span>
          </div>
          <div className={styles.refBlocks}>
            <div>
              <div className={styles.refLabel}>Work visa</div>
              <div className={styles.refValue}>{country.visa_summary}</div>
            </div>
            <div>
              <div className={styles.refLabel}>PR path</div>
              <div className={styles.refValue}>{country.pr_summary}</div>
            </div>
            <div>
              <div className={styles.refLabel}>Citizenship</div>
              <div className={styles.refValue}>{country.citizenship_summary}</div>
            </div>
          </div>
          <div className={styles.refVerified}>verified {country.verified_at}</div>
        </div>
      )}

      <div className={styles.filterBar}>
        <div className={styles.toolbar}>
          <StatusTabs view={view} onViewChange={setView} />
        </div>

        <FilterBar
          q={q}
          markets={markets ?? []}
          coverage={coverage ?? null}
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
          showFitSort={resumeId !== null}
        />
      </div>

      <div className={styles.listWrap}>
        {isError && <p className={styles.stateText}>Could not reach the Beacon API.</p>}
        {!isError && !isPending && jobs.length === 0 && (
          <div className={styles.empty}>
            <p className={styles.emptyTitle}>{EMPTY_TEXT[view].title}</p>
            <p className={styles.stateText}>{EMPTY_TEXT[view].subtitle}</p>
          </div>
        )}
        {jobs.length > 0 && (
          <JobList
            jobs={jobs}
            onOpen={openJob}
            onSetStatus={(id, status) => statusMutation.mutate({ id, status })}
          />
        )}
        {hasNextPage && (
          <button
            type="button"
            className={styles.loadMore}
            onClick={() => void fetchNextPage()}
            disabled={isFetchingNextPage}
          >
            {isFetchingNextPage
              ? 'Loading…'
              : `Load more · ${jobs.length.toLocaleString()} of ${total?.toLocaleString() ?? '?'}`}
          </button>
        )}
      </div>

      {openJobId !== null && (
        <JobDrawer
          jobId={openJobId}
          // The row is already scored (page-bounded, §11) — hand its fit down so the drawer's
          // Fit card needs no extra fetch; null when no resume is active.
          matchScore={jobs.find((job) => job.id === openJobId)?.match_score ?? null}
          // The active resume id drives the drawer's on-demand "Assess fit" LLM deep-match (§11).
          resumeId={resumeId}
          onClose={closeJob}
          onSetStatus={(id, status) => statusMutation.mutate({ id, status })}
        />
      )}
    </section>
  )
}

// DESIGN §1: the home-market substitute for the relocation legend. Every field the legend
// carries — work visa, PR path, citizenship, verified date — is inapplicable here, and
// rendering them empty or as "n/a" would read as missing data rather than as an absent
// question. What replaces them is the one line that matters and the role focus (SPEC §4).
function HomeMarketBlock({ name }: { name: string }) {
  return (
    <div className={styles.homeMarket}>
      <div className={styles.refHead}>
        <span className={styles.refTitle}>{name} — home market</span>
        <span className={`${styles.tierPill} ${styles.tierHome}`}>Home</span>
      </div>
      <p className={styles.homeCopy}>
        You already have the right to work here. These roles need no visa, no sponsor and no
        registry check.
      </p>
      <div>
        <div className={styles.refLabel}>Focus</div>
        <div className={styles.refValue}>iOS · Backend (Java, Python) · AI/ML</div>
      </div>
    </div>
  )
}
