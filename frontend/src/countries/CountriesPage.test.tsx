import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CompanyHealth, Country, RegistryCoverage } from '../api/types'
import { CountriesPage } from './CountriesPage'
import { TOUR_DWELL_MS, TOUR_IDLE_MS } from './useIdleTour'

const countries: Country[] = [
  // The API returns the home row first (SqliteCountryRepo orders home > primary > rest), and
  // the stack renders in that order — DESIGN §1 pins Indonesia above the relocation markets.
  {
    code: 'ID',
    name: 'Indonesia',
    visa_summary: 'None — right to work already held',
    pr_summary: 'n/a — citizen',
    citizenship_summary: 'Held',
    registry_name: "n/a — not_required comes from the job's location, never a register",
    priority_tier: 'home',
    verified_at: '2026-09-01',
    source_url: 'https://example.test/spec',
  },
  {
    code: 'NL',
    name: 'Netherlands',
    visa_summary: 'HSM kennismigrant',
    pr_summary: '5yr',
    citizenship_summary: '5yr; renounce',
    registry_name: 'IND recognised sponsors list (public)',
    priority_tier: 'primary',
    verified_at: '2026-01-15',
    source_url: 'https://ind.nl',
  },
  {
    code: 'SE',
    name: 'Sweden',
    visa_summary: 'Work permit, ~80% median salary',
    pr_summary: '4yr',
    citizenship_summary: '5yr → reform to 8yr + tests',
    registry_name: 'None — employer certification scheme discontinued Dec 2023',
    priority_tier: 'nice_to_have',
    verified_at: '2026-01-15',
    source_url: 'https://www.migrationsverket.se',
  },
]

// The globe widget reads two rollups; the page tests only need them well-formed, so the
// numbers themselves are pinned in SourceHealth.test.tsx rather than duplicated here.
const health: CompanyHealth = {
  summary: {
    seed: 3,
    supported: 2,
    healthy: 2,
    degraded: 0,
    quarantined: 1,
    pending: 0,
    by_ats: { greenhouse: 2, gem: 1 },
    last_poll_at: '2026-09-15T05:00:04Z',
  },
  companies: [],
}

const coverage: RegistryCoverage = {
  registries: [{ registry: 'IE', fetched_at: '2026-09-04T05:29:57Z', row_count: 6360, companies: 21, stale: false }],
}

// One route → one body. A chain of ternaries silently served a jobs page to every URL it did
// not recognise, so a new endpoint failed as a render crash instead of as a missing mock.
const BODIES: Record<string, unknown> = {
  '/resumes': [],
  '/companies/health': health,
  '/registries': coverage,
}

function bodyFor(url: string): unknown {
  if (url in BODIES) return BODIES[url]
  if (url.startsWith('/countries')) return countries
  return { total: 0, jobs: [] }
}

const fetchMock = vi.fn()

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/']}>
        <CountriesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  fetchMock.mockImplementation((url: RequestInfo | URL) => {
    const body = bodyFor(String(url))
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response)
  })
  vi.stubGlobal('fetch', fetchMock)
  // jsdom has no canvas 2d context; return null so the globe engine is skipped cleanly.
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null)
})

afterEach(() => {
  // Only unfake what was faked: an unconditional useRealTimers() leaves residue on the timer
  // globals that testing-library then mistakes for a live fake clock in the next test.
  if (vi.isFakeTimers()) vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

describe('CountriesPage', () => {
  it('renders a card per country from the API', async () => {
    renderPage()

    expect(await screen.findByRole('button', { name: 'Netherlands details' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sweden details' })).toBeInTheDocument()
  })

  it('names the home marker in the globe legend, not just the two relocation tiers', async () => {
    // The origin pin is amber while every other pin is teal or grey, and until now the legend
    // explained only the two relocation tiers — so the one colour that means "you already live
    // here" was the only one a first-time viewer could not look up.
    renderPage()

    const legend = within(await screen.findByTestId('globe-legend'))
    expect(legend.getByText('Primary target')).toBeInTheDocument()
    expect(legend.getByText('Nice-to-have')).toBeInTheDocument()
    expect(legend.getByText('Home')).toBeInTheDocument()
  })

  it('pins the home market first and badges it Home, not as a relocation tier', async () => {
    // SPEC §4 / DESIGN §1: Indonesia is the baseline every relocation is measured against,
    // so it leads the stack — and it is not a "primary" target, it is not a target at all.
    renderPage()

    const cards = await screen.findAllByRole('button', { name: /details$/ })
    expect(cards[0]).toHaveAccessibleName('Indonesia details')
    expect(within(cards[0]).getByText('Home')).toBeInTheDocument()
  })

  it('replaces the visa legend with the home-market block when Indonesia is selected', async () => {
    // DESIGN §1: every relocation field is inapplicable at home, and rendering them empty or
    // as "n/a" would read as missing data rather than as an absent question. No verified date
    // either — the row states a fact about citizenship, not a policy that expires.
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Indonesia details' }))

    expect(screen.getByText(/already have the right to work here/i)).toBeInTheDocument()
    expect(screen.getByText(/iOS · Backend \(Java, Python\) · AI\/ML/)).toBeInTheDocument()
    expect(screen.queryByText('Work visa')).not.toBeInTheDocument()
    expect(screen.queryByText('Citizenship')).not.toBeInTheDocument()
    expect(screen.queryByText(/^verified /)).not.toBeInTheDocument()
  })

  it('surfaces Sweden’s no-registry note and verified date verbatim on the card', async () => {
    renderPage()

    const card = await screen.findByRole('button', { name: 'Sweden details' })
    const swedish = within(card)
    // The compact card shows the registry note + verified date; citizenship moves to the
    // reference legend shown once the market is selected.
    expect(swedish.getByText(/scheme discontinued Dec 2023/)).toBeInTheDocument()
    expect(swedish.getByText(/✓ 2026-01-15/)).toBeInTheDocument()
  })

  it('selecting a country opens its jobs pane + reference legend; back returns to the stack', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Sweden details' }))

    // The card stack is replaced by the jobs pane, filtered to that country.
    expect(await screen.findByRole('heading', { name: 'Jobs · Sweden' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Sweden details' })).not.toBeInTheDocument()
    // The relocation-reference legend surfaces the country's citizenship figure verbatim.
    expect(screen.getByText(/reform to 8yr/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /all markets/i }))
    expect(await screen.findByRole('button', { name: 'Sweden details' })).toBeInTheDocument()
  })

  it('gives the home market a pin like any other, and draws it no arc', async () => {
    // DESIGN §Globe: the amber origin marker is a pin like any other; picking it shows
    // Indonesia's jobs with no arc drawn, because origin and destination coincide.
    const user = userEvent.setup()
    renderPage()

    const pin = await screen.findByRole('button', { name: 'Indonesia on globe' })
    await user.click(pin)

    expect(await screen.findByRole('heading', { name: 'Jobs · Indonesia' })).toBeInTheDocument()
    expect(pin).toHaveAttribute('aria-pressed', 'true')
    expect(pin).toHaveAttribute('data-origin', 'true')
  })

  it('a globe pin control opens the selection', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('button', { name: 'Sweden details' })

    const pin = screen.getByRole('button', { name: 'Sweden on globe' })
    expect(pin).toHaveAttribute('aria-pressed', 'false')

    await user.click(pin)
    expect(await screen.findByRole('heading', { name: 'Jobs · Sweden' })).toBeInTheDocument()
  })

  it('tours the markets once the page has gone idle, and yields the moment the user moves', async () => {
    // The idle timer is armed on mount, so the clock has to be fake before the page renders.
    vi.useFakeTimers()
    renderPage()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1)
    })
    expect(screen.getByRole('button', { name: 'Sweden details' })).toBeInTheDocument()

    // Untouched for the idle delay: the globe starts walking the markets on its own, in the
    // order the stack shows them — so the home market leads (DESIGN §1).
    await act(async () => {
      vi.advanceTimersByTime(TOUR_IDLE_MS)
    })
    expect(screen.getByRole('heading', { name: 'Jobs · Indonesia' })).toBeInTheDocument()

    await act(async () => {
      vi.advanceTimersByTime(TOUR_DWELL_MS)
    })
    expect(screen.getByRole('heading', { name: 'Jobs · Netherlands' })).toBeInTheDocument()

    // A real pointer move hands control back, leaving that market selected. Asserted over the
    // restarted countdown rather than a dwell multiple: the tour is *meant* to resume once the
    // page goes quiet again, so a window longer than TOUR_IDLE_MS would be testing the opposite.
    await act(async () => {
      window.dispatchEvent(new MouseEvent('pointermove', { clientX: 400, clientY: 300 }))
    })
    await act(async () => {
      vi.advanceTimersByTime(TOUR_IDLE_MS - 1)
    })
    expect(screen.getByRole('heading', { name: 'Jobs · Netherlands' })).toBeInTheDocument()
  })
})
