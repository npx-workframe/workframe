import { useEffect, useRef } from 'react'

import { scrollAreaClass } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

type TerminalListenerProps = {
  lines: string[]
  connected?: boolean
  active?: boolean
  className?: string
}

export function TerminalListener({
  lines,
  connected = false,
  active = false,
  className,
}: TerminalListenerProps) {
  const bodyRef = useRef<HTMLPreElement>(null)

  useEffect(() => {
    const body = bodyRef.current
    if (!body) return
    body.scrollTop = body.scrollHeight
  }, [lines])

  const statusLabel = active ? 'Live' : connected ? 'Listening' : 'Connecting…'

  return (
    <section
      className={cn('wf-terminal-listener', active && 'wf-terminal-listener--active', className)}
      aria-label="Hermes terminal activity"
    >
      <header className="wf-terminal-listener__header">
        <span className="wf-terminal-listener__title">Terminal</span>
        <span className="wf-terminal-listener__status" aria-live="polite">
          {statusLabel}
        </span>
      </header>
      <pre ref={bodyRef} className={cn('wf-terminal-listener__body', scrollAreaClass, 'wf-scroll--vertical')}>
        {lines.length === 0 ? (
          <span className="wf-terminal-listener__placeholder">
            Hermes TUI output appears here while the agent runs.
          </span>
        ) : (
          lines.join('\n')
        )}
      </pre>
    </section>
  )
}
