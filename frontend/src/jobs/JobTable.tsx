import { ExternalLink } from 'lucide-react'
import type { Job, SponsorTier } from '../api/types'
import styles from './JobTable.module.css'
import { postedAgo } from './postedAgo'

const TIER_LABEL: Record<SponsorTier, string> = {
  explicit_yes: 'Sponsors',
  registry_inferred: 'Registry',
  unknown: 'Unknown',
  explicit_no: 'No sponsor',
}

export function JobTable({ jobs }: { jobs: Job[] }) {
  return (
    <div className={styles.card}>
      <div className={styles.headerRow}>
        <span>Role</span>
        <span>Location</span>
        <span className={styles.right}>Sponsor · Posted</span>
        <span />
      </div>
      {jobs.map((job) => (
        <div key={job.id} className={styles.row}>
          <div className={styles.roleCell}>
            <div className={styles.title}>{job.title}</div>
            <div className={styles.company}>{job.company}</div>
          </div>
          <div className={styles.locationCell}>
            <div className={styles.city}>{job.location || '—'}</div>
            {job.country && <div className={styles.countryCode}>{job.country}</div>}
          </div>
          <div className={styles.sponsorCell}>
            <span className={`${styles.tierChip} ${styles[job.sponsor_tier]}`}>
              <span className={styles.tierDot} aria-hidden />
              {TIER_LABEL[job.sponsor_tier]}
            </span>
            <span className={styles.posted}>{postedAgo(job.posted_at)}</span>
          </div>
          <div className={styles.actions}>
            <a
              className={styles.iconButton}
              href={job.url}
              target="_blank"
              rel="noreferrer"
              aria-label={`Open original posting: ${job.title}`}
            >
              <ExternalLink size={16} aria-hidden />
            </a>
          </div>
        </div>
      ))}
    </div>
  )
}
