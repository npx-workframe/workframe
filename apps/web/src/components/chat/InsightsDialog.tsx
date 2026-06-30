import { useEffect, useState } from 'react'

import { DialogFrame } from '@/components/dialogs/DialogFrame'
import { fetchHermesInsights, type HermesInsightsResponse } from '@/lib/hermesCatalogApi'

type InsightsDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function InsightsDialog({ open, onOpenChange }: InsightsDialogProps) {
  const [data, setData] = useState<HermesInsightsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setError(null)
    setData(null)
    fetchHermesInsights()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : 'load failed'))
  }, [open])

  return (
    <DialogFrame
      open={open}
      onOpenChange={onOpenChange}
      title="Insights"
      description={data ? `Profile: ${data.profile} · last 7 days` : 'Loading…'}
      contentClassName="wf-dialog--insights"
    >
      {error && <p className="wf-dialog__error">{error}</p>}
      {data && (
        <>
          {data.daily.length > 0 && (
            <>
              <p className="wf-dialog__section-label">Daily usage</p>
              <table className="wf-dialog__table">
                <thead><tr><th>Day</th><th>Sessions</th><th>Input</th><th>Output</th></tr></thead>
                <tbody>
                  {data.daily.map((d) => (
                    <tr key={d.day}>
                      <td>{d.day}</td>
                      <td>{d.sessions}</td>
                      <td>{d.input_tokens.toLocaleString()}</td>
                      <td>{d.output_tokens.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          {data.models.length > 0 && (
            <>
              <p className="wf-dialog__section-label">Models</p>
              <table className="wf-dialog__table">
                <thead><tr><th>Model</th><th>Sessions</th><th>Input tokens</th></tr></thead>
                <tbody>
                  {data.models.map((m) => (
                    <tr key={m.model}>
                      <td>{m.model}</td>
                      <td>{m.sessions}</td>
                      <td>{m.input_tokens.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </>
      )}
    </DialogFrame>
  )
}
