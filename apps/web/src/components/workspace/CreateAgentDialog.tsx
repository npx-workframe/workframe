import { useEffect, useMemo, useState } from 'react'

import { OnboardingIdentityFields } from '@/components/onboarding/OnboardingIdentityFields'
import { DialogCancelButton, DialogConfirmButton } from '@/components/dialogs/DialogActions'
import { DialogField } from '@/components/dialogs/DialogField'
import { ModelPickerPanel } from '@/components/settings/ModelPickerPanel'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { OperationProgress, type OperationStep } from '@/components/ui/OperationProgress'
import { WorkframeNotice } from '@/components/ui/WorkframeNotice'
import { SettingsSheetFrame } from '@/components/workspace/SettingsSheetFrame'
import { WizardFormActions } from '@/components/workspace/WizardFormActions'
import { setHermesFallbackChain, type FallbackEntry } from '@/lib/hermesCatalogApi'
import { agentAvatarPersistPayload, pickRandomPreset } from '@/lib/presetAssets'
import { workframeAuthApi, type WorkspaceRoom } from '@/lib/workframeAuthApi'
import { cn } from '@/lib/utils'

const STEP_LABELS: Record<string, string> = {
  hermes_profile_create: 'Create Hermes profile',
  strip_forbidden_skills: 'Install native toolset',
  install_child_base: 'Write agent identity',
  configure_api: 'Configure gateway API',
  patch_run_script: 'Patch gateway run script',
  gateway_start: 'Start gateway',
  dm_room: 'Open agent chat',
  bootstrap_dm_lane: 'Open agent chat',
  room_chat_bind: 'Bind chat session',
  seed_user_soul: 'Save instructions',
  register_route: 'Register in Workframe',
  assign_avatar: 'Assign avatar',
}

const PROGRESS_STEPS = [
  { id: 'hermes_profile_create', label: STEP_LABELS.hermes_profile_create },
  { id: 'strip_forbidden_skills', label: STEP_LABELS.strip_forbidden_skills },
  { id: 'configure_api', label: STEP_LABELS.configure_api },
  { id: 'dm_room', label: STEP_LABELS.dm_room },
]

type DialogTab = 'identity' | 'instructions' | 'model'

type CreateAgentDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated?: (result: {
    profile: string
    room_id?: string
    room?: WorkspaceRoom
  }) => void
}

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64)
}

export function CreateAgentDialog({ open, onOpenChange, onCreated }: CreateAgentDialogProps) {
  const [tab, setTab] = useState<DialogTab>('identity')
  const [profileSlug, setProfileSlug] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [role, setRole] = useState('')
  const [tagline, setTagline] = useState('')
  const [soul, setSoul] = useState('')
  const [model, setModel] = useState('')
  const [fallbackDraft, setFallbackDraft] = useState<FallbackEntry[]>([])
  const [avatarUrl, setAvatarUrl] = useState(() => pickRandomPreset('agent'))
  const [workspaceId, setWorkspaceId] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [steps, setSteps] = useState<OperationStep[]>([])

  const resolvedSlug = useMemo(() => slugify(profileSlug), [profileSlug])

  useEffect(() => {
    if (!open) return
    let cancelled = false
    workframeAuthApi
      .getMe()
      .then((profile) => {
        if (!cancelled) {
          setWorkspaceId(profile?.current_workspace?.id ?? profile?.default_workspace?.id)
        }
      })
      .catch(() => {
        if (!cancelled) setWorkspaceId(undefined)
      })
    return () => {
      cancelled = true
    }
  }, [open])

  const reset = () => {
    setTab('identity')
    setProfileSlug('')
    setDisplayName('')
    setRole('')
    setTagline('')
    setSoul('')
    setModel('')
    setFallbackDraft([])
    setAvatarUrl(pickRandomPreset('agent'))
    setError('')
    setSteps([])
  }

  const applyApiSteps = (apiSteps: Array<{ step?: string; ok?: boolean; error?: string }> | undefined) => {
    const rows = apiSteps ?? []
    if (!rows.length) return
    const byId = new Map(rows.map((row) => [String(row.step || ''), row]))
    const order = rows.map((row) => String(row.step || '')).filter(Boolean)
    const extras = PROGRESS_STEPS.map((entry) => entry.id).filter((id) => !order.includes(id))
    const ids = [...order, ...extras.filter((id) => byId.has(id))]

    setSteps(
      (ids.length ? ids : PROGRESS_STEPS.map((entry) => entry.id)).map((id) => {
        const row = byId.get(id)
        const label = STEP_LABELS[id] ?? id.replace(/_/g, ' ')
        if (!row) return { id, label, status: 'pending' as const }
        if (row.ok === false) {
          return { id, label, status: 'error' as const, detail: String(row.error || 'Failed') }
        }
        return { id, label, status: 'done' as const }
      }),
    )
  }

  const finishCreated = async (result: {
    profile: string
    room_id?: string
    room?: WorkspaceRoom
  }) => {
    let room = result.room
    if (result.room_id && (avatarUrl || displayName.trim() || tagline.trim())) {
      try {
        const patched = await workframeAuthApi.patchRoom(result.room_id, {
          ...(avatarUrl ? { avatar_url: avatarUrl } : {}),
          ...(displayName.trim() ? { name: displayName.trim() } : {}),
          ...(tagline.trim() ? { topic: tagline.trim() } : {}),
        })
        room = patched.room
      } catch {
        // ponytail: room identity patch is best-effort after bootstrap
      }
    }
    await new Promise((resolve) => window.setTimeout(resolve, 400))
    onCreated?.({ ...result, room })
    onOpenChange(false)
    reset()
  }

  const createAgent = async () => {
    if (!resolvedSlug) {
      setError('Profile slug is required')
      setTab('identity')
      return
    }
    if (!workspaceId) {
      setError('Workframe not loaded — close this dialog and try again.')
      return
    }
    setBusy(true)
    setError('')
    setSteps(PROGRESS_STEPS.map((step, index) => ({ ...step, status: index === 0 ? 'active' : 'pending' })))
    try {
      const avatar = avatarUrl ? agentAvatarPersistPayload(avatarUrl) : null
      const result = await workframeAuthApi.createHermesProfile({
        name: resolvedSlug,
        description: role.trim() || undefined,
        display_name: displayName.trim() || undefined,
        role: role.trim() || undefined,
        tagline: tagline.trim() || undefined,
        soul: soul.trim() || undefined,
        model: model.trim() || undefined,
        workspace_id: workspaceId,
        ...(avatar ?? {}),
      })
      applyApiSteps(result.steps as Array<{ step?: string; ok?: boolean; error?: string }> | undefined)
      const profileSlug = result.runtime_profile || result.profile
      if (fallbackDraft.length && profileSlug) {
        try {
          await setHermesFallbackChain(
            fallbackDraft.map((entry) => ({ provider: entry.provider, model: entry.model })),
            profileSlug,
          )
        } catch {
          // ponytail: fallback chain is best-effort right after create
        }
      }
      await finishCreated({
        profile: profileSlug,
        room_id: result.room_id,
        room: result.room,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create agent')
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
      title="Create agent"
      summary={resolvedSlug ? `Profile slug: ${resolvedSlug}` : 'New Hermes specialist'}
      titleId="wf-create-agent-title"
      sheetClassName="wf-dialog-content--settings-compact"
      contentFill={tab === 'model'}
      tabs={[
        { id: 'identity', label: 'Identity & Bio' },
        { id: 'instructions', label: 'Instructions' },
        { id: 'model', label: 'LLM models' },
      ]}
      activeTab={tab}
      onTabChange={(next) => setTab(next as DialogTab)}
      actions={
        <WizardFormActions>
          <DialogCancelButton onClick={() => onOpenChange(false)} disabled={busy}>
            Cancel
          </DialogCancelButton>
          <DialogConfirmButton onClick={() => void createAgent()} disabled={busy || !resolvedSlug}>
            {busy ? 'Creating…' : 'Create agent'}
          </DialogConfirmButton>
        </WizardFormActions>
      }
    >
      <div
        className={cn('space-y-4', tab === 'model' && 'wf-settings-fill-stack')}
        role="tabpanel"
      >
        {error ? <WorkframeNotice message={error} /> : null}
        {busy ? <OperationProgress steps={steps} title="Creating agent…" /> : null}

        {tab === 'identity' ? (
          <div className="wf-wizard-panel wf-onboarding-form">
            <DialogField
              label="Profile slug"
              htmlFor="wf-create-agent-slug"
              hint={
                resolvedSlug ? (
                  <>
                    Will create <code className="wf-dialog__code">{resolvedSlug}</code>
                  </>
                ) : (
                  'Lowercase id for the Hermes profile folder.'
                )
              }
            >
              <Input
                id="wf-create-agent-slug"
                className="wf-dialog-input"
                value={profileSlug}
                onChange={(event) => setProfileSlug(event.target.value)}
                placeholder="my-specialist"
                disabled={busy}
              />
            </DialogField>

            <DialogField label="Role" htmlFor="wf-create-agent-role" hint="What this agent specializes in.">
              <Input
                id="wf-create-agent-role"
                className="wf-dialog-input"
                value={role}
                onChange={(event) => setRole(event.target.value)}
                placeholder="Implementation, research, docs…"
                disabled={busy}
              />
            </DialogField>

            <OnboardingIdentityFields
              avatarKind="agent"
              avatarUrl={avatarUrl}
              onAvatarChange={setAvatarUrl}
              disabled={busy}
              primary={{
                id: 'wf-create-agent-display-name',
                label: 'Display name',
                value: displayName,
                onChange: setDisplayName,
              }}
              secondary={{
                id: 'wf-create-agent-tagline',
                label: 'Tagline',
                value: tagline,
                onChange: setTagline,
              }}
            />
          </div>
        ) : tab === 'instructions' ? (
          <div className="wf-wizard-panel wf-onboarding-form">
            <DialogField
              label="Operating instructions"
              htmlFor="wf-create-agent-soul"
              hint="Layered on the system prompt — does not replace Workframe rules."
            >
              <Textarea
                id="wf-create-agent-soul"
                className="wf-dialog-input font-mono text-sm"
                value={soul}
                onChange={(event) => setSoul(event.target.value)}
                rows={12}
                placeholder="Personality and operating instructions"
                disabled={busy}
              />
            </DialogField>
          </div>
        ) : (
          <ModelPickerPanel
            workspaceId={workspaceId}
            embedded
            selectionOnly
            value={model}
            onChanged={setModel}
            onFallbacksDraftChange={setFallbackDraft}
            onError={setError}
          />
        )}
      </div>
    </SettingsSheetFrame>
  )
}
