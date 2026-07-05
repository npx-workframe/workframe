import { MessageSquarePlus } from 'lucide-react'
import type { IDockviewPanelProps } from 'dockview'
import { useCallback, useEffect, useState } from 'react'

import { ChatSplit } from '@/components/chat/ChatSplit'
import { ChatSettingsSheet } from '@/components/workspace/ChatSettingsSheet'
import { PanelHeader } from '@/components/workspace/PanelHeader'
import { PanelShell } from '@/components/workspace/PanelShell'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { useHermesSession } from '@/contexts/HermesSessionContext'
import { useWorkspacePanels } from '@/contexts/WorkspacePanelsContext'
import { isAgentChatRoom } from '@/lib/agentProfile'
import { PANEL_IDS } from '@/lib/panelControlConfig'

export function ChatWorkspacePanel({ api }: IDockviewPanelProps) {
  const { activeRoom, registerOpenChatSettings } = useWorkspacePanels()
  const { startNewSession, turnActive, sessionReady } = useHermesSession()
  const [resetting, setResetting] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [settingsAgentTab, setSettingsAgentTab] = useState<'identity' | 'instructions' | 'models' | undefined>()
  const agentRoom = isAgentChatRoom(activeRoom)

  useEffect(() => {
    registerOpenChatSettings((agentTab) => {
      setSettingsAgentTab(agentTab)
      setSettingsOpen(true)
    })
    return () => registerOpenChatSettings(null)
  }, [registerOpenChatSettings])

  const onNewSession = useCallback(async () => {
    if (resetting || turnActive) return
    setResetting(true)
    try {
      await startNewSession()
    } finally {
      setResetting(false)
    }
  }, [resetting, startNewSession, turnActive])

  const newSessionControl = agentRoom ? (
    <TooltipProvider delayDuration={400}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className="wf-panel__control-btn"
            onClick={() => void onNewSession()}
            disabled={!sessionReady || turnActive || resetting}
            aria-label="Start new session"
          >
            <MessageSquarePlus aria-hidden="true" />
          </button>
        </TooltipTrigger>
        <TooltipContent side="bottom">New session</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  ) : null

  return (
    <PanelShell className="wf-panel--chat wf-panel--dockable">
      <PanelHeader
        label="Chat"
        panelId={PANEL_IDS.chat}
        api={api}
        leading={newSessionControl}
        settingsOpen={settingsOpen}
        onSettingsOpenChange={setSettingsOpen}
        renderSettings={({ open, onClose }) => (
          <ChatSettingsSheet
            open={open}
            onClose={() => {
              setSettingsAgentTab(undefined)
              onClose()
            }}
            initialAgentTab={settingsAgentTab}
          />
        )}
      />

      <ChatSplit />
    </PanelShell>
  )
}
