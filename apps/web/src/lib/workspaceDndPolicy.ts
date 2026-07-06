import type {
  DockviewApi,
  DockviewDidDropEvent,
  DockviewDndOverlayEvent,
  DockviewGroupPanel,
  DockviewWillDropEvent,
  DockviewWillShowOverlayLocationEvent,
  DroptargetOverlayModel,
} from 'dockview'

import {
  capturePanelWidths,
  restorePanelWidthsAfterDrop,
} from '@/lib/workspaceLayout'

/**
 * Dockview shapes drop targets with DroptargetOverlayModel:
 * - activationSize: pointer zone that arms a side
 * - size: visible band thickness (when small*Boundary is 0)
 * - small*Boundary: 0 = always use size bands; default 100px switches to 4px lines
 *
 * dndEdges shapes the outer layout only. Per-panel content uses setOverlayModel
 * below until dockview exposes dropOverlayModel on DockviewReact (7.x master).
 */

const WF_DND_MACRO_PX = 16
const WF_DND_PANEL_PX = 40

const PIXEL_BAND: Pick<
  DroptargetOverlayModel,
  'smallWidthBoundary' | 'smallHeightBoundary'
> = {
  smallWidthBoundary: 0,
  smallHeightBoundary: 0,
}

export const WORKFRAME_DND_EDGES: DroptargetOverlayModel = {
  activationSize: { type: 'pixels', value: WF_DND_MACRO_PX },
  size: { type: 'pixels', value: WF_DND_MACRO_PX },
  ...PIXEL_BAND,
}

const WORKFRAME_DND_CONTENT: DroptargetOverlayModel = {
  activationSize: { type: 'pixels', value: WF_DND_PANEL_PX },
  size: { type: 'pixels', value: WF_DND_PANEL_PX },
  ...PIXEL_BAND,
}

function isContentCenterDrop(kind: string, position: string) {
  return kind === 'content' && position === 'center'
}

let workspaceCanvasEl: HTMLElement | null = null

function isPointerInCanvas(event: Event) {
  if (!workspaceCanvasEl) return true
  const pointer = event as PointerEvent & DragEvent
  if (typeof pointer.clientX !== 'number' || typeof pointer.clientY !== 'number') return true
  const rect = workspaceCanvasEl.getBoundingClientRect()
  return (
    pointer.clientX >= rect.left &&
    pointer.clientX <= rect.right &&
    pointer.clientY >= rect.top &&
    pointer.clientY <= rect.bottom
  )
}

export function handleWorkspaceWillShowOverlay(
  event: DockviewWillShowOverlayLocationEvent,
) {
  if (!isPointerInCanvas(event.nativeEvent)) {
    event.preventDefault()
    return
  }
  if (isContentCenterDrop(event.kind, event.position)) {
    event.preventDefault()
  }
}

export function handleWorkspaceDragOver(event: DockviewDndOverlayEvent) {
  if (!isPointerInCanvas(event.nativeEvent)) return
  if (isContentCenterDrop(event.target, event.position)) return
  event.accept()
}

export function handleWorkspaceWillDrop(event: DockviewWillDropEvent) {
  if (!isPointerInCanvas(event.nativeEvent)) {
    event.preventDefault()
    return
  }
  if (isContentCenterDrop(event.kind, event.position)) {
    event.preventDefault()
  }
}

type GroupContentDropTargets = {
  dropTarget: { setOverlayModel: (model: DroptargetOverlayModel) => void }
  pointerDropTarget: { setOverlayModel: (model: DroptargetOverlayModel) => void }
}

function applyContentOverlayModel(group: DockviewGroupPanel) {
  const content = (
    group.model as unknown as { contentContainer: GroupContentDropTargets }
  ).contentContainer
  content.dropTarget.setOverlayModel(WORKFRAME_DND_CONTENT)
  content.pointerDropTarget.setOverlayModel(WORKFRAME_DND_CONTENT)
}

export function setupWorkspaceDnd(api: DockviewApi, canvasEl?: HTMLElement | null) {
  workspaceCanvasEl = canvasEl ?? null
  let widthSnapshot = capturePanelWidths(api)

  for (const group of api.groups) {
    applyContentOverlayModel(group)
  }

  api.onDidAddGroup(applyContentOverlayModel)

  api.onWillDragPanel(() => {
    widthSnapshot = capturePanelWidths(api)
  })

  api.onWillDragGroup(() => {
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
