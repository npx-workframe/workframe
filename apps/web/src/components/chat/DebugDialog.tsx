import { useEffect, useState } from 'react'

import { DialogFrame } from '@/components/dialogs/DialogFrame'
import { fetchHermesDebug, type HermesDebugResponse } from '@/lib/hermesCatalogApi'

type DebugDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function DebugDialog({ open, onOpenChange }: DebugDialogProps) {
  const [data, setData] = useState<HermesDebugResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setError(null)
    setData(null)
    fetchHermesDebug()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : 'load failed'))
  }, [open])

  return (
    <DialogFrame
      open={open}
      onOpenChange={onOpenChange}
      title="Debug"
      description={data ? `Profile: ${data.profile}` : 'Loading…'}
      contentClassName="wf-dialog--debug"
    >
      {error && <p className="wf-dialog__error">{error}</p>}
      {data && (
        <dl className="wf-dialog__status">
          <div className="wf-dialog__status-row"><dt>Profile</dt><dd>{data.profile}</dd></div>
          <div className="wf-dialog__status-row"><dt>Python</dt><dd>{data.python_version.split('\n')[0]}</dd></div>
          <div className="wf-dialog__status-row"><dt>Platform</dt><dd>{data.platform}</dd></div>
          <div className="wf-dialog__status-row"><dt>Sessions</dt><dd>{data.session_count}</dd></div>
          <div className="wf-dialog__status-row"><dt>Messages</dt><dd>{data.message_count}</dd></div>
        </dl>
      )}
    </DialogFrame>
  )
}
