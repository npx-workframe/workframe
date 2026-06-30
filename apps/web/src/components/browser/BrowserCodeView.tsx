import { useMemo } from 'react'

import { ScrollArea } from '@/components/ui/scroll-area'
import type { BrowserTab } from '@/lib/browserTypes'
import { getFileCapability } from '@/lib/fileCapabilities'
import { highlightCode } from '@/lib/highlightCode'

type BrowserCodeViewProps = {
  tab: BrowserTab
}

export function BrowserCodeView({ tab }: BrowserCodeViewProps) {
  const capability = getFileCapability(tab.title)

  const html = useMemo(
    () => highlightCode(tab.content, capability.language),
    [capability.language, tab.content],
  )

  return (
    <ScrollArea className="wf-browser-pane wf-browser-code wf-syntax">
      <pre className="wf-browser-code__pre">
        <code
          className={`hljs language-${capability.language}`}
          dangerouslySetInnerHTML={{ __html: html }}
        />
      </pre>
    </ScrollArea>
  )
}
