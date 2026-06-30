import type { IDockviewPanelProps } from 'dockview'

import { ProjectFileTree } from '@/components/files/ProjectFileTree'
import { PanelHeader } from '@/components/workspace/PanelHeader'
import { PanelShell } from '@/components/workspace/PanelShell'
import { useWorkspaceBranding } from '@/hooks/useWorkspaceBranding'
import { PANEL_IDS } from '@/lib/panelControlConfig'
import { NAVIGATOR_PANEL_LABEL } from '@/lib/panelDisplayLabels'

export function FilesExplorerPanel({ api }: IDockviewPanelProps) {
  const fallbackName = import.meta.env.VITE_WORKFRAME_PROJECT?.trim() || 'Workframe'
  const { name: projectName } = useWorkspaceBranding(fallbackName)

  return (
    <PanelShell className="wf-panel--files wf-panel--dockable">
      <PanelHeader label={NAVIGATOR_PANEL_LABEL} panelId={PANEL_IDS.files} api={api} />
      <ProjectFileTree projectName={projectName} />
    </PanelShell>
  )
}
