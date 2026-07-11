import { DialogField } from '@/components/dialogs/DialogField'
import { Textarea } from '@/components/ui/textarea'

type AgentInstructionsFieldsProps = {
  id: string
  value: string
  onChange: (value: string) => void
  disabled?: boolean
  rows?: number
  placeholder?: string
}

export function AgentInstructionsFields({
  id,
  value,
  onChange,
  disabled,
  rows = 12,
  placeholder = 'Personality and operating instructions',
}: AgentInstructionsFieldsProps) {
  return (
    <DialogField
      label="Operating instructions"
      htmlFor={id}
      hint="Layered on the system prompt — does not replace Workframe rules."
    >
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
  )
}
