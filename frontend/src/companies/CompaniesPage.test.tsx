import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CompanyHealth } from '../api/types'
import { CompaniesPage } from './CompaniesPage'

const health: CompanyHealth = {
  summary: {
    seed: 3,
    supported: 2,
    healthy: 1,
    degraded: 0,
    quarantined: 1,
    pending: 1,
    by_ats: { greenhouse: 1, lever: 1, smartrecruiters: 1 },
  },
  companies: [
    {
      name: 'Healthy Co',
      ats_type: 'greenhouse',
      ats_slug: 'healthy',
      country_hq: 'IE',
      status: 'ok',
      reason: null,
      last_success_at: '2026-07-08T06:00:00+00:00',
      consecutive_failures: 0,
    },
    {
      name: 'Dead Co',
      ats_type: 'lever',
      ats_slug: 'dead',
      country_hq: 'US',
      status: 'quarantined',
      reason: 'gone',
      last_success_at: null,
      consecutive_failures: 3,
    },
    {
      name: 'Dormant Co',
      ats_type: 'smartrecruiters',
      ats_slug: 'dormant',
      country_hq: 'SG',
      status: 'pending',
      reason: null,
      last_success_at: null,
      consecutive_failures: 0,
    },
  ],
}

const fetchMock = vi.fn()

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <CompaniesPage />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  fetchMock.mockResolvedValue({ ok: true, json: () => Promise.resolve(health) } as Response)
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('CompaniesPage', () => {
  it('lists a row per company with its ATS and HQ', async () => {
    renderPage()

    expect(await screen.findByText('Healthy Co')).toBeInTheDocument()
    expect(screen.getByText('Dead Co')).toBeInTheDocument()
    expect(screen.getByText('Dormant Co')).toBeInTheDocument()
    expect(screen.getByText('lever · dead')).toBeInTheDocument()
  })

  it('shows a quarantined source with its reason', async () => {
    renderPage()
    await screen.findByText('Dead Co')

    expect(screen.getByText('Quarantined')).toBeInTheDocument()
    expect(screen.getByText('gone')).toBeInTheDocument()
  })

  it('marks a company whose ATS has no adapter as pending', async () => {
    renderPage()
    const row = (await screen.findByText('Dormant Co')).closest('div')
    expect(row).not.toBeNull()

    const dormant = within(row as HTMLElement)
    expect(dormant.getByText('Pending')).toBeInTheDocument()
    expect(dormant.getByText('adapter pending')).toBeInTheDocument()
  })

  it('computes the seed line from the data', async () => {
    renderPage()

    const line = await screen.findByText(/seed 3/)
    expect(line).toHaveTextContent('greenhouse 1')
    expect(line).toHaveTextContent('1 awaiting adapters')
  })

  it('summarizes health counts in cards', async () => {
    renderPage()
    await screen.findByText('Healthy Co')

    // The quarantined summary card shows its count of 1.
    const label = screen.getByText('quarantined')
    const card = label.closest('div')
    expect(card).not.toBeNull()
    expect(within(card as HTMLElement).getByText('1')).toBeInTheDocument()
  })
})
