import { useCallback } from 'react'

import { useBrowserWorkspace } from '@/contexts/BrowserWorkspaceContext'
import { useWorkspacePanels } from '@/contexts/WorkspacePanelsContext'
import type { OpenFilePayload } from '@/lib/browserTypes'
import { PANEL_IDS } from '@/lib/panelControlConfig'

export function useOpenWorkspaceFile() {
  const { openFile } = useBrowserWorkspace()
  const { openPanel } = useWorkspacePanels()

  return useCallback(
    (payload: OpenFilePayload) => {
      openPanel(PANEL_IDS.browser)
      openFile(payload)
    },
    [openFile, openPanel],
  )
}
