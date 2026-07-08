import { ExternalLink, Eye, EyeOff, Star } from 'lucide-react'
import type { Job, SponsorTier, UserStatus } from '../api/types'
import styles from './JobTable.module.css'
import { postedAgo } from './postedAgo'
import { categoryLabel } from './taxonomy'

const TIER_LABEL: Record<SponsorTier, string> = {
  explicit_yes: 'Sponsors',
  registry_inferred: 'Registry',
  unknown: 'Unknown',
  explicit_no: 'No sponsor',
}

interface JobTableProps {
  jobs: Job[]
  onSetStatus: (id: number, status: UserStatus) => void
}

export function JobTable({ jobs, onSetStatus }: JobTableProps) {
  return (
    <div className={styles.card} data-testid="job-table">
      <div className={styles.headerRow}>
        <span>Role</span>
        <span>Location</span>
        <span>Category</span>
        <span>Level</span>
        <span className={styles.right}>Sponsor · Posted</span>
        <span />
      </div>
      {jobs.map((job) => {
        const starred = job.user_status === 'starred'
        const hidden = job.user_status === 'hidden'
        return (
        <div key={job.id} className={hidden ? `${styles.row} ${styles.rowMuted}` : styles.row}>
          <div className={styles.roleCell}>
            <div className={styles.title}>
              <span
                className={job.user_status === 'new' ? styles.newDot : styles.newDotIdle}
                aria-hidden
              />
              {job.title}
            </div>
            <div className={styles.company}>{job.company}</div>
          </div>
          <div className={styles.locationCell}>
            <div className={styles.city}>{job.location || '—'}</div>
            {job.country && <div className={styles.countryCode}>{job.country}</div>}
          </div>
          <div className={styles.categoryCell}>
            {job.categories.length > 0 ? (
              job.categories.map((category) => (
                <span key={category} className={styles.categoryChip}>
                  {categoryLabel(category)}
                </span>
              ))
            ) : (
              <span className={styles.categoryEmpty}>—</span>
            )}
          </div>
          <div className={styles.levelCell}>{job.level ? job.level.toUpperCase() : '—'}</div>
          <div className={styles.sponsorCell}>
            <span className={`${styles.tierChip} ${styles[job.sponsor_tier]}`}>
              <span className={styles.tierDot} aria-hidden />
              {TIER_LABEL[job.sponsor_tier]}
            </span>
            <span className={styles.posted}>{postedAgo(job.posted_at)}</span>
          </div>
          <div className={styles.actions}>
            <button
              type="button"
              className={starred ? styles.iconButtonActive : styles.iconButton}
              aria-label={`${starred ? 'Unstar' : 'Star'} ${job.title}`}
              aria-pressed={starred}
              onClick={() => onSetStatus(job.id, starred ? 'seen' : 'starred')}
            >
              <Star size={16} fill={starred ? 'currentColor' : 'none'} aria-hidden />
            </button>
            <button
              type="button"
              className={styles.iconButton}
              aria-label={`${hidden ? 'Restore' : 'Hide'} ${job.title}`}
              onClick={() => onSetStatus(job.id, hidden ? 'seen' : 'hidden')}
            >
              {hidden ? <Eye size={16} aria-hidden /> : <EyeOff size={16} aria-hidden />}
            </button>
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
        )
      })}
    </div>
  )
}
