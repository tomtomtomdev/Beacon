import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Country, JobDetail } from '../api/types'
import { JobDrawer } from './JobDrawer'

const seJob: JobDetail = {
  id: 1,
  title: 'Senior iOS Engineer',
  company: 'Spotify',
  url: 'https://example.test/apply/1',
  location: 'Stockholm, Sweden',
  country: 'SE',
  city: 'Stockholm',
  categories: ['ios'],
  level: 'senior',
  posted_at: '2026-07-01T00:00:00+00:00',
  sponsor_tier: 'registry_inferred',
  user_status: 'new',
  description: 'Build the iOS app.\n\nWork with a strong team.',
  sponsor_evidence: null,
  registries: ['UK', 'NL'],
  match_confidence: 0.94,
  duplicate_sources: [
    { source: 'greenhouse', company: 'Spotify', url: 'https://example.test/apply/1' },
    { source: 'remoteok', company: 'Spotify', url: 'https://example.test/ro/1' },
  ],
}

const yesJob: JobDetail = {
  ...seJob,
  id: 2,
  sponsor_tier: 'explicit_yes',
  sponsor_evidence: 'Visa sponsorship available for this role.',
  registries: [],
  match_confidence: null,
  user_status: 'seen',
}

const sweden: Country = {
  code: 'SE',
  name: 'Sweden',
  visa_summary: 'Work permit, ~80% median salary',
  pr_summary: '4yr',
  citizenship_summary: '5yr → reform to 8yr + tests was in progress — likely law by 2026',
  registry_name: 'None — employer certification scheme discontinued Dec 2023',
  priority_tier: 'nice_to_have',
  verified_at: '2026-01-15',
  source_url: 'https://www.migrationsverket.se',
}

const fetchMock = vi.fn()

function ok(body: unknown): Promise<Response> {
  return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response)
}

beforeEach(() => {
  fetchMock.mockImplementation((url: RequestInfo | URL) => {
    const u = String(url)
    if (u === '/countries') return ok([sweden])
    if (u === '/jobs/2') return ok(yesJob)
    return ok(seJob)
  })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

function renderDrawer(jobId = 1) {
  const onClose = vi.fn()
  const onSetStatus = vi.fn()
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <JobDrawer jobId={jobId} onClose={onClose} onSetStatus={onSetStatus} />
    </QueryClientProvider>,
  )
  return { onClose, onSetStatus }
}

describe('JobDrawer', () => {
  it('renders the job title and company', async () => {
    renderDrawer()

    expect(await screen.findByRole('heading', { name: 'Senior iOS Engineer' })).toBeInTheDocument()
    expect(screen.getByText('Spotify')).toBeInTheDocument()
  })

  it('shows the country visa panel with the reform caveat and verified date', async () => {
    renderDrawer()

    const panel = within(await screen.findByTestId('country-panel'))
    expect(panel.getByText(/Sweden — relocation reference/)).toBeInTheDocument()
    expect(panel.getByText(/reform to 8yr/)).toBeInTheDocument()
    expect(panel.getByText(/verified 2026-01-15/)).toBeInTheDocument()
  })

  it('lists the matched registries and confidence for a registry-inferred tier', async () => {
    renderDrawer()

    const card = within(await screen.findByTestId('sponsorship-card'))
    expect(card.getByText('Registry-inferred signal')).toBeInTheDocument()
    expect(card.getByText(/UK Home Office/)).toBeInTheDocument()
    expect(card.getByText(/IND recognised/)).toBeInTheDocument()
    expect(card.getByText(/Match confidence 0\.94/)).toBeInTheDocument()
  })

  it('quotes the evidence sentence for an explicit tier', async () => {
    renderDrawer(2)

    const card = within(await screen.findByTestId('sponsorship-card'))
    expect(card.getByText('Sponsorship offered')).toBeInTheDocument()
    expect(card.getByText(/Visa sponsorship available for this role\./)).toBeInTheDocument()
  })

  it('links the CTA to the original posting', async () => {
    renderDrawer()

    const cta = await screen.findByRole('link', { name: /open original posting/i })
    expect(cta).toHaveAttribute('href', 'https://example.test/apply/1')
  })

  it('closes on Escape', async () => {
    const user = userEvent.setup()
    const { onClose } = renderDrawer()
    await screen.findByRole('heading', { name: 'Senior iOS Engineer' })

    await user.keyboard('{Escape}')

    expect(onClose).toHaveBeenCalledOnce()
  })

  it('closes when the overlay is clicked', async () => {
    const user = userEvent.setup()
    const { onClose } = renderDrawer()
    await screen.findByRole('heading', { name: 'Senior iOS Engineer' })

    await user.click(screen.getByTestId('drawer-overlay'))

    expect(onClose).toHaveBeenCalled()
  })

  it('starring the job calls onSetStatus with starred', async () => {
    const user = userEvent.setup()
    const { onSetStatus } = renderDrawer()
    await screen.findByRole('heading', { name: 'Senior iOS Engineer' })

    await user.click(screen.getByRole('button', { name: 'Star' }))

    expect(onSetStatus).toHaveBeenCalledWith(1, 'starred')
  })
})
