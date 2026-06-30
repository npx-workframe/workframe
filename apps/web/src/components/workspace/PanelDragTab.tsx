import { useCallback, useState, type HTMLAttributes, type PointerEvent } from 'react'
import { Move } from 'lucide-react'
import type { IDockviewPanelHeaderProps } from 'dockview'

import { isDockablePanelId, panelDragIconFor } from '@/lib/panelDragIcons'
import { cn } from '@/lib/utils'

export function PanelDragTab({
  api,
  onPointerDown,
  onPointerUp,
  onPointerLeave,
  className,
  ...rest
}: IDockviewPanelHeaderProps & HTMLAttributes<HTMLDivElement>) {
  const panelId = api.id
  const dockable = isDockablePanelId(panelId)
  const Icon = panelDragIconFor(panelId)
  const [hovered, setHovered] = useState(false)
  const [pressed, setPressed] = useState(false)

  const showMoveIcon = hovered || pressed

  const handlePointerDown = useCallback(
    (event: PointerEvent<HTMLDivElement>) => {
      if (!dockable) return
      setPressed(true)
      onPointerDown?.(event)
    },
    [dockable, onPointerDown],
  )

  const handlePointerUp = useCallback(
    (event: PointerEvent<HTMLDivElement>) => {
      setPressed(false)
      onPointerUp?.(event)
    },
    [onPointerUp],
  )

  const handlePointerLeave = useCallback(
    (event: PointerEvent<HTMLDivElement>) => {
      setHovered(false)
      setPressed(false)
      onPointerLeave?.(event)
    },
    [onPointerLeave],
  )

  if (!dockable) {
    return <div className="wf-panel-drag-tab wf-panel-drag-tab--hidden" aria-hidden="true" />
  }

  return (
    <div
      {...rest}
      className={cn(
        'wf-panel-drag-tab',
        (hovered || pressed) && 'wf-panel-drag-tab--active',
        className,
      )}
      data-panel-id={panelId}
      role="button"
      tabIndex={0}
      aria-label={`Move ${api.title} panel`}
      onPointerEnter={() => setHovered(true)}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
      onPointerLeave={handlePointerLeave}
    >
      {showMoveIcon ? (
        <Move className="wf-panel-drag-tab__icon" aria-hidden="true" />
      ) : (
        <Icon className="wf-panel-drag-tab__icon" aria-hidden="true" />
      )}
    </div>
  )
}
