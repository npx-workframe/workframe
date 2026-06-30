import { useEffect, useState } from 'react'

import { DialogCancelButton, DialogConfirmButton } from '@/components/dialogs/DialogActions'
import { Checkbox } from '@/components/ui/checkbox'
import { DialogFrame } from '@/components/dialogs/DialogFrame'
import { Label } from '@/components/ui/label'

export type CheckboxListOption = {
  id: string
  label: string
  description?: string
}

type CheckboxListDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  options: CheckboxListOption[]
  defaultSelectedIds?: string[]
  saveLabel?: string
  cancelLabel?: string
  onSave: (selectedIds: string[]) => void
}

export function CheckboxListDialog({
  open,
  onOpenChange,
  title,
  description,
  options,
  defaultSelectedIds = [],
  saveLabel = 'Save',
  cancelLabel = 'Cancel',
  onSave,
}: CheckboxListDialogProps) {
  const [selected, setSelected] = useState<Set<string>>(() => new Set(defaultSelectedIds))

  useEffect(() => {
    if (open) setSelected(new Set(defaultSelectedIds))
  }, [open, defaultSelectedIds])

  const toggle = (id: string, checked: boolean) => {
    setSelected((current) => {
      const next = new Set(current)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

  const handleSave = () => {
    onSave([...selected])
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
          <DialogConfirmButton onClick={handleSave}>{saveLabel}</DialogConfirmButton>
        </>
      }
    >
      <ul className="wf-dialog-checklist" role="group" aria-label={title}>
        {options.map((option) => {
          const checked = selected.has(option.id)
          const inputId = `wf-dialog-check-${option.id}`

          return (
            <li key={option.id} className="wf-dialog-checklist__item">
              <Checkbox
                id={inputId}
                checked={checked}
                onCheckedChange={(next) => toggle(option.id, next === true)}
              />
              <div className="wf-dialog-checklist__copy">
                <Label htmlFor={inputId}>{option.label}</Label>
                {option.description ? (
                  <p className="wf-dialog-checklist__hint">{option.description}</p>
                ) : null}
              </div>
            </li>
          )
        })}
      </ul>
    </DialogFrame>
  )
}
