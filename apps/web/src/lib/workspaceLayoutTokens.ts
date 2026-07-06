import { PANEL_IDS } from '@/lib/panelControlConfig'

/** Approximate dockview sash width between adjacent groups. */
export const WF_LAYOUT_SASH_WIDTH = 4

/** Left → right dockview panel order (rail is outside dockview). */
export const WORKSPACE_PANEL_ORDER = [
  PANEL_IDS.chat,
  PANEL_IDS.files,
  PANEL_IDS.browser,
  PANEL_IDS.activity,
] as const

/** Main canvas panels only (excludes Workframe rail). */
export const WF_MAIN_PANEL_ORDER = WORKSPACE_PANEL_ORDER

export type MainPanelId = (typeof WF_MAIN_PANEL_ORDER)[number]

export type PanelWidthRule = {
  initial: number
  preferred: number
  min: number
  /** Max when sharing canvas; alone always gets full canvas. */
  max: number
  /** Primary flex pair on viewport resize. */
  stretchable: boolean
}

export const WF_PANEL_RULES: Record<MainPanelId, PanelWidthRule> = {
  [PANEL_IDS.chat]: {
    initial: 480,
    preferred: 480,
    min: 360,
    max: Number.POSITIVE_INFINITY,
    stretchable: true,
  },
  [PANEL_IDS.files]: {
    initial: 200,
    preferred: 200,
    min: 200,
    max: 300,
    stretchable: false,
  },
  [PANEL_IDS.browser]: {
    initial: 600,
    preferred: 600,
    min: 200,
    max: Number.POSITIVE_INFINITY,
    stretchable: true,
  },
  [PANEL_IDS.activity]: {
    initial: 240,
    preferred: 240,
    min: 200,
    max: 300,
    stretchable: false,
  },
}

export const WF_CHAT_BROWSER_EVEN_SPLIT_BELOW =
  WF_PANEL_RULES[PANEL_IDS.chat].preferred * 2

export function isMainPanelId(id: string): id is MainPanelId {
  return (WF_MAIN_PANEL_ORDER as readonly string[]).includes(id)
}

export function panelInitial(panelId: string): number | null {
  if (isMainPanelId(panelId)) return WF_PANEL_RULES[panelId].initial
  return null
}

export function panelRule(panelId: MainPanelId): PanelWidthRule {
  return WF_PANEL_RULES[panelId]
}
