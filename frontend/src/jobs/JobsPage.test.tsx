import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
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
      posted_at: '2026-07-01T00:00:00+00:00',
      sponsor_tier: 'unknown',
    },
    {
      id: 2,
      title: 'Platform Engineer',
      company: 'Tines',
      url: 'https://example.test/2',
      location: 'Dublin, Ireland (Hybrid)',
      country: 'IE',
      city: 'Dublin',
      posted_at: null,
      sponsor_tier: 'unknown',
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

  it('reads initial sort and tier filter from the URL', async () => {
    renderPage('/?sort=date&sponsor_tier=registry_inferred')

    await screen.findByText('Swift Engineer')
    const firstUrl = String(fetchMock.mock.calls[0][0])
    expect(firstUrl).toContain('sort=date')
    expect(firstUrl).toContain('sponsor_tier=registry_inferred')
  })

  it('shows the empty state when nothing matches', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ total: 0, jobs: [] }),
    } as Response)

    renderPage()

    expect(await screen.findByText(/no postings/i)).toBeInTheDocument()
  })
})
