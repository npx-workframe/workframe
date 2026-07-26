import { DialogField } from '@/components/dialogs/DialogField'
import { Textarea } from '@/components/ui/textarea'

type AgentInstructionsFieldsProps = {
  id: string
  value: string
  onChange: (value: string) => void
  disabled?: boolean
  rows?: number
  placeholder?: string
  label?: string
  hint?: string
  systemSoul?: string
  workspaceSpiceNote?: boolean
}

export function AgentInstructionsFields({
  id,
  value,
  onChange,
  disabled,
  rows = 12,
  placeholder = 'Personality and operating instructions',
  label = 'Operating instructions',
  hint,
  systemSoul,
  workspaceSpiceNote = false,
}: AgentInstructionsFieldsProps) {
  const resolvedHint =
    hint ??
    (workspaceSpiceNote
      ? 'Your manager preferences. Workspace-wide agent spice lives in Workframe Settings.'
      : 'Editable layer — combined with the system prompt at runtime.')

  return (
    <div className="space-y-4">
      {systemSoul?.trim() ? (
        <details className="wf-user-settings__hint">
          <summary className="cursor-pointer font-medium">System prompt (read-only)</summary>
          <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-muted/40 p-3 font-mono text-xs">
            {systemSoul.trim()}
          </pre>
        </details>
      ) : null}
      <DialogField label={label} htmlFor={id} hint={resolvedHint}>
        <Textarea
          id={id}
          className="wf-dialog-input font-mono text-sm"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
          rows={rows}
          placeholder={placeholder}
        />
      </DialogField>
    </div>
  )
}
