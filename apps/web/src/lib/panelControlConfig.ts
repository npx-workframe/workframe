export const PANEL_IDS = {
  crew: 'agent-rail',
  chat: 'chat-workspace',
  activity: 'activity',
  files: 'files-explorer',
  browser: 'browser',
} as const

export type PanelControlAction = 'close' | 'expand' | 'settings' | 'external'

/** Visual order left → right; close is always last. */
export const PANEL_CONTROL_ORDER: PanelControlAction[] = [
  'external',
  'settings',
  'expand',
  'close',
]

export function orderPanelActions(actions: PanelControlAction[]): PanelControlAction[] {
  return PANEL_CONTROL_ORDER.filter((action) => actions.includes(action))
}

export type PanelControlsConfig = {
  actions: PanelControlAction[]
  externalHref?: () => string
  settingsHint?: string
}

export function getPanelControlsConfig(panelId: string): PanelControlsConfig {
  switch (panelId) {
    case PANEL_IDS.crew:
      return {
        actions: ['settings'],
        settingsHint: 'Workspace members, invites, and contact management.',
      }
    case PANEL_IDS.chat:
      return {
        actions: ['settings', 'expand', 'close'],
        settingsHint: 'Context settings for the active agent lane, project, or DM.',
      }
    case PANEL_IDS.activity:
      return {
        actions: ['close'],
      }
    case PANEL_IDS.files:
      return {
        actions: ['close'],
      }
    case PANEL_IDS.browser:
      return {
        actions: ['external', 'expand', 'close'],
      }
    default:
      return { actions: ['settings', 'expand', 'close'] }
  }
}
