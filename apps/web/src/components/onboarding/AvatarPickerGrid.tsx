import { useMemo } from 'react'
import { Plus } from 'lucide-react'

import { useAvatarFileUpload } from '@/components/onboarding/useAvatarFileUpload'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { listPresets, presetIdFromSrc, type PresetKind } from '@/lib/presetAssets'
import { cn } from '@/lib/utils'

type AvatarPickerGridProps = {
  kind: PresetKind
  value: string
  onChange: (url: string) => void
  disabled?: boolean
  onUploadClick?: () => void
  withTooltipProvider?: boolean
}

function presetMatchesValue(kind: PresetKind, value: string, itemSrc: string, itemId: string): boolean {
  const raw = String(value || '').trim()
  if (!raw) return false
  if (raw === itemSrc) return true
  const valueId = presetIdFromSrc(kind, raw)
  return Boolean(valueId && valueId === itemId)
}

function AvatarPickerGridBody({
  kind,
  value,
  onChange,
  disabled,
  onUploadClick,
}: Omit<AvatarPickerGridProps, 'withTooltipProvider'>) {
  const presets = useMemo(() => listPresets(kind), [kind])

  const ariaLabel =
    kind === 'logo' ? 'Choose logo' : kind === 'agent' ? 'Choose agent avatar' : 'Choose avatar'

  return (
    <div className="wf-avatar-grid" role="listbox" aria-label={ariaLabel}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className={cn(
              'wf-avatar-grid__item wf-avatar-grid__item--upload',
              value.startsWith('data:') && 'wf-avatar-grid__item--active',
            )}
            disabled={disabled}
            onClick={onUploadClick}
          >
            <Plus aria-hidden />
          </button>
        </TooltipTrigger>
        <TooltipContent side="bottom">Upload image</TooltipContent>
      </Tooltip>
      {presets.map((item) => {
        const selected = presetMatchesValue(kind, value, item.src, item.id)
        return (
          <Tooltip key={item.id}>
            <TooltipTrigger asChild>
              <button
                type="button"
                role="option"
                aria-selected={selected}
                disabled={disabled}
                className={cn('wf-avatar-grid__item', selected && 'wf-avatar-grid__item--active')}
                onClick={() => onChange(item.src)}
              >
                <img src={item.src} alt="" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="bottom">{item.label}</TooltipContent>
          </Tooltip>
        )
      })}
    </div>
  )
}

export function AvatarPickerGrid({
  withTooltipProvider = true,
  onUploadClick,
  onChange,
  ...props
}: AvatarPickerGridProps) {
  const internalUpload = useAvatarFileUpload(onChange)
  const openUpload = onUploadClick ?? internalUpload.openFilePicker

  const grid = (
    <ScrollArea axis="horizontal" className="wf-avatar-picker-scroll wf-scroll--horizontal">
      <AvatarPickerGridBody {...props} onChange={onChange} onUploadClick={openUpload} />
      {!onUploadClick ? internalUpload.fileInput : null}
    </ScrollArea>
  )

  if (!withTooltipProvider) return grid

  return <TooltipProvider delayDuration={400}>{grid}</TooltipProvider>
}
