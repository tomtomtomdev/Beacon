import { useQuery } from '@tanstack/react-query'
import { companyHealthQuery } from '../api/companies'
import { fetchRegistryCoverage } from '../api/registries'
import type { HealthSummary, RegistryCoverageRow } from '../api/types'
import styles from './CountriesPage.module.css'
import { ageLabel } from './freshness'

// The glass widget folded into the globe legend (DESIGN §1, bottom-right). Every number here
// is read off the API: it shipped as four literals ("44 OK / 1 degraded / 2 quarantined /
// poll 07:04") against a live 65/0/3 with two pending sources it had no row for, and that
// class of defect — asserting what was never measured — is what slice 19 exists to close.

type StatusKey = 'healthy' | 'degraded' | 'quarantined' | 'pending'

const STATUS_ROWS: readonly { key: StatusKey; label: string; dot: string }[] = [
  { key: 'healthy', label: 'OK', dot: styles.dotOk },
  { key: 'degraded', label: 'degraded', dot: styles.dotDegraded },
  { key: 'quarantined', label: 'quarantined', dot: styles.dotQuarantined },
  // A seed company whose ATS has no adapter yet. It has never been polled, so it is neither
  // healthy nor failing — and until now it was simply missing from a widget that read as a total.
  { key: 'pending', label: 'pending', dot: styles.dotPending },
]

export function SourceHealth() {
  const { data: health, isError: healthFailed } = useQuery(companyHealthQuery)
  const { data: coverage } = useQuery({
    queryKey: ['registryCoverage'],
    queryFn: fetchRegistryCoverage,
  })

  return (
    <div className={styles.health} data-testid="source-health">
      <div className={styles.healthHead}>
        <span className={styles.healthLabel}>Source health</span>
        <span className={styles.healthPoll}>{pollLabel(health?.summary.last_poll_at ?? null)}</span>
      </div>
      {healthFailed && <div className={styles.healthState}>counts unavailable</div>}
      {health && (
        <div className={styles.healthRows}>
          {STATUS_ROWS.map((row) => (
            <div key={row.key} className={styles.healthRow}>
              <span className={`${styles.healthDot} ${row.dot}`} />
              <span className={styles.healthCount}>{health.summary[row.key]}</span> {row.label}
            </div>
          ))}
        </div>
      )}
      {coverage && <RegistryCoverageBlock rows={coverage.registries} />}
    </div>
  )
}

// A bare clock time cannot tell this morning's poll from last Tuesday's, which is the same
// failure mode as the counts it sits beside — so the age is what renders.
function pollLabel(lastPollAt: HealthSummary['last_poll_at']): string {
  return lastPollAt ? `poll ${ageLabel(lastPollAt)}` : 'no poll yet'
}

// Sponsor-registry coverage. The absence is the point: UK/NL/US have adapters, are wired into
// refresh.py and have never been ingested here, and nothing on screen said so.
function RegistryCoverageBlock({ rows }: { rows: RegistryCoverageRow[] }) {
  return (
    <div className={styles.registries} data-testid="registry-coverage">
      <span className={styles.healthLabel}>Registers</span>
      <div className={styles.registryRows}>
        {rows.map((row) => (
          <div key={row.registry} className={styles.registryRow}>
            <span className={styles.registryName}>{row.registry}</span>
            <span className={row.fetched_at ? styles.registryDetail : styles.registryMissing}>
              {registryDetail(row)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function registryDetail(row: RegistryCoverageRow): string {
  if (!row.fetched_at) return 'never ingested'
  const rows = row.row_count?.toLocaleString('en-US') ?? '—'
  const age = ageLabel(row.fetched_at)
  return `${rows} · ${row.companies} firms · ${row.stale ? `${age} · stale` : age}`
}
