import styles from './PanelTabs.module.css'

export type Panel = 'jobs' | 'markets'

// The side panel used to be gated on ?focus=: no country selected meant the card stack, and the
// job list was unreachable until you tapped a beacon. Jobs is the default now and the visa
// reference is a tab — the panel's content is a choice, not a consequence of the globe.
export function PanelTabs({
  panel,
  onPanelChange,
}: {
  panel: Panel
  onPanelChange: (panel: Panel) => void
}) {
  return (
    <div className={styles.tabs} role="group" aria-label="Side panel">
      {(['jobs', 'markets'] as const).map((value) => (
        <button
          key={value}
          type="button"
          className={panel === value ? styles.segmentActive : styles.segment}
          aria-pressed={panel === value}
          onClick={() => onPanelChange(value)}
        >
          {value === 'jobs' ? 'Jobs' : 'Markets'}
        </button>
      ))}
    </div>
  )
}
