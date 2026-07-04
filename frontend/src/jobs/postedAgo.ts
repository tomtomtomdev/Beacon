export function postedAgo(isoDate: string | null, now: Date = new Date()): string {
  if (!isoDate) return '—'
  const days = Math.floor((now.getTime() - new Date(isoDate).getTime()) / 86_400_000)
  if (days <= 0) return 'today'
  return `${days}d ago`
}
