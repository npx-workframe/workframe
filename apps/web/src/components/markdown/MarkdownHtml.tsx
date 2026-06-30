import { useLayoutEffect, useRef } from 'react'

import { hydrateMermaid } from '@/lib/hydrateMermaid'
import { safeHtml } from '@/lib/safeHtml'
import { cn } from '@/lib/utils'

type MarkdownHtmlProps = {
  html: string
  className?: string
}

export function MarkdownHtml({ html, className }: MarkdownHtmlProps) {
  const rootRef = useRef<HTMLDivElement>(null)

  // ponytail: fallback for marked-emitted wf-mermaid blocks in static HTML previews
  useLayoutEffect(() => {
    const root = rootRef.current
    if (!root) return
    void hydrateMermaid(root)
  }, [html])

  return <div ref={rootRef} className={cn(className)} dangerouslySetInnerHTML={{ __html: safeHtml(html) }} />
}
