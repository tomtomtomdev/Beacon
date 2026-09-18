import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CompanyHealth, Country, MarketCoverage, RegistryCoverage } from '../api/types'
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

// The §4 markets the stack shows, plus one country the reference never assessed.
const markets: MarketCoverage = {
  target_markets: [
    { code: 'ID', open_jobs: 12 },
    { code: 'NL', open_jobs: 272 },
    { code: 'SE', open_jobs: 393 },
  ],
  other_markets: [{ code: 'DE', open_jobs: 198 }],
}

// One route → one body. A chain of ternaries silently served a jobs page to every URL it did
// not recognise, so a new endpoint failed as a render crash instead of as a missing mock.
const BODIES: Record<string, unknown> = {
  '/resumes': [],
  '/companies/health': health,
  '/registries': coverage,
  '/markets': markets,
}

function bodyFor(url: string): unknown {
  if (url in BODIES) return BODIES[url]
  if (url.startsWith('/countries')) return countries
  return { total: 0, jobs: [] }
}

const fetchMock = vi.fn()

function renderPage(initialUrl = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialUrl]}>
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
    renderPage('/?panel=markets')

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
    renderPage('/?panel=markets')

    const cards = await screen.findAllByRole('button', { name: /details$/ })
    expect(cards[0]).toHaveAccessibleName('Indonesia details')
    expect(within(cards[0]).getByText('Home')).toBeInTheDocument()
  })

  it('replaces the visa legend with the home-market block when Indonesia is selected', async () => {
    // DESIGN §1: every relocation field is inapplicable at home, and rendering them empty or
    // as "n/a" would read as missing data rather than as an absent question. No verified date
    // either — the row states a fact about citizenship, not a policy that expires.
    const user = userEvent.setup()
    renderPage('/?panel=markets')

    await user.click(await screen.findByRole('button', { name: 'Indonesia details' }))

    expect(screen.getByText(/already have the right to work here/i)).toBeInTheDocument()
    expect(screen.getByText(/iOS · Backend \(Java, Python\) · AI\/ML/)).toBeInTheDocument()
    expect(screen.queryByText('Work visa')).not.toBeInTheDocument()
    expect(screen.queryByText('Citizenship')).not.toBeInTheDocument()
    expect(screen.queryByText(/^verified /)).not.toBeInTheDocument()
  })

  it('surfaces Sweden’s no-registry note and verified date verbatim on the card', async () => {
    renderPage('/?panel=markets')

    const card = await screen.findByRole('button', { name: 'Sweden details' })
    const swedish = within(card)
    // The compact card shows the registry note + verified date; citizenship moves to the
    // reference legend shown once the market is selected.
    expect(swedish.getByText(/scheme discontinued Dec 2023/)).toBeInTheDocument()
    expect(swedish.getByText(/✓ 2026-01-15/)).toBeInTheDocument()
  })

  it('picking a country from the stack shows its jobs + reference legend; back clears the filter', async () => {
    const user = userEvent.setup()
    renderPage('/?panel=markets')

    await user.click(await screen.findByRole('button', { name: 'Sweden details' }))

    // Picking a market from the stack switches the panel to that market's jobs.
    expect(await screen.findByRole('heading', { name: 'Jobs · Sweden' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Sweden details' })).not.toBeInTheDocument()
    // The relocation-reference legend surfaces the country's citizenship figure verbatim.
    expect(screen.getByText(/reform to 8yr/)).toBeInTheDocument()

    // Back clears the country filter and leaves the jobs panel showing every market.
    await user.click(screen.getByRole('button', { name: /all markets/i }))
    expect(await screen.findByRole('heading', { name: 'Jobs' })).toBeInTheDocument()
    expect(screen.queryByText(/reform to 8yr/)).not.toBeInTheDocument()
  })

  // 21d: the panel used to be gated on ?focus= — no country selected meant no jobs on screen at
  // all, while the corpus held 9,130 open canonical ones. ?focus= is now a filter, not a gate.
  it('opens on the jobs panel, not the card stack', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Jobs' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Sweden details' })).not.toBeInTheDocument()
  })

  it('shows the card stack on the Markets tab, and the tab survives a reload', async () => {
    renderPage('/?panel=markets')

    expect(await screen.findByRole('button', { name: 'Sweden details' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Jobs' })).not.toBeInTheDocument()
  })

  it('switches between the two panels from the tabs', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('heading', { name: 'Jobs' })

    await user.click(screen.getByRole('button', { name: /^markets$/i }))
    expect(await screen.findByRole('button', { name: 'Sweden details' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /^jobs$/i }))
    expect(await screen.findByRole('heading', { name: 'Jobs' })).toBeInTheDocument()
  })

  it('selecting a country adds its filter without moving the status view', async () => {
    // Selection used to force status=all, so every beacon tap moved the list out from under
    // the reader. It is purely additive now: a country filter and a reference legend.
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('heading', { name: 'Jobs' })
    const before = screen.getByRole('button', { name: 'New' }).getAttribute('aria-pressed')

    await user.click(screen.getByRole('button', { name: 'Sweden on globe' }))

    expect(await screen.findByRole('heading', { name: 'Jobs · Sweden' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'New' })).toHaveAttribute('aria-pressed', before ?? '')
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
    await screen.findByRole('heading', { name: 'Jobs' })

    const pin = screen.getByRole('button', { name: 'Sweden on globe' })
    expect(pin).toHaveAttribute('aria-pressed', 'false')

    await user.click(pin)
    expect(await screen.findByRole('heading', { name: 'Jobs · Sweden' })).toBeInTheDocument()
  })

  // 21e: the tour used to rewrite ?focus= every 9s, which was harmless while the panel showed
  // visa cards and intolerable once it shows the job list — it would take the list away from a
  // reader mid-scan and never return to the unfiltered view. It drives the globe now, and only
  // the globe: the lit beacon field survives, the reading surface stops moving.
  it('tours the globe once the page has gone idle, without touching the job list', async () => {
    // The idle timer is armed on mount, so the clock has to be fake before the page renders.
    vi.useFakeTimers()
    renderPage()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1)
    })
    expect(screen.getByRole('heading', { name: 'Jobs' })).toBeInTheDocument()

    // Untouched for the idle delay: the globe starts walking the markets on its own, in the
    // order the stack shows them — so the home market leads (DESIGN §1).
    await act(async () => {
      vi.advanceTimersByTime(TOUR_IDLE_MS)
    })
    expect(screen.getByRole('button', { name: 'Indonesia on globe' })).toHaveAttribute(
      'data-touring',
      'true',
    )
    // The panel did not move: no country filter, no heading change, nothing refetched under
    // the reader.
    expect(screen.getByRole('heading', { name: 'Jobs' })).toBeInTheDocument()

    await act(async () => {
      vi.advanceTimersByTime(TOUR_DWELL_MS)
    })
    expect(screen.getByRole('button', { name: 'Netherlands on globe' })).toHaveAttribute(
      'data-touring',
      'true',
    )
    expect(screen.getByRole('heading', { name: 'Jobs' })).toBeInTheDocument()

    // A real pointer move hands control back and the highlight goes out. Asserted over the
    // restarted countdown rather than a dwell multiple: the tour is *meant* to resume once the
    // page goes quiet again, so a window longer than TOUR_IDLE_MS would be testing the opposite.
    await act(async () => {
      window.dispatchEvent(new MouseEvent('pointermove', { clientX: 400, clientY: 300 }))
    })
    await act(async () => {
      vi.advanceTimersByTime(TOUR_IDLE_MS - 1)
    })
    expect(screen.getByRole('button', { name: 'Netherlands on globe' })).toHaveAttribute(
      'data-touring',
      'false',
    )
  })
})
