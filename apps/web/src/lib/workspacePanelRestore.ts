import type { DockviewApi, IDockviewPanel } from 'dockview'

import { PANEL_IDS } from '@/lib/panelControlConfig'
import { panelDisplayTitle } from '@/lib/panelDisplayLabels'
import { getInitialPanelOptions, getWorkspaceLayoutController } from '@/lib/workspaceLayout'
import { isMainPanelId } from '@/lib/workspaceLayoutTokens'
import { isWorkspacePanelId, WORKSPACE_PANEL_ORDER } from '@/lib/railPanelShortcuts'

const PANEL_COMPONENTS = {
  [PANEL_IDS.crew]: 'agentRail',
  [PANEL_IDS.chat]: 'chatWorkspace',
  [PANEL_IDS.files]: 'filesExplorer',
  [PANEL_IDS.browser]: 'browser',
  [PANEL_IDS.activity]: 'activity',
} as const

function panelTitle(panelId: string) {
  return panelDisplayTitle(panelId)
}

function referencePanelForRestore(api: DockviewApi, panelId: string): IDockviewPanel | undefined {
  const index = WORKSPACE_PANEL_ORDER.indexOf(panelId as (typeof WORKSPACE_PANEL_ORDER)[number])
  if (index <= 0) return undefined

  for (let i = index - 1; i >= 0; i -= 1) {
    const candidate = api.getPanel(WORKSPACE_PANEL_ORDER[i])
    if (candidate) return candidate
  }

  return undefined
}

function anchorPanelForRestore(api: DockviewApi, panelId: string): IDockviewPanel | undefined {
  const index = WORKSPACE_PANEL_ORDER.indexOf(panelId as (typeof WORKSPACE_PANEL_ORDER)[number])
  if (index < 0) return undefined

  for (let i = index + 1; i < WORKSPACE_PANEL_ORDER.length; i += 1) {
    const candidate = api.getPanel(WORKSPACE_PANEL_ORDER[i])
    if (candidate) return candidate
  }

  return api.panels[0]
}

export function restoreWorkspacePanel(
  api: DockviewApi,
  panelId: string,
  _projectName: string,
) {
  if (panelId === PANEL_IDS.crew) return
  if (!isWorkspacePanelId(panelId) || api.getPanel(panelId)) return

  const component = PANEL_COMPONENTS[panelId]
  const baseOptions = {
    id: panelId,
    component,
    title: panelTitle(panelId),
    ...getInitialPanelOptions(panelId),
  }

  const leftReference = referencePanelForRestore(api, panelId)
  if (leftReference) {
    api.addPanel({
      ...baseOptions,
      position: { referencePanel: leftReference, direction: 'right' },
    })
  } else {
    const rightAnchor = anchorPanelForRestore(api, panelId)
    if (rightAnchor && panelId !== rightAnchor.id) {
      api.addPanel({
        ...baseOptions,
        position: { referencePanel: rightAnchor, direction: 'left' },
      })
    } else {
      api.addPanel(baseOptions)
    }
  }
}

export type WorkspacePanelTracking = {
  onPanelClosed: (panelId: string) => void
  onPanelOpened: (panelId: string) => void
}

export function setupWorkspacePanelTracking(
  api: DockviewApi,
  tracking: WorkspacePanelTracking,
) {
  const scheduleLayout = (openedPanelId?: string) => {
    requestAnimationFrame(() => {
      const controller = getWorkspaceLayoutController()
      controller?.layout('panel-change', {
        preferInitialFor: openedPanelId,
      })
    })
  }

  const disposables = [
    api.onDidRemovePanel((panel) => {
      if (!isWorkspacePanelId(panel.id) || panel.id === PANEL_IDS.crew) return
      tracking.onPanelClosed(panel.id)
      scheduleLayout()
    }),
    api.onDidAddPanel((panel) => {
      if (!isWorkspacePanelId(panel.id) || panel.id === PANEL_IDS.crew) return
      tracking.onPanelOpened(panel.id)
      scheduleLayout(isMainPanelId(panel.id) ? panel.id : undefined)
    }),
  ]

  return () => {
    for (const disposable of disposables) disposable.dispose()
  }
}
