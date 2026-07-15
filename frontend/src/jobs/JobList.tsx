import { Eye, EyeOff, Star } from 'lucide-react'
import type { Job, UserStatus } from '../api/types'
import styles from './JobList.module.css'
import { postedAgo } from './postedAgo'
import { TIER_LABEL } from './taxonomy'

interface JobListProps {
  jobs: Job[]
  onOpen: (id: number) => void
  onSetStatus: (id: number, status: UserStatus) => void
}

// Compact stacked job cards (Beacon-2 §2) — the narrow side panel replaces the wide table:
// title over company, star/hide actions top-right, then a sponsor · city · level · posted meta row.
export function JobList({ jobs, onOpen, onSetStatus }: JobListProps) {
  return (
    <div className={styles.list} data-testid="job-list">
      {jobs.map((job) => {
        const starred = job.user_status === 'starred'
        const hidden = job.user_status === 'hidden'
        return (
          <div key={job.id} className={hidden ? `${styles.card} ${styles.cardMuted}` : styles.card}>
            <div className={styles.top}>
              <button
                type="button"
                className={styles.roleButton}
                aria-label={`Open ${job.title} details`}
                onClick={() => onOpen(job.id)}
              >
                <span className={styles.title}>{job.title}</span>
                <span className={styles.company}>{job.company}</span>
              </button>
              <div className={styles.actions}>
                <button
                  type="button"
                  className={starred ? styles.iconButtonActive : styles.iconButton}
                  aria-label={`${starred ? 'Unstar' : 'Star'} ${job.title}`}
                  aria-pressed={starred}
                  onClick={() => onSetStatus(job.id, starred ? 'seen' : 'starred')}
                >
                  <Star size={15} fill={starred ? 'currentColor' : 'none'} aria-hidden />
                </button>
                <button
                  type="button"
                  className={styles.iconButton}
                  aria-label={`${hidden ? 'Restore' : 'Hide'} ${job.title}`}
                  onClick={() => onSetStatus(job.id, hidden ? 'seen' : 'hidden')}
                >
                  {hidden ? <Eye size={15} aria-hidden /> : <EyeOff size={15} aria-hidden />}
                </button>
              </div>
            </div>
            <div className={styles.meta}>
              <span className={`${styles.tierChip} ${styles[job.sponsor_tier]}`}>
                <span className={styles.tierDot} aria-hidden />
                {TIER_LABEL[job.sponsor_tier]}
              </span>
              {job.match_score && (
                <span className={styles.fitChip}>Fit {job.match_score.overall}</span>
              )}
              {job.city && <span className={styles.city}>{job.city}</span>}
              {job.level && <span className={styles.level}>{job.level.toUpperCase()}</span>}
              <span className={styles.posted}>{postedAgo(job.posted_at)}</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
