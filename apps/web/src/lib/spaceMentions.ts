import type { MentionAgent } from '@/components/chat/MentionPalette'

export function parseSpaceMentions(text: string, agents: MentionAgent[]): MentionAgent[] {
  const handles = new Set(
    [...String(text || '').matchAll(/@([\w-]+)/g)].map((match) => match[1].toLowerCase()),
  )
  if (!handles.size) return []

  const matched: MentionAgent[] = []
  const seen = new Set<string>()
  for (const agent of agents) {
    const slug = agent.slug.toLowerCase()
    const name = agent.name.toLowerCase()
    const handle = agent.handle.toLowerCase()
    const compact = name.replace(/[^a-z0-9]+/g, '')
    if (
      !handles.has(slug) &&
      !handles.has(handle) &&
      !handles.has(name) &&
      !(compact && handles.has(compact))
    ) {
      continue
    }
    if (seen.has(agent.slug)) continue
    seen.add(agent.slug)
    matched.push(agent)
  }
  return matched
}
