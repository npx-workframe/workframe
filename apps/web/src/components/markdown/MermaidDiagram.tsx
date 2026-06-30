import { useLayoutEffect, useRef, useState } from 'react'

import { mountMermaidSvg, renderMermaidDiagram } from '@/lib/hydrateMermaid'
import { cn } from '@/lib/utils'

type MermaidDiagramProps = {
  source: string
  className?: string
}

export function MermaidDiagram({ source, className }: MermaidDiagramProps) {
  const hostRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(true)

  useLayoutEffect(() => {
    const host = hostRef.current
    if (!host) return

    let cancelled = false
    setError(null)
    setPending(true)
    host.replaceChildren()

    void (async () => {
      try {
        const { svg, bindFunctions } = await renderMermaidDiagram(source)
        if (cancelled) return
        mountMermaidSvg(host, svg)
        bindFunctions?.(host)
        setPending(false)
      } catch (err) {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Could not render diagram')
        setPending(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [source])

  return (
    <div
      ref={hostRef}
      className={cn('wf-mermaid', pending && 'wf-mermaid--pending', className)}
      role="img"
      aria-label="Diagram"
    >
      {error ? <pre className="wf-mermaid__error">{error}</pre> : null}
    </div>
  )
}
