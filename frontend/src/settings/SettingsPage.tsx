import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { fetchTelegramSettings, sendTestMessage, updateTelegramSettings } from '../api/settings'
import styles from './SettingsPage.module.css'

export function SettingsPage() {
  const queryClient = useQueryClient()
  const { data, isPending, isError } = useQuery({
    queryKey: ['settings', 'telegram'],
    queryFn: fetchTelegramSettings,
  })

  const saveMutation = useMutation({
    mutationFn: updateTelegramSettings,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['settings', 'telegram'] }),
  })
  const testMutation = useMutation({ mutationFn: sendTestMessage })

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const chatId = String(form.get('chat_id') ?? '').trim()
    const token = String(form.get('bot_token') ?? '')
    // A blank token means "keep the stored one" — the secret is never re-sent on save.
    saveMutation.mutate({
      chat_id: chatId || null,
      bot_token: token.trim() === '' ? null : token,
    })
  }

  return (
    <main className={styles.main}>
      <header className={styles.header}>
        <h1 className={styles.h1}>Settings</h1>
        <p className={styles.subtitle}>Where Beacon sends your saved-search digests.</p>
      </header>

      {isError && <p className={styles.stateText}>Could not reach the Beacon API.</p>}

      {!isError && !isPending && data && (
        <>
          <section className={styles.card}>
            <div className={styles.cardHead}>
              <h2 className={styles.cardTitle}>Telegram</h2>
              <span
                className={`${styles.status} ${
                  data.bot_token_set && data.chat_id ? styles.statusOn : styles.statusOff
                }`}
              >
                {data.bot_token_set && data.chat_id ? 'Connected' : 'Not configured'}
              </span>
            </div>

            {/* key resets the form (clears the token field, refreshes chat_id) after a
                save+refetch changes the stored settings. */}
            <form
              key={`${data.chat_id ?? ''}:${data.bot_token_set}`}
              className={styles.form}
              onSubmit={onSubmit}
            >
              <label className={styles.field}>
                <span className={styles.label}>Bot token</span>
                <input
                  type="password"
                  name="bot_token"
                  aria-label="bot token"
                  autoComplete="off"
                  className={styles.input}
                  placeholder={
                    data.bot_token_set ? '•••••••• (set — leave blank to keep)' : 'from @BotFather'
                  }
                />
              </label>

              <label className={styles.field}>
                <span className={styles.label}>Chat ID</span>
                <input
                  type="text"
                  name="chat_id"
                  aria-label="chat id"
                  className={styles.input}
                  defaultValue={data.chat_id ?? ''}
                  placeholder="e.g. 4242 or -100…"
                />
              </label>

              <div className={styles.actions}>
                <button type="submit" className={styles.saveButton} disabled={saveMutation.isPending}>
                  {saveMutation.isPending ? 'Saving…' : 'Save'}
                </button>
                {saveMutation.isSuccess && <span className={styles.savedNote}>Saved ✓</span>}
                {saveMutation.isError && (
                  <span className={styles.errorNote} role="alert">
                    Could not save.
                  </span>
                )}
              </div>
            </form>
          </section>

          <section className={styles.testRow}>
            <button
              type="button"
              className={styles.testButton}
              onClick={() => testMutation.mutate()}
              disabled={testMutation.isPending}
            >
              {testMutation.isPending ? 'Sending…' : 'Send test message'}
            </button>
            {testMutation.isSuccess && (
              <span className={styles.testOk}>
                Sent via {testMutation.data.channel} ✓
                {testMutation.data.channel === 'stdout' && ' (no creds set — printed to server log)'}
              </span>
            )}
            {testMutation.isError && (
              <span className={styles.testError} role="alert">
                {testMutation.error.message}
              </span>
            )}
          </section>
        </>
      )}
    </main>
  )
}
