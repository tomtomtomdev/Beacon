import { useQuery } from '@tanstack/react-query'
import { fetchCompanyHealth } from '../api/companies'
import type { CompanyHealthRow, HealthStatus, HealthSummary } from '../api/types'
import { postedAgo } from '../jobs/postedAgo'
import styles from './CompaniesPage.module.css'

const HEALTH_LABEL: Record<HealthStatus, string> = {
  ok: 'OK',
  degraded: 'Degraded',
  quarantined: 'Quarantined',
  pending: 'Pending',
}

const STATUS_CLASS: Record<HealthStatus, string> = {
  ok: styles.ok,
  degraded: styles.degraded,
  quarantined: styles.quarantined,
  pending: styles.pending,
}

// The mono reason beside the health badge (DESIGN §3): "gone", "2 failures · unreachable", …
function healthReason(row: CompanyHealthRow): string | null {
  switch (row.status) {
    case 'pending':
      return 'adapter pending'
    case 'quarantined':
      return row.reason
    case 'degraded':
      return `${row.consecutive_failures} failures · ${row.reason ?? ''}`.trim()
    case 'ok':
      return null
  }
}

export function CompaniesPage() {
  const { data, isPending, isError } = useQuery({
    queryKey: ['company-health'],
    queryFn: fetchCompanyHealth,
  })

  return (
    <main className={styles.main}>
      <header className={styles.header}>
        <h1 className={styles.h1}>Companies</h1>
        <p className={styles.subtitle}>
          Source health is a first-class state: sources that move, break, or go quiet are
          quarantined and surfaced here — never silently dropped, never corrupting the data.
        </p>
        {data && <p className={styles.seedLine}>{seedLine(data.companies, data.summary)}</p>}
      </header>

      {isError && <p className={styles.state}>Could not reach the Beacon API.</p>}
      {isPending && <p className={styles.state}>Loading…</p>}

      {data && (
        <>
          <SummaryCards summary={data.summary} />
          <HealthTable companies={data.companies} />
        </>
      )}
    </main>
  )
}

// "seed 53 · greenhouse 24 · lever 10 · ashby 11 · 8 awaiting adapters" — computed, never
// hardcoded: supported ATS types are those whose companies aren't pending.
function seedLine(companies: CompanyHealthRow[], summary: HealthSummary): string {
  const supported = new Map<string, number>()
  for (const company of companies) {
    if (company.status !== 'pending') {
      supported.set(company.ats_type, (supported.get(company.ats_type) ?? 0) + 1)
    }
  }
  const parts = [`seed ${summary.seed}`]
  for (const [ats, count] of supported) parts.push(`${ats} ${count}`)
  parts.push(`${summary.pending} awaiting adapters`)
  return parts.join(' · ')
}

const CARDS: readonly { key: keyof HealthSummary; label: string; tone?: HealthStatus }[] = [
  { key: 'seed', label: 'seed companies' },
  { key: 'supported', label: 'supported adapters' },
  { key: 'healthy', label: 'healthy', tone: 'ok' },
  { key: 'degraded', label: 'degraded', tone: 'degraded' },
  { key: 'quarantined', label: 'quarantined', tone: 'quarantined' },
  { key: 'pending', label: 'adapter pending', tone: 'pending' },
]

function SummaryCards({ summary }: { summary: HealthSummary }) {
  return (
    <div className={styles.cards}>
      {CARDS.map((card) => (
        <div key={card.key} className={styles.card}>
          <span className={`${styles.cardValue} ${card.tone ? STATUS_CLASS[card.tone] : ''}`}>
            {summary[card.key] as number}
          </span>
          <span className={styles.cardLabel}>{card.label}</span>
        </div>
      ))}
    </div>
  )
}

function HealthTable({ companies }: { companies: CompanyHealthRow[] }) {
  return (
    <div className={styles.table}>
      <div className={styles.head}>
        <span>Company</span>
        <span>ATS · slug</span>
        <span>HQ</span>
        <span>Last success</span>
        <span>Health</span>
      </div>
      {companies.map((company) => (
        <HealthRow key={company.name} company={company} />
      ))}
    </div>
  )
}

function HealthRow({ company }: { company: CompanyHealthRow }) {
  const reason = healthReason(company)
  return (
    <div className={styles.row}>
      <span className={styles.company}>{company.name}</span>
      <span className={styles.mono}>
        {company.ats_type}
        {company.ats_slug ? ` · ${company.ats_slug}` : ''}
      </span>
      <span className={styles.hq}>{company.country_hq}</span>
      <span className={styles.mono}>{postedAgo(company.last_success_at)}</span>
      <span className={styles.healthCell}>
        <span className={`${styles.badge} ${STATUS_CLASS[company.status]}`}>
          <span className={styles.dot} />
          {HEALTH_LABEL[company.status]}
        </span>
        {reason && <span className={styles.reason}>{reason}</span>}
      </span>
    </div>
  )
}
