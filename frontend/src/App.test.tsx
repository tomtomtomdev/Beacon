import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CompanyHealth, SavedSearch } from './api/types'
import App from './App'

// Dated relative to the real clock rather than by faking it: these tests drive userEvent,
// whose own timer advancement has to be wired up by hand under vi.useFakeTimers, and a
// relative fixture needs neither.
const EIGHT_HOURS_AGO = new Date(Date.now() - 8.5 * 3_600_000).toISOString()

const health: CompanyHealth = {
  summary: {
    seed: 70,
    supported: 68,
    healthy: 65,
    degraded: 0,
    quarantined: 3,
    pending: 2,
    by_ats: {},
    last_poll_at: EIGHT_HOURS_AGO,
  },
  companies: [],
}

function savedSearch(id: number, newCount: number): SavedSearch {
  return {
    id,
    name: `search-${id}`,
    filters: { q: null, countries: [], categories: [], levels: [], tiers: [] },
    notify_channel: 'telegram',
    last_run_at: null,
    new_count: newCount,
  }
}

const fetchMock = vi.fn()

let searches: SavedSearch[] = []

beforeEach(() => {
  // App routes through BrowserRouter, so the view lives in the real jsdom URL — and jsdom keeps
  // one location for the whole file. Without this reset, the test that clicks through to Saved
  // searches leaves ?view=searches behind and every later test starts on the wrong screen.
  window.history.replaceState({}, '', '/')
  searches = [savedSearch(1, 4), savedSearch(2, 3)]
  fetchMock.mockImplementation((url: string) => {
    let body: unknown = { total: 0, jobs: [] }
    if (String(url).startsWith('/countries')) body = []
    else if (String(url).startsWith('/searches')) body = searches
    else if (String(url).startsWith('/resumes')) body = []
    else if (String(url) === '/companies/health') body = health
    else if (String(url) === '/registries') body = { registries: [] }
    else if (String(url) === '/markets') body = { target_markets: [], other_markets: [] }
    else if (String(url).startsWith('/settings/telegram')) {
      body = { chat_id: null, bot_token_set: false }
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response)
  })
  vi.stubGlobal('fetch', fetchMock)
  // jsdom has no canvas 2d context; return null so the globe engine is skipped cleanly.
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

describe('App', () => {
  it('renders the app name', () => {
    render(<App />)
    expect(screen.getByText('Beacon')).toBeInTheDocument()
  })

  it('defaults to the Countries globe home, with the jobs panel open', async () => {
    render(<App />)
    expect(
      await screen.findByRole('heading', { name: /open roles & target markets/i }),
    ).toBeInTheDocument()
    // The panel is no longer gated on a selected country — the list is there on arrival.
    expect(await screen.findByRole('heading', { name: 'Jobs' })).toBeInTheDocument()
  })

  it('switches to the Saved searches view from the nav', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /saved/i }))

    expect(await screen.findByRole('heading', { name: /saved searches/i })).toBeInTheDocument()
  })

  it('badges Saved with the real number of new matches', async () => {
    // The rail shipped a hardcoded "4" — a prototype constant rendering as fact beside two
    // saved searches holding 7 new matches between them.
    render(<App />)

    expect(await screen.findByTestId('saved-badge')).toHaveTextContent('7')
  })

  it('shows no badge at all when nothing is new', async () => {
    // Absence is the honest rendering of zero; a "0" chip is noise that reads as a control.
    searches = [savedSearch(1, 0)]
    render(<App />)

    expect(await screen.findByRole('button', { name: /saved/i })).toBeInTheDocument()
    expect(screen.queryByTestId('saved-badge')).not.toBeInTheDocument()
  })

  it('reports the real last poll in the rail footer, not a frozen clock', async () => {
    render(<App />)

    expect(await screen.findByText(/8h ago/)).toBeInTheDocument()
    expect(screen.queryByText(/07:04/)).not.toBeInTheDocument()
  })

  it('shares one health fetch between the rail footer and the globe widget', async () => {
    // Both read ['companyHealth'], so the query cache is the sharing mechanism and the second
    // surface costs no request — the same reason 18a could derive the country list for free,
    // and the reason this repo has no global client-state lib.
    render(<App />)
    await screen.findByText(/8h ago/)

    const healthCalls = fetchMock.mock.calls.filter(([url]) => String(url) === '/companies/health')
    expect(healthCalls).toHaveLength(1)
  })

  it('opens Settings from the rail footer', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'Settings' }))

    expect(await screen.findByRole('heading', { name: /settings/i })).toBeInTheDocument()
  })
})
