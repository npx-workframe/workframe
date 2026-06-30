/** Active `@slug` token at the caret, if any. */
export function mentionTokenAt(value: string, caret: number): { start: number; query: string } | null {
  const before = value.slice(0, Math.max(0, caret))
  const match = before.match(/(?:^|[\s])@([\w-]*)$/)
  if (!match) return null
  const query = match[1] ?? ''
  const start = before.length - query.length - 1
  return { start, query }
}
