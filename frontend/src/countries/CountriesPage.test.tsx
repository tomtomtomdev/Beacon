import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
      <CountriesPage />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  fetchMock.mockResolvedValue({ ok: true, json: () => Promise.resolve(countries) } as Response)
  vi.stubGlobal('fetch', fetchMock)
  // jsdom has no canvas 2d context; return null so the decorative draw is skipped cleanly.
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

  it('surfaces Sweden’s no-registry note and verified date verbatim', async () => {
    renderPage()

    const card = await screen.findByRole('button', { name: 'Sweden details' })
    const swedish = within(card)
    expect(swedish.getByText(/scheme discontinued Dec 2023/)).toBeInTheDocument()
    expect(swedish.getByText(/reform to 8yr/)).toBeInTheDocument()
    expect(swedish.getByText(/✓ 2026-01-15/)).toBeInTheDocument()
  })

  it('clicking a card cross-highlights its map pin', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('button', { name: 'Sweden details' })

    const pin = screen.getByRole('button', { name: 'Sweden on globe' })
    expect(pin).toHaveAttribute('aria-pressed', 'false')

    await user.click(screen.getByRole('button', { name: 'Sweden details' }))
    expect(pin).toHaveAttribute('aria-pressed', 'true')

    // Clicking again deselects (DESIGN §4 map toggle).
    await user.click(screen.getByRole('button', { name: 'Sweden details' }))
    expect(pin).toHaveAttribute('aria-pressed', 'false')
  })
})
