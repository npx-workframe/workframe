import { useEffect, useState } from 'react'

import { DialogFrame } from '@/components/dialogs/DialogFrame'
import { ScrollArea } from '@/components/ui/scroll-area'

type PersonalityDialogProps = { open: boolean; onOpenChange: (open: boolean) => void }

const PERSONALITIES = [
  { id: 'default', name: 'Default', description: 'Standard Workframe Agent personality' },
  { id: 'concise', name: 'Concise', description: 'Brief, to-the-point responses' },
  { id: 'detailed', name: 'Detailed', description: 'Thorough, comprehensive responses' },
  { id: 'friendly', name: 'Friendly', description: 'Warm, conversational tone' },
  { id: 'professional', name: 'Professional', description: 'Formal, business-appropriate tone' },
]

export function PersonalityDialog({ open, onOpenChange }: PersonalityDialogProps) {
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    if (!open) setSelected(null)
  }, [open])

  return (
    <DialogFrame open={open} onOpenChange={onOpenChange} title="Personality"
      description="Choose a personality for the active session" contentClassName="wf-dialog--personality"
    >
      <ScrollArea axis="vertical" className="wf-dialog__list">
        {PERSONALITIES.map((p) => (
          <button key={p.id} type="button" className="wf-dialog__option"
            data-selected={selected === p.id ? 'true' : undefined}
            onClick={() => setSelected(p.id)}
          >
            <span className="wf-dialog__option-label">{p.name}</span>
            <span className="wf-dialog__option-desc">{p.description}</span>
          </button>
        ))}
      </ScrollArea>
      {selected && (
        <p className="wf-dialog__hint">
          Selected: <strong>{PERSONALITIES.find(p => p.id === selected)?.name}</strong> — click to apply (coming in next slice)
        </p>
      )}
    </DialogFrame>
  )
}
