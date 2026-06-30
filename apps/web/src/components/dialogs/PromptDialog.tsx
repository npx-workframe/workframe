import { useEffect, useId, useState } from 'react'

import { DialogCancelButton, DialogConfirmButton } from '@/components/dialogs/DialogActions'
import { DialogFrame } from '@/components/dialogs/DialogFrame'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

type PromptDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  label?: string
  placeholder?: string
  defaultValue?: string
  inputType?: 'text' | 'password'
  confirmLabel?: string
  cancelLabel?: string
  onSave: (value: string) => void
}

export function PromptDialog({
  open,
  onOpenChange,
  title,
  description,
  label = 'Value',
  placeholder,
  defaultValue = '',
  inputType = 'text',
  confirmLabel = 'Save',
  cancelLabel = 'Cancel',
  onSave,
}: PromptDialogProps) {
  const fieldId = useId()
  const [value, setValue] = useState(defaultValue)

  useEffect(() => {
    if (open) setValue(defaultValue)
  }, [open, defaultValue])

  const handleSave = () => {
    onSave(value)
    onOpenChange(false)
  }

  return (
    <DialogFrame
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      description={description}
      footer={
        <>
          <DialogCancelButton onClick={() => onOpenChange(false)}>{cancelLabel}</DialogCancelButton>
          <DialogConfirmButton onClick={handleSave}>{confirmLabel}</DialogConfirmButton>
        </>
      }
    >
      <div className="wf-dialog-field">
        <Label htmlFor={fieldId}>{label}</Label>
        <Input
          id={fieldId}
          type={inputType}
          value={value}
          placeholder={placeholder}
          autoComplete={inputType === 'password' ? 'off' : undefined}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              handleSave()
            }
          }}
        />
      </div>
    </DialogFrame>
  )
}
