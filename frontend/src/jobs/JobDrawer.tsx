import { useQuery } from '@tanstack/react-query'
import { ExternalLink, Eye, EyeOff, Globe, Star, X } from 'lucide-react'
import { useEffect } from 'react'
import { fetchCountries } from '../api/countries'
import { fetchJobDetail } from '../api/jobs'
import type { JobDetail, MatchScore, SponsorTier, UserStatus } from '../api/types'
import styles from './JobDrawer.module.css'
import { TIER_LABEL } from './taxonomy'
import { postedAgo } from './postedAgo'

// Sponsorship-evidence card heading per tier (DESIGN.md §2).
const EVIDENCE_HEADER: Record<SponsorTier, string> = {
  explicit_yes: 'Sponsorship offered',
  explicit_no: 'No sponsorship',
  registry_inferred: 'Registry-inferred signal',
  unknown: 'No signal detected',
}

const STATUS_LABEL: Record<UserStatus, string> = {
  new: 'New',
  seen: 'Seen',
  starred: '★ Starred',
  hidden: 'Hidden',
}

// Friendly names for the registers a company matched (DESIGN.md §2 registry rows).
const REGISTRY_LABEL: Record<string, string> = {
  UK: 'UK Home Office licensed sponsors',
  NL: 'IND recognised sponsors (Netherlands)',
  US: 'US H-1B LCA disclosures',
  MANUAL: 'Manually verified sponsor',
}

interface JobDrawerProps {
  jobId: number
  // The resume-fit score for this job, already computed for the list row (§11); null when no
  // resume is active. Passed down rather than refetched — the row is page-bounded-scored.
  matchScore: MatchScore | null
  onClose: () => void
  onSetStatus: (id: number, status: UserStatus) => void
}

export function JobDrawer({ jobId, matchScore, onClose, onSetStatus }: JobDrawerProps) {
  const { data: job, isPending, isError } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => fetchJobDetail(jobId),
  })
  const { data: countries } = useQuery({ queryKey: ['countries'], queryFn: fetchCountries })

  // Esc closes the drawer (DESIGN.md §Interactions) — a document-level listener is an
  // external subscription, so an effect with cleanup is the right tool.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const country = job?.country ? countries?.find((c) => c.code === job.country) : undefined

  return (
    <div className={styles.overlay} onClick={onClose} data-testid="drawer-overlay">
      <aside
        className={styles.panel}
        role="dialog"
        aria-modal="true"
        aria-label={job ? job.title : 'Job details'}
        onClick={(event) => event.stopPropagation()}
      >
        {isError && <p className={styles.state}>Could not load this posting.</p>}
        {isPending && <p className={styles.state}>Loading…</p>}
        {job && (
          <>
            <header className={styles.header}>
              <div className={styles.headerText}>
                <div className={styles.company}>{job.company}</div>
                <h2 className={styles.title}>{job.title}</h2>
              </div>
              <div className={styles.actions}>
                <button
                  type="button"
                  className={styles.actionButton}
                  aria-label={job.user_status === 'starred' ? 'Unstar' : 'Star'}
                  aria-pressed={job.user_status === 'starred'}
                  onClick={() =>
                    onSetStatus(job.id, job.user_status === 'starred' ? 'seen' : 'starred')
                  }
                >
                  <Star
                    size={17}
                    fill={job.user_status === 'starred' ? 'currentColor' : 'none'}
                    aria-hidden
                  />
                </button>
                <button
                  type="button"
                  className={styles.actionButton}
                  aria-label={job.user_status === 'hidden' ? 'Restore' : 'Hide'}
                  onClick={() =>
                    onSetStatus(job.id, job.user_status === 'hidden' ? 'seen' : 'hidden')
                  }
                >
                  {job.user_status === 'hidden' ? (
                    <Eye size={17} aria-hidden />
                  ) : (
                    <EyeOff size={17} aria-hidden />
                  )}
                </button>
                <button
                  type="button"
                  className={styles.actionButton}
                  aria-label="Close"
                  onClick={onClose}
                >
                  <X size={17} aria-hidden />
                </button>
              </div>
            </header>

            <div className={styles.chips}>
              <span className={`${styles.tierChip} ${styles[job.sponsor_tier]}`}>
                <span className={styles.tierDot} aria-hidden />
                {TIER_LABEL[job.sponsor_tier]}
              </span>
              <span className={`${styles.statusPill} ${styles[`status_${job.user_status}`]}`}>
                {STATUS_LABEL[job.user_status]}
              </span>
              {job.city && <span className={styles.chip}>{job.city}</span>}
              {job.country && <span className={styles.chip}>{job.country}</span>}
              {job.level && <span className={styles.chip}>{job.level.toUpperCase()}</span>}
              <span className={styles.posted}>{postedAgo(job.posted_at)}</span>
            </div>

            <SponsorshipCard job={job} />

            {matchScore && <FitCard score={matchScore} />}

            <section className={styles.section}>
              <div className={styles.sectionLabel}>Description</div>
              {job.description
                .split(/\n+/)
                .map((para) => para.trim())
                .filter(Boolean)
                .map((para, index) => (
                  <p key={index} className={styles.paragraph}>
                    {para}
                  </p>
                ))}
            </section>

            <section
              className={`${styles.section} ${styles.countryPanel}`}
              data-testid="country-panel"
            >
              <div className={styles.countryHeader}>
                <Globe size={16} aria-hidden />
                {country ? `${country.name} — relocation reference` : 'Relocation reference'}
              </div>
              {country ? (
                <>
                  <div className={styles.countryBlocks}>
                    <div className={styles.countryBlock}>
                      <div className={styles.countryBlockLabel}>Work visa</div>
                      <div className={styles.countryBlockValue}>{country.visa_summary}</div>
                    </div>
                    <div className={styles.countryBlock}>
                      <div className={styles.countryBlockLabel}>PR path</div>
                      <div className={styles.countryBlockValue}>{country.pr_summary}</div>
                    </div>
                    <div className={styles.countryBlock}>
                      <div className={styles.countryBlockLabel}>Citizenship</div>
                      <div className={styles.countryBlockValue}>{country.citizenship_summary}</div>
                    </div>
                  </div>
                  <div className={styles.verified}>verified {country.verified_at}</div>
                </>
              ) : (
                <p className={styles.countryEmpty}>
                  No relocation reference on file for this location.
                </p>
              )}
            </section>

            <section className={styles.section}>
              <div className={styles.sectionLabel}>
                Sources
                {job.duplicate_sources.length > 1 &&
                  ` · deduped across ${job.duplicate_sources.length}`}
              </div>
              {job.duplicate_sources.map((source) => (
                <div key={source.url} className={styles.sourceRow}>
                  {source.source} · {source.company}
                </div>
              ))}
              <a
                className={styles.cta}
                href={job.url}
                target="_blank"
                rel="noreferrer"
              >
                Open original posting <ExternalLink size={15} aria-hidden />
              </a>
            </section>
          </>
        )}
      </aside>
    </div>
  )
}

function SponsorshipCard({ job }: { job: JobDetail }) {
  const tier = job.sponsor_tier
  return (
    <section
      className={`${styles.evidenceCard} ${styles[`evidence_${tier}`]}`}
      data-testid="sponsorship-card"
    >
      <div className={styles.evidenceHeader}>{EVIDENCE_HEADER[tier]}</div>
      {(tier === 'explicit_yes' || tier === 'explicit_no') && job.sponsor_evidence && (
        <blockquote className={styles.evidenceQuote}>“{job.sponsor_evidence}”</blockquote>
      )}
      {tier === 'registry_inferred' && (
        <div className={styles.evidenceBody}>
          <p>Posting text is silent on sponsorship, but the company appears on:</p>
          <ul className={styles.registryList}>
            {job.registries.map((code) => (
              <li key={code} className={styles.registryRow}>
                <span className={styles.registryDot} aria-hidden />
                {REGISTRY_LABEL[code] ?? code}
              </li>
            ))}
          </ul>
          {job.match_confidence !== null && (
            <p className={styles.confidence}>
              Match confidence {job.match_confidence.toFixed(2)} · company-level signal, not a
              per-role guarantee.
            </p>
          )}
        </div>
      )}
      {tier === 'unknown' && (
        <p className={styles.evidenceBody}>
          No sponsorship language detected and no registry match. Shown, ranked below explicit and
          registry signals — never excluded.
        </p>
      )}
    </section>
  )
}

// Sub-scores in display order (category alignment folds into `overall` — no stored column, §11).
const FIT_SUBSCORES: ReadonlyArray<{ key: keyof MatchScore; label: string }> = [
  { key: 'skills_score', label: 'Skills' },
  { key: 'level_score', label: 'Level' },
  { key: 'sponsor_score', label: 'Sponsor / country' },
]

// Résumé-fit card — a soft signal rendered exactly like the sponsorship card (§11): overall
// score, the sub-scores that built it, and the matched/missing skill breakdown. Never a filter.
function FitCard({ score }: { score: MatchScore }) {
  return (
    <section className={styles.fitCard} data-testid="fit-card">
      <div className={styles.fitHead}>
        <div className={styles.fitHeader}>Résumé fit</div>
        <div className={styles.fitOverall}>
          <span className={styles.fitOverallValue}>{score.overall}</span>
          <span className={styles.fitOverallMax}>/100</span>
        </div>
      </div>

      <div className={styles.fitBars}>
        {FIT_SUBSCORES.map(({ key, label }) => {
          const value = score[key] as number
          return (
            <div key={key} className={styles.fitBarRow}>
              <span className={styles.fitBarLabel}>{label}</span>
              <span className={styles.fitBarTrack} aria-hidden>
                <span className={styles.fitBarFill} style={{ width: `${value}%` }} />
              </span>
              <span className={styles.fitBarValue}>{value}</span>
            </div>
          )
        })}
      </div>

      <div className={styles.fitSkills}>
        <div className={styles.fitSkillGroup}>
          <div className={styles.fitSkillLabel}>Matched skills</div>
          {score.matched_skills.length > 0 ? (
            <div className={styles.fitChips}>
              {score.matched_skills.map((skill) => (
                <span key={skill} className={styles.fitChipMatched}>
                  {skill}
                </span>
              ))}
            </div>
          ) : (
            <p className={styles.fitSkillEmpty}>None of the job's skills are on your resume.</p>
          )}
        </div>
        <div className={styles.fitSkillGroup}>
          <div className={styles.fitSkillLabel}>Missing skills</div>
          {score.missing_skills.length > 0 ? (
            <div className={styles.fitChips}>
              {score.missing_skills.map((skill) => (
                <span key={skill} className={styles.fitChipMissing}>
                  {skill}
                </span>
              ))}
            </div>
          ) : (
            <p className={styles.fitSkillEmpty}>You cover every skill this posting names.</p>
          )}
        </div>
      </div>

      <p className={styles.fitNote}>
        Heuristic fit against your active resume — a soft signal, like the sponsorship badge. Never
        hides a posting.
      </p>
    </section>
  )
}
