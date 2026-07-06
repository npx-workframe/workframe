import { useCallback, useEffect, useMemo, useRef } from 'react'
import {
  DockviewReact,
  type DockviewReadyEvent,
  type IDockviewPanelProps,
} from 'dockview'
import type { DockviewApi } from 'dockview'

import { AgentRailPanel } from '@/components/workspace/panels/AgentRailPanel'
import { ChatWorkspacePanel } from '@/components/workspace/panels/ChatWorkspacePanel'
import { FilesExplorerPanel } from '@/components/workspace/panels/FilesExplorerPanel'
import { ActivityPanel } from '@/components/workspace/panels/ActivityPanel'
import { BrowserPanel } from '@/components/workspace/panels/BrowserPanel'
import { PanelDragTab } from '@/components/workspace/PanelDragTab'
import { useWorkspacePanels } from '@/contexts/WorkspacePanelsContext'
import { PANEL_IDS } from '@/lib/panelControlConfig'
import { panelDisplayTitle } from '@/lib/panelDisplayLabels'
import { useTheme } from '@/hooks/useTheme'
import { getInitialPanelOptions } from '@/lib/workspaceLayout'
import {
  setupWorkspaceDnd,
  WORKFRAME_DND_OVERLAY,
} from '@/lib/workspaceDndPolicy'
import { cn } from '@/lib/utils'

const DOCKVIEW_DND_THEME = {
  dndOverlayMounting: 'relative' as const,
  dndPanelOverlay: 'content' as const,
  dndTabIndicator: 'line' as const,
}

function initWorkspace(event: DockviewReadyEvent) {
  const api = event.api

  const agentPanel = api.addPanel({
    id: PANEL_IDS.crew,
    component: 'agentRail',
    title: panelDisplayTitle(PANEL_IDS.crew),
    ...getInitialPanelOptions(PANEL_IDS.crew),
  })
  agentPanel.group.api.locked = true

  const chatPanel = api.addPanel({
    id: PANEL_IDS.chat,
    component: 'chatWorkspace',
    title: 'Chat',
    position: { referencePanel: agentPanel, direction: 'right' },
    ...getInitialPanelOptions(PANEL_IDS.chat),
  })

  const filesPanel = api.addPanel({
    id: PANEL_IDS.files,
    component: 'filesExplorer',
    title: panelDisplayTitle(PANEL_IDS.files),
    position: { referencePanel: chatPanel, direction: 'right' },
    ...getInitialPanelOptions(PANEL_IDS.files),
  })

  const browserPanel = api.addPanel({
    id: PANEL_IDS.browser,
    component: 'browser',
    title: 'Browser',
    position: { referencePanel: filesPanel, direction: 'right' },
    ...getInitialPanelOptions(PANEL_IDS.browser),
  })

  api.addPanel({
    id: PANEL_IDS.activity,
    component: 'activity',
    title: 'Activity',
    position: { referencePanel: browserPanel, direction: 'right' },
    ...getInitialPanelOptions(PANEL_IDS.activity),
  })

  setupWorkspaceDnd(api)
}

function projectNameFromEnv() {
  return import.meta.env.VITE_WORKFRAME_PROJECT?.trim() || 'Workframe'
}

export function DockviewWorkspace() {
  const { theme } = useTheme()
  const { registerWorkspaceApi } = useWorkspacePanels()

  const apiRef = useRef<DockviewApi | null>(null)
  const workspaceRef = useRef<HTMLDivElement | null>(null)
  const teardownRef = useRef<(() => void) | null>(null)

  const components = useMemo(
    () =>
      ({
        agentRail: AgentRailPanel,
        chatWorkspace: ChatWorkspacePanel,
        activity: ActivityPanel,
        filesExplorer: FilesExplorerPanel,
        browser: BrowserPanel,
      }) satisfies Record<string, React.FunctionComponent<IDockviewPanelProps>>,
    [],
  )

  const onReady = useCallback(
    (event: DockviewReadyEvent) => {
      initWorkspace(event)
      apiRef.current = event.api
      teardownRef.current?.()
      teardownRef.current = registerWorkspaceApi(
        event.api,
        projectNameFromEnv(),
        workspaceRef.current,
      )
    },
    [registerWorkspaceApi],
  )

  useEffect(() => {
    return () => {
      teardownRef.current?.()
      teardownRef.current = null
    }
  }, [])

  return (
    <div className="wf-workspace-shell">
      <div
        ref={workspaceRef}
        className={cn(
          'wf-workspace',
          theme === 'dark' ? 'dockview-theme-dark' : 'dockview-theme-light',
        )}
      >
        <DockviewReact
          className="wf-workspace__dock"
          components={components}
          defaultTabComponent={PanelDragTab}
          onReady={onReady}
          hideBorders
          dndEdges={WORKFRAME_DND_OVERLAY}
          theme={{
            ...DOCKVIEW_DND_THEME,
            ...(theme === 'dark'
              ? { name: 'wf-dark', className: 'dockview-theme-dark' }
              : { name: 'wf-light', className: 'dockview-theme-light' }),
          }}
        />
      </div>


    </div>
  )
}
