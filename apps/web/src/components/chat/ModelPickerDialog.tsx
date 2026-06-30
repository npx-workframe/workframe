import { useEffect, useState } from 'react'

import { ModelPickerPanel } from '@/components/settings/ModelPickerPanel'
import { DialogCancelButton } from '@/components/dialogs/DialogActions'
import { SettingsSheetFrame } from '@/components/workspace/SettingsSheetFrame'
import { WorkframeNotice } from '@/components/ui/WorkframeNotice'
import { fetchHermesModels, type FallbackEntry, type HermesModelsResponse } from '@/lib/hermesCatalogApi'

type ModelPickerDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onChanged?: (model: string) => void
  profile?: string
  workspaceId?: string
  onConnectProvider?: () => void
}

export function ModelPickerDialog({
  open,
  onOpenChange,
  onChanged,
  profile,
  workspaceId,
  onConnectProvider,
}: ModelPickerDialogProps) {
  const [data, setData] = useState<HermesModelsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    setError(null)
    setLoading(true)
    fetchHermesModels(profile, workspaceId)
      .then((res) => {
        if (!res.ok) {
          setError('Could not load model surface')
          return
        }
        setData(res)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'load failed'))
      .finally(() => setLoading(false))
  }, [open, profile, workspaceId])

  const summary = data
    ? `${data.primary || '—'}${data.provider ? ` · ${data.provider}` : ''}`
    : undefined

  return (
    <SettingsSheetFrame
      open={open}
      onClose={() => onOpenChange(false)}
      title="LLM Models"
      summary={summary}
      titleId="wf-model-picker-title"
      sheetClassName="wf-dialog-content--settings-compact"
      loading={loading}
      actions={
        onConnectProvider ? (
          <DialogCancelButton
            onClick={() => {
              onOpenChange(false)
              onConnectProvider()
            }}
          >
            Connect provider
          </DialogCancelButton>
        ) : (
          <DialogCancelButton onClick={() => onOpenChange(false)}>Close</DialogCancelButton>
        )
      }
    >
      <div className="space-y-4" role="tabpanel">
        {error ? <WorkframeNotice message={error} /> : null}

        {!loading && data && !data.has_llm_provider ? (
          <div className="wf-wizard-panel wf-onboarding-form">
            <p className="text-sm text-muted-foreground">
              Connect an LLM provider under Settings → Connected Accounts.
            </p>
          </div>
        ) : (
          <div className="wf-wizard-panel wf-onboarding-form">
            <ModelPickerPanel
              profile={profile}
              workspaceId={workspaceId}
              embedded
              onError={setError}
              onChanged={(model) => {
                onChanged?.(model)
                onOpenChange(false)
              }}
            />
          </div>
        )}
      </div>
    </SettingsSheetFrame>
  )
}

export type { FallbackEntry }
