import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { JobsPageResponse, Resume } from '../api/types'
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

const fetchMock = vi.fn()

// Data-driven boundary mock: /resumes returns the resume list; a /jobs request that carries
// ?resume= gets scored rows (mirrors the backend), everything else the unscored base.
let jobsPayload: JobsPageResponse = payload
let resumesPayload: Resume[] = []

function ok(body: unknown): Promise<Response> {
  return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response)
}

function renderPage(initialUrl = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialUrl]}>
        <JobsPane onBack={() => {}} />
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
  fetchMock.mockImplementation((url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url)
    const method = init?.method ?? 'GET'
    if (u === '/resumes' && method === 'GET') return ok(resumesPayload)
    if (u === '/countries') return ok([])
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
