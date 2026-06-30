/** Parsed Hermes dashboard sidebar event (PTY sidecar → /api/pub → /api/events). */
export type HermesEventFrame = {
  type: string
  sessionId: string
  payload: Record<string, unknown>
}

const TURN_COMPLETE_EVENTS = new Set([
  'message.complete',
  // legacy aliases — harmless if never emitted
  'turn.complete',
  'turn.end',
  'assistant.complete',
  'assistant.done',
  'session.idle',
])

export function isTurnCompleteEvent(type: string): boolean {
  return TURN_COMPLETE_EVENTS.has(type)
}

/** Wire format: `{ jsonrpc, method: "event", params: { type, session_id, payload } }` */
export function parseHermesEvent(raw: string): HermesEventFrame | null {
  try {
    const frame = JSON.parse(raw) as {
      method?: string
      params?: {
        type?: string
        session_id?: string
        payload?: Record<string, unknown>
      }
      type?: string
      payload?: Record<string, unknown>
    }

    if (frame.method === 'event' && frame.params?.type) {
      return {
        type: frame.params.type,
        sessionId: String(frame.params.session_id ?? ''),
        payload: frame.params.payload ?? {},
      }
    }

    if (frame.type) {
      return {
        type: frame.type,
        sessionId: '',
        payload: (frame.payload as Record<string, unknown>) ?? {},
      }
    }

    return null
  } catch {
    return null
  }
}

export function eventText(payload: Record<string, unknown>): string {
  const text = payload.text ?? payload.content ?? payload.preview ?? ''
  return typeof text === 'string' ? text : String(text)
}

export function eventToolName(payload: Record<string, unknown>): string {
  const name = payload.name ?? payload.tool_name ?? 'tool'
  return String(name)
}

/** Best-effort visible text from a turn-complete event payload. */
export function completeEventText(payload: Record<string, unknown>): string {
  const text = eventText(payload).trim()
  if (text) return text

  const warning = String(payload.warning ?? '').trim()
  if (warning) return warning

  const status = String(payload.status ?? '').trim().toLowerCase()
  if (status === 'error' || status === 'interrupted') {
    return status === 'error'
      ? 'The agent could not reach the model provider. Check API keys and the model in Settings.'
      : 'The agent turn was interrupted.'
  }

  return ''
}
