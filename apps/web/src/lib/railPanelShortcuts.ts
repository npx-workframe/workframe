import { Activity, FolderTree, Globe, MessageSquare, Users, type LucideIcon } from 'lucide-react'

import { PANEL_IDS } from '@/lib/panelControlConfig'
import { panelDisplayTitle } from '@/lib/panelDisplayLabels'
import { WORKSPACE_PANEL_ORDER } from '@/lib/workspaceLayoutTokens'

export { WORKSPACE_PANEL_ORDER }

export type WorkspacePanelId = (typeof WORKSPACE_PANEL_ORDER)[number]

export type RailPanelShortcut = {
  id: WorkspacePanelId
  label: string
  icon: LucideIcon
}

export function isWorkspacePanelId(id: string): id is WorkspacePanelId {
  return (WORKSPACE_PANEL_ORDER as readonly string[]).includes(id)
}

/** Shortcuts shown on the rail when a panel is closed. */
export function railPanelShortcuts(_projectName: string): RailPanelShortcut[] {
  return [
    { id: PANEL_IDS.crew, label: panelDisplayTitle(PANEL_IDS.crew), icon: Users },
    { id: PANEL_IDS.chat, label: panelDisplayTitle(PANEL_IDS.chat), icon: MessageSquare },
    { id: PANEL_IDS.files, label: panelDisplayTitle(PANEL_IDS.files), icon: FolderTree },
    { id: PANEL_IDS.browser, label: panelDisplayTitle(PANEL_IDS.browser), icon: Globe },
    { id: PANEL_IDS.activity, label: panelDisplayTitle(PANEL_IDS.activity), icon: Activity },
  ]
}
