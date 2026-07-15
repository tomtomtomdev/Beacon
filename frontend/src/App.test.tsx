import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const fetchMock = vi.fn()

beforeEach(() => {
  fetchMock.mockImplementation((url: string) => {
    let body: unknown = { total: 0, jobs: [] }
    if (String(url).startsWith('/countries')) body = []
    else if (String(url).startsWith('/searches')) body = []
    else if (String(url).startsWith('/resumes')) body = []
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

  it('defaults to the Countries globe home', async () => {
    render(<App />)
    expect(
      await screen.findByRole('heading', { name: /country & visa reference/i }),
    ).toBeInTheDocument()
  })

  it('switches to the Saved searches view from the nav', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /saved/i }))

    expect(await screen.findByRole('heading', { name: /saved searches/i })).toBeInTheDocument()
  })

  it('opens Settings from the rail footer', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'Settings' }))

    expect(await screen.findByRole('heading', { name: /settings/i })).toBeInTheDocument()
  })
})
