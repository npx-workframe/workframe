import { useState } from 'react'
import { Brain, ChevronDown, Loader2, Terminal, CheckCircle2, XCircle } from 'lucide-react'

import type { ChatSegment } from '@/lib/chatTypes'
import { scrollAreaClass } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

type ToolRunCardProps = {
  segment: Extract<ChatSegment, { kind: 'tool' }>
  glyph?: 'tool' | 'thinking'
}

export function ToolRunCard({ segment, glyph = 'tool' }: ToolRunCardProps) {
  const { name, status, output, preview } = segment
  const isRunning = status === 'running'
  const isError = status === 'error'
  const isThinking = glyph === 'thinking'
  const Glyph = isThinking ? Brain : Terminal
  const displayStatus = isThinking && isRunning ? 'thinking' : status
  const detail = (isRunning ? preview : output)?.trim()
  // Only collapsible when there's something to show. Tools that complete
  // without output (e.g. a read on an empty file) render as a static one-liner.
  const hasDetail = Boolean(detail)
  // Default closed — the header alone is the one-liner, and the chevron's
  // job is to expand on demand. Opening by default made the output look
  // like a duplicate line under the header.
  const [open, setOpen] = useState(false)
  const toggle = () => setOpen((value) => !value)

  const icon = isRunning ? (
    <Loader2 className="wf-tool-run__icon wf-tool-run__icon--spin" aria-hidden="true" />
  ) : isError ? (
    <XCircle className="wf-tool-run__icon" aria-hidden="true" />
  ) : (
    <CheckCircle2 className="wf-tool-run__icon" aria-hidden="true" />
  )

  return (
    <div
      className={cn(
        'wf-tool-run',
        isRunning && 'wf-tool-run--running',
        isError && 'wf-tool-run--error',
        !hasDetail && 'wf-tool-run--static',
      )}
    >
      {hasDetail ? (
        <button
          type="button"
          className="wf-tool-run__header wf-tool-run__header--button"
          onClick={toggle}
          aria-expanded={open}
          aria-label={`${name} ${displayStatus}`}
          title={open ? 'Collapse' : 'Expand'}
        >
          <ChevronDown
            className={cn('wf-tool-run__chevron', open && 'wf-tool-run__chevron--open')}
            aria-hidden="true"
          />
          <Glyph className="wf-tool-run__glyph" aria-hidden="true" />
          <span className="wf-tool-run__name">{name}</span>
          {icon}
        </button>
      ) : (
        <div className="wf-tool-run__header" role="status" aria-label={`${name} ${displayStatus}`}>
          <Glyph className="wf-tool-run__glyph" aria-hidden="true" />
          <span className="wf-tool-run__name">{name}</span>
          {icon}
        </div>
      )}
      {open && hasDetail ? (
        <pre className={cn('wf-tool-run__output', scrollAreaClass, 'wf-scroll--vertical')}>{detail}</pre>
      ) : null}
    </div>
  )
}
