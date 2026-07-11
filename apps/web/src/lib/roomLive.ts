import type { ChatMessage, ChatSegment } from '@/lib/chatTypes'
import { emptyAgentStreamMessage } from '@/lib/chatTypes'

export type RoomLiveFrame =
  | { type: 'heartbeat'; room_id: string; ts: number }
      | {
      type: 'turn.started'
      turn_id: string
      room_id: string
      agent_slug: string
      agent_name: string
      agent_profile_id: string
      model?: string
      llm_provider?: string
      triggered_by_user_id?: string
    }
  | {
      type: 'turn.snapshot'
      turn_id: string
      room_id: string
      agent_slug: string
      agent_name: string
      agent_profile_id?: string
      segments: ChatSegment[]
      status?: string
    }
  | {
      type: 'turn.update'
      turn_id: string
      room_id: string
      segments: ChatSegment[]
      status?: string
    }
  | { type: 'turn.complete'; turn_id: string; room_id: string; message_id?: string }
  | {
      type: 'turn.error'
      turn_id: string
      room_id: string
      error: string
      segments?: ChatSegment[]
    }

export function watchRoomLive(
  roomId: string,
  onEvent: (frame: RoomLiveFrame) => void,
): () => void {
  const source = new EventSource(`/api/rooms/${encodeURIComponent(roomId)}/live`)
  source.onmessage = (event) => {
    try {
      const frame = JSON.parse(event.data) as RoomLiveFrame
      if (frame.type === 'heartbeat') return
      onEvent(frame)
    } catch {
      // Ignore malformed frames.
    }
  }
  source.onerror = () => {
    // EventSource auto-reconnects.
  }
  return () => source.close()
}

export function liveTurnToChatMessage(
  turnId: string,
  agentSlug: string,
  agentName: string,
  segments: ChatSegment[],
  model?: { modelId?: string; llmProvider?: string },
): ChatMessage {
  const base = emptyAgentStreamMessage(
    turnId,
    agentSlug,
    agentName,
    new Date().toISOString(),
  )
  return {
    ...base,
    segments: segments.length ? segments : base.segments,
    ...(model?.modelId ? { modelId: model.modelId } : {}),
    ...(model?.llmProvider ? { llmProvider: model.llmProvider } : {}),
  }
}

export function liveTurnStatusText(agentName: string, status?: string): string | null {
  if (!status) return `${agentName} is thinking…`
  if (status === 'writing') return `${agentName} is writing…`
  if (status === 'thinking' || status === 'starting') return `${agentName} is thinking…`
  if (status.startsWith('tool:')) return `${agentName} is running ${status.slice(5)}…`
  if (status === 'error') return null
  return `${agentName} is thinking…`
}

type LiveTurnBatcher = {
  push: (turnId: string, message: ChatMessage) => void
  flush: () => void
  cancel: () => void
}

export function createLiveTurnBatcher(
  onFlush: (updates: Record<string, ChatMessage>) => void,
): LiveTurnBatcher {
  let pending: Record<string, ChatMessage> = {}
  let raf = 0

  const flush = () => {
    raf = 0
    if (!Object.keys(pending).length) return
    const batch = pending
    pending = {}
    onFlush(batch)
  }

  return {
    push(turnId: string, message: ChatMessage) {
      pending[turnId] = message
      if (!raf) raf = window.requestAnimationFrame(flush)
    },
    flush() {
      if (raf) {
        window.cancelAnimationFrame(raf)
        raf = 0
      }
      flush()
    },
    cancel() {
      if (raf) window.cancelAnimationFrame(raf)
      raf = 0
      pending = {}
    },
  }
}
