import type { IDockviewPanelProps } from 'dockview'

import { ChatSplit } from '@/components/chat/ChatSplit'
import { PanelHeader } from '@/components/workspace/PanelHeader'
import { PanelShell } from '@/components/workspace/PanelShell'
import { PANEL_IDS } from '@/lib/panelControlConfig'

export function ChatWorkspacePanel({ api }: IDockviewPanelProps) {
  return (
    <PanelShell className="wf-panel--chat wf-panel--dockable">
      <PanelHeader label="Chat" panelId={PANEL_IDS.chat} api={api} showLabel={false} showControls={false} />
      <ChatSplit />
    </PanelShell>
  )
}
