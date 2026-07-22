import { DialogCancelButton, DialogConfirmButton } from '@/components/dialogs/DialogActions'
import { DialogFrame } from '@/components/dialogs/DialogFrame'

type ConfirmDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  confirmVariant?: 'accent' | 'warn'
  onConfirm: () => void
  onCancel?: () => void
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  confirmVariant = 'accent',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const handleCancel = () => {
    onCancel?.()
    onOpenChange(false)
  }

  const handleConfirm = () => {
    onConfirm()
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
          <DialogCancelButton onClick={handleCancel}>{cancelLabel}</DialogCancelButton>
          <DialogConfirmButton
            className={confirmVariant === 'warn' ? 'wf-action-btn--warn' : undefined}
            onClick={handleConfirm}
          >
            {confirmLabel}
          </DialogConfirmButton>
        </>
      }
    />
  )
}
