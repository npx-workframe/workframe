import { useEffect, useState } from 'react'
import { ChevronDown } from 'lucide-react'

import { cn } from '@/lib/utils'

type ThinkingBlockProps = {
  text: string
  defaultOpen?: boolean
  live?: boolean
}

export function ThinkingBlock({ text, defaultOpen = false, live = false }: ThinkingBlockProps) {
  const [open, setOpen] = useState(defaultOpen || live)
  const preview = text.trim().slice(0, 120)

  useEffect(() => {
    if (live) setOpen(true)
  }, [live, text])

  return (
    <details
      className={cn('wf-thinking', open && 'wf-thinking--open')}
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="wf-thinking__summary">
        <ChevronDown className="wf-thinking__chevron" aria-hidden="true" />
        <span className="wf-thinking__label">Thinking</span>
        {!open && preview ? (
          <span className="wf-thinking__preview">{preview}{text.length > 120 ? '…' : ''}</span>
        ) : null}
      </summary>
      <pre className="wf-thinking__body">{text}</pre>
    </details>
  )
}
