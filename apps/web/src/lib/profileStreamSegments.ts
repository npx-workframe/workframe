import type { ProfileStreamEvent } from '@/lib/chatApi'
import type { ChatSegment } from '@/lib/chatTypes'
import {
  appendTextSegment,
  appendThinkingSegment,
  completeTool,
  setFinalTextSegment,
  upsertRunningTool,
} from '@/lib/chatLiveSegments'

function streamText(data: Record<string, unknown>): string {
  return String(data.delta ?? data.text ?? data.content ?? '')
}

export function reduceProfileStreamEvent(segments: ChatSegment[], evt: ProfileStreamEvent): ChatSegment[] {
  const { event, data } = evt
  switch (event) {
    case 'thinking.delta':
    case 'reasoning.delta':
      return appendThinkingSegment(segments, streamText(data))
    case 'message.delta':
    case 'assistant.delta':
      return appendTextSegment(segments, streamText(data))
    case 'tool.started':
      return upsertRunningTool(segments, String(data.tool_name ?? 'tool'), String(data.preview ?? ''))
    case 'tool.completed':
    case 'tool.failed':
      return completeTool(
        segments,
        String(data.tool_name ?? 'tool'),
        String(data.preview ?? data.output ?? ''),
      )
    case 'tool.progress': {
      const toolName = String(data.tool_name ?? 'tool')
      if (toolName === '_thinking') return segments
      return upsertRunningTool(segments, toolName, streamText(data))
    }
    case 'message.complete':
    case 'assistant.completed': {
      const final = String(data.content ?? data.text ?? '').trim()
      return final ? setFinalTextSegment(segments, final) : segments
    }
    case 'error':
      return appendTextSegment(segments, String(data.error ?? data.message ?? 'Stream error'))
    default:
      return segments
  }
}

export function segmentsToReplyText(segments: ChatSegment[]): string {
  return segments
    .filter((segment): segment is Extract<ChatSegment, { kind: 'text' }> => segment.kind === 'text')
    .map((segment) => segment.text)
    .join('')
    .trim()
}
