// How long ago something happened, at the granularity the source-health widget needs.
//
// Deliberately NOT jobs/postedAgo: that one is day-granular ("today" / "3d ago"), which is right
// for a posting date and useless for a poll that runs every 4–6 hours — every poll of the day
// would read "today". `now` is injected the same way, so both stay pure and testable.
export function ageLabel(iso: string, now: Date = new Date()): string {
  const minutes = Math.floor((now.getTime() - new Date(iso).getTime()) / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}
