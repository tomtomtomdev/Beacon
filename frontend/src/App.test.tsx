import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const fetchMock = vi.fn()

beforeEach(() => {
  fetchMock.mockImplementation((url: string) => {
    let body: unknown = { total: 0, jobs: [] }
    if (String(url).startsWith('/searches')) body = []
    else if (String(url).startsWith('/settings/telegram')) {
      body = { chat_id: null, bot_token_set: false }
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response)
  })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('App', () => {
  it('renders the app name', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: /beacon/i })).toBeInTheDocument()
  })

  it('switches to the Saved searches view from the nav', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'Saved searches' }))

    expect(await screen.findByRole('heading', { name: /saved searches/i })).toBeInTheDocument()
  })

  it('switches to the Settings view from the nav', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'Settings' }))

    expect(await screen.findByRole('heading', { name: /settings/i })).toBeInTheDocument()
  })
})
