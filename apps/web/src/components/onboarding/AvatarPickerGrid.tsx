import { useMemo, useRef } from 'react'
import { Plus } from 'lucide-react'

import { readFileAsDataUrl } from '@/components/workspace/profileBadge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { listPresets, presetIdFromSrc, type PresetKind } from '@/lib/presetAssets'
import { validateAvatarFile } from '@/lib/workframeErrors'
import { cn } from '@/lib/utils'

type AvatarPickerGridProps = {
  kind: PresetKind
  value: string
  onChange: (url: string) => void
  disabled?: boolean
}

function presetMatchesValue(kind: PresetKind, value: string, itemSrc: string, itemId: string): boolean {
  const raw = String(value || '').trim()
  if (!raw) return false
  if (raw === itemSrc) return true
  const valueId = presetIdFromSrc(kind, raw)
  return Boolean(valueId && valueId === itemId)
}

export function AvatarPickerGrid({ kind, value, onChange, disabled }: AvatarPickerGridProps) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const presets = useMemo(() => listPresets(kind), [kind])

  async function onUpload(file: File | null) {
    if (!file) return
    const invalid = validateAvatarFile(file)
    if (invalid) return
    const dataUrl = await readFileAsDataUrl(file)
    onChange(dataUrl)
  }

  const ariaLabel =
    kind === 'logo' ? 'Choose logo' : kind === 'agent' ? 'Choose agent avatar' : 'Choose avatar'

  return (
    <ScrollArea axis="horizontal" className="wf-avatar-picker-scroll wf-scroll--horizontal">
      <div className="wf-avatar-grid" role="listbox" aria-label={ariaLabel}>
        <button
          type="button"
          className={cn(
            'wf-avatar-grid__item wf-avatar-grid__item--upload',
            value.startsWith('data:') && 'wf-avatar-grid__item--active',
          )}
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
          title="Upload image"
        >
          <Plus aria-hidden />
        </button>
        {presets.map((item) => {
          const selected = presetMatchesValue(kind, value, item.src, item.id)
          return (
            <button
              key={item.id}
              type="button"
              role="option"
              aria-selected={selected}
              disabled={disabled}
              className={cn('wf-avatar-grid__item', selected && 'wf-avatar-grid__item--active')}
              onClick={() => onChange(item.src)}
              title={item.label}
            >
              <img src={item.src} alt="" />
            </button>
          )
        })}
        <input
          ref={inputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          className="sr-only"
          onChange={(e) => void onUpload(e.target.files?.[0] ?? null)}
        />
      </div>
    </ScrollArea>
  )
}
