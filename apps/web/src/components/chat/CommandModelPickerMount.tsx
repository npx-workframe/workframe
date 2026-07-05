import { ModelPickerDialog } from '@/components/chat/ModelPickerDialog'
import { useAgentRoute } from '@/contexts/AgentRouteContext'
import { useCommandDialogs } from '@/contexts/CommandDialogsContext'
import { useHermesSession } from '@/contexts/HermesSessionContext'
import { useWorkspacePanels } from '@/contexts/WorkspacePanelsContext'
import { resolveAgentModelsProfile } from '@/lib/agentProfile'
import { notifyHermesModelsChanged } from '@/lib/hermesCatalogApi'

/** Mounts the slash-command model picker dialog (CommandDialogsContext.modelOpen). */
export function CommandModelPickerMount() {
  const { modelOpen, closeModelPicker } = useCommandDialogs()
  const { profile: runtimeProfile } = useHermesSession()
  const { activeRoom, openUserSettings } = useWorkspacePanels()
  const { activeProfile } = useAgentRoute()
  const modelsProfile = resolveAgentModelsProfile(activeRoom, activeProfile, runtimeProfile)
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
