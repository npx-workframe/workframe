import type { ChatSegment } from '@/lib/chatTypes'

export function stripPlaceholderSegments(segments: ChatSegment[]): ChatSegment[] {
  return segments.filter(
    (s) => !(s.kind === 'text' && (s.text === 'Thinking…' || s.text === '…' || s.text === '')),
  )
}

export function appendTextSegment(segments: ChatSegment[], text: string): ChatSegment[] {
  if (!text) return segments
  const base = stripPlaceholderSegments(segments)
  const last = base.at(-1)
  if (last?.kind === 'text') {
    return [...base.slice(0, -1), { kind: 'text', text: last.text + text }]
  }
  return [...base, { kind: 'text', text }]
}

/** Replace the trailing text segment — use on message.complete (deltas already streamed). */
export function setFinalTextSegment(segments: ChatSegment[], text: string): ChatSegment[] {
  const final = text.trim()
  if (!final) return segments
  const base = stripPlaceholderSegments(segments)
  const last = base.at(-1)
  if (last?.kind === 'text') {
    return [...base.slice(0, -1), { kind: 'text', text: final }]
  }
  return [...base, { kind: 'text', text: final }]
}

export function appendThinkingSegment(segments: ChatSegment[], text: string): ChatSegment[] {
  if (!text) return segments
  const base = stripPlaceholderSegments(segments)
  const last = base.at(-1)
  if (last?.kind === 'thinking') {
    return [...base.slice(0, -1), { kind: 'thinking', text: last.text + text }]
  }
  return [...base, { kind: 'thinking', text }]
}

export function upsertRunningTool(segments: ChatSegment[], name: string, preview = ''): ChatSegment[] {
  const base = stripPlaceholderSegments(segments)
  const idx = [...base].reverse().findIndex((s) => s.kind === 'tool' && s.name === name)
  if (idx >= 0) {
    const realIdx = base.length - 1 - idx
    const existing = base[realIdx]
    if (existing.kind === 'tool') {
      const next = [...base]
      next[realIdx] = {
        ...existing,
        status: 'running',
        preview: preview || existing.preview,
      }
      return next
    }
  }
  return [...base, { kind: 'tool', name, status: 'running', preview: preview || undefined }]
}

export function completeTool(
  segments: ChatSegment[],
  name: string,
  output: string,
): ChatSegment[] {
  const base = stripPlaceholderSegments(segments)
  const idx = [...base].reverse().findIndex((s) => s.kind === 'tool' && s.name === name)
  if (idx < 0) {
    return [...base, { kind: 'tool', name, status: 'done', output }]
  }
  const realIdx = base.length - 1 - idx
  const next = [...base]
  const existing = next[realIdx]
  if (existing.kind === 'tool') {
    next[realIdx] = {
      ...existing,
      status: 'done',
      output: output || existing.output || existing.preview || '',
      preview: undefined,
    }
  }
  return next
}

export function segmentCount(segments: ChatSegment[]): number {
  return stripPlaceholderSegments(segments).length
}

export function hasVisibleLiveContent(segments: ChatSegment[]): boolean {
  return segmentCount(segments) > 0
}
