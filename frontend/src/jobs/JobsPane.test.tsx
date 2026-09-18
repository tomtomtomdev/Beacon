import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type {
  Country,
  JobsPageResponse,
  MarketCoverage,
  PriorityTier,
  Resume,
} from '../api/types'
import { JobsPane } from './JobsPane'

const payload: JobsPageResponse = {
  total: 2,
  jobs: [
    {
      id: 1,
      title: 'Swift Engineer',
      company: 'Spotify',
      url: 'https://example.test/1',
      location: 'Stockholm, Sweden',
      country: 'SE',
      city: 'Stockholm',
      categories: ['ios', 'ai-ml'],
      level: 'senior',
      posted_at: '2026-07-01T00:00:00+00:00',
      sponsor_tier: 'unknown',
      user_status: 'new',
      closed_at: null,
    },
    {
      id: 2,
      title: 'Platform Engineer',
      company: 'Tines',
      url: 'https://example.test/2',
      location: 'Dublin, Ireland (Hybrid)',
      country: 'IE',
      city: 'Dublin',
      categories: ['backend'],
      level: null,
      posted_at: null,
      sponsor_tier: 'unknown',
      user_status: 'starred',
      closed_at: null,
    },
  ],
}

// One live row and one the closed-posting sweep delisted. SPEC §5 keeps a closed posting and
// renders it greyed rather than dropping it — it is evidence about a company that was hiring.
const withClosedPayload: JobsPageResponse = {
  total: 2,
  jobs: [
    payload.jobs[0],
    {
      ...payload.jobs[1],
      id: 3,
      title: 'Delisted Engineer',
      company: 'SAP',
      closed_at: '2026-08-20T05:00:00+00:00',
    },
  ],
}

// The scored variant the API returns only when ?resume= names an active resume (§11).
const scoredPayload: JobsPageResponse = {
  total: 2,
  jobs: [
    {
      ...payload.jobs[0],
      match_score: {
        overall: 96,
        skills_score: 100,
        level_score: 80,
        sponsor_score: 40,
        matched_skills: ['swift', 'ios'],
        missing_skills: ['kotlin'],
      },
    },
    {
      ...payload.jobs[1],
      match_score: {
        overall: 41,
        skills_score: 20,
        level_score: 70,
        sponsor_score: 40,
        matched_skills: [],
        missing_skills: ['go'],
      },
    },
  ],
}

const activeResume: Resume = {
  id: 7,
  label: 'My CV',
  active: true,
  created_at: '2026-07-15T00:00:00+00:00',
  resume_hash: 'abc123',
  profile: {
    categories: ['ios'],
    level: 'senior',
    years: 8,
    skills: ['swift', 'ios'],
    target_countries: ['SE'],
  },
}

// The markets /countries serves. Only code/name/priority_tier matter to the Jobs pane — the
// visa prose belongs to the reference card, so it is filled but never asserted on here.
const market = (code: string, name: string, priority_tier: PriorityTier): Country => ({
  code,
  name,
  priority_tier,
  visa_summary: 'visa',
  pr_summary: 'pr',
  citizenship_summary: 'citizenship',
  registry_name: 'registry',
  verified_at: '2026-01-15',
  source_url: 'https://example.test/source',
})

// In the server's order: home first, then primary, then alphabetical within tier
// (SqliteCountryRepo.get_all) — the pane renders the list as served, it does not re-sort.
const markets: Country[] = [
  market('ID', 'Indonesia', 'home'),
  market('AU', 'Australia', 'primary'),
  market('CA', 'Canada', 'primary'),
  market('IE', 'Ireland', 'primary'),
  market('JP', 'Japan', 'primary'),
  market('NL', 'Netherlands', 'primary'),
  market('SG', 'Singapore', 'primary'),
  market('US', 'United States', 'primary'),
  market('CH', 'Switzerland', 'nice_to_have'),
  market('DK', 'Denmark', 'nice_to_have'),
  market('NO', 'Norway', 'nice_to_have'),
  market('SE', 'Sweden', 'nice_to_have'),
]

// GET /markets — the open-job histogram split against SPEC §4. Target markets come from the
// reference and may read zero; other markets come from the corpus, so a zero cannot exist.
const coverage: MarketCoverage = {
  target_markets: [
    { code: 'ID', open_jobs: 12 },
    { code: 'SE', open_jobs: 393 },
    { code: 'NO', open_jobs: 0 },
  ],
  other_markets: [
    { code: 'IN', open_jobs: 355 },
    { code: 'DE', open_jobs: 198 },
  ],
}

const fetchMock = vi.fn()

// Data-driven boundary mock: /resumes returns the resume list; a /jobs request that carries
// ?resume= gets scored rows (mirrors the backend), everything else the unscored base.
let jobsPayload: JobsPageResponse = payload
let resumesPayload: Resume[] = []
let countriesPayload: Country[] = markets
let coveragePayload: MarketCoverage = coverage

function ok(body: unknown): Promise<Response> {
  return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response)
}

function renderPage(initialUrl = '/', onBack: () => void = () => {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialUrl]}>
        <JobsPane onBack={onBack} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

// Every /jobs list request the component made (not detail/status), newest last.
function jobListUrls(): string[] {
  return fetchMock.mock.calls
    .map((call) => String(call[0]))
    .filter((u) => u === '/jobs' || u.startsWith('/jobs?'))
}

function firstJobsUrl(): string {
  return jobListUrls()[0]
}

beforeEach(() => {
  jobsPayload = payload
  resumesPayload = []
  countriesPayload = markets
  coveragePayload = coverage
  fetchMock.mockImplementation((url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url)
    const method = init?.method ?? 'GET'
    if (u === '/resumes' && method === 'GET') return ok(resumesPayload)
    if (u === '/countries') return ok(countriesPayload)
    if (u === '/markets') return ok(coveragePayload)
    if (u.startsWith('/jobs/')) return ok({}) // detail / status PATCH — overridden where asserted
    if ((u === '/jobs' || u.startsWith('/jobs?')) && u.includes('resume=')) return ok(scoredPayload)
    return ok(jobsPayload)
  })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('JobsPane', () => {
  it('renders a row per job from the API', async () => {
    renderPage()

    expect(await screen.findByText('Swift Engineer')).toBeInTheDocument()
    expect(screen.getByText('Platform Engineer')).toBeInTheDocument()
    expect(screen.getByText('Spotify')).toBeInTheDocument()
    expect(screen.getByText(/2 postings/)).toBeInTheDocument()
  })

  it('typing a keyword refetches with q', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Swift Engineer')

    await user.type(screen.getByPlaceholderText(/search title, company/i), 'swift')

    await waitFor(() => {
      expect(jobListUrls().some((u) => u.includes('q=swift'))).toBe(true)
    })
  })

  it('selecting countries refetches with repeated country params', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Swift Engineer')

    await user.click(screen.getByRole('button', { name: /country/i }))
    await user.click(screen.getByRole('checkbox', { name: /sweden/i }))
    await user.click(screen.getByRole('checkbox', { name: /ireland/i }))

    await waitFor(() => {
      expect(jobListUrls().some((u) => u.includes('country=SE') && u.includes('country=IE'))).toBe(
        true,
      )
    })
  })

  // 18a: the filter menu is built from /countries, not from a second hardcoded copy of the
  // country table. GB is the case that exposed it — 480 open jobs the API can filter and the
  // UI could not reach, because a market absent from the frontend array has no checkbox.
  it('lists every market the API serves, including one the frontend never hardcoded', async () => {
    const user = userEvent.setup()
    countriesPayload = [...markets, market('GB', 'United Kingdom', 'primary')]
    renderPage()
    await screen.findByText('Swift Engineer')

    await user.click(screen.getByRole('button', { name: /country/i }))

    const gb = await screen.findByRole('checkbox', { name: /united kingdom/i })
    await user.click(gb)
    await waitFor(() => {
      expect(jobListUrls().some((u) => u.includes('country=GB'))).toBe(true)
    })
  })

  // 20d: the countries holding open jobs that SPEC §4 has never assessed. /jobs already took an
  // arbitrary ?country=, so every one of those jobs was already served — what was missing was
  // the way to ask for them. Measured against the live DB on 2026-09-18: 47 countries, 1,844
  // open canonical jobs, led by IN 355 · MY 235 · TH 215 · DE 198.
  async function openCountryMenu(): Promise<HTMLElement> {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Swift Engineer')
    await user.click(screen.getByRole('button', { name: /country/i }))
    return screen.getByRole('group', { name: 'Filter by country' })
  }

  it('groups the markets §4 never assessed under their own heading', async () => {
    const menu = within(await openCountryMenu())

    // The heading is load-bearing: it is what stops a DE row reading as a relocation target.
    expect(menu.getByText('Other markets')).toBeInTheDocument()
    expect(menu.getByText(/not relocation targets/i)).toBeInTheDocument()
  })

  it('names an other market rather than showing its bare code', async () => {
    // These countries have no name source in the repo, and a 47-row code→name table here would
    // be a second source of truth for something the browser already ships as Intl.DisplayNames.
    const menu = within(await openCountryMenu())

    expect(menu.getByRole('checkbox', { name: /germany/i })).toBeInTheDocument()
    expect(menu.getByRole('checkbox', { name: /india/i })).toBeInTheDocument()
  })

  it('checking an other market filters the list', async () => {
    const user = userEvent.setup()
    const menu = within(await openCountryMenu())

    await user.click(menu.getByRole('checkbox', { name: /germany/i }))

    await waitFor(() => {
      expect(jobListUrls().some((u) => u.includes('country=DE'))).toBe(true)
    })
  })

  it('renders every market open count from /markets, including an assessed market at zero', async () => {
    // Slice 19's rule, and it binds here: a number on screen is derived or it is not there. A
    // target market is a reference fact and keeps its row at zero; an other market is a corpus
    // fact, so a zero one cannot exist.
    const menu = within(await openCountryMenu())

    expect(menu.getByRole('checkbox', { name: /sweden/i })).toHaveAccessibleName(/393/)
    expect(menu.getByRole('checkbox', { name: /norway/i })).toHaveAccessibleName(/\b0\b/)
    expect(menu.getByRole('checkbox', { name: /germany/i })).toHaveAccessibleName(/198/)
  })

  it('gives an other market no priority-tier glyph — none was ever assessed', async () => {
    // COUNTRY_BADGE is keyed by priority_tier, a §4 concept these countries do not have. A grey
    // "unknown" glyph would assert a tier had been considered and found wanting.
    const menu = within(await openCountryMenu())

    const germany = menu.getByRole('checkbox', { name: /germany/i }).closest('label')
    const sweden = menu.getByRole('checkbox', { name: /sweden/i }).closest('label')

    expect(within(sweden as HTMLElement).getByText('☆')).toBeInTheDocument()
    expect(within(germany as HTMLElement).queryByText(/^[P☆⌂]$/)).not.toBeInTheDocument()
  })

  it('preselects no market at all — the default view claims nothing and hides nothing', async () => {
    const menu = within(await openCountryMenu())

    for (const box of menu.getAllByRole('checkbox')) expect(box).not.toBeChecked()
  })

  // 20e: /jobs serves 6,518 closed postings among 15,648 rows and said nothing about them, so
  // a delisted job read exactly like a live one — and the country menu's "198" opened onto 266.
  it('marks a closed posting as closed instead of serving it as though you could apply', async () => {
    jobsPayload = withClosedPayload
    renderPage()

    const closed = (await screen.findByText('Delisted Engineer')).closest(`[class*="card"]`)
    expect(within(closed as HTMLElement).getByText(/closed/i)).toBeInTheDocument()
  })

  it('leaves a live posting unmarked', async () => {
    jobsPayload = withClosedPayload
    renderPage()

    const live = (await screen.findByText('Swift Engineer')).closest(`[class*="card"]`)
    expect(within(live as HTMLElement).queryByText(/closed/i)).not.toBeInTheDocument()
  })

  it('says the country-menu counts are open postings, since the list also carries closed ones', async () => {
    const menu = within(await openCountryMenu())

    expect(menu.getByText(/open postings/i)).toBeInTheDocument()
  })

  // 21c: the sub-line read `data.jobs.length` — one page of 50 — so selecting the US reported
  // "50 postings" against a live 3,365, and the unfiltered list would have read 50 of 9,130.
  // A number on screen is derived or it is not there (slice 19), and a list you cannot page
  // past row 50 makes the derived number a different kind of lie.
  function pageOf(count: number, offset: number, total: number): JobsPageResponse {
    return {
      total,
      jobs: Array.from({ length: count }, (_, index) => ({
        ...payload.jobs[0],
        id: offset + index + 1,
        title: `Engineer ${offset + index + 1}`,
      })),
    }
  }

  function servePages(pageSize: number, total: number): void {
    fetchMock.mockImplementation((url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url)
      if ((init?.method ?? 'GET') !== 'GET') return ok({})
      if (u === '/resumes') return ok([])
      if (u === '/countries') return ok(markets)
      if (u === '/markets') return ok(coverage)
      if (u.startsWith('/jobs/')) return ok({})
      const offset = Number(new URL(u, 'http://t').searchParams.get('offset') ?? 0)
      return ok(pageOf(Math.min(pageSize, total - offset), offset, total))
    })
  }

  it('reports the server total, not the number of rows on the page', async () => {
    servePages(50, 9130)
    renderPage()

    expect(await screen.findByText(/9,130 postings/)).toBeInTheDocument()
    expect(screen.queryByText(/50 postings/)).not.toBeInTheDocument()
  })

  it('loads the next page on demand and appends it to the list', async () => {
    const user = userEvent.setup()
    servePages(50, 120)
    renderPage()
    await screen.findByText('Engineer 1')
    expect(screen.queryByText('Engineer 51')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /load more/i }))

    expect(await screen.findByText('Engineer 51')).toBeInTheDocument()
    // The first page is still there — pages append, they do not replace.
    expect(screen.getByText('Engineer 1')).toBeInTheDocument()
    expect(jobListUrls().some((u) => u.includes('offset=50'))).toBe(true)
  })

  it('offers no Load more once every row is loaded', async () => {
    servePages(50, 40)
    renderPage()
    await screen.findByText('Engineer 1')

    expect(screen.queryByRole('button', { name: /load more/i })).not.toBeInTheDocument()
  })

  it('offers no "All markets" escape when the list is already every market', async () => {
    // The back button clears the country filter. With no filter set it is a control that
    // undoes nothing, on a view whose heading already says "Jobs".
    renderPage()
    await screen.findByText('Swift Engineer')

    expect(screen.queryByRole('button', { name: /all markets/i })).not.toBeInTheDocument()
  })

  it('offers it once a country is filtered, and it asks the page to clear the selection', async () => {
    // Clearing spans both params — ?country= is this pane's, ?focus= is the page's — so the
    // button reports up rather than half-clearing. CountriesPage covers the end-to-end drop.
    const user = userEvent.setup()
    const onBack = vi.fn()
    renderPage('/?focus=SE&country=SE', onBack)
    await screen.findByText('Swift Engineer')

    await user.click(screen.getByRole('button', { name: /all markets/i }))

    expect(onBack).toHaveBeenCalledOnce()
  })

  // 22: closed postings are out of the list by default. They are kept (SPEC §5) and reachable,
  // but Sweden measured 2,669 canonical against 393 open — 86% closed — so carrying them by
  // default made a filtered list mostly dead rows.
  it('asks for no closed postings by default', async () => {
    renderPage()
    await screen.findByText('Swift Engineer')

    expect(firstJobsUrl()).not.toContain('include_closed')
  })

  it('brings them back on request, and says so in the URL', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Swift Engineer')

    await user.click(screen.getByRole('button', { name: /show closed/i }))

    await waitFor(() => {
      expect(jobListUrls().some((u) => u.includes('include_closed=true'))).toBe(true)
    })
  })

  it('reads the closed toggle from the URL, so the view is shareable', async () => {
    renderPage('/?closed=1')
    await screen.findByText('Swift Engineer')

    expect(firstJobsUrl()).toContain('include_closed=true')
    expect(screen.getByRole('button', { name: /show closed/i })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('sends no offset param on the first page, so a shared URL stays clean', async () => {
    servePages(50, 120)
    renderPage()
    await screen.findByText('Engineer 1')

    expect(firstJobsUrl()).not.toContain('offset')
  })

  it('names a served country in the heading instead of falling back to its bare code', async () => {
    countriesPayload = [...markets, market('GB', 'United Kingdom', 'primary')]
    renderPage('/?country=GB')

    expect(await screen.findByText('Jobs · United Kingdom')).toBeInTheDocument()
  })

  it('reads initial filters from the URL so filtered views are shareable', async () => {
    renderPage('/?q=swift&country=SE')

    await screen.findByText('Swift Engineer')
    expect(firstJobsUrl()).toContain('q=swift')
    expect(firstJobsUrl()).toContain('country=SE')
  })

  it('defaults to sponsor-tier sort with no sort or tier params (filter is opt-in)', async () => {
    renderPage()
    await screen.findByText('Swift Engineer')

    expect(firstJobsUrl()).not.toContain('sort=')
    expect(firstJobsUrl()).not.toContain('sponsor_tier=')
  })

  it('switching sort to Date refetches with sort=date', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Swift Engineer')

    await user.click(screen.getByRole('button', { name: 'Date' }))

    await waitFor(() => {
      expect(jobListUrls().some((u) => u.includes('sort=date'))).toBe(true)
    })
  })

  it('selecting a sponsor tier refetches with the opt-in filter param', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Swift Engineer')

    await user.click(screen.getByRole('button', { name: /filter by sponsor tier/i }))
    await user.click(screen.getByRole('checkbox', { name: /registry/i }))

    await waitFor(() => {
      expect(jobListUrls().some((u) => u.includes('sponsor_tier=registry_inferred'))).toBe(true)
    })
  })

  it('selecting a category pill refetches with the category param', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Swift Engineer')

    await user.click(screen.getByRole('button', { name: 'iOS' }))

    await waitFor(() => {
      expect(jobListUrls().some((u) => u.includes('category=ios'))).toBe(true)
    })
  })

  it('selecting a level pill refetches with the level param', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Swift Engineer')

    await user.click(screen.getByRole('button', { name: 'Senior' }))

    await waitFor(() => {
      expect(jobListUrls().some((u) => u.includes('level=senior'))).toBe(true)
    })
  })

  it('reads initial category and level filters from the URL', async () => {
    renderPage('/?category=ios&level=senior')

    await screen.findByText('Swift Engineer')
    expect(firstJobsUrl()).toContain('category=ios')
    expect(firstJobsUrl()).toContain('level=senior')
  })

  it('renders the city and level on each compact card', async () => {
    renderPage()

    await screen.findByText('Swift Engineer')
    // The compact card meta row shows city + level (categories are filters, not shown per card).
    const list = within(screen.getByTestId('job-list'))
    expect(list.getByText('Stockholm')).toBeInTheDocument()
    expect(list.getByText('SENIOR')).toBeInTheDocument() // level uppercased
  })

  it('badges a home-market job as needing no visa', async () => {
    // SPEC §3/§6: an ID job carries not_required, the fifth tier — the one that says the
    // sponsorship question does not arise, rather than answering it.
    jobsPayload = {
      total: 1,
      jobs: [{ ...payload.jobs[0], id: 3, country: 'ID', sponsor_tier: 'not_required' }],
    }

    renderPage()

    const list = within(await screen.findByTestId('job-list'))
    expect(list.getByText('No visa needed')).toBeInTheDocument()
  })

  it('offers all five sponsor tiers in the filter, none pre-selected', async () => {
    // CLAUDE.md: tier filtering stays opt-in — no UI state ships with chips pre-selected.
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Swift Engineer')

    await user.click(screen.getByRole('button', { name: /filter by sponsor tier/i }))

    const boxes = screen.getAllByRole('checkbox')
    expect(boxes).toHaveLength(5)
    expect(boxes.every((box) => !(box as HTMLInputElement).checked)).toBe(true)
    expect(screen.getByRole('checkbox', { name: /no visa needed/i })).toBeInTheDocument()
  })

  it('reads initial sort and tier filter from the URL', async () => {
    renderPage('/?sort=date&sponsor_tier=registry_inferred')

    await screen.findByText('Swift Engineer')
    expect(firstJobsUrl()).toContain('sort=date')
    expect(firstJobsUrl()).toContain('sponsor_tier=registry_inferred')
  })

  it('defaults to the New view — the morning scan', async () => {
    renderPage()
    await screen.findByText('Swift Engineer')

    expect(firstJobsUrl()).toContain('status=new')
    expect(screen.getByRole('button', { name: 'New' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('switching to All refetches without a status param (all but hidden)', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Swift Engineer')

    await user.click(screen.getByRole('button', { name: 'All' }))

    await waitFor(() => {
      expect(jobListUrls().some((u) => !u.includes('status'))).toBe(true)
    })
  })

  it('switching to Starred refetches with status=starred', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Swift Engineer')

    await user.click(screen.getByRole('button', { name: 'Starred' }))

    await waitFor(() => {
      expect(jobListUrls().some((u) => u.includes('status=starred'))).toBe(true)
    })
  })

  it('starring a row PATCHes the job status to starred', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Swift Engineer')

    await user.click(screen.getByRole('button', { name: /star Swift Engineer/i }))

    await waitFor(() => {
      const patch = fetchMock.mock.calls.find(
        (call) => String(call[0]) === '/jobs/1/status' && call[1]?.method === 'PATCH',
      )
      expect(patch).toBeDefined()
      expect(JSON.parse(String(patch?.[1]?.body))).toEqual({ status: 'starred' })
    })
  })

  it('hiding a row PATCHes the job status to hidden', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Swift Engineer')

    await user.click(screen.getByRole('button', { name: /hide Swift Engineer/i }))

    await waitFor(() => {
      const patch = fetchMock.mock.calls.find(
        (call) => String(call[0]) === '/jobs/1/status' && call[1]?.method === 'PATCH',
      )
      expect(JSON.parse(String(patch?.[1]?.body))).toEqual({ status: 'hidden' })
    })
  })

  it('opening a new job sets the ?job param and marks it seen', async () => {
    const detail = {
      ...payload.jobs[0],
      description: 'Details.',
      sponsor_evidence: null,
      registries: [],
      match_confidence: null,
      duplicate_sources: [],
    }
    fetchMock.mockImplementation((url: RequestInfo | URL) => {
      const u = String(url)
      if (u === '/resumes') return ok([])
      if (u === '/countries') return ok([])
      if (u === '/markets') return ok(coverage)
      if (u.startsWith('/jobs/') && !u.includes('/status')) return ok(detail)
      return ok(payload)
    })
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Swift Engineer')

    await user.click(screen.getByRole('button', { name: /open Swift Engineer details/i }))

    // The drawer opens (its own detail fetch) and the `new` job is PATCHed to seen.
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    await waitFor(() => {
      const patch = fetchMock.mock.calls.find(
        (call) => String(call[0]) === '/jobs/1/status' && call[1]?.method === 'PATCH',
      )
      expect(JSON.parse(String(patch?.[1]?.body))).toEqual({ status: 'seen' })
    })
  })

  it('shows a per-view empty state when nothing matches (New = all caught up)', async () => {
    jobsPayload = { total: 0, jobs: [] }

    renderPage()

    expect(await screen.findByText(/you're all caught up/i)).toBeInTheDocument()
  })

  // ---- §11 resume-fit (slice 12d) ----

  it('with no active resume, sends no resume param and shows no fit badge', async () => {
    renderPage()
    await screen.findByText('Swift Engineer')

    expect(jobListUrls().every((u) => !u.includes('resume='))).toBe(true)
    expect(screen.queryByText(/^Fit\b/)).not.toBeInTheDocument()
    // The Fit sort option is hidden until a resume is active.
    expect(screen.queryByRole('button', { name: 'Fit' })).not.toBeInTheDocument()
  })

  it('with an active resume, scores the list with ?resume= and shows a fit badge per row', async () => {
    resumesPayload = [activeResume]
    renderPage()

    // The scored rows carry a fit badge (overall score); soft signal like the tier chip.
    expect(await screen.findByText('Fit 96')).toBeInTheDocument()
    await waitFor(() => {
      expect(jobListUrls().some((u) => u.includes('resume=7'))).toBe(true)
    })
  })

  it('with an active resume, switching sort to Fit refetches with sort=match', async () => {
    resumesPayload = [activeResume]
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Fit 96')

    await user.click(screen.getByRole('button', { name: 'Fit' }))

    await waitFor(() => {
      expect(jobListUrls().some((u) => u.includes('sort=match') && u.includes('resume=7'))).toBe(
        true,
      )
    })
  })
})
