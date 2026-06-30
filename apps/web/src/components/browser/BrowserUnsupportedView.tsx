import { FileWarning } from 'lucide-react'

import { ScrollArea } from '@/components/ui/scroll-area'
import type { BrowserTab } from '@/lib/browserTypes'
import { getFileCapability } from '@/lib/fileCapabilities'

type BrowserUnsupportedViewProps = {
  tab: BrowserTab
}

export function BrowserUnsupportedView({ tab }: BrowserUnsupportedViewProps) {
  const capability = getFileCapability(tab.title)
  const ext = tab.title.includes('.') ? tab.title.split('.').pop()?.toUpperCase() : tab.title

  return (
    <ScrollArea className="wf-browser-pane wf-browser-preview wf-browser-preview--unsupported">
      <div className="wf-browser-unsupported">
        <div className="wf-browser-unsupported__icon" aria-hidden="true">
          <FileWarning />
        </div>
        <p className="wf-browser-unsupported__eyebrow">Preview unavailable</p>
        <h2 className="wf-browser-unsupported__title">Can&apos;t preview this file</h2>
        <p className="wf-browser-unsupported__body">
          <strong>{tab.title}</strong>
          {ext ? ` (${ext})` : null} is a binary or office format. Workframe won&apos;t render it as
          fake text — open or download it from the gateway when <code>/Files/</code> is wired.
        </p>
        <p className="wf-browser-unsupported__meta">{capability.mimeType}</p>
      </div>
    </ScrollArea>
  )
}
