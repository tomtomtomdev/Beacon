import type { TelegramSettings, TelegramSettingsUpdate, TestResult } from './types'

export async function fetchTelegramSettings(): Promise<TelegramSettings> {
  const response = await fetch('/settings/telegram')
  if (!response.ok) {
    throw new Error(`GET /settings/telegram failed: ${response.status}`)
  }
  return (await response.json()) as TelegramSettings
}

export async function updateTelegramSettings(
  body: TelegramSettingsUpdate,
): Promise<TelegramSettings> {
  const response = await fetch('/settings/telegram', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw new Error(`PUT /settings/telegram failed: ${response.status}`)
  }
  return (await response.json()) as TelegramSettings
}

export async function sendTestMessage(): Promise<TestResult> {
  const response = await fetch('/settings/telegram/test', { method: 'POST' })
  if (!response.ok) {
    // The API surfaces Telegram's own reason (e.g. "chat not found") in `detail`.
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `test send failed: ${response.status}`)
  }
  return (await response.json()) as TestResult
}
