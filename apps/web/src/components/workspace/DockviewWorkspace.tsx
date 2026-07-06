import { useCallback, useEffect, useMemo, useRef, type CSSProperties } from 'react'
import {
  DockviewReact,
  type DockviewReadyEvent,
  type IDockviewPanelProps,
} from 'dockview'
import type { DockviewApi } from 'dockview'

import { AgentRailPanel } from '@/components/workspace/panels/AgentRailPanel'
import { RAIL_WIDTH } from '@/components/workspace/railLayout'
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
  WORKFRAME_DND_EDGES,
} from '@/lib/workspaceDndPolicy'
import { cn } from '@/lib/utils'

function initWorkspace(event: DockviewReadyEvent, canvasEl: HTMLElement | null) {
  const api = event.api

  const chatPanel = api.addPanel({
    id: PANEL_IDS.chat,
    component: 'chatWorkspace',
    title: 'Chat',
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

  setupWorkspaceDnd(api, canvasEl)
}

function projectNameFromEnv() {
  return import.meta.env.VITE_WORKFRAME_PROJECT?.trim() || 'Workframe'
}

export function DockviewWorkspace() {
  const { theme } = useTheme()
  const { railExpanded, registerWorkspaceApi } = useWorkspacePanels()
  const railWidth = railExpanded ? RAIL_WIDTH.expanded : RAIL_WIDTH.collapsed

  const apiRef = useRef<DockviewApi | null>(null)
  const workspaceRef = useRef<HTMLDivElement | null>(null)
  const teardownRef = useRef<(() => void) | null>(null)

  const components = useMemo(
    () =>
      ({
        chatWorkspace: ChatWorkspacePanel,
        activity: ActivityPanel,
        filesExplorer: FilesExplorerPanel,
        browser: BrowserPanel,
      }) satisfies Record<string, React.FunctionComponent<IDockviewPanelProps>>,
    [],
  )

  const onReady = useCallback(
    (event: DockviewReadyEvent) => {
      initWorkspace(event, workspaceRef.current)
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
    <div
      className="wf-workspace-shell"
      style={{ '--wf-rail-width': `${railWidth}px` } as CSSProperties}
    >
      <aside className="wf-rail-fallback" aria-label="Workspace rail">
        <AgentRailPanel />
      </aside>
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
          dndEdges={WORKFRAME_DND_EDGES}
          theme={{
            dndTabIndicator: 'line',
            dndOverlayMounting: 'relative',
            ...(theme === 'dark'
              ? { name: 'wf-dark', className: 'dockview-theme-dark' }
              : { name: 'wf-light', className: 'dockview-theme-light' }),
          }}
        />
      </div>
    </div>
  )
}
