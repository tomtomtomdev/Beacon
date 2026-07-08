import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { createSearch, deleteSearch, fetchSearches } from '../api/searches'
import type { SearchFilters, SponsorTier } from '../api/types'
import { categoryLabel } from '../jobs/taxonomy'
import styles from './SavedSearchesPage.module.css'

const CHANNEL_LABEL: Record<string, string> = { telegram: 'Telegram ✈', stdout: 'Stdout ▸' }

function summarize(filters: SearchFilters): string {
  const parts: string[] = []
  if (filters.categories.length) parts.push(filters.categories.map(categoryLabel).join('/'))
  if (filters.countries.length) parts.push(filters.countries.join('+'))
  if (filters.levels.length) parts.push(filters.levels.join('/'))
  if (filters.tiers.length) parts.push(`tier: ${filters.tiers.join(',')}`)
  if (filters.q) parts.push(`"${filters.q}"`)
  return parts.length ? parts.join(' · ') : 'all jobs'
}

function lastRunLabel(iso: string | null): string {
  return iso ? `last run ${new Date(iso).toLocaleDateString()}` : 'never run'
}

export function SavedSearchesPage() {
  const [searchParams] = useSearchParams()
  const currentFilters: SearchFilters = {
    q: searchParams.get('q'),
    countries: searchParams.getAll('country'),
    categories: searchParams.getAll('category'),
    levels: searchParams.getAll('level'),
    tiers: searchParams.getAll('sponsor_tier') as SponsorTier[],
  }

  const queryClient = useQueryClient()
  const { data: searches, isPending, isError } = useQuery({
    queryKey: ['searches'],
    queryFn: fetchSearches,
  })
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['searches'] })
  const createMutation = useMutation({ mutationFn: createSearch, onSuccess: invalidate })
  const deleteMutation = useMutation({ mutationFn: deleteSearch, onSuccess: invalidate })

  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')

  const openCreate = () => {
    setName(summarize(currentFilters))
    setCreating(true)
  }
  const submitCreate = (event: FormEvent) => {
    event.preventDefault()
    createMutation.mutate({ name: name.trim() || 'Untitled search', filters: currentFilters })
    setCreating(false)
    setName('')
  }

  return (
    <main className={styles.main}>
      <header className={styles.header}>
        <h1 className={styles.h1}>Saved searches</h1>
        <p className={styles.subtitle}>
          New matches ping your phone via Telegram after each poll.
        </p>
      </header>

      {isError && <p className={styles.stateText}>Could not reach the Beacon API.</p>}

      {!isError && !isPending && searches && searches.length === 0 && (
        <div className={styles.empty}>
          <p className={styles.emptyTitle}>No saved searches yet</p>
          <p className={styles.stateText}>
            Filter the Jobs view, then save it here to get alerted on new matches.
          </p>
        </div>
      )}

      <div className={styles.list}>
        {searches?.map((search) => (
          <article key={search.id} className={styles.card}>
            <div className={styles.cardMain}>
              <div className={styles.cardTop}>
                <h2 className={styles.cardName}>{search.name}</h2>
                <span
                  className={`${styles.pill} ${search.new_count > 0 ? styles.pillNew : styles.pillIdle}`}
                >
                  {search.new_count > 0 ? `${search.new_count} new` : 'up to date'}
                </span>
              </div>
              <p className={styles.summary}>{summarize(search.filters)}</p>
            </div>
            <div className={styles.cardSide}>
              <span className={styles.channel}>
                {CHANNEL_LABEL[search.notify_channel] ?? search.notify_channel}
              </span>
              <span className={styles.lastRun}>{lastRunLabel(search.last_run_at)}</span>
              <button
                type="button"
                className={styles.deleteButton}
                aria-label={`delete ${search.name}`}
                onClick={() => deleteMutation.mutate(search.id)}
              >
                Remove
              </button>
            </div>
          </article>
        ))}

        {creating ? (
          <form className={styles.createForm} onSubmit={submitCreate}>
            <label className={styles.createLabel} htmlFor="search-name">
              Name this search — it saves the current Jobs filters.
            </label>
            <div className={styles.createRow}>
              <input
                id="search-name"
                className={styles.nameInput}
                aria-label="search name"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
              <button type="submit" className={styles.saveButton}>
                Save
              </button>
              <button
                type="button"
                className={styles.cancelButton}
                onClick={() => setCreating(false)}
              >
                Cancel
              </button>
            </div>
            <p className={styles.summaryPreview}>{summarize(currentFilters)}</p>
          </form>
        ) : (
          <button type="button" className={styles.addButton} onClick={openCreate}>
            + New saved search from current filters
          </button>
        )}
      </div>
    </main>
  )
}
