import { useCallback } from 'react'

import { useBrowserWorkspace } from '@/contexts/BrowserWorkspaceContext'
import { useWorkspacePanels } from '@/contexts/WorkspacePanelsContext'
import { fetchHermesBootstrap } from '@/lib/hermesDashboardApi'
import { PANEL_IDS } from '@/lib/panelControlConfig'

function isHermesDashboardUrl(url: string) {
  return /hermes-dashboard/i.test(url)
}

export function useOpenBrowserUrl() {
  const { openUrl } = useBrowserWorkspace()
  const { openPanel } = useWorkspacePanels()

  return useCallback(
    (url: string) => {
      openPanel(PANEL_IDS.browser)

      if (!isHermesDashboardUrl(url)) {
        openUrl(url)
        return
      }

      void fetchHermesBootstrap()
        .then((boot) => {
          const target =
            boot.ok && boot.dashboardUrl
              ? boot.dashboardUrl.endsWith('/')
                ? boot.dashboardUrl
                : `${boot.dashboardUrl}/`
              : url
          openUrl(target)
        })
        .catch(() => {
          openUrl(url)
        })
    },
    [openPanel, openUrl],
  )
}
