import type {
  DockviewApi,
  DockviewDidDropEvent,
  DockviewDndOverlayEvent,
  DockviewGroupPanel,
  DockviewWillDropEvent,
  DockviewWillShowOverlayLocationEvent,
  DroptargetOverlayModel,
} from 'dockview'

import { PANEL_IDS } from '@/lib/panelControlConfig'
import {
  capturePanelWidths,
  restorePanelWidthsAfterDrop,
} from '@/lib/workspaceLayout'

/**
 * Strip-only drop indicators — never half-pane overlays.
 * POSITIVE_INFINITY boundaries force dockview's 4px line mode on all targets.
 */
export const WORKFRAME_DND_OVERLAY: DroptargetOverlayModel = {
  activationSize: { type: 'pixels', value: 20 },
  size: { type: 'pixels', value: 3 },
  smallWidthBoundary: Number.POSITIVE_INFINITY,
  smallHeightBoundary: Number.POSITIVE_INFINITY,
}

const SPLIT_POSITIONS = new Set(['top', 'bottom', 'left', 'right'])

function isTabLikeDrop(kind: string, position: string) {
  return kind === 'tab' || kind === 'header_space' || position === 'center'
}

export function handleWorkspaceWillShowOverlay(event: DockviewWillShowOverlayLocationEvent) {
  if (isTabLikeDrop(event.kind, event.position)) {
    event.preventDefault()
  }
}

export function handleWorkspaceDragOver(event: DockviewDndOverlayEvent) {
  if (isTabLikeDrop(event.target, event.position)) return
  if (event.target === 'content' && !SPLIT_POSITIONS.has(event.position)) return
  event.accept()
}

export function handleWorkspaceWillDrop(event: DockviewWillDropEvent) {
  if (isTabLikeDrop(event.kind, event.position)) {
    event.preventDefault()
  }
}

type GroupModelInternals = {
  contentContainer: {
    dropTarget: { setOverlayModel: (model: DroptargetOverlayModel) => void }
    pointerDropTarget: { setOverlayModel: (model: DroptargetOverlayModel) => void }
  }
}

function applyStripOverlayToGroup(group: DockviewGroupPanel) {
  const internals = group.model as unknown as GroupModelInternals
  internals.contentContainer.dropTarget.setOverlayModel(WORKFRAME_DND_OVERLAY)
  internals.contentContainer.pointerDropTarget.setOverlayModel(WORKFRAME_DND_OVERLAY)
}

function applyStripOverlayToAllGroups(api: DockviewApi) {
  for (const group of api.groups) {
    applyStripOverlayToGroup(group)
  }
}

export function setupWorkspaceDnd(api: DockviewApi) {
  let widthSnapshot = capturePanelWidths(api)

  const applyStripOverlays = () => applyStripOverlayToAllGroups(api)

  applyStripOverlays()
  requestAnimationFrame(applyStripOverlays)

  api.onDidAddGroup((group) => {
    applyStripOverlayToGroup(group)
    requestAnimationFrame(() => applyStripOverlayToGroup(group))
  })

  api.onWillDragPanel((event) => {
    if (event.panel?.id === PANEL_IDS.crew) {
      event.nativeEvent.preventDefault()
      return
    }
    widthSnapshot = capturePanelWidths(api)
  })

  api.onWillDragGroup((event) => {
    if (event.group?.activePanel?.id === PANEL_IDS.crew) {
      event.nativeEvent.preventDefault()
      return
    }
    widthSnapshot = capturePanelWidths(api)
  })

  api.onWillShowOverlay(handleWorkspaceWillShowOverlay)
  api.onUnhandledDragOverEvent(handleWorkspaceDragOver)
  api.onWillDrop(handleWorkspaceWillDrop)

  api.onDidDrop((event: DockviewDidDropEvent) => {
    const snapshot = widthSnapshot
    requestAnimationFrame(() => {
      restorePanelWidthsAfterDrop(api, snapshot, dropContextFromEvent(event))
    })
  })
}

function dropContextFromEvent(event: DockviewDidDropEvent) {
  const data = event.getData()
  return {
    position: event.position,
    draggedPanelId: data?.panelId ?? null,
    targetGroupId: event.group?.id,
    targetPanelId: event.panel?.id ?? null,
  }
}
