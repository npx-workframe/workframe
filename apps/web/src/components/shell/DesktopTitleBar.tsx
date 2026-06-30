import { type MouseEvent } from 'react'
import { createPortal } from 'react-dom'
import { Minus, Square, X } from 'lucide-react'

import { BrandMark } from '@/components/shell/BrandMark'
import { isElectronRuntime } from '@/lib/runtime'
import { cn } from '@/lib/utils'

type DesktopTitleBarProps = {
  title?: string
}

function desktopBridge() {
  if (typeof window === 'undefined') return undefined
  return (window as Window & {
    workframe?: {
      getPlatform?: () => string
      minimizeWindow?: () => Promise<void>
      toggleMaximizeWindow?: () => Promise<{ maximized: boolean }>
      closeWindow?: () => Promise<void>
    }
  }).workframe
}

function WindowControls() {
  const bridge = desktopBridge()

  const run = (action?: () => Promise<unknown>) => {
    void action?.().catch((err) => {
      console.error('[workframe] desktop window control failed', err)
    })
  }

  const onControlActivate = (event: MouseEvent, action?: () => Promise<unknown>) => {
    event.preventDefault()
    event.stopPropagation()
    run(action)
  }

  return (
    <div className="wf-desktop-titlebar__controls" aria-label="Window controls">
      <button
        type="button"
        className="wf-desktop-titlebar__btn"
        onMouseDown={(event) => onControlActivate(event, bridge?.minimizeWindow)}
        aria-label="Minimize window"
      >
        <Minus aria-hidden="true" />
      </button>
      <button
        type="button"
        className="wf-desktop-titlebar__btn"
        onMouseDown={(event) => onControlActivate(event, bridge?.toggleMaximizeWindow)}
        aria-label="Maximize window"
      >
        <Square aria-hidden="true" />
      </button>
      <button
        type="button"
        className="wf-desktop-titlebar__btn wf-desktop-titlebar__btn--close"
        onMouseDown={(event) => onControlActivate(event, bridge?.closeWindow)}
        aria-label="Close window"
      >
        <X aria-hidden="true" />
      </button>
    </div>
  )
}

export function DesktopTitleBar({ title = 'Workframe' }: DesktopTitleBarProps) {
  if (!isElectronRuntime()) return null

  const platform = desktopBridge()?.getPlatform?.()
  const isMac = platform === 'darwin'
  const isWin = platform === 'win32'

  const bar = (
    <header
      className={cn(
        'wf-desktop-titlebar',
        isMac && 'wf-desktop-titlebar--mac',
        isWin && 'wf-desktop-titlebar--win32',
      )}
    >
      <div className="wf-desktop-titlebar__drag" aria-hidden="true" />
      {isMac ? <WindowControls /> : null}
      <div className="wf-desktop-titlebar__brand">
        <BrandMark className="wf-desktop-titlebar__mark" />
        <span className="wf-desktop-titlebar__title">{title}</span>
      </div>
      {!isMac ? <WindowControls /> : null}
    </header>
  )

  return (
    <>
      <div className="wf-desktop-titlebar-spacer" aria-hidden="true" />
      {createPortal(bar, document.body)}
    </>
  )
}
