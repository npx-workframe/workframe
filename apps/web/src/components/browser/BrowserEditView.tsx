import { useRef } from 'react'

import { MarkdownEditToolbar } from '@/components/browser/MarkdownEditToolbar'
import { scrollAreaClass } from '@/components/ui/scroll-area'
import { Textarea } from '@/components/ui/textarea'
import { useBrowserWorkspace } from '@/contexts/BrowserWorkspaceContext'
import type { BrowserTab } from '@/lib/browserTypes'
import { getFileCapability } from '@/lib/fileCapabilities'
import { cn } from '@/lib/utils'

type BrowserEditViewProps = {
  tab: BrowserTab
}

export function BrowserEditView({ tab }: BrowserEditViewProps) {
  const { updateTabContent } = useBrowserWorkspace()
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const isMarkdown = getFileCapability(tab.title).language === 'markdown'

  const applyEdit = (next: string) => {
    updateTabContent(tab.id, next)
  }

  const wrapSelection = (before: string, after = '', placeholder = '') => {
    const element = textareaRef.current
    if (!element) return

    const start = element.selectionStart
    const end = element.selectionEnd
    const selected = tab.content.slice(start, end) || placeholder
    const next =
      tab.content.slice(0, start) + before + selected + after + tab.content.slice(end)

    applyEdit(next)
    requestAnimationFrame(() => {
      element.focus()
      const cursor = start + before.length + selected.length + after.length
      element.setSelectionRange(cursor, cursor)
    })
  }

  const insertLinePrefix = (prefix: string) => {
    const element = textareaRef.current
    if (!element) return

    const start = element.selectionStart
    const lineStart = tab.content.lastIndexOf('\n', start - 1) + 1
    const next = `${tab.content.slice(0, lineStart)}${prefix}${tab.content.slice(lineStart)}`
    applyEdit(next)
  }

  return (
    <div className="wf-browser-pane wf-browser-edit">
      {isMarkdown ? (
        <MarkdownEditToolbar onWrap={wrapSelection} onInsertLine={insertLinePrefix} />
      ) : null}

      <Textarea
        ref={textareaRef}
        className={cn('wf-browser-edit__textarea', scrollAreaClass, 'wf-scroll--vertical')}
        value={tab.content}
        onChange={(event) => applyEdit(event.target.value)}
        spellCheck={false}
        aria-label={`Edit ${tab.title}`}
      />
    </div>
  )
}
