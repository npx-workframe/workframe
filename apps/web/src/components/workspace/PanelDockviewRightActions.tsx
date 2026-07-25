import { MessageSquarePlus } from 'lucide-react'
import type { IDockviewHeaderActionsProps } from 'dockview'
import { useCallback, useEffect, useState } from 'react'

import { ChatSettingsSheet } from '@/components/workspace/ChatSettingsSheet'
import { PanelHeaderControls } from '@/components/workspace/PanelHeaderControls'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { useBrowserWorkspace } from '@/contexts/BrowserWorkspaceContext'
import { useHermesSession } from '@/contexts/HermesSessionContext'
import { useWorkspacePanels } from '@/contexts/WorkspacePanelsContext'
import { isAgentChatRoom } from '@/lib/agentProfile'
import { resolveBrowserExternalHref } from '@/lib/browserTabUtils'
import { PANEL_IDS } from '@/lib/panelControlConfig'

/** Dockview-native header chrome — lives in `.dv-right-actions-container`, not under the void overlay. */
export function PanelDockviewRightActions({ activePanel }: IDockviewHeaderActionsProps) {
  const { activeRoom, registerOpenChatSettings } = useWorkspacePanels()
  const { activeTab } = useBrowserWorkspace()
  const { startNewSession, turnActive, sessionReady } = useHermesSession()
  const [resetting, setResetting] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [settingsAgentTab, setSettingsAgentTab] = useState<
    'identity' | 'instructions' | 'models' | undefined
  >()

  const onNewSession = useCallback(async () => {
    if (resetting || turnActive) return
    setResetting(true)
    try {
      await startNewSession()
    } finally {
      setResetting(false)
    }
  }, [resetting, startNewSession, turnActive])

  useEffect(() => {
    registerOpenChatSettings((agentTab) => {
      setSettingsAgentTab(agentTab)
      setSettingsOpen(true)
    })
    return () => registerOpenChatSettings(null)
  }, [registerOpenChatSettings])

  if (!activePanel) return null

  const panelId = activePanel.id
  const agentRoom = panelId === PANEL_IDS.chat && isAgentChatRoom(activeRoom)
  const externalHref =
    panelId === PANEL_IDS.browser ? resolveBrowserExternalHref(activeTab) : undefined

  return (
    <div className="wf-panel__header-actions wf-panel__header-actions--dockview">
      {agentRoom ? (
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
      ) : null}

      <PanelHeaderControls
        panelId={panelId}
        panelLabel={activePanel.title || panelId}
        api={activePanel.api}
        externalHref={externalHref}
        settingsOpen={panelId === PANEL_IDS.chat ? settingsOpen : undefined}
        onSettingsOpenChange={panelId === PANEL_IDS.chat ? setSettingsOpen : undefined}
        renderSettings={
          panelId === PANEL_IDS.chat
            ? ({ open, onClose }) => (
                <ChatSettingsSheet
                  open={open}
                  onClose={() => {
                    setSettingsAgentTab(undefined)
                    onClose()
                  }}
                  initialAgentTab={settingsAgentTab}
                />
              )
            : undefined
        }
      />
    </div>
  )
}
