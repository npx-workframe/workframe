import { useMemo } from 'react'

import { MermaidDiagram } from '@/components/markdown/MermaidDiagram'
import { MarkdownHtml } from '@/components/markdown/MarkdownHtml'
import { splitMarkdownBlocks } from '@/lib/splitMarkdownBlocks'
import { renderMarkdown, renderMarkdownInner } from '@/lib/renderMarkdown'
import { cn } from '@/lib/utils'

type MarkdownContentProps = {
  text: string
  className?: string
  wrapperClass?: string
}

export function MarkdownContent({
  text,
  className,
  wrapperClass = 'wf-markdown wf-syntax',
}: MarkdownContentProps) {
  const blocks = useMemo(() => splitMarkdownBlocks(text), [text])
  const hasMermaid = blocks.some((block) => block.kind === 'mermaid')
  const articleClass = cn(wrapperClass, className)

  if (!hasMermaid) {
    return <MarkdownHtml html={renderMarkdown(text, articleClass)} />
  }

  return (
    <article className={articleClass}>
      {blocks.map((block, index) => {
        if (block.kind === 'mermaid') {
          return <MermaidDiagram key={`mmd-${index}`} source={block.source} />
        }
        if (!block.text.trim()) return null
        return <MarkdownHtml key={`md-${index}`} html={renderMarkdownInner(block.text)} />
      })}
    </article>
  )
}
