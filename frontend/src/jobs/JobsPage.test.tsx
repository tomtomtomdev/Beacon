import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { JobsPageResponse } from '../api/types'
import { JobsPage } from './JobsPage'

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

const fetchMock = vi.fn()

function renderPage(initialUrl = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialUrl]}>
        <JobsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  fetchMock.mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(payload),
  } as Response)
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('JobsPage', () => {
  it('renders a row per job from the API', async () => {
    renderPage()

    expect(await screen.findByText('Swift Engineer')).toBeInTheDocument()
    expect(screen.getByText('Platform Engineer')).toBeInTheDocument()
    expect(screen.getByText('Spotify')).toBeInTheDocument()
    expect(screen.getByText(/2 postings/)).toBeInTheDocument()
  })

  it('links each row to the original posting', async () => {
    renderPage()

    const links = await screen.findAllByRole('link', { name: /open original posting/i })
    expect(links.map((a) => a.getAttribute('href'))).toEqual([
      'https://example.test/1',
      'https://example.test/2',
    ])
  })

  it('typing a keyword refetches with q', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Swift Engineer')

    await user.type(screen.getByPlaceholderText(/search title, company/i), 'swift')

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]))
      expect(urls.some((u) => u.includes('q=swift'))).toBe(true)
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
      const urls = fetchMock.mock.calls.map((call) => String(call[0]))
      expect(urls.some((u) => u.includes('country=SE') && u.includes('country=IE'))).toBe(true)
    })
  })

  it('reads initial filters from the URL so filtered views are shareable', async () => {
    renderPage('/?q=swift&country=SE')

    await screen.findByText('Swift Engineer')
    const firstUrl = String(fetchMock.mock.calls[0][0])
    expect(firstUrl).toContain('q=swift')
    expect(firstUrl).toContain('country=SE')
  })

  it('defaults to sponsor-tier sort with no sort or tier params (filter is opt-in)', async () => {
    renderPage()
    await screen.findByText('Swift Engineer')

    const firstUrl = String(fetchMock.mock.calls[0][0])
    expect(firstUrl).not.toContain('sort=')
    expect(firstUrl).not.toContain('sponsor_tier=')
  })

  it('switching sort to Date refetches with sort=date', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Swift Engineer')

    await user.click(screen.getByRole('button', { name: 'Date' }))

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]))
      expect(urls.some((u) => u.includes('sort=date'))).toBe(true)
    })
  })

  it('selecting a sponsor tier refetches with the opt-in filter param', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Swift Engineer')

    await user.click(screen.getByRole('button', { name: /filter by sponsor tier/i }))
    await user.click(screen.getByRole('checkbox', { name: /registry/i }))

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]))
      expect(urls.some((u) => u.includes('sponsor_tier=registry_inferred'))).toBe(true)
    })
  })

  it('selecting a category pill refetches with the category param', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Swift Engineer')

    await user.click(screen.getByRole('button', { name: 'iOS' }))

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]))
      expect(urls.some((u) => u.includes('category=ios'))).toBe(true)
    })
  })

  it('selecting a level pill refetches with the level param', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Swift Engineer')

    await user.click(screen.getByRole('button', { name: 'Senior' }))

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]))
      expect(urls.some((u) => u.includes('level=senior'))).toBe(true)
    })
  })

  it('reads initial category and level filters from the URL', async () => {
    renderPage('/?category=ios&level=senior')

    await screen.findByText('Swift Engineer')
    const firstUrl = String(fetchMock.mock.calls[0][0])
    expect(firstUrl).toContain('category=ios')
    expect(firstUrl).toContain('level=senior')
  })

  it('renders category chips and the level per row', async () => {
    renderPage()

    await screen.findByText('Swift Engineer')
    // Scope to the table — category labels also appear as filter pills in the bar.
    const table = within(screen.getByTestId('job-table'))
    expect(table.getByText('iOS')).toBeInTheDocument() // multi-label: both chips render
    expect(table.getByText('AI/ML')).toBeInTheDocument()
    expect(table.getByText('SENIOR')).toBeInTheDocument() // level uppercased
  })

  it('reads initial sort and tier filter from the URL', async () => {
    renderPage('/?sort=date&sponsor_tier=registry_inferred')

    await screen.findByText('Swift Engineer')
    const firstUrl = String(fetchMock.mock.calls[0][0])
    expect(firstUrl).toContain('sort=date')
    expect(firstUrl).toContain('sponsor_tier=registry_inferred')
  })

  it('defaults to the New view — the morning scan', async () => {
    renderPage()
    await screen.findByText('Swift Engineer')

    const firstUrl = String(fetchMock.mock.calls[0][0])
    expect(firstUrl).toContain('status=new')
    expect(screen.getByRole('button', { name: 'New' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('switching to All refetches without a status param (all but hidden)', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Swift Engineer')

    await user.click(screen.getByRole('button', { name: 'All' }))

    await waitFor(() => {
      const listCalls = fetchMock.mock.calls
        .map((call) => String(call[0]))
        .filter((u) => u.startsWith('/jobs?') || u === '/jobs')
      expect(listCalls.some((u) => !u.includes('status'))).toBe(true)
    })
  })

  it('switching to Starred refetches with status=starred', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Swift Engineer')

    await user.click(screen.getByRole('button', { name: 'Starred' }))

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]))
      expect(urls.some((u) => u.includes('status=starred'))).toBe(true)
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

  it('shows a per-view empty state when nothing matches (New = all caught up)', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ total: 0, jobs: [] }),
    } as Response)

    renderPage()

    expect(await screen.findByText(/you're all caught up/i)).toBeInTheDocument()
  })
})
