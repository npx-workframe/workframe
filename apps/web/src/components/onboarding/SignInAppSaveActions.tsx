import { WfActionButton } from '@/components/ui/WfActionButton'

type SignInAppSaveActionsProps = {
  disabled?: boolean
  busy?: boolean
  saveDisabled?: boolean
  onCancel: () => void
  onSave: () => void
}

export function SignInAppSaveActions({
  disabled,
  busy,
  saveDisabled,
  onCancel,
  onSave,
}: SignInAppSaveActionsProps) {
  return (
    <div className="wf-provider-connect__editor-actions">
      <WfActionButton wizardSize disabled={disabled || busy} onClick={onCancel}>
        Cancel
      </WfActionButton>
      <WfActionButton
        wizardSize
        tone="primary"
        disabled={disabled || busy || saveDisabled}
        onClick={onSave}
      >
        {busy ? 'Saving…' : 'Save'}
      </WfActionButton>
    </div>
  )
}
