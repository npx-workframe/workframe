/** Compact @mention handle from a display name (matches server `_mention_handle`). */
export function mentionHandleFromLabel(label: string, fallback = ''): string {
  const compact = String(label || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '')
  if (compact) return compact.slice(0, 32)
  return fallback.trim().toLowerCase()
}
