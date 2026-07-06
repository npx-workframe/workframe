import { useState } from 'react'

import { DialogCancelButton, DialogConfirmButton } from '@/components/dialogs/DialogActions'
import { DialogField } from '@/components/dialogs/DialogField'
import { DialogSelect } from '@/components/dialogs/DialogSelect'
import { Input } from '@/components/ui/input'
import { WorkframeNotice, WorkframeStatusNotice } from '@/components/ui/WorkframeNotice'
import { SettingsSheetFrame } from '@/components/workspace/SettingsSheetFrame'
import { WizardFormActions } from '@/components/workspace/WizardFormActions'
import { workframeAuthApi } from '@/lib/workframeAuthApi'

type InviteMemberDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  workspaceId: string
  workspaceName: string
  onInvited?: () => void
}

export function InviteMemberDialog({
  open,
  onOpenChange,
  workspaceId,
  workspaceName,
  onInvited,
}: InviteMemberDialogProps) {
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<'member' | 'viewer' | 'editor' | 'admin'>('member')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')

  const reset = () => {
    setEmail('')
    setRole('member')
    setError('')
    setStatus('')
  }

  const sendInvite = async () => {
    if (!email.trim()) {
      setError('Email is required')
      return
    }
    setBusy(true)
    setError('')
    setStatus('Creating invite…')
    try {
      const result = await workframeAuthApi.createWorkspaceInvite(workspaceId, {
        email: email.trim(),
        role,
      })
      setStatus(`Invite created for ${result.email}.`)
      setEmail('')
      onInvited?.()
    } catch (err) {
      setStatus('')
      setError(err instanceof Error ? err.message : 'Failed to create invite')
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
      title="Invite teammate"
      sectionLabel="Invite details"
      summary={`Invite to ${workspaceName}`}
      titleId="wf-invite-member-title"
      sheetClassName="wf-dialog-content--settings-compact"
      actions={
        <WizardFormActions>
          <DialogCancelButton onClick={() => onOpenChange(false)} disabled={busy}>
            Close
          </DialogCancelButton>
          <DialogConfirmButton onClick={() => void sendInvite()} disabled={busy || !workspaceId}>
            {busy ? 'Sending…' : 'Send invite'}
          </DialogConfirmButton>
        </WizardFormActions>
      }
    >
      <div className="space-y-4" role="tabpanel">
        {error ? <WorkframeNotice message={error} /> : null}
        {status ? <WorkframeStatusNotice message={status} /> : null}

        <div className="wf-wizard-panel wf-onboarding-form">
          <DialogField label="Email" htmlFor="wf-invite-email" hint="They sign in with a verification code and accept the invite.">
            <Input
              id="wf-invite-email"
              className="wf-dialog-input"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="teammate@example.com"
              autoComplete="email"
              disabled={busy}
            />
          </DialogField>

          <DialogField label="Role" htmlFor="wf-invite-role">
            <DialogSelect
              id="wf-invite-role"
              value={role}
              onValueChange={(next) => setRole(next as typeof role)}
              disabled={busy}
              options={[
                { value: 'member', label: 'Member' },
                { value: 'viewer', label: 'Viewer' },
                { value: 'editor', label: 'Editor' },
                { value: 'admin', label: 'Admin' },
              ]}
            />
          </DialogField>
        </div>
      </div>
    </SettingsSheetFrame>
  )
}
