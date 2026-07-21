import { ModelPickerDialog } from '@/components/chat/ModelPickerDialog'
import { useAgentRoute } from '@/contexts/AgentRouteContext'
import { useCommandDialogs } from '@/contexts/CommandDialogsContext'
import { useWorkspacePanels } from '@/contexts/WorkspacePanelsContext'
import { resolveAgentModelsProfile } from '@/lib/agentProfile'
import { notifyHermesModelsChanged } from '@/lib/hermesCatalogApi'

/** Mounts the slash-command model picker dialog (CommandDialogsContext.modelOpen). */
export function CommandModelPickerMount() {
  const { modelOpen, closeModelPicker } = useCommandDialogs()
  const { activeRoom, openUserSettings } = useWorkspacePanels()
  const { activeProfile } = useAgentRoute()
  const modelsProfile = resolveAgentModelsProfile(activeRoom, activeProfile)
  const workspaceId = activeRoom?.workspace_id ?? ''

  return (
    <ModelPickerDialog
      open={modelOpen}
      onOpenChange={(open) => {
        if (!open) closeModelPicker()
      }}
      profile={modelsProfile}
      workspaceId={workspaceId}
      onConnectProvider={() => openUserSettings('connect')}
      onChanged={() => notifyHermesModelsChanged(modelsProfile)}
    />
  )
}
