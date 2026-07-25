import type { DockviewApi } from 'dockview'

import { PANEL_IDS } from '@/lib/panelControlConfig'
import { isWorkspacePanelId, WORKSPACE_PANEL_ORDER } from '@/lib/railPanelShortcuts'
import { getWorkspaceLayoutController } from '@/lib/workspaceLayout'
import { restoreWorkspacePanel } from '@/lib/workspacePanelRestore'

export function getOpenWorkspacePanelIds(api: DockviewApi): string[] {
  return WORKSPACE_PANEL_ORDER.filter((panelId) => Boolean(api.getPanel(panelId)))
}

export function getFocusedWorkspacePanelId(api: DockviewApi): string | null {
  const open = getOpenWorkspacePanelIds(api)
  if (open.length === 0) return null
  if (open.length === 1) return open[0]
  if (open.includes(PANEL_IDS.chat)) return PANEL_IDS.chat
  return open[0]
}

export function focusWorkspacePanel(
  api: DockviewApi,
  panelId: string,
  projectName: string,
): string | null {
  if (!isWorkspacePanelId(panelId)) return null

  if (!api.getPanel(panelId)) {
    restoreWorkspacePanel(api, panelId, projectName)
  }

  for (const id of WORKSPACE_PANEL_ORDER) {
    if (id === panelId) continue
    api.getPanel(id)?.api.close()
  }

  requestAnimationFrame(() => {
    getWorkspaceLayoutController()?.layout('panel-change', { preferInitialFor: panelId })
  })

  return panelId
}

export function enforceSingleWorkspacePanel(
  api: DockviewApi,
  projectName: string,
  preferredPanelId?: string | null,
): string | null {
  const open = getOpenWorkspacePanelIds(api)
  const keep =
    preferredPanelId && open.includes(preferredPanelId)
      ? preferredPanelId
      : open.includes(PANEL_IDS.chat)
        ? PANEL_IDS.chat
        : open[0] ?? PANEL_IDS.chat

  return focusWorkspacePanel(api, keep, projectName)
}
