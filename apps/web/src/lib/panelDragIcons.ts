import { Activity, FolderTree, Globe, MessageSquare } from 'lucide-react'

import { PANEL_IDS } from '@/lib/panelControlConfig'

export type PanelDragIcon = typeof MessageSquare

export const PANEL_DRAG_ICONS: Record<string, PanelDragIcon> = {
  [PANEL_IDS.chat]: MessageSquare,
  [PANEL_IDS.files]: FolderTree,
  [PANEL_IDS.browser]: Globe,
  [PANEL_IDS.activity]: Activity,
}

export function isDockablePanelId(panelId: string) {
  return panelId in PANEL_DRAG_ICONS
}

export function panelDragIconFor(panelId: string): PanelDragIcon {
  return PANEL_DRAG_ICONS[panelId] ?? MessageSquare
}
