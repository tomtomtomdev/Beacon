import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Country, JobDetail, MatchRationale, MatchScore } from '../api/types'
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

const fit: MatchScore = {
  overall: 96,
  skills_score: 100,
  level_score: 80,
  sponsor_score: 40,
  matched_skills: ['swift', 'ios'],
  missing_skills: ['kotlin'],
}

const rationale: MatchRationale = {
  summary: 'Strong iOS fit against a Swift-heavy senior role.',
  strengths: ['8 years of Swift and SwiftUI'],
  gaps: ['No Kotlin exposure'],
  verdict: 'Worth applying.',
  sponsor_note: 'Registry-inferred sponsor in a target country.',
}

function renderDrawer(
  jobId = 1,
  matchScore: MatchScore | null = null,
  resumeId: number | null = null,
) {
  const onClose = vi.fn()
  const onSetStatus = vi.fn()
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <JobDrawer
        jobId={jobId}
        matchScore={matchScore}
        resumeId={resumeId}
        onClose={onClose}
        onSetStatus={onSetStatus}
      />
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

  it('shows no Fit card when no resume score is passed', async () => {
    renderDrawer()
    await screen.findByRole('heading', { name: 'Senior iOS Engineer' })

    expect(screen.queryByTestId('fit-card')).not.toBeInTheDocument()
  })

  it('renders the Fit card with overall, sub-scores and matched/missing skills', async () => {
    renderDrawer(1, fit)
    await screen.findByRole('heading', { name: 'Senior iOS Engineer' })

    const card = within(await screen.findByTestId('fit-card'))
    expect(card.getByText('96')).toBeInTheDocument() // overall
    // Sub-scores are labelled and valued.
    expect(card.getByText(/Skills/)).toBeInTheDocument()
    expect(card.getByText(/Level/)).toBeInTheDocument()
    expect(card.getByText(/Sponsor/)).toBeInTheDocument()
    // Matched and missing skills surface as chips.
    expect(card.getByText('swift')).toBeInTheDocument()
    expect(card.getByText('kotlin')).toBeInTheDocument()
  })

  it('offers an Assess fit button in the Fit card when a resume is active', async () => {
    renderDrawer(1, fit, 5)

    const card = within(await screen.findByTestId('fit-card'))
    expect(card.getByRole('button', { name: /assess fit/i })).toBeInTheDocument()
    // The rationale is not requested until the button is clicked.
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining('/match'),
      expect.anything(),
    )
  })

  it('fetches and renders the LLM rationale when Assess fit is clicked', async () => {
    const user = userEvent.setup()
    fetchMock.mockImplementation((url: RequestInfo | URL) => {
      const u = String(url)
      if (u === '/countries') return ok([sweden])
      if (u.includes('/match')) return ok({ match_score: fit, rationale })
      return ok(seJob)
    })
    renderDrawer(1, fit, 5)

    const card = within(await screen.findByTestId('fit-card'))
    await user.click(card.getByRole('button', { name: /assess fit/i }))

    expect(await screen.findByText(/Strong iOS fit/)).toBeInTheDocument()
    expect(screen.getByText('Worth applying.')).toBeInTheDocument()
    expect(screen.getByText(/8 years of Swift/)).toBeInTheDocument()
    expect(screen.getByText(/No Kotlin exposure/)).toBeInTheDocument()
    expect(screen.getByText(/Registry-inferred sponsor/)).toBeInTheDocument()
    // The POST hit the right endpoint with the active resume id.
    expect(fetchMock).toHaveBeenCalledWith('/jobs/1/match?resume=5', expect.anything())
  })

  it('shows a fallback note when the deep match is unavailable (no key/budget)', async () => {
    const user = userEvent.setup()
    fetchMock.mockImplementation((url: RequestInfo | URL) => {
      const u = String(url)
      if (u === '/countries') return ok([sweden])
      if (u.includes('/match')) return ok({ match_score: fit, rationale: null })
      return ok(seJob)
    })
    renderDrawer(1, fit, 5)

    const card = within(await screen.findByTestId('fit-card'))
    await user.click(card.getByRole('button', { name: /assess fit/i }))

    expect(await screen.findByText(/unavailable/i)).toBeInTheDocument()
  })
})
