import type { IDockviewPanelProps } from 'dockview'

import { BrowserWorkspace } from '@/components/browser/BrowserWorkspace'
import { PanelHeader } from '@/components/workspace/PanelHeader'
import { PanelShell } from '@/components/workspace/PanelShell'
import { PANEL_IDS } from '@/lib/panelControlConfig'

export function BrowserPanel({ api }: IDockviewPanelProps) {
  return (    <PanelShell className="wf-panel--browser wf-panel--dockable">
      <PanelHeader label="Browser" panelId={PANEL_IDS.browser} api={api} showLabel={false} showControls={false} />
      <BrowserWorkspace />
    </PanelShell>
  )
}
