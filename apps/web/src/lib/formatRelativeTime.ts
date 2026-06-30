/** Compact relative time: just now, 3m ago, 3h ago, 3d ago, 3w ago, 3mo ago, 3yr ago */
export function formatRelativeTime(isoOrMs: string | number): string {
  const then = typeof isoOrMs === 'number' ? isoOrMs : Date.parse(isoOrMs)
  if (!Number.isFinite(then)) return ''

  const deltaSec = Math.max(0, Math.floor((Date.now() - then) / 1000))
  if (deltaSec < 45) return 'just now'

  const minutes = Math.floor(deltaSec / 60)
  if (minutes < 60) return `${minutes}m ago`

  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`

  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`

  const weeks = Math.floor(days / 7)
  if (weeks < 5) return `${weeks}w ago`

  const months = Math.floor(days / 30)
  if (months < 12) return `${months}mo ago`

  const years = Math.floor(days / 365)
  return `${Math.max(1, years)}yr ago`
}
