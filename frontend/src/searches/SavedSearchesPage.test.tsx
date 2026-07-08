import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { SavedSearch } from '../api/types'
import { SavedSearchesPage } from './SavedSearchesPage'

const searches: SavedSearch[] = [
  {
    id: 1,
    name: 'Senior iOS',
    filters: { q: null, countries: ['SE', 'NL'], categories: ['ios'], levels: ['senior'], tiers: [] },
    notify_channel: 'telegram',
    last_run_at: '2026-07-08T06:00:00+00:00',
    new_count: 3,
  },
  {
    id: 2,
    name: 'Backend anywhere',
    filters: { q: null, countries: [], categories: ['backend'], levels: [], tiers: [] },
    notify_channel: 'stdout',
    last_run_at: null,
    new_count: 0,
  },
]

const fetchMock = vi.fn()

function renderPage(initialUrl = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialUrl]}>
        <SavedSearchesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  fetchMock.mockImplementation((url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    if (url === '/searches' && method === 'GET') {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(searches) } as Response)
    }
    if (url === '/searches' && method === 'POST') {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(searches[0]) } as Response)
    }
    if (method === 'DELETE') {
      return Promise.resolve({ ok: true, status: 204, json: () => Promise.resolve({}) } as Response)
    }
    return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) } as Response)
  })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('SavedSearchesPage', () => {
  it('renders a card per saved search with its filter summary', async () => {
    renderPage()

    expect(await screen.findByText('Senior iOS')).toBeInTheDocument()
    expect(screen.getByText('Backend anywhere')).toBeInTheDocument()
    // Filter summary is rendered (categories + countries + levels).
    expect(screen.getByText(/iOS · SE\+NL · senior/i)).toBeInTheDocument()
  })

  it('shows an "N new" pill when there are new matches and "up to date" otherwise', async () => {
    renderPage()

    expect(await screen.findByText('3 new')).toBeInTheDocument()
    expect(screen.getByText(/up to date/i)).toBeInTheDocument()
  })

  it('creates a saved search from the current filters in the URL', async () => {
    const user = userEvent.setup()
    renderPage('/?category=ios&country=SE&country=NL&level=senior&sponsor_tier=registry_inferred')
    await screen.findByText('Senior iOS')

    await user.click(screen.getByRole('button', { name: /new saved search from current filters/i }))
    const nameInput = screen.getByRole('textbox', { name: /search name/i })
    await user.clear(nameInput)
    await user.type(nameInput, 'My iOS alert')
    await user.click(screen.getByRole('button', { name: /^save$/i }))

    await waitFor(() => {
      const post = fetchMock.mock.calls.find(
        (call) => String(call[0]) === '/searches' && call[1]?.method === 'POST',
      )
      expect(post).toBeDefined()
      expect(JSON.parse(String(post?.[1]?.body))).toEqual({
        name: 'My iOS alert',
        filters: {
          q: null,
          countries: ['SE', 'NL'],
          categories: ['ios'],
          levels: ['senior'],
          tiers: ['registry_inferred'],
        },
      })
    })
  })

  it('deletes a saved search when its remove button is clicked', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Senior iOS')

    await user.click(screen.getByRole('button', { name: /delete Senior iOS/i }))

    await waitFor(() => {
      const del = fetchMock.mock.calls.find(
        (call) => String(call[0]) === '/searches/1' && call[1]?.method === 'DELETE',
      )
      expect(del).toBeDefined()
    })
  })

  it('shows an empty state when there are no saved searches', async () => {
    fetchMock.mockImplementation(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve([]) } as Response),
    )

    renderPage()

    expect(await screen.findByText(/no saved searches yet/i)).toBeInTheDocument()
  })
})
