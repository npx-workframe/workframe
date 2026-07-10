import { Plus } from 'lucide-react'

import { AvatarPickerGrid } from '@/components/onboarding/AvatarPickerGrid'
import { useAvatarFileUpload } from '@/components/onboarding/useAvatarFileUpload'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import type { PresetKind } from '@/lib/presetAssets'
import { cn } from '@/lib/utils'

type FieldConfig = {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
}

type OnboardingIdentityFieldsProps = {
  avatarKind: PresetKind
  avatarUrl: string
  onAvatarChange: (url: string) => void
  avatarLabel?: string
  primary: FieldConfig
  secondary: FieldConfig
  body?: FieldConfig & { rows?: number; placeholder?: string }
  disabled?: boolean
}

export function OnboardingIdentityFields({
  avatarKind,
  avatarUrl,
  onAvatarChange,
  avatarLabel = 'Avatar',
  primary,
  secondary,
  body,
  disabled,
}: OnboardingIdentityFieldsProps) {
  const { openFilePicker, fileInput } = useAvatarFileUpload(onAvatarChange)
  const hasCustomUpload = avatarUrl.startsWith('data:')

  return (
    <TooltipProvider delayDuration={400}>
      <div className="wf-onboarding-identity">
        {fileInput}
        <div className="wf-onboarding-identity__row">
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className={cn(
                  'wf-onboarding-identity__preview-btn wf-avatar-grid__item',
                  !avatarUrl && 'wf-avatar-grid__item--upload',
                  hasCustomUpload && 'wf-avatar-grid__item--active',
                )}
                disabled={disabled}
                onClick={openFilePicker}
                aria-label="Upload image"
              >
                {avatarUrl ? <img src={avatarUrl} alt="" /> : null}
                <span className="wf-onboarding-identity__preview-overlay" aria-hidden="true">
                  <Plus />
                </span>
              </button>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="wf-tooltip-nudge-x-30">
              Upload image
            </TooltipContent>
          </Tooltip>
          <div className="wf-onboarding-identity__fields">
            <div className="wf-dialog-field">
              <Label htmlFor={primary.id}>{primary.label}</Label>
              <Input
                id={primary.id}
                value={primary.value}
                onChange={(e) => primary.onChange(e.target.value)}
                disabled={disabled}
              />
            </div>
            <div className="wf-dialog-field">
              <Label htmlFor={secondary.id}>{secondary.label}</Label>
              <Input
                id={secondary.id}
                value={secondary.value}
                onChange={(e) => secondary.onChange(e.target.value)}
                disabled={disabled}
              />
            </div>
          </div>
        </div>

        <div className="wf-dialog-field">
          <Label>{avatarLabel}</Label>
          <AvatarPickerGrid
            kind={avatarKind}
            value={avatarUrl}
            onChange={onAvatarChange}
            disabled={disabled}
            onUploadClick={openFilePicker}
            withTooltipProvider={false}
          />
        </div>

        {body ? (
          <div className="wf-dialog-field">
            <Label htmlFor={body.id}>{body.label}</Label>
            <Textarea
              id={body.id}
              value={body.value}
              onChange={(e) => body.onChange(e.target.value)}
              rows={body.rows ?? 4}
              placeholder={body.placeholder}
              disabled={disabled}
            />
          </div>
        ) : null}
      </div>
    </TooltipProvider>
  )
}
