import type { ReactNode } from 'react'
import type { IDockviewPanelProps } from 'dockview'

import { PanelHeaderControls } from '@/components/workspace/PanelHeaderControls'
import { cn } from '@/lib/utils'

type PanelHeaderProps = {
  label?: string
  panelId: string
  api?: IDockviewPanelProps['api']
  className?: string
  showLabel?: boolean
  showControls?: boolean
  externalHref?: string
  leading?: ReactNode
  trailing?: ReactNode
  settingsOpen?: boolean
  onSettingsOpenChange?: (open: boolean) => void
  renderSettings?: (props: { open: boolean; onClose: () => void }) => ReactNode
}

export function PanelHeader({
  label = '',
  panelId,
  api,
  className,
  showLabel = true,
  showControls = true,
  externalHref,
  leading,
  trailing,
  settingsOpen,
  onSettingsOpenChange,
  renderSettings,
}: PanelHeaderProps) {
  return (
    <div className={cn('wf-panel__header', className)}>
      {showLabel && label ? <span className="wf-panel__label">{label}</span> : null}

      <div className="wf-panel__header-actions">
        {leading}
        {showControls ? (
          <PanelHeaderControls
            panelId={panelId}
            panelLabel={label || panelId}
            api={api}
            externalHref={externalHref}
            settingsOpen={settingsOpen}
            onSettingsOpenChange={onSettingsOpenChange}
            renderSettings={renderSettings}
          />
        ) : null}
        {trailing}
      </div>
    </div>
  )
}
