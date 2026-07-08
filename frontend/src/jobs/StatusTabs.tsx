import type { StatusView } from '../api/jobs'
import styles from './StatusTabs.module.css'

// DESIGN.md §2 status segmented control — the primary "what am I looking at" switch.
// Live per-segment counts (DESIGN) land with the nav badge work in slice 10.
const VIEWS: ReadonlyArray<{ value: StatusView; label: string }> = [
  { value: 'new', label: 'New' },
  { value: 'starred', label: 'Starred' },
  { value: 'all', label: 'All' },
  { value: 'hidden', label: 'Hidden' },
]

interface StatusTabsProps {
  view: StatusView
  onViewChange: (view: StatusView) => void
}

export function StatusTabs({ view, onViewChange }: StatusTabsProps) {
  return (
    <div className={styles.track} role="group" aria-label="Status view">
      {VIEWS.map(({ value, label }) => (
        <button
          key={value}
          type="button"
          className={view === value ? styles.segmentActive : styles.segment}
          aria-pressed={view === value}
          onClick={() => onViewChange(value)}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
