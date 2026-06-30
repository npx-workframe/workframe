import { PANEL_IDS } from '@/lib/panelControlConfig'

export const WORKFRAME_RAIL_LABEL = 'Workframe'
export const NAVIGATOR_PANEL_LABEL = 'Navigator'

export function panelDisplayTitle(panelId: string): string {
  switch (panelId) {
    case PANEL_IDS.crew:
      return WORKFRAME_RAIL_LABEL
    case PANEL_IDS.chat:
      return 'Chat'
    case PANEL_IDS.files:
      return NAVIGATOR_PANEL_LABEL
    case PANEL_IDS.browser:
      return 'Browser'
    case PANEL_IDS.activity:
      return 'Activity'
    default:
      return panelId
  }
}
