import type { ReactNode } from 'react'
import { Minus, Square, X } from 'lucide-react'

import { BrandMark } from '@/components/shell/BrandMark'
import { BrandTitle } from '@/components/shell/BrandTitle'
import { Button } from '@/components/ui/button'
import { isElectronRuntime } from '@/lib/runtime'

type ShellHeaderProps = {
  projectName: string
  subtitle?: string
  brandLogoUrl?: string
  nav?: ReactNode
  actions?: ReactNode
}

export function ShellHeader({ projectName, subtitle, brandLogoUrl, nav, actions }: ShellHeaderProps) {
  const isElectron = isElectronRuntime()

  return (
    <header className="wf-shell__header">
      <div className="wf-brand">
        {brandLogoUrl ? (
          <img
            src={brandLogoUrl}
            alt=""
            className="wf-brand__mark wf-brand__mark--image"
            aria-hidden="true"
          />
        ) : (
          <BrandMark />
        )}
        <BrandTitle projectName={projectName} subtitle={subtitle} />
      </div>

      {nav}

      {isElectron ? <div className="wf-shell__drag" aria-hidden="true" /> : null}

      {actions ? <div className="wf-shell__actions">{actions}</div> : null}

      {isElectron ? <DesktopWindowControls /> : null}
    </header>
  )
}

function DesktopWindowControls() {
  const bridge = typeof window !== 'undefined' ? (window as Window & { workframe?: {
    minimizeWindow?: () => Promise<void>
    toggleMaximizeWindow?: () => Promise<{ maximized: boolean }>
    closeWindow?: () => Promise<void>
  } }).workframe : undefined

  return (
    <div className="wf-shell__window-controls" aria-label="Window controls">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="wf-shell__window-btn"
        onClick={() => void bridge?.minimizeWindow?.()}
        aria-label="Minimize window"
      >
        <Minus aria-hidden="true" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="wf-shell__window-btn"
        onClick={() => void bridge?.toggleMaximizeWindow?.()}
        aria-label="Maximize window"
      >
        <Square aria-hidden="true" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="wf-shell__window-btn wf-shell__window-btn--close"
        onClick={() => void bridge?.closeWindow?.()}
        aria-label="Close window"
      >
        <X aria-hidden="true" />
      </Button>
    </div>
  )
}
