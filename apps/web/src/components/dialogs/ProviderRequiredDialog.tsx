import { DialogCancelButton } from '@/components/dialogs/DialogActions'
import { SettingsSheetFrame } from '@/components/workspace/SettingsSheetFrame'
import { WizardFormActions } from '@/components/workspace/WizardFormActions'
import { ProviderConnectPanel } from '@/components/workspace/ProviderConnectPanel'

type ProviderRequiredDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  workspaceId?: string
  errorMessage?: string | null
  onConnected?: () => void
}

export function ProviderRequiredDialog({
  open,
  onOpenChange,
  workspaceId,
  errorMessage,
  onConnected,
}: ProviderRequiredDialogProps) {
  return (
    <SettingsSheetFrame
      open={open}
      onClose={() => onOpenChange(false)}
      title="Connect provider"
      sectionLabel="Provider keys"
      summary={errorMessage?.trim() || 'Connect an LLM provider to start chatting.'}
      titleId="wf-provider-required-title"
      sheetClassName="wf-dialog-content--settings-compact"
      actions={
        <WizardFormActions>
          <DialogCancelButton onClick={() => onOpenChange(false)}>Close</DialogCancelButton>
        </WizardFormActions>
      }
    >
      <div className="wf-wizard-panel wf-onboarding-form">
        <ProviderConnectPanel
          workspaceId={workspaceId}
          categories={['llm']}
          hint="none"
          layout="stack"
          onConnected={onConnected}
        />
      </div>
    </SettingsSheetFrame>
  )
}
