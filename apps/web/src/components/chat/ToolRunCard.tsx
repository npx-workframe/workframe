import { useState } from 'react'
import { ChevronDown, Loader2, Terminal, CheckCircle2, XCircle } from 'lucide-react'

import type { ChatSegment } from '@/lib/chatTypes'
import { scrollAreaClass } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

type ToolRunCardProps = {
  segment: Extract<ChatSegment, { kind: 'tool' }>
}

export function ToolRunCard({ segment }: ToolRunCardProps) {
  const { name, status, output, preview } = segment
  const isRunning = status === 'running'
  const isError = status === 'error'
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
          title={open ? 'Collapse' : 'Expand'}
        >
          <ChevronDown
            className={cn('wf-tool-run__chevron', open && 'wf-tool-run__chevron--open')}
            aria-hidden="true"
          />
          {icon}
          <Terminal className="wf-tool-run__glyph" aria-hidden="true" />
          <span className="wf-tool-run__name">{name}</span>
          <span className="wf-tool-run__status">{status}</span>
        </button>
      ) : (
        <div className="wf-tool-run__header">
          {icon}
          <Terminal className="wf-tool-run__glyph" aria-hidden="true" />
          <span className="wf-tool-run__name">{name}</span>
          <span className="wf-tool-run__status">{status}</span>
        </div>
      )}
      {open && hasDetail ? (
        <pre className={cn('wf-tool-run__output', scrollAreaClass, 'wf-scroll--vertical')}>{detail}</pre>
      ) : null}
    </div>
  )
}
