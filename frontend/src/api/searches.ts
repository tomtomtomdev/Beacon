import type { SavedSearch, SearchFilters } from './types'

export interface NewSearch {
  name: string
  filters: SearchFilters
}

export async function fetchSearches(): Promise<SavedSearch[]> {
  const response = await fetch('/searches')
  if (!response.ok) {
    throw new Error(`GET /searches failed: ${response.status}`)
  }
  return (await response.json()) as SavedSearch[]
}

export async function createSearch(body: NewSearch): Promise<SavedSearch> {
  const response = await fetch('/searches', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw new Error(`POST /searches failed: ${response.status}`)
  }
  return (await response.json()) as SavedSearch
}

export async function deleteSearch(id: number): Promise<void> {
  const response = await fetch(`/searches/${id}`, { method: 'DELETE' })
  if (!response.ok) {
    throw new Error(`DELETE /searches/${id} failed: ${response.status}`)
  }
}
