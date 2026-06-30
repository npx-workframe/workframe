import { useEffect, useMemo, useState } from 'react'

import { ScrollArea } from '@/components/ui/scroll-area'
import { WorkframeNotice } from '@/components/ui/WorkframeNotice'
import type { BrowserTab } from '@/lib/browserTypes'
import { fetchHermesBootstrap } from '@/lib/hermesDashboardApi'

type BrowserNavigateViewProps = {
  tab: BrowserTab
}

function isHermesDashboardLocation(location: string) {
  return /hermes-dashboard/i.test(location)
}

function normalizeDashboardUrl(url: string) {
  return url.endsWith('/') ? url : `${url}/`
}

export function BrowserNavigateView({ tab }: BrowserNavigateViewProps) {
  const isHermesDashboard = useMemo(() => isHermesDashboardLocation(tab.location), [tab.location])
  const [frameSrc, setFrameSrc] = useState(tab.location)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!isHermesDashboard) {
      setFrameSrc(tab.location)
      setError('')
      return
    }

    let cancelled = false
    setError('')
    void fetchHermesBootstrap()
      .then((boot) => {
        if (cancelled) return
        const url =
          boot.ok && boot.dashboardUrl
            ? boot.dashboardUrl
            : tab.location
        setFrameSrc(normalizeDashboardUrl(url))
        if (!boot.ok && boot.error) {
          setError(boot.error)
        }
      })
      .catch(() => {
        if (cancelled) return
        setFrameSrc(normalizeDashboardUrl(tab.location))
      })

    return () => {
      cancelled = true
    }
  }, [isHermesDashboard, tab.location, tab.reloadNonce])

  return (
    <ScrollArea className="wf-browser-pane wf-browser-navigate">
      {error ? (
        <div className="wf-browser-navigate__error">
          <WorkframeNotice message={error} />
        </div>
      ) : null}
      <iframe
        key={tab.reloadNonce}
        className="wf-browser-navigate__frame"
        src={frameSrc}
        title={tab.title}
        allow="fullscreen; autoplay; clipboard-read; clipboard-write; gamepad"
        sandbox={
          isHermesDashboard
            ? 'allow-scripts allow-same-origin allow-forms allow-popups allow-modals allow-downloads allow-pointer-lock allow-top-navigation-by-user-activation'
            : 'allow-scripts allow-forms allow-popups allow-pointer-lock allow-top-navigation-by-user-activation'
        }
      />
    </ScrollArea>
  )
}
