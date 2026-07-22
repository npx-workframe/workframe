import type { WorkframeNoticeInfo } from '@/lib/workframeErrors'
import { billingProviderDisplayLabel } from '@/lib/brandAssets'
import { inferProviderFromModelId } from '@/lib/workframeAssets'

export type ChatSegment =
  | { kind: 'text'; text: string }
  | { kind: 'thinking'; text: string }
  | { kind: 'concierge'; notice: WorkframeNoticeInfo }
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
  /** ISO-8601 timestamp for relative display. */
  timestamp: string
  tokens: number
  /** Billing provider slug for agent turns (e.g. openrouter, codex). */
  llmProvider?: string
  /** Model id used for this agent turn. */
  modelId?: string
  /** Live stream placeholder — replaced on history refresh. */
  ephemeral?: boolean
  color?: string
  avatarUrl?: string | null
  initials?: string
  replyTo?: ChatReplyTarget
}

export type ChatReplyTarget = {
  id: string
  authorId: string
  authorName: string
  preview: string
}

export type ChatReaction = {
  emoji: string
  count: number
  reacted: boolean
}

export function chatMessagePreview(message: ChatMessage, maxLength = 120): string {
  const raw = message.segments
    .map((segment) => {
      // Reply and navigator previews describe the visible message, never the
      // agent's private reasoning that may precede it in the segment stream.
      if (segment.kind === 'text') return segment.text
      if (segment.kind === 'thinking') return ''
      if (segment.kind === 'image') return segment.name ? `Image: ${segment.name}` : 'Image attachment'
      if (segment.kind === 'tool') return `Tool: ${segment.name}`
      return segment.notice.message
    })
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim()
  if (!raw) return 'Message'
  return raw.length > maxLength ? `${raw.slice(0, Math.max(1, maxLength - 1)).trimEnd()}…` : raw
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

/** Known provider label from explicit billing id or recognized model prefix only. */
export function resolveProviderDisplayLabel(providerId?: string, modelId?: string): string {
  const fromProvider = billingProviderDisplayLabel(providerId ?? '')
  if (fromProvider) return fromProvider
  const inferred = inferProviderFromModelId(modelId ?? '')
  if (!inferred) return ''
  return billingProviderDisplayLabel(inferred)
}

/** Composer/settings badge: "Provider · model" or model-only when provider is unknown. */
export function formatComposerModelLabel(providerId?: string, modelId?: string): string {
  const modelLabel = modelLabelFromId(modelId ?? '')
  const provider = resolveProviderDisplayLabel(providerId, modelId)
  const hasModel = Boolean(modelId?.trim()) && modelLabel !== 'No model'
  if (provider && hasModel) return `${provider} · ${modelLabel}`
  if (hasModel) return modelLabel
  return provider
}

/** Compact provider · model label for message attribution. */
export function formatModelAttribution(modelId?: string, llmProvider?: string): string {
  const model = modelId?.trim() ?? ''
  if (model && /^u-[a-z0-9][a-z0-9-]*$/i.test(model)) return ''
  return formatComposerModelLabel(llmProvider, model)
}

export function systemNoticeChatMessage(
  notice: WorkframeNoticeInfo,
  options?: { id?: string; authorName?: string; avatarUrl?: string | null },
): ChatMessage {
  return {
    id: options?.id ?? `sys-notice-${notice.code ?? Date.now()}`,
    authorId: 'system',
    authorName: options?.authorName ?? 'Workframe',
    role: 'agent',
    segments: [{ kind: 'concierge', notice }],
    timestamp: new Date().toISOString(),
    tokens: 0,
    avatarUrl: options?.avatarUrl,
  }
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
