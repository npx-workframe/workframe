import { apiGet, apiPost } from '@/lib/apiClient'
import { authenticatedFetch, readApiError } from '@/lib/authenticatedFetch'
import type { ChatMessage, ChatSegment } from '@/lib/chatTypes'

type ChatApiMessage = {
  id: string
  authorId: string
  authorName: string
  role: 'user' | 'agent'
  segments: ChatSegment[]
  timestamp: string
  tokens: number
}

export type ChatSessionInfo = {
  ok?: boolean
  session_id: string
  title?: string
  active?: boolean
  message_count?: number
  started_at?: string
}

type ChatMessagesResponse = {
  ok?: boolean
  session_id: string
  session?: ChatSessionInfo
  messages: ChatApiMessage[]
}

function formatTimestamp(iso: string): string {
  if (!iso) return '--:--'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export async function fetchChatMessages(
  profile: string,
  sessionId?: string,
  sourceId?: string,
): Promise<{ sessionId: string; messages: ChatMessage[] }> {
  const params = new URLSearchParams({ profile })
  if (sessionId) params.set('session', sessionId)
  if (sourceId) params.set('source', sourceId)
  const data = await apiGet<ChatMessagesResponse>(
    `/api/chat/messages?${params.toString()}`,
  )
  return {
    sessionId: data.session_id ?? sessionId ?? '',
    messages: data.messages.map((m) => ({
      ...m,
      timestamp: formatTimestamp(m.timestamp),
    })),
  }
}

export type ProfileSessionResponse = {
  ok?: boolean
  profile: string
  session_id: string
  created?: boolean
}

export type ProfileBindResponse = ProfileSessionResponse & {
  template_profile?: string
  messages?: ChatApiMessage[]
  session?: ChatSessionInfo
  llm_ready?: boolean
  has_llm_provider?: boolean
  agent_display_name?: string
}

export async function ensureRoomBind(payload: {
  room_id: string
  source_id: string
  client_id: string
  new_session?: boolean
  title?: string
  binding_version?: number
}): Promise<{ sessionId: string; profile: string; templateProfile: string; agentDisplayName: string; created: boolean; llmReady: boolean; messages: ChatMessage[] }> {
  const data = await apiPost<ProfileBindResponse>(
    `/api/rooms/${encodeURIComponent(payload.room_id)}/bind`,
    payload,
  )
  return {
    sessionId: data.session_id ?? '',
    profile: data.profile ?? '',
    templateProfile: data.template_profile ?? data.profile ?? '',
    agentDisplayName: data.agent_display_name ?? '',
    created: Boolean(data.created),
    llmReady: data.llm_ready ?? data.has_llm_provider ?? false,
    messages: (data.messages ?? []).map((m) => ({
      ...m,
      timestamp: formatTimestamp(m.timestamp),
    })),
  }
}

export async function ensureProfileBind(payload: {
  profile: string
  room_id: string
  source_id: string
  client_id: string
  new_session?: boolean
  title?: string
  binding_version?: number
}): Promise<{ sessionId: string; profile: string; templateProfile: string; agentDisplayName: string; created: boolean; llmReady: boolean; messages: ChatMessage[] }> {
  const data = await apiPost<ProfileBindResponse>(
    `/api/hermes/profiles/${encodeURIComponent(payload.profile)}/bind`,
    payload,
  )
  return {
    sessionId: data.session_id ?? '',
    profile: data.profile ?? payload.profile,
    templateProfile: data.template_profile ?? data.profile ?? payload.profile,
    agentDisplayName: data.agent_display_name ?? '',
    created: Boolean(data.created),
    llmReady: data.llm_ready ?? data.has_llm_provider ?? false,
    messages: (data.messages ?? []).map((m) => ({
      ...m,
      timestamp: formatTimestamp(m.timestamp),
    })),
  }
}

export type ProfileStreamEvent = {
  event: string
  data: Record<string, unknown>
}

export async function streamProfileMessage(
  payload: {
    profile: string
    session_id: string
    room_id?: string
    source_id: string
    client_id: string
    binding_version?: number
    text: string
  },
  onEvent: (event: ProfileStreamEvent) => void,
): Promise<void> {
  const response = await authenticatedFetch(
    `/api/hermes/profiles/${encodeURIComponent(payload.profile)}/messages/stream`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
  if (!response.ok) {
    const message = await readApiError(response)
    throw new Error(`POST /api/hermes/profiles/${payload.profile}/messages/stream failed: ${message}`)
  }
  if (!response.body) throw new Error('Streaming response body unavailable')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let currentEvent = 'message'
  let sawDone = false

  const takeNextFrame = (): string | null => {
    const match = buffer.match(/\r?\n\r?\n/)
    if (!match || match.index == null) return null
    const frame = buffer.slice(0, match.index).trim()
    buffer = buffer.slice(match.index + match[0].length)
    return frame
  }

  const flushFrame = (frame: string) => {
    const lines = frame.split(/\r?\n/)
    const dataLines: string[] = []
    let eventName = currentEvent
    for (const line of lines) {
      if (!line) continue
      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim() || 'message'
        continue
      }
      if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trimStart())
      }
    }
    currentEvent = 'message'
    if (!dataLines.length) return
    try {
      onEvent({ event: eventName, data: JSON.parse(dataLines.join('\n')) as Record<string, unknown> })
    } catch {
      onEvent({ event: eventName, data: { text: dataLines.join('\n') } })
    }
    if (eventName === 'done') {
      sawDone = true
    }
  }

  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })

    let frame = takeNextFrame()
    while (frame !== null) {
      if (frame) flushFrame(frame)
      if (sawDone) {
        try {
          await reader.cancel()
        } catch {
          // ignore cancel races
        }
        return
      }
      frame = takeNextFrame()
    }

    if (done) {
      const tail = buffer.trim()
      if (tail) flushFrame(tail)
      if (!sawDone) {
        onEvent({ event: 'done', data: {} })
      }
      break
    }
  }
}
