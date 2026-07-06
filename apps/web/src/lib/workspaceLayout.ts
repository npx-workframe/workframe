import type { DockviewApi, IDockviewPanel } from 'dockview'

import { PANEL_IDS } from '@/lib/panelControlConfig'
import { RAIL_WIDTH } from '@/components/workspace/railLayout'
import {
  canvasFromWorkspace,
  clearFlexManualOnViewport,
  createInitialLayoutState,
  railWidthForState,
  reconcileSashWidths,
  sashCountFor,
  solveCanvasWidths,
  type LayoutMeasure,
  type LayoutReason,
  type WorkspaceLayoutState,
} from '@/lib/workspaceLayoutEngine'
import {
  isMainPanelId,
  panelInitial,
  panelRule,
  WF_MAIN_PANEL_ORDER,
  WF_PANEL_RULES,
  type MainPanelId,
} from '@/lib/workspaceLayoutTokens'

export { PANEL_IDS }
export {
  WF_CHAT_BROWSER_EVEN_SPLIT_BELOW,
  WF_LAYOUT_SASH_WIDTH,
  WF_MAIN_PANEL_ORDER,
  WF_PANEL_RULES,
  WORKSPACE_PANEL_ORDER,
} from '@/lib/workspaceLayoutTokens'

export type { WorkspaceLayoutState, LayoutReason } from '@/lib/workspaceLayoutEngine'

export type ApplyLayoutOptions = {
  preferInitialFor?: string
}

export const RAIL_EXPANDED_WIDTH = RAIL_WIDTH.expanded

function getPanel(api: DockviewApi, panelId: string): IDockviewPanel | undefined {
  return api.getPanel(panelId)
}

export function readGroupWidth(panel: IDockviewPanel | undefined): number | null {
  if (!panel) return null
  const width = panel.group?.api.width ?? panel.api.width
  if (!width || width <= 0) return null
  return Math.round(width)
}

export function resolveWorkspaceWidth(
  api: DockviewApi,
  fallbackEl?: HTMLElement | null,
): number {
  if (api.width > 0) return api.width
  if (fallbackEl?.clientWidth) return fallbackEl.clientWidth
  return typeof window !== 'undefined' ? window.innerWidth : 0
}

function readMainWidths(api: DockviewApi): Partial<Record<MainPanelId, number>> {
  const widths: Partial<Record<MainPanelId, number>> = {}
  for (const id of WF_MAIN_PANEL_ORDER) {
    const panel = getPanel(api, id)
    const width = readGroupWidth(panel)
    if (width) widths[id] = width
  }
  return widths
}

function measure(api: DockviewApi, state: WorkspaceLayoutState, fallbackEl?: HTMLElement | null): LayoutMeasure | null {
  const workspaceWidth = resolveWorkspaceWidth(api, fallbackEl)
  if (workspaceWidth <= 0) return null

  const railWidth = railWidthForState(state)
  const visible = WF_MAIN_PANEL_ORDER.filter((id) => Boolean(getPanel(api, id)))
  const sashCount = sashCountFor(visible.length)
  const canvas = canvasFromWorkspace(workspaceWidth, sashCount)

  return { workspaceWidth, railWidth, canvas, visible }
}

function setGroupWidth(panel: IDockviewPanel | undefined, width: number) {
  if (!panel?.api.isVisible) return
  const rounded = Math.max(1, Math.round(width))
  panel.group.api.setSize({ width: rounded })
}

function configureMainPanel(panel: IDockviewPanel, panelId: MainPanelId, width: number) {
  const rule = panelRule(panelId)
  panel.group.api.setConstraints({
    minimumWidth: rule.min,
    maximumWidth: Number.isFinite(rule.max) ? rule.max : undefined,
  })
  setGroupWidth(panel, width)
}

export class WorkspaceLayoutController {
  readonly state: WorkspaceLayoutState = createInitialLayoutState()

  root: HTMLElement | null
  private api: DockviewApi
  private applying = false
  private lastCanvasWidth = 0
  private sashFrame = 0
  private disposables: Array<{ dispose: () => void }> = []

  constructor(api: DockviewApi, root: HTMLElement | null) {
    this.api = api
    this.root = root
  }

  dispose() {
    for (const disposable of this.disposables) disposable.dispose()
    this.disposables = []
    cancelAnimationFrame(this.sashFrame)
  }

  setRailExpanded(expanded: boolean) {
    this.state.railExpanded = expanded
    this.layout('rail')
  }

  layout(reason: LayoutReason, options: ApplyLayoutOptions = {}) {
    if (this.applying) return false

    const measureCtx = measure(this.api, this.state, this.root)
    if (!measureCtx) return false

    if (reason === 'viewport' || reason === 'rail') {
      clearFlexManualOnViewport(this.state)
    }

    const opened =
      options.preferInitialFor && isMainPanelId(options.preferInitialFor)
        ? options.preferInitialFor
        : undefined

    const targets = solveCanvasWidths(measureCtx, this.state, reason, opened)
    this.apply(measureCtx, targets)
    this.state.widths = { ...targets }
    this.lastCanvasWidth = measureCtx.canvas
    return true
  }

  watch() {
    let resizeFrame = 0
    let lastContainerWidth = this.root?.clientWidth ?? 0

    const onViewport = () => {
      cancelAnimationFrame(resizeFrame)
      resizeFrame = requestAnimationFrame(() => this.layout('viewport'))
    }

    if (this.root) {
      const ro = new ResizeObserver((entries) => {
        const width = entries[0]?.contentRect.width ?? this.root!.clientWidth
        if (width <= 0 || Math.abs(width - lastContainerWidth) < 1) return
        lastContainerWidth = width
        onViewport()
      })
      ro.observe(this.root)
      this.disposables.push({ dispose: () => ro.disconnect() })
    }

    window.addEventListener('resize', onViewport)
    this.disposables.push({ dispose: () => window.removeEventListener('resize', onViewport) })

    const layoutDisposable = this.api.onDidLayoutChange(() => {
      if (this.applying) return
      cancelAnimationFrame(this.sashFrame)
      this.sashFrame = requestAnimationFrame(() => this.onDockviewLayout())
    })
    this.disposables.push(layoutDisposable)

    return () => this.dispose()
  }

  private onDockviewLayout() {
    const measureCtx = measure(this.api, this.state, this.root)
    if (!measureCtx) return

    if (Math.abs(measureCtx.canvas - this.lastCanvasWidth) >= 2) {
      this.layout('viewport')
      return
    }

    const readings = readMainWidths(this.api)
    const targets = reconcileSashWidths(measureCtx, readings, this.state)
    this.state.widths = { ...targets }
    this.lastCanvasWidth = measureCtx.canvas
  }

  private apply(measureCtx: LayoutMeasure, targets: Partial<Record<MainPanelId, number>>) {
    this.applying = true
    try {
      for (const id of measureCtx.visible) {
        const panel = getPanel(this.api, id)
        if (!panel) continue
        configureMainPanel(panel, id, targets[id] ?? panelRule(id).min)
      }
    } finally {
      this.applying = false
    }
  }
}

let activeController: WorkspaceLayoutController | null = null

export function getWorkspaceLayoutController() {
  return activeController
}

export function createWorkspaceLayoutController(api: DockviewApi, root: HTMLElement | null) {
  activeController?.dispose()
  activeController = new WorkspaceLayoutController(api, root)
  return activeController
}

export function applyWorkspaceLayout(
  api: DockviewApi,
  fallbackEl?: HTMLElement | null,
  options: ApplyLayoutOptions = {},
) {
  if (activeController) {
    activeController.root = fallbackEl ?? activeController.root
    return activeController.layout('panel-change', options)
  }

  const controller = new WorkspaceLayoutController(api, fallbackEl ?? null)
  return controller.layout('init', options)
}

export function capturePanelWidths(api: DockviewApi): Map<string, number> {
  const widths = new Map<string, number>()
  for (const panel of api.panels) {
    if (panel.id === PANEL_IDS.crew) continue
    const width = readGroupWidth(panel)
    if (width) widths.set(panel.id, width)
  }
  return widths
}

export function restorePanelWidthsAfterDrop(
  api: DockviewApi,
  _before: Map<string, number>,
  drop?: { position?: string },
) {
  if (drop?.position === 'top' || drop?.position === 'bottom') return
  if (activeController) {
    activeController.layout('panel-change')
  } else {
    applyWorkspaceLayout(api)
  }
}

export function getInitialPanelOptions(panelId: string) {
  const initial =
    panelInitial(panelId) ??
    (panelId === PANEL_IDS.browser ? WF_PANEL_RULES[PANEL_IDS.browser].initial : 120)

  if (!isMainPanelId(panelId)) {
    return { initialWidth: initial }
  }

  const rule = panelRule(panelId)
  return {
    minimumWidth: rule.min,
    maximumWidth: Number.isFinite(rule.max) ? rule.max : undefined,
    initialWidth: initial,
  }
}
