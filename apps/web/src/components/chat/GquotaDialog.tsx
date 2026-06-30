import { useEffect, useState } from 'react'

import { DialogFrame } from '@/components/dialogs/DialogFrame'
import { fetchHermesGquota, type HermesGquotaResponse } from '@/lib/hermesCatalogApi'

type GquotaDialogProps = { open: boolean; onOpenChange: (open: boolean) => void }

export function GquotaDialog({ open, onOpenChange }: GquotaDialogProps) {
  const [data, setData] = useState<HermesGquotaResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setError(null); setData(null)
    fetchHermesGquota().then(setData).catch((err) => setError(err instanceof Error ? err.message : 'load failed'))
  }, [open])

  return (
    <DialogFrame open={open} onOpenChange={onOpenChange} title="Google Quota"
      description={data ? `Profile: ${data.profile}` : 'Loading…'} contentClassName="wf-dialog--gquota"
    >
      {error && <p className="wf-dialog__error">{error}</p>}
      {data && !data.configured && <p className="wf-dialog__hint">{data.message}</p>}
      {data && data.configured && (
        <dl className="wf-dialog__status">
          <div className="wf-dialog__status-row"><dt>Profile</dt><dd>{data.profile}</dd></div>
        </dl>
      )}
    </DialogFrame>
  )
}
