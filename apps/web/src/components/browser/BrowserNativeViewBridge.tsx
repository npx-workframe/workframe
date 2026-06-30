import { useEffect, useMemo, useRef } from 'react'

import type { BrowserTab } from '@/lib/browserTypes'
import { isElectronRuntime } from '@/lib/runtime'

type BrowserNativeViewBridgeProps = {
  tab: BrowserTab
}

function getBrowserUrl(tab: BrowserTab) {
  return tab.location.trim()
}

export function BrowserNativeViewBridge({ tab }: BrowserNativeViewBridgeProps) {
  const rootRef = useRef<HTMLDivElement | null>(null)
  const isElectron = useMemo(() => isElectronRuntime(), [])

  useEffect(() => {
    if (!isElectron) return
    const root = rootRef.current
    const bridge = (window as unknown as { workframe?: {
      setBrowserViewBounds: (bounds: { x: number; y: number; width: number; height: number }) => Promise<void>
      setBrowserViewUrl: (url: string) => Promise<void>
      clearBrowserView: () => Promise<void>
    } }).workframe
    if (!root || !bridge) return

    const sendBounds = () => {
      const rect = root.getBoundingClientRect()
      void bridge.setBrowserViewBounds({
        x: Math.round(rect.left),
        y: Math.round(rect.top),
        width: Math.max(0, Math.round(rect.width)),
        height: Math.max(0, Math.round(rect.height)),
      })
    }

    sendBounds()

    const observer = new ResizeObserver(sendBounds)
    observer.observe(root)
    window.addEventListener('resize', sendBounds)

    return () => {
      observer.disconnect()
      window.removeEventListener('resize', sendBounds)
    }
  }, [isElectron])

  useEffect(() => {
    const bridge = (window as unknown as { workframe?: {
      setBrowserViewBounds: (bounds: { x: number; y: number; width: number; height: number }) => Promise<void>
      setBrowserViewUrl: (url: string) => Promise<void>
      clearBrowserView: () => Promise<void>
    } }).workframe
    if (!isElectron || !bridge) return
    const url = getBrowserUrl(tab)
    if (!url) return
    void bridge.setBrowserViewUrl(url)
    return () => {
      void bridge.clearBrowserView()
    }
  }, [isElectron, tab.id, tab.location, tab.reloadNonce])

  if (!isElectron) return null

  return <div ref={rootRef} className="wf-browser-pane wf-browser-native" aria-hidden="true" />
}
