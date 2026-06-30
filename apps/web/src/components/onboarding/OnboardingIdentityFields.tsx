import { AvatarPickerGrid } from '@/components/onboarding/AvatarPickerGrid'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import type { PresetKind } from '@/lib/presetAssets'

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
  return (
    <div className="wf-onboarding-identity">
      <div className="wf-onboarding-identity__row">
        <div className="wf-onboarding-identity__preview" aria-hidden="true">
          {avatarUrl ? <img src={avatarUrl} alt="" /> : null}
        </div>
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
  )
}
