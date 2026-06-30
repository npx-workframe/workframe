import { useEffect, useState } from 'react'

import { DialogFrame } from '@/components/dialogs/DialogFrame'
import { fetchHermesProfile, type HermesProfileResponse } from '@/lib/hermesCatalogApi'

type ProfileDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function ProfileDialog({ open, onOpenChange }: ProfileDialogProps) {
  const [data, setData] = useState<HermesProfileResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setError(null)
    setData(null)
    fetchHermesProfile()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : 'load failed'))
  }, [open])

  return (
    <DialogFrame
      open={open}
      onOpenChange={onOpenChange}
      title="Profile"
      description={data ? `Active: ${data.profile}` : 'Loading…'}
      contentClassName="wf-dialog--profile"
    >
      {error && <p className="wf-dialog__error">{error}</p>}
      {data && (
        <div className="wf-dialog__profile">
          <p className="wf-dialog__profile-name">{data.profile}</p>
          {data.description && <p className="wf-dialog__profile-desc">{data.description}</p>}
          <p className="wf-dialog__profile-state">
            Gateway: {data.gateway_running ? 'running' : 'stopped'}
          </p>
          {data.session && (
            <dl className="wf-dialog__status">
              <div className="wf-dialog__status-row">
                <dt>Session</dt>
                <dd>{data.session.title || data.session.id}</dd>
              </div>
              <div className="wf-dialog__status-row">
                <dt>Messages</dt>
                <dd>{data.session.message_count}</dd>
              </div>
            </dl>
          )}
        </div>
      )}
    </DialogFrame>
  )
}
