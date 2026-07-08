import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const fetchMock = vi.fn()

beforeEach(() => {
  fetchMock.mockImplementation((url: string) => {
    const body = String(url).startsWith('/searches') ? [] : { total: 0, jobs: [] }
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
})
