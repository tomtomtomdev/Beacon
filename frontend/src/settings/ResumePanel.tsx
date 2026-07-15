import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Trash2, Upload } from 'lucide-react'
import { useState, type ChangeEvent, type FormEvent } from 'react'
import { activateResume, createResume, deleteResume, fetchResumes } from '../api/resumes'
import type { Resume } from '../api/types'
import styles from './ResumePanel.module.css'

// Resume upload + management (§11 slice 12d). The active resume drives ?resume= fit scoring on
// the Jobs list; scoring is a soft, opt-in signal, so this lives quietly in Settings.
export function ResumePanel() {
  const queryClient = useQueryClient()
  const { data: resumes, isPending, isError } = useQuery({
    queryKey: ['resumes'],
    queryFn: fetchResumes,
  })

  const [label, setLabel] = useState('')
  const [text, setText] = useState('')
  const [countries, setCountries] = useState('')

  // A resume change (add / activate / delete) re-scores the Jobs list, so both caches refresh.
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['resumes'] })
    queryClient.invalidateQueries({ queryKey: ['jobs'] })
  }

  const createMutation = useMutation({
    mutationFn: createResume,
    onSuccess: () => {
      invalidate()
      setLabel('')
      setText('')
      setCountries('')
    },
  })
  const activateMutation = useMutation({ mutationFn: activateResume, onSuccess: invalidate })
  const deleteMutation = useMutation({ mutationFn: deleteResume, onSuccess: invalidate })

  // Read a pasted-in .txt client-side (SPEC §11 always-available path); no server round-trip.
  const onFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      setText(String(reader.result ?? ''))
      if (!label) setLabel(file.name.replace(/\.txt$/i, ''))
    }
    reader.readAsText(file)
  }

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!text.trim()) return
    createMutation.mutate({
      label: label.trim() || 'Resume',
      text,
      target_countries: countries
        .split(',')
        .map((code) => code.trim().toUpperCase())
        .filter(Boolean),
    })
  }

  return (
    <section className={styles.wrap}>
      <div className={styles.cardHead}>
        <h2 className={styles.cardTitle}>Resume match</h2>
        <span className={styles.hint}>Scores each posting's fit — a soft signal, never a filter.</span>
      </div>

      {isError && <p className={styles.stateText}>Could not load resumes.</p>}

      {!isError && !isPending && resumes && (
        <>
          {resumes.length === 0 ? (
            <p className={styles.stateText}>No resume uploaded yet. Paste one below to score jobs.</p>
          ) : (
            <ul className={styles.list}>
              {resumes.map((resume) => (
                <li key={resume.id} className={styles.item} data-testid={`resume-${resume.id}`}>
                  <div className={styles.itemMain}>
                    <div className={styles.itemTop}>
                      <span className={styles.itemLabel}>{resume.label}</span>
                      {resume.active && <span className={styles.activeBadge}>Active</span>}
                    </div>
                    <div className={styles.itemMeta}>{profileSummary(resume)}</div>
                  </div>
                  <div className={styles.itemActions}>
                    {!resume.active && (
                      <button
                        type="button"
                        className={styles.useButton}
                        aria-label={`Use ${resume.label}`}
                        onClick={() => activateMutation.mutate(resume.id)}
                        disabled={activateMutation.isPending}
                      >
                        <Check size={14} aria-hidden />
                        Use
                      </button>
                    )}
                    <button
                      type="button"
                      className={styles.deleteButton}
                      aria-label={`Delete ${resume.label}`}
                      onClick={() => deleteMutation.mutate(resume.id)}
                      disabled={deleteMutation.isPending}
                    >
                      <Trash2 size={14} aria-hidden />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}

          <form className={styles.form} onSubmit={onSubmit}>
            <label className={styles.field}>
              <span className={styles.label}>Label</span>
              <input
                type="text"
                aria-label="label"
                className={styles.input}
                placeholder="e.g. iOS senior CV"
                value={label}
                onChange={(event) => setLabel(event.target.value)}
              />
            </label>

            <label className={styles.field}>
              <span className={styles.label}>Resume text</span>
              <textarea
                aria-label="resume text"
                className={styles.textarea}
                rows={7}
                placeholder="Paste your resume as plain text…"
                value={text}
                onChange={(event) => setText(event.target.value)}
              />
            </label>

            <label className={styles.field}>
              <span className={styles.label}>Target countries (optional)</span>
              <input
                type="text"
                aria-label="target countries"
                className={styles.input}
                placeholder="comma-separated ISO codes, e.g. SE, NL, GB"
                value={countries}
                onChange={(event) => setCountries(event.target.value)}
              />
            </label>

            <div className={styles.actions}>
              <button
                type="submit"
                className={styles.addButton}
                disabled={!text.trim() || createMutation.isPending}
              >
                {createMutation.isPending ? 'Adding…' : 'Add resume'}
              </button>
              <label className={styles.fileButton}>
                <Upload size={14} aria-hidden />
                Load .txt
                <input
                  type="file"
                  accept=".txt,text/plain"
                  aria-label="load .txt file"
                  className={styles.fileInput}
                  onChange={onFile}
                />
              </label>
              {createMutation.isError && (
                <span className={styles.errorNote} role="alert">
                  Could not add resume.
                </span>
              )}
            </div>
          </form>
        </>
      )}
    </section>
  )
}

function profileSummary(resume: Resume): string {
  const { level, skills, target_countries } = resume.profile
  const parts = [level, `${skills.length} skills`]
  if (target_countries.length > 0) parts.push(`target ${target_countries.join(', ')}`)
  return parts.join(' · ')
}
