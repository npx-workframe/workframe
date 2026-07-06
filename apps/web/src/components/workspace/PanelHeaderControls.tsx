import { ExternalLink, Maximize2, Minimize2, Settings, X } from 'lucide-react'
import type { IDockviewPanelProps } from 'dockview'
import { useCallback, useState, type ReactNode } from 'react'

import { PanelSettingsOverlay } from '@/components/workspace/PanelSettingsOverlay'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  getPanelControlsConfig,
  orderPanelActions,
  type PanelControlAction,
} from '@/lib/panelControlConfig'
import { cn } from '@/lib/utils'

type PanelHeaderControlsProps = {
  panelId: string
  panelLabel: string
  api?: IDockviewPanelProps['api']
  className?: string
  externalHref?: string
  settingsOpen?: boolean
  onSettingsOpenChange?: (open: boolean) => void
  renderSettings?: (props: { open: boolean; onClose: () => void }) => ReactNode
}

export function PanelHeaderControls({
  panelId,
  panelLabel,
  api,
  className,
  externalHref,
  settingsOpen: settingsOpenProp,
  onSettingsOpenChange,
  renderSettings,
}: PanelHeaderControlsProps) {
  const config = getPanelControlsConfig(panelId)
  const resolvedExternalHref = externalHref ?? config.externalHref?.()
  const actions = orderPanelActions(config.actions).filter((action) => {
    if (action === 'external' && !resolvedExternalHref) return false
    if ((action === 'close' || action === 'expand') && !api) return false
    return true
  })
  const [settingsOpenInternal, setSettingsOpenInternal] = useState(false)
  const settingsOpen = settingsOpenProp ?? settingsOpenInternal
  const setSettingsOpen = onSettingsOpenChange ?? setSettingsOpenInternal
  const [maximized, setMaximized] = useState(() => api?.isMaximized() ?? false)

  const onClose = useCallback(() => {
    api?.close()
  }, [api])

  const onExpand = useCallback(() => {
    if (!api) return
    if (api.isMaximized()) {
      api.exitMaximized()
      setMaximized(false)
      return
    }
    api.maximize()
    setMaximized(true)
  }, [api])

  const onSettings = useCallback(() => {
    setSettingsOpen(true)
  }, [setSettingsOpen])

  const onExternal = useCallback(() => {
    if (!resolvedExternalHref) return
    window.open(resolvedExternalHref, '_blank', 'noopener,noreferrer')
  }, [resolvedExternalHref])

  const handlers: Record<PanelControlAction, () => void> = {
    close: onClose,
    expand: onExpand,
    settings: onSettings,
    external: onExternal,
  }

  return (
    <>
      <TooltipProvider delayDuration={400}>
        <div
          className={cn('wf-panel__controls', className)}
          role="toolbar"
          aria-label={`${panelLabel} panel controls`}
        >
          {actions.map((action) => (
            <PanelControlButton
              key={action}
              action={action}
              maximized={maximized}
              onClick={handlers[action]}
            />
          ))}
        </div>
      </TooltipProvider>

      {renderSettings ? (
        renderSettings({ open: settingsOpen, onClose: () => setSettingsOpen(false) })
      ) : (
        <PanelSettingsOverlay
          panelLabel={panelLabel}
          hint={config.settingsHint}
          open={settingsOpen}
          onClose={() => setSettingsOpen(false)}
        />
      )}
    </>
  )
}

type PanelControlButtonProps = {
  action: PanelControlAction
  maximized: boolean
  onClick: () => void
}

function PanelControlButton({ action, maximized, onClick }: PanelControlButtonProps) {
  const meta = controlMeta(action, maximized)

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className="wf-panel__control-btn"
          onClick={onClick}
          aria-label={meta.label}
        >
          <meta.icon aria-hidden="true" />
        </button>
      </TooltipTrigger>
      <TooltipContent side="bottom">{meta.label}</TooltipContent>
    </Tooltip>
  )
}

function controlMeta(action: PanelControlAction, maximized: boolean) {
  switch (action) {
    case 'close':
      return { label: 'Close panel', icon: X }
    case 'expand':
      return maximized
        ? { label: 'Exit full screen', icon: Minimize2 }
        : { label: 'Expand panel', icon: Maximize2 }
    case 'settings':
      return { label: 'Panel settings', icon: Settings }
    case 'external':
      return { label: 'Open in browser', icon: ExternalLink }
    default:
      return { label: action, icon: Settings }
  }
}
