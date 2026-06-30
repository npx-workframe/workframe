export type ChatSegment =
  | { kind: 'text'; text: string }
  | { kind: 'thinking'; text: string }
  | { kind: 'image'; path: string; name?: string; alt?: string }
  | {
      kind: 'tool'
      name: string
      status: 'running' | 'done' | 'error'
      input?: string
      output?: string
      /** Live progress hint from tool.progress events */
      preview?: string
    }

export type ChatMessage = {
  id: string
  /** Hermes profile slug or `user`. */
  authorId: string
  authorName: string
  role: 'user' | 'agent'
  segments: ChatSegment[]
  timestamp: string
  tokens: number
  /** Live stream placeholder — replaced on history refresh. */
  ephemeral?: boolean
  color?: string
  avatarUrl?: string | null
  initials?: string
}

export type ChatModel = {
  id: string
  label: string
  provider: string
}

export function modelLabelFromId(modelId: string): string {
  const trimmed = modelId.trim()
  if (!trimmed) return 'No model'
  const slash = trimmed.lastIndexOf('/')
  return slash >= 0 ? trimmed.slice(slash + 1) : trimmed
}

export function emptyAgentStreamMessage(
  id: string,
  authorId: string,
  authorName: string,
  timestamp: string,
  avatarUrl?: string | null,
): ChatMessage {
  return {
    id,
    authorId,
    authorName,
    role: 'agent',
    segments: [],
    timestamp,
    tokens: 0,
    ephemeral: true,
    ...(avatarUrl ? { avatarUrl } : {}),
  }
}

export function userChatMessage(id: string, text: string, timestamp: string): ChatMessage {
  return {
    id,
    authorId: 'user',
    authorName: 'You',
    role: 'user',
    segments: [{ kind: 'text', text }],
    timestamp,
    tokens: 0,
  }
}

export function userImageChatMessage(
  id: string,
  path: string,
  name: string,
  timestamp: string,
  caption = '',
): ChatMessage {
  const segments: ChatMessage['segments'] = [{ kind: 'image', path, name, alt: name }]
  if (caption.trim()) segments.push({ kind: 'text', text: caption.trim() })
  return {
    id,
    authorId: 'user',
    authorName: 'You',
    role: 'user',
    segments,
    timestamp,
    tokens: 0,
  }
}
