import { useEffect, useState } from 'react'
import { AppWindow, ExternalLink } from 'lucide-react'

import { useOpenBrowserUrl } from '@/hooks/useOpenBrowserUrl'
import { getSurfaceLinks } from '@/lib/surfaceLinks'
import { workframeAuthApi } from '@/lib/workframeAuthApi'

export function ShellNavLinks() {
  const [links, setLinks] = useState(() => getSurfaceLinks())
  const openBrowserUrl = useOpenBrowserUrl()

  useEffect(() => {
    let cancelled = false
    void workframeAuthApi.getMe().then((profile) => {
      if (cancelled) return
      const includeDashboard = profile.hermes_dashboard_access !== false
      setLinks(getSurfaceLinks({ includeDashboard }))
    }).catch(() => {
      if (!cancelled) setLinks(getSurfaceLinks())
    })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <nav className="wf-shell-nav" aria-label="External surfaces">
      {links.map((link) => {
        if (link.id === 'dashboard') {
          return (
            <button
              key={link.id}
              type="button"
              className="wf-shell-nav__link"
              onClick={() => openBrowserUrl(link.href)}
            >
              <span>{link.label}</span>
              <AppWindow className="wf-shell-nav__icon" aria-hidden="true" />
            </button>
          )
        }

        return (
          <a
            key={link.id}
            className="wf-shell-nav__link"
            href={link.href}
            target="_blank"
            rel="noopener noreferrer"
          >
            <span>{link.label}</span>
            <ExternalLink className="wf-shell-nav__icon" aria-hidden="true" />
          </a>
        )
      })}
    </nav>
  )
}
