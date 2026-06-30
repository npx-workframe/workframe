import { DialogFrame } from '@/components/dialogs/DialogFrame'

type PanelSettingsOverlayProps = {
  panelLabel: string
  hint?: string
  open: boolean
  onClose: () => void
}

export function PanelSettingsOverlay({
  panelLabel,
  hint,
  open,
  onClose,
}: PanelSettingsOverlayProps) {
  return (
    <DialogFrame
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose()
      }}
      title={`${panelLabel} settings`}
      description={hint ?? 'Panel settings will appear here in a later slice.'}
    />
  )
}
