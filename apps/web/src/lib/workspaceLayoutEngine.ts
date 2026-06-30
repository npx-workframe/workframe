import { PANEL_IDS } from '@/lib/panelControlConfig'
import { RAIL_WIDTH } from '@/components/workspace/railLayout'
import {
  WF_LAYOUT_SASH_WIDTH,
  WF_MAIN_PANEL_ORDER,
  WF_PANEL_RULES,
  type MainPanelId,
} from '@/lib/workspaceLayoutTokens'

export type WorkspaceLayoutState = {
  railExpanded: boolean
  /** Last applied / measured canvas panel widths. */
  widths: Partial<Record<MainPanelId, number>>
  /** User sash overrides — sticky across viewport resizes for side columns. */
  manual: Partial<Record<MainPanelId, number>>
}

export type LayoutMeasure = {
  workspaceWidth: number
  railWidth: number
  canvas: number
  visible: MainPanelId[]
}

export type LayoutReason = 'init' | 'viewport' | 'panel-change' | 'rail' | 'sash'

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

function sumVisible(widths: Partial<Record<MainPanelId, number>>, visible: MainPanelId[]) {
  return visible.reduce((total, id) => total + (widths[id] ?? 0), 0)
}

function minSumFor(visible: MainPanelId[], skip?: MainPanelId) {
  return visible.reduce((total, id) => {
    if (id === skip) return total
    return total + WF_PANEL_RULES[id].min
  }, 0)
}

export function createInitialLayoutState(): WorkspaceLayoutState {
  return {
    railExpanded: true,
    widths: {},
    manual: {},
  }
}

export function railWidthForState(state: WorkspaceLayoutState) {
  return state.railExpanded ? RAIL_WIDTH.expanded : RAIL_WIDTH.collapsed
}

/** Chat + browser split for remaining canvas after side columns. */
export function splitChatBrowserFlex(flexCanvas: number): { chat: number; browser: number } {
  const chatRule = WF_PANEL_RULES[PANEL_IDS.chat]
  const browserRule = WF_PANEL_RULES[PANEL_IDS.browser]
  const idealChat = chatRule.preferred
  const idealBrowser = browserRule.preferred

  if (flexCanvas <= 0) {
    return { chat: 0, browser: 0 }
  }

  if (flexCanvas >= idealChat + idealBrowser) {
    return { chat: idealChat, browser: flexCanvas - idealChat }
  }

  let chat = clamp(idealChat, chatRule.min, Math.min(chatRule.max, flexCanvas - browserRule.min))
  let browser = flexCanvas - chat

  if (browser >= browserRule.min) {
    return { chat, browser }
  }

  chat = Math.round(flexCanvas * 0.5)
  chat = clamp(chat, chatRule.min, chatRule.max)
  browser = flexCanvas - chat

  if (browser < browserRule.min) {
    chat = clamp(flexCanvas - browserRule.min, chatRule.min, chatRule.max)
    browser = flexCanvas - chat
  }

  return { chat, browser }
}

function resolveSideWidth(
  id: MainPanelId,
  state: WorkspaceLayoutState,
  reason: LayoutReason,
  remaining: number,
  visible: MainPanelId[],
): number {
  const rule = WF_PANEL_RULES[id]
  const stickyManual =
    reason !== 'init' &&
    reason !== 'panel-change' &&
    state.manual[id] !== undefined &&
    !rule.stretchable

  const base = stickyManual
    ? state.manual[id]!
    : reason === 'panel-change' && state.widths[id] !== undefined
      ? state.widths[id]!
      : rule.preferred

  const maxAllowed = Math.min(rule.max, remaining - minSumFor(visible, id))
  return clamp(base, rule.min, Math.max(rule.min, maxAllowed))
}

/**
 * Compute target widths for all visible main panels.
 * Files + Activity hold preferred/manual; Chat + Browser absorb the remainder.
 */
export function solveCanvasWidths(
  measure: LayoutMeasure,
  state: WorkspaceLayoutState,
  reason: LayoutReason,
  openedPanelId?: MainPanelId,
): Partial<Record<MainPanelId, number>> {
  const { canvas, visible } = measure
  if (visible.length === 0) return {}
  if (visible.length === 1) {
    return { [visible[0]]: Math.round(canvas) }
  }

  const widths = Object.fromEntries(visible.map((id) => [id, 0])) as Record<MainPanelId, number>
  let remaining = canvas

  for (const id of [PANEL_IDS.files, PANEL_IDS.activity] as const) {
    if (!visible.includes(id)) continue
    if (reason === 'panel-change' && openedPanelId === id) {
      widths[id] = clamp(WF_PANEL_RULES[id].initial, WF_PANEL_RULES[id].min, remaining)
    } else {
      widths[id] = resolveSideWidth(id, state, reason, remaining, visible)
    }
    remaining -= widths[id]
  }

  const chatOpen = visible.includes(PANEL_IDS.chat)
  const browserOpen = visible.includes(PANEL_IDS.browser)

  if (chatOpen && browserOpen) {
    const split = splitChatBrowserFlex(Math.max(0, remaining))
    widths[PANEL_IDS.chat] = split.chat
    widths[PANEL_IDS.browser] = split.browser
  } else if (chatOpen) {
    widths[PANEL_IDS.chat] = remaining
  } else if (browserOpen) {
    widths[PANEL_IDS.browser] = remaining
  }

  const assigned = sumVisible(widths, visible)
  if (assigned !== canvas && browserOpen) {
    widths[PANEL_IDS.browser] = Math.max(
      WF_PANEL_RULES[PANEL_IDS.browser].min,
      widths[PANEL_IDS.browser] + (canvas - assigned),
    )
  }

  return widths
}

/** After a sash drag, sync state from dockview readings and absorb slack in browser. */
export function reconcileSashWidths(
  measure: LayoutMeasure,
  readings: Partial<Record<MainPanelId, number>>,
  state: WorkspaceLayoutState,
): Partial<Record<MainPanelId, number>> {
  const { canvas, visible } = measure
  if (visible.length === 0) return {}

  if (visible.length === 1) {
    return { [visible[0]]: canvas }
  }

  const widths: Partial<Record<MainPanelId, number>> = {}
  for (const id of visible) {
    const rule = WF_PANEL_RULES[id]
    widths[id] = clamp(readings[id] ?? state.widths[id] ?? rule.preferred, rule.min, canvas)
  }

  let total = sumVisible(widths, visible)
  if (total !== canvas && visible.includes(PANEL_IDS.browser)) {
    widths[PANEL_IDS.browser] = Math.max(
      WF_PANEL_RULES[PANEL_IDS.browser].min,
      (widths[PANEL_IDS.browser] ?? 0) + (canvas - total),
    )
    total = sumVisible(widths, visible)
  }

  if (total > canvas) {
    const scale = canvas / total
    for (const id of visible) {
      const rule = WF_PANEL_RULES[id]
      widths[id] = Math.max(rule.min, Math.floor((widths[id] ?? 0) * scale))
    }
    const slack = canvas - sumVisible(widths, visible)
    if (slack !== 0 && visible.includes(PANEL_IDS.browser)) {
      widths[PANEL_IDS.browser] = Math.max(
        WF_PANEL_RULES[PANEL_IDS.browser].min,
        (widths[PANEL_IDS.browser] ?? 0) + slack,
      )
    }
  }

  for (const id of visible) {
    const rule = WF_PANEL_RULES[id]
    const width = widths[id] ?? rule.preferred
    if (!rule.stretchable && Math.abs(width - rule.preferred) > 2) {
      state.manual[id] = width
    }
    if (rule.stretchable) {
      delete state.manual[id]
    }
  }

  return widths
}

export function clearFlexManualOnViewport(state: WorkspaceLayoutState) {
  for (const id of WF_MAIN_PANEL_ORDER) {
    if (WF_PANEL_RULES[id].stretchable) {
      delete state.manual[id]
    }
  }
}

export function sashCountFor(crewPresent: boolean, mainCount: number) {
  return (crewPresent ? 1 : 0) + Math.max(0, mainCount - 1)
}

export function canvasFromWorkspace(workspaceWidth: number, railWidth: number, sashCount: number) {
  return Math.max(
    WF_PANEL_RULES[PANEL_IDS.chat].min,
    workspaceWidth - railWidth - sashCount * WF_LAYOUT_SASH_WIDTH,
  )
}
