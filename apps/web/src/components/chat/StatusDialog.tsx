import { useEffect, useState } from 'react'

import { DialogFrame } from '@/components/dialogs/DialogFrame'
import { useHermesSession } from '@/contexts/HermesSessionContext'
import { fetchWorkframeMeta, type WorkframeMeta } from '@/lib/workframeMetaApi'

type StatusDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

type Row = { label: string; value: string }

export function StatusDialog({ open, onOpenChange }: StatusDialogProps) {
  const { profile, agentDisplayName, sessionReady, messages, stateDbSessionId, gatewaySessionId } =
    useHermesSession()
  const [meta, setMeta] = useState<WorkframeMeta | null>(null)
  const [metaError, setMetaError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setMetaError(null)
    fetchWorkframeMeta()
      .then(setMeta)
      .catch((err) => setMetaError(err instanceof Error ? err.message : 'load failed'))
  }, [open])

  const rows: Row[] = [
    { label: 'Profile', value: profile || '—' },
    { label: 'Agent', value: agentDisplayName || '—' },
    { label: 'Session ready', value: sessionReady ? 'yes' : 'no' },
    {
      label: 'state.db session',
      value: stateDbSessionId ? stateDbSessionId.slice(0, 12) + '…' : '—',
    },
    {
      label: 'Gateway session',
      value: gatewaySessionId ? gatewaySessionId.slice(0, 16) + '…' : '—',
    },
    { label: 'Messages loaded', value: String(messages.length) },
    { label: 'Project', value: meta?.project_name ?? '—' },
    { label: 'Native profile', value: meta?.native_profile ?? '—' },
    { label: 'Native agent', value: meta?.native_agent_name ?? '—' },
    { label: 'Active model', value: meta?.native_model ?? '—' },
  ]

  return (
    <DialogFrame
      open={open}
      onOpenChange={onOpenChange}
      title="Session status"
      description="Live snapshot of the active session and profile."
      contentClassName="wf-dialog--status"
    >
      {metaError ? <p className="wf-dialog__error">{metaError}</p> : null}
      <dl className="wf-dialog__status">
        {rows.map((row) => (
          <div key={row.label} className="wf-dialog__status-row">
            <dt>{row.label}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>
    </DialogFrame>
  )
}
