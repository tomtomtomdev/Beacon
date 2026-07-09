import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { TelegramSettings } from '../api/types'
import { SettingsPage } from './SettingsPage'

const fetchMock = vi.fn()

let current: TelegramSettings = { chat_id: null, bot_token_set: false }
let testResponse: { ok: boolean; status: number; body: unknown } = {
  ok: true,
  status: 200,
  body: { ok: true, channel: 'telegram' },
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <SettingsPage />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  current = { chat_id: null, bot_token_set: false }
  testResponse = { ok: true, status: 200, body: { ok: true, channel: 'telegram' } }
  fetchMock.mockImplementation((url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    if (url === '/settings/telegram' && method === 'GET') {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(current) } as Response)
    }
    if (url === '/settings/telegram' && method === 'PUT') {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(current) } as Response)
    }
    if (url === '/settings/telegram/test' && method === 'POST') {
      return Promise.resolve({
        ok: testResponse.ok,
        status: testResponse.status,
        json: () => Promise.resolve(testResponse.body),
      } as Response)
    }
    return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) } as Response)
  })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('SettingsPage', () => {
  it('shows the current chat id and a Connected status when creds are set', async () => {
    current = { chat_id: '4242', bot_token_set: true }
    renderPage()

    expect(await screen.findByText('Connected')).toBeInTheDocument()
    expect(screen.getByLabelText(/chat id/i)).toHaveValue('4242')
    // The token is never returned, so the field is empty but signals it is set.
    expect(screen.getByLabelText(/bot token/i)).toHaveValue('')
  })

  it('shows Not configured when nothing is set', async () => {
    renderPage()

    expect(await screen.findByText('Not configured')).toBeInTheDocument()
  })

  it('saves entered creds via PUT', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Not configured')

    await user.type(screen.getByLabelText(/bot token/i), '123:secret')
    await user.type(screen.getByLabelText(/chat id/i), '4242')
    await user.click(screen.getByRole('button', { name: /^save$/i }))

    await waitFor(() => {
      const put = fetchMock.mock.calls.find(
        (call) => String(call[0]) === '/settings/telegram' && call[1]?.method === 'PUT',
      )
      expect(put).toBeDefined()
      expect(JSON.parse(String(put?.[1]?.body))).toEqual({
        chat_id: '4242',
        bot_token: '123:secret',
      })
    })
  })

  it('omits the token (sends null) when the field is left blank', async () => {
    const user = userEvent.setup()
    current = { chat_id: '4242', bot_token_set: true }
    renderPage()
    await screen.findByText('Connected')

    await user.click(screen.getByRole('button', { name: /^save$/i }))

    await waitFor(() => {
      const put = fetchMock.mock.calls.find((call) => call[1]?.method === 'PUT')
      expect(JSON.parse(String(put?.[1]?.body))).toEqual({ chat_id: '4242', bot_token: null })
    })
  })

  it('sends a test message and reports the channel', async () => {
    const user = userEvent.setup()
    current = { chat_id: '4242', bot_token_set: true }
    renderPage()
    await screen.findByText('Connected')

    await user.click(screen.getByRole('button', { name: /send test message/i }))

    expect(await screen.findByText(/sent via telegram/i)).toBeInTheDocument()
  })

  it('surfaces the Telegram error when the test send fails', async () => {
    const user = userEvent.setup()
    current = { chat_id: 'bad', bot_token_set: true }
    testResponse = { ok: false, status: 400, body: { detail: 'chat not found' } }
    renderPage()
    await screen.findByText('Connected')

    await user.click(screen.getByRole('button', { name: /send test message/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent('chat not found')
  })
})
