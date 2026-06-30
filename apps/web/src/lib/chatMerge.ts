import type { ChatMessage, ChatSegment } from '@/lib/chatTypes'
import { stripPlaceholderSegments } from '@/lib/chatLiveSegments'

const WORKFRAME_LANE_RE = /\[WORKFRAME_LANE\][\s\S]*?\[\/WORKFRAME_LANE\]\s*/gi

function normalizeUserText(text: string): string {
  return text.replace(WORKFRAME_LANE_RE, '').trim()
}

function userText(message: ChatMessage): string {
  return message.segments
    .filter((s) => s.kind === 'text')
    .map((s) => s.text)
    .join('\n')
    .trim()
}

function hasImageSegment(message: ChatMessage): boolean {
  return message.segments.some((s) => s.kind === 'image')
}

function serverHasUserTurn(server: ChatMessage[], localUser: ChatMessage): boolean {
  const text = normalizeUserText(userText(localUser))
  const localImages = localUser.segments.filter((s) => s.kind === 'image').length
  return server.some((m) => {
    if (m.role !== 'user') return false
    if (text && normalizeUserText(userText(m)) === text) return true
    if (localImages > 0 && hasImageSegment(m)) {
      const localPaths = new Set(
        localUser.segments.filter((s) => s.kind === 'image').map((s) => s.path),
      )
      return m.segments.some((s) => s.kind === 'image' && localPaths.has(s.path))
    }
    return false
  })
}

function hasSubstantiveContent(segments: ChatSegment[]): boolean {
  return stripPlaceholderSegments(segments).some(
    (s) =>
      (s.kind === 'text' && s.text.trim().length > 0) ||
      s.kind === 'tool' ||
      (s.kind === 'thinking' && s.text.trim().length > 0),
  )
}

function thinkingText(segments: ChatSegment[]): string {
  return segments
    .filter((s) => s.kind === 'thinking')
    .map((s) => s.text)
    .join('')
    .trim()
}

function mergeAgentFromEphemeral(serverAgent: ChatMessage, ephemeral: ChatMessage): ChatMessage {
  const live = stripPlaceholderSegments(ephemeral.segments)
  const server = serverAgent.segments

  if (!hasSubstantiveContent(server) && hasSubstantiveContent(live)) {
    return { ...serverAgent, segments: live, ephemeral: false }
  }

  const liveThinking = thinkingText(live)
  const serverThinking = thinkingText(server)
  const thinking =
    liveThinking.length > serverThinking.length ? liveThinking : serverThinking

  const liveText = live
    .filter((s) => s.kind === 'text')
    .map((s) => s.text)
    .join('')
    .trim()
  const serverText = server
    .filter((s) => s.kind === 'text')
    .map((s) => s.text)
    .join('')
    .trim()
  const replyText = liveText.length > serverText.length ? liveText : serverText

  const tools = [...server.filter((s) => s.kind === 'tool')]
  for (const segment of live) {
    if (segment.kind !== 'tool') continue
    const idx = tools.findIndex((t) => t.kind === 'tool' && t.name === segment.name)
    if (idx >= 0) {
      const existing = tools[idx]
      if (existing.kind === 'tool') {
        const preferLive =
          segment.status === 'running' ||
          (segment.output?.length ?? 0) > (existing.output?.length ?? 0)
        if (preferLive) tools[idx] = segment
      }
    } else {
      tools.push(segment)
    }
  }

  const segments: ChatSegment[] = []
  if (thinking) segments.push({ kind: 'thinking', text: thinking })
  segments.push(...tools)
  if (replyText) segments.push({ kind: 'text', text: replyText })

  if (!segments.length && hasSubstantiveContent(live)) {
    return { ...serverAgent, segments: live, ephemeral: false }
  }

  return { ...serverAgent, segments, ephemeral: false }
}

/** True when state.db already has a substantive agent turn after the latest user message. */
export function serverTurnSettled(server: ChatMessage[]): boolean {
  const lastUserIdx = server.findLastIndex((m) => m.role === 'user')
  if (lastUserIdx < 0) return false

  const agentTurn = server.slice(lastUserIdx + 1).find((m) => m.role === 'agent')
  if (!agentTurn) return false

  return hasSubstantiveContent(agentTurn.segments)
}

/**
 * While a turn is in flight: keep pending user rows + the single live ephemeral card.
 */
export function mergeLiveTurn(
  server: ChatMessage[],
  local: ChatMessage[],
  activeStreamId: string | null,
): ChatMessage[] {
  const pendingUsers = local.filter(
    (m) => m.id.startsWith('u-') && !serverHasUserTurn(server, m),
  )

  const activeEphemeral =
    (activeStreamId ? local.find((m) => m.ephemeral && m.id === activeStreamId) : null) ??
    local.findLast((m) => m.ephemeral)

  if (!activeEphemeral) {
    return [...server, ...pendingUsers]
  }

  return [...server, ...pendingUsers, activeEphemeral]
}

function localAgentHandoff(local: ChatMessage[]): ChatMessage | null {
  const live =
    local.findLast((m) => m.ephemeral && m.role === 'agent') ??
    local.findLast((m) => m.role === 'agent' && hasSubstantiveContent(m.segments))
  return live ?? null
}

/**
 * After message.complete: server history is canonical; merge live streamed content in.
 * ponytail: state.db often lags the SSE stream — never drop a substantive local agent turn.
 */
export function finalizeChatHandoff(server: ChatMessage[], local: ChatMessage[]): ChatMessage[] {
  const pendingUsers = local.filter(
    (m) => m.id.startsWith('u-') && m.role === 'user' && !serverHasUserTurn(server, m),
  )

  const localAgent = localAgentHandoff(local)
  if (!localAgent) {
    return [...server, ...pendingUsers]
  }

  const result = [...server]
  const lastUserIdx = result.findLastIndex((m) => m.role === 'user')
  const serverAgentForTurn =
    lastUserIdx >= 0
      ? result.slice(lastUserIdx + 1).findLast((m) => m.role === 'agent')
      : result.findLast((m) => m.role === 'agent')

  if (!serverAgentForTurn) {
    return [...result, ...pendingUsers, { ...localAgent, ephemeral: false }]
  }

  const agentIdx = result.findLastIndex((m) => m.id === serverAgentForTurn.id)
  result[agentIdx] = mergeAgentFromEphemeral(result[agentIdx], localAgent)
  return [...result, ...pendingUsers]
}

/** @deprecated use mergeLiveTurn or finalizeChatHandoff */
export function mergeChatMessages(
  server: ChatMessage[],
  local: ChatMessage[],
  activeStreamId: string | null = null,
): ChatMessage[] {
  if (activeStreamId) {
    return mergeLiveTurn(server, local, activeStreamId)
  }
  if (serverTurnSettled(server)) {
    return finalizeChatHandoff(server, local)
  }
  return mergeLiveTurn(server, local, activeStreamId)
}
