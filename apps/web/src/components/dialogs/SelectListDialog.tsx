import { useEffect, useState } from 'react'
import { Check } from 'lucide-react'

import { DialogCancelButton, DialogConfirmButton } from '@/components/dialogs/DialogActions'
import { DialogFrame } from '@/components/dialogs/DialogFrame'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

export type SelectListOption = {
  id: string
  label: string
  description?: string
}

type SelectListDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  options: SelectListOption[]
  defaultSelectedId?: string
  saveLabel?: string
  cancelLabel?: string
  onSave: (selectedId: string) => void
}

export function SelectListDialog({
  open,
  onOpenChange,
  title,
  description,
  options,
  defaultSelectedId,
  saveLabel = 'Save',
  cancelLabel = 'Cancel',
  onSave,
}: SelectListDialogProps) {
  const [selectedId, setSelectedId] = useState(defaultSelectedId ?? options[0]?.id ?? '')

  useEffect(() => {
    if (open) setSelectedId(defaultSelectedId ?? options[0]?.id ?? '')
  }, [open, defaultSelectedId, options])

  const handleSave = () => {
    if (!selectedId) return
    onSave(selectedId)
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
          <DialogConfirmButton onClick={handleSave} disabled={!selectedId}>
            {saveLabel}
          </DialogConfirmButton>
        </>
      }
    >
      <ScrollArea axis="vertical" className="wf-dialog-select-list">
        <ul role="listbox" aria-label={title} className="wf-dialog-select-list__items">
        {options.map((option) => {
          const isSelected = option.id === selectedId

          return (
            <li key={option.id} role="presentation">
              <button
                type="button"
                role="option"
                aria-selected={isSelected}
                className={cn('wf-dialog-select-list__option', isSelected && 'is-selected')}
                onClick={() => setSelectedId(option.id)}
              >
                <span className="wf-dialog-select-list__label">{option.label}</span>
                {option.description ? (
                  <span className="wf-dialog-select-list__hint">{option.description}</span>
                ) : null}
                {isSelected ? <Check className="wf-dialog-select-list__check" aria-hidden="true" /> : null}
              </button>
            </li>
          )
        })}
        </ul>
      </ScrollArea>
    </DialogFrame>
  )
}
