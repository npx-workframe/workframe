import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

type UserPlatformIdsFieldsProps = {
  discordId: string
  telegramId: string
  disabled?: boolean
  onDiscordChange: (value: string) => void
  onTelegramChange: (value: string) => void
}

export function UserPlatformIdsFields({
  discordId,
  telegramId,
  disabled,
  onDiscordChange,
  onTelegramChange,
}: UserPlatformIdsFieldsProps) {
  return (
    <section className="wf-wizard-section">
      <h2 className="wf-wizard-section__title">Messaging identity</h2>
      <p className="wf-wizard-section__hint">
        Your platform user IDs — merged into the workframe bot allowlist when you save. Not bot tokens.
      </p>
      <div className="wf-onboarding-form__row wf-onboarding-form__row--2col">
        <div className="wf-dialog-field">
          <Label htmlFor="wf-user-discord-id">Discord user ID</Label>
          <Input
            id="wf-user-discord-id"
            value={discordId}
            onChange={(e) => onDiscordChange(e.target.value)}
            placeholder="123456789012345678"
            disabled={disabled}
          />
        </div>
        <div className="wf-dialog-field">
          <Label htmlFor="wf-user-telegram-id">Telegram user ID</Label>
          <Input
            id="wf-user-telegram-id"
            value={telegramId}
            onChange={(e) => onTelegramChange(e.target.value)}
            placeholder="123456789"
            disabled={disabled}
          />
        </div>
      </div>
    </section>
  )
}
