import { useEffect, useState } from 'react'

import { DialogFrame } from '@/components/dialogs/DialogFrame'
import {
  fetchHermesUsage,
  type HermesUsageResponse,
} from '@/lib/hermesCatalogApi'

type UsageDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

type Row = { label: string; value: string }

export function UsageDialog({ open, onOpenChange }: UsageDialogProps) {
  const [data, setData] = useState<HermesUsageResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setError(null)
    setData(null)
    fetchHermesUsage()
      .then((res) => {
        if (!res.ok) {
          setError(res.error ?? 'Could not load usage')
          return
        }
        setData(res)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'load failed'))
  }, [open])

  const rows: Row[] = []
  if (data?.session) {
    const s = data.session
    rows.push({ label: 'Session', value: s.title || s.id })
    rows.push({ label: 'Session id', value: s.id })
    rows.push({ label: 'Model', value: s.model })
    rows.push({ label: 'Messages', value: String(s.message_count) })
    rows.push({ label: 'Tool calls', value: String(s.tool_call_count) })
    rows.push({ label: 'Input tokens', value: s.input_tokens.toLocaleString() })
    rows.push({ label: 'Output tokens', value: s.output_tokens.toLocaleString() })
    rows.push({ label: 'Total tokens', value: s.total_tokens.toLocaleString() })
    rows.push({ label: 'Started', value: s.started_at ?? '—' })
    rows.push({ label: 'Ended', value: s.ended_at ?? 'still active' })
  }

  return (
    <DialogFrame
      open={open}
      onOpenChange={onOpenChange}
      title="Token usage"
      description={
        data
          ? `Profile: ${data.profile}${data.session ? '' : ' · no session found'}`
          : 'Loading usage…'
      }
      contentClassName="wf-dialog--usage"
    >
      {error ? <p className="wf-dialog__error">{error}</p> : null}
      {!data && !error ? <p className="wf-dialog__hint">Loading…</p> : null}
      {data && !data.session ? (
        <p className="wf-dialog__hint">No session found for this profile.</p>
      ) : null}
      {rows.length > 0 ? (
        <dl className="wf-dialog__status">
          {rows.map((row) => (
            <div key={row.label} className="wf-dialog__status-row">
              <dt>{row.label}</dt>
              <dd>{row.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </DialogFrame>
  )
}
