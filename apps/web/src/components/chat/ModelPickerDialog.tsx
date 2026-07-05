import { useState } from 'react'

import { ModelPickerPanel } from '@/components/settings/ModelPickerPanel'
import { DialogCancelButton } from '@/components/dialogs/DialogActions'
import { SettingsSheetFrame } from '@/components/workspace/SettingsSheetFrame'
import { WorkframeNotice } from '@/components/ui/WorkframeNotice'
import { billingProviderDisplayLabel } from '@/lib/brandAssets'
import { modelLabelFromId } from '@/lib/chatTypes'
import type { FallbackEntry, HermesModelsResponse } from '@/lib/hermesCatalogApi'

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
  const [summary, setSummary] = useState<string>()
  const [error, setError] = useState<string | null>(null)

  const handleLoaded = (data: HermesModelsResponse) => {
    const provider = billingProviderDisplayLabel(data.billing_provider || data.provider || '')
    const model = modelLabelFromId(data.primary || '')
    setSummary(provider && model ? `${provider} · ${model}` : model || provider || undefined)
  }

  return (
    <SettingsSheetFrame
      open={open}
      onClose={() => onOpenChange(false)}
      title="LLM Models"
      summary={summary}
      titleId="wf-model-picker-title"
      sheetClassName="wf-dialog-content--settings-compact"
      contentFill
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
      <div className="wf-settings-fill-stack space-y-4" role="tabpanel">
        {error ? <WorkframeNotice message={error} /> : null}

        <ModelPickerPanel
          profile={profile}
          workspaceId={workspaceId}
          embedded
          onError={setError}
          onLoaded={handleLoaded}
          onChanged={(model) => {
            onChanged?.(model)
            onOpenChange(false)
          }}
        />
      </div>
    </SettingsSheetFrame>
  )
}

export type { FallbackEntry }
