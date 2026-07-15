import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Resume } from '../api/types'
import { ResumePanel } from './ResumePanel'

function makeResume(overrides: Partial<Resume> = {}): Resume {
  return {
    id: 1,
    label: 'My CV',
    active: true,
    created_at: '2026-07-15T00:00:00+00:00',
    resume_hash: 'abc123',
    profile: {
      categories: ['ios'],
      level: 'senior',
      years: 8,
      skills: ['swift', 'ios', 'combine'],
      target_countries: ['SE', 'NL'],
    },
    ...overrides,
  }
}

const fetchMock = vi.fn()
let resumesPayload: Resume[] = []

function ok(body: unknown): Promise<Response> {
  return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response)
}

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <ResumePanel />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  resumesPayload = []
  fetchMock.mockImplementation((url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url)
    const method = init?.method ?? 'GET'
    if (u === '/resumes' && method === 'GET') return ok(resumesPayload)
    if (u === '/resumes' && method === 'POST') return ok(makeResume())
    if (u.endsWith('/active') && method === 'PUT') return ok(makeResume())
    if (u.startsWith('/resumes/') && method === 'DELETE')
      return Promise.resolve({ ok: true, status: 204, json: () => Promise.resolve({}) } as Response)
    return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) } as Response)
  })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('ResumePanel', () => {
  it('lists stored resumes and marks the active one', async () => {
    resumesPayload = [
      makeResume({ id: 1, label: 'Active CV', active: true }),
      makeResume({ id: 2, label: 'Old CV', active: false }),
    ]
    renderPanel()

    expect(await screen.findByText('Active CV')).toBeInTheDocument()
    expect(screen.getByText('Old CV')).toBeInTheDocument()
    // The active resume shows an Active badge.
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('shows an empty hint when no resume is uploaded', async () => {
    renderPanel()

    expect(await screen.findByText(/no resume uploaded/i)).toBeInTheDocument()
  })

  it('pasting text and adding POSTs a new resume', async () => {
    const user = userEvent.setup()
    renderPanel()
    await screen.findByText(/no resume uploaded/i)

    await user.type(screen.getByLabelText(/label/i), 'Backend CV')
    await user.type(screen.getByLabelText(/resume text/i), 'Senior iOS engineer, 8 years of Swift.')
    await user.type(screen.getByLabelText(/target countries/i), 'se, nl')
    await user.click(screen.getByRole('button', { name: /add resume/i }))

    await waitFor(() => {
      const post = fetchMock.mock.calls.find(
        (call) => String(call[0]) === '/resumes' && call[1]?.method === 'POST',
      )
      expect(post).toBeDefined()
      expect(JSON.parse(String(post?.[1]?.body))).toEqual({
        label: 'Backend CV',
        text: 'Senior iOS engineer, 8 years of Swift.',
        target_countries: ['SE', 'NL'],
      })
    })
  })

  it('does not submit an empty resume', async () => {
    const user = userEvent.setup()
    renderPanel()
    await screen.findByText(/no resume uploaded/i)

    await user.click(screen.getByRole('button', { name: /add resume/i }))

    // Nothing posted — the button is inert without pasted text.
    expect(
      fetchMock.mock.calls.find((call) => call[1]?.method === 'POST'),
    ).toBeUndefined()
  })

  it('activating an inactive resume PUTs to /active', async () => {
    resumesPayload = [
      makeResume({ id: 1, label: 'Active CV', active: true }),
      makeResume({ id: 2, label: 'Old CV', active: false }),
    ]
    const user = userEvent.setup()
    renderPanel()
    await screen.findByText('Old CV')

    await user.click(screen.getByRole('button', { name: /use .*old cv/i }))

    await waitFor(() => {
      const put = fetchMock.mock.calls.find(
        (call) => String(call[0]) === '/resumes/2/active' && call[1]?.method === 'PUT',
      )
      expect(put).toBeDefined()
    })
  })

  it('deleting a resume DELETEs it', async () => {
    resumesPayload = [makeResume({ id: 5, label: 'Stale CV', active: false })]
    const user = userEvent.setup()
    renderPanel()
    await screen.findByText('Stale CV')

    await user.click(screen.getByRole('button', { name: /delete .*stale cv/i }))

    await waitFor(() => {
      const del = fetchMock.mock.calls.find(
        (call) => String(call[0]) === '/resumes/5' && call[1]?.method === 'DELETE',
      )
      expect(del).toBeDefined()
    })
  })

  it('loading a .txt file fills the resume text field', async () => {
    const user = userEvent.setup()
    renderPanel()
    await screen.findByText(/no resume uploaded/i)

    const file = new File(['iOS engineer resume body'], 'cv.txt', { type: 'text/plain' })
    await user.upload(screen.getByLabelText(/load \.txt/i), file)

    await waitFor(() => {
      expect(screen.getByLabelText(/resume text/i)).toHaveValue('iOS engineer resume body')
    })
  })

  it('shows the active profile summary (level and skill count)', async () => {
    resumesPayload = [makeResume({ id: 1, label: 'My CV', active: true })]
    renderPanel()

    const card = within(await screen.findByTestId('resume-1'))
    expect(card.getByText(/senior/i)).toBeInTheDocument()
    expect(card.getByText(/3 skills/i)).toBeInTheDocument()
  })
})
