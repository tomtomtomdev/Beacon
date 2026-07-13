import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Country } from '../api/types'
import { CountriesPage } from './CountriesPage'

const countries: Country[] = [
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
    const body = String(url).startsWith('/countries') ? countries : { total: 0, jobs: [] }
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

describe('CountriesPage', () => {
  it('renders a card per country from the API', async () => {
    renderPage()

    expect(await screen.findByRole('button', { name: 'Netherlands details' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sweden details' })).toBeInTheDocument()
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

  it('a globe pin control opens the selection', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('button', { name: 'Sweden details' })

    const pin = screen.getByRole('button', { name: 'Sweden on globe' })
    expect(pin).toHaveAttribute('aria-pressed', 'false')

    await user.click(pin)
    expect(await screen.findByRole('heading', { name: 'Jobs · Sweden' })).toBeInTheDocument()
  })
})
