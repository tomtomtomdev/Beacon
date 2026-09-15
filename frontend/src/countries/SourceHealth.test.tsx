import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CompanyHealth, RegistryCoverage } from '../api/types'
import { SourceHealth } from './SourceHealth'

// The live shape on 2026-09-15, which is also the point of the slice: the widget shipped
// "44 OK / 1 degraded / 2 quarantined" as literals against these numbers.
const health: CompanyHealth = {
  summary: {
    seed: 70,
    supported: 68,
    healthy: 65,
    degraded: 0,
    quarantined: 3,
    pending: 2,
    by_ats: { greenhouse: 28 },
    last_poll_at: '2026-09-15T05:00:04Z',
  },
  companies: [],
}

const coverage: RegistryCoverage = {
  registries: [
    { registry: 'UK', fetched_at: null, row_count: null, companies: 0, stale: false },
    { registry: 'NL', fetched_at: null, row_count: null, companies: 0, stale: false },
    { registry: 'US', fetched_at: null, row_count: null, companies: 0, stale: false },
    {
      registry: 'IE',
      fetched_at: '2026-09-04T05:29:57Z',
      row_count: 6360,
      companies: 21,
      stale: false,
    },
    {
      registry: 'CA',
      fetched_at: '2026-07-01T05:29:57Z',
      row_count: 7884,
      companies: 10,
      stale: true,
    },
  ],
}

const fetchMock = vi.fn()

function mockApi(overrides: { health?: CompanyHealth; coverage?: RegistryCoverage } = {}) {
  fetchMock.mockImplementation((url: RequestInfo | URL) => {
    const body = String(url) === '/registries' ? (overrides.coverage ?? coverage) : (overrides.health ?? health)
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response)
  })
}

function renderWidget() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <SourceHealth />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  mockApi()
  vi.stubGlobal('fetch', fetchMock)
  vi.useFakeTimers({ shouldAdvanceTime: true })
  // 8h30m after the fixture's last poll, so the rendered age is unambiguous.
  vi.setSystemTime(new Date('2026-09-15T13:30:04Z'))
})

afterEach(() => {
  if (vi.isFakeTimers()) vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

describe('SourceHealth widget', () => {
  it('renders the counts the API reports, not the prototype literals', async () => {
    renderWidget()

    const widget = within(await screen.findByTestId('source-health'))
    expect(widget.getByText('65')).toBeInTheDocument()
    expect(widget.getByText('3')).toBeInTheDocument()
    expect(widget.queryByText('44')).not.toBeInTheDocument()
  })

  it('shows a pending row — the fourth status the widget never had', async () => {
    // 2 seed companies have an ATS with no adapter yet. They were invisible: not OK, not
    // degraded, not quarantined, and absent from a widget that claimed to total the sources.
    renderWidget()

    const widget = within(await screen.findByTestId('source-health'))
    expect(widget.getByText(/pending/)).toBeInTheDocument()
    expect(widget.getByText('2')).toBeInTheDocument()
  })

  it('reports how long ago the last poll ran, not a bare clock time', async () => {
    // "poll 07:04" cannot tell this morning from last Tuesday — the exact defect this slice
    // exists to close, so the age is what renders.
    renderWidget()

    expect(await screen.findByText(/poll 8h ago/)).toBeInTheDocument()
  })

  it('says so when nothing has ever polled instead of inventing a time', async () => {
    mockApi({ health: { ...health, summary: { ...health.summary, last_poll_at: null } } })
    renderWidget()

    expect(await screen.findByText(/no poll yet/i)).toBeInTheDocument()
  })
})

describe('registry coverage', () => {
  it('names a register that has never been ingested instead of omitting it', async () => {
    // The finding slice 18 tripped over: SPEC §4 said the UK register was ingested, the
    // adapter exists and is wired into refresh.py, and no snapshot has ever been downloaded
    // onto this box. _available_ingesters prints a skip line and returns, so nothing said so.
    renderWidget()

    const block = within(await screen.findByTestId('registry-coverage'))
    expect(block.getByText('UK')).toBeInTheDocument()
    expect(block.getAllByText('never ingested')).toHaveLength(3) // UK, NL, US
  })

  it('reports an ingested snapshot’s rows, matches and age', async () => {
    renderWidget()

    const block = within(await screen.findByTestId('registry-coverage'))
    expect(block.getByText(/6,360 · 21 firms · 11d ago/)).toBeInTheDocument()
  })

  it('marks a snapshot that has aged past the staleness window', async () => {
    // The 45-day nag the digest already sends at 06:00, made visible on the way there.
    renderWidget()

    const block = within(await screen.findByTestId('registry-coverage'))
    expect(block.getByText(/7,884 · 10 firms · 76d ago · stale/)).toBeInTheDocument()
  })
})
