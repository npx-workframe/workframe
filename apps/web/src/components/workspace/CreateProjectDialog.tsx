import { useState } from 'react'

import { AvatarPickerGrid } from '@/components/onboarding/AvatarPickerGrid'
import { DialogCancelButton, DialogConfirmButton } from '@/components/dialogs/DialogActions'
import { DialogField } from '@/components/dialogs/DialogField'
import { Input } from '@/components/ui/input'
import { OperationProgress, type OperationStep } from '@/components/ui/OperationProgress'
import { WorkframeNotice } from '@/components/ui/WorkframeNotice'
import { SettingsSheetFrame } from '@/components/workspace/SettingsSheetFrame'
import { WizardFormActions } from '@/components/workspace/WizardFormActions'
import { DEFAULT_WORKSPACE_LOGO } from '@/lib/workframeAssets'
import { logoAvatarPersistPayload, pickRandomPreset } from '@/lib/presetAssets'
import { workframeAuthApi } from '@/lib/workframeAuthApi'

type CreateProjectDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  workspaceId: string
  onCreated?: () => void
}

const CREATE_PROJECT_STEPS = [
  { id: 'validate', label: 'Validate project details' },
  { id: 'create_room', label: 'Create channel' },
  { id: 'assign_logo', label: 'Apply project logo' },
]

function normalizeRoomSlug(seed: string): string {
  return seed
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48)
}

export function CreateProjectDialog({
  open,
  onOpenChange,
  workspaceId,
  onCreated,
}: CreateProjectDialogProps) {
  const [name, setName] = useState('')
  const [topic, setTopic] = useState('')
  const [logoUrl, setLogoUrl] = useState(() => pickRandomPreset('logo') || DEFAULT_WORKSPACE_LOGO)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [steps, setSteps] = useState<OperationStep[]>([])

  const reset = () => {
    setName('')
    setTopic('')
    setLogoUrl(pickRandomPreset('logo') || DEFAULT_WORKSPACE_LOGO)
    setError('')
    setSteps([])
  }

  const createProject = async () => {
    const trimmed = name.trim()
    if (!trimmed) {
      setError('Project name is required')
      return
    }
    if (!workspaceId) {
      setError('Workframe not loaded')
      return
    }

    setBusy(true)
    setError('')
    setSteps(CREATE_PROJECT_STEPS.map((step, index) => ({ ...step, status: index === 0 ? 'active' : 'pending' })))

    try {
      await new Promise((resolve) => window.setTimeout(resolve, 200))
      setSteps((current) =>
        current.map((step, index) => ({
          ...step,
          status: index === 0 ? 'done' : index === 1 ? 'active' : 'pending',
        })),
      )
      const logo = logoUrl ? logoAvatarPersistPayload(logoUrl) : null
      await workframeAuthApi.createWorkspaceRoom(workspaceId, {
        name: trimmed,
        slug: normalizeRoomSlug(trimmed),
        topic: topic.trim() || undefined,
        room_type: 'channel',
        ...(logo ?? {}),
      })
      setSteps((current) => current.map((step) => ({ ...step, status: 'done' as const })))
      await new Promise((resolve) => window.setTimeout(resolve, 350))
      reset()
      onCreated?.()
      onOpenChange(false)
    } catch (err) {
      setSteps((current) =>
        current.map((step, index) =>
          step.status === 'active' || (index === current.length - 1 && step.status !== 'done')
            ? { ...step, status: 'error', detail: err instanceof Error ? err.message : 'Failed' }
            : step,
        ),
      )
      setError(err instanceof Error ? err.message : 'Failed to create project')
    } finally {
      setBusy(false)
    }
  }

  return (
    <SettingsSheetFrame
      open={open}
      onClose={() => {
        onOpenChange(false)
        reset()
      }}
      title="Create project"
      sectionLabel="Project details"
      summary="Add a project channel to this workframe."
      titleId="wf-create-project-title"
      sheetClassName="wf-dialog-content--settings-compact"
      actions={
        <WizardFormActions>
          <DialogCancelButton onClick={() => onOpenChange(false)} disabled={busy}>
            Cancel
          </DialogCancelButton>
          <DialogConfirmButton onClick={() => void createProject()} disabled={busy || !workspaceId}>
            {busy ? 'Creating…' : 'Create project'}
          </DialogConfirmButton>
        </WizardFormActions>
      }
    >
      <div className="space-y-4" role="tabpanel">
        {error ? <WorkframeNotice message={error} /> : null}
        {busy ? <OperationProgress steps={steps} title="Creating project…" /> : null}

        <div className="wf-wizard-panel wf-onboarding-form">
          <DialogField label="Logo">
            <AvatarPickerGrid kind="logo" value={logoUrl} onChange={setLogoUrl} disabled={busy} />
          </DialogField>

          <DialogField label="Name" htmlFor="wf-create-project-name">
            <Input
              id="wf-create-project-name"
              className="wf-dialog-input"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Engineering"
              disabled={busy}
            />
          </DialogField>

          <DialogField label="Topic" htmlFor="wf-create-project-topic" hint="Optional short description.">
            <Input
              id="wf-create-project-topic"
              className="wf-dialog-input"
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
              placeholder="Ship logs, standups, releases…"
              disabled={busy}
            />
          </DialogField>
        </div>
      </div>
    </SettingsSheetFrame>
  )
}
