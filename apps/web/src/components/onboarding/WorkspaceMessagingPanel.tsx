import { useCallback, useEffect, useState } from 'react'

import { SecretInput } from '@/components/ui/SecretInput'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { workframeAuthApi } from '@/lib/workframeAuthApi'

type MessagingBlock = {
  home_channel: string
  allowed_users: string
  bot_token_configured: boolean
}

type WorkspaceMessagingPanelProps = {
  workspaceId: string
  disabled?: boolean
  onBindSave?: (save: () => Promise<boolean>) => void
  onError?: (message: string) => void
}

const EMPTY_BLOCK: MessagingBlock = {
  home_channel: '',
  allowed_users: '',
  bot_token_configured: false,
}

export function WorkspaceMessagingPanel({
  workspaceId,
  disabled,
  onBindSave,
  onError,
}: WorkspaceMessagingPanelProps) {
  const [discord, setDiscord] = useState<MessagingBlock>(EMPTY_BLOCK)
  const [telegram, setTelegram] = useState<MessagingBlock>(EMPTY_BLOCK)
  const [discordToken, setDiscordToken] = useState('')
  const [telegramToken, setTelegramToken] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await workframeAuthApi.getWorkspace(workspaceId)
      const messaging = result.workspace?.integrations?.messaging
      const d = messaging?.discord
      const t = messaging?.telegram
      setDiscord({
        home_channel: d?.home_channel ?? '',
        allowed_users: d?.allowed_users ?? '',
        bot_token_configured: Boolean(d?.bot_token_configured),
      })
      setTelegram({
        home_channel: t?.home_channel ?? '',
        allowed_users: t?.allowed_users ?? '',
        bot_token_configured: Boolean(t?.bot_token_configured),
      })
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Failed to load messaging settings')
    } finally {
      setLoading(false)
    }
  }, [onError, workspaceId])

  useEffect(() => {
    void load()
  }, [load])

  const saveAll = useCallback(async (): Promise<boolean> => {
    onError?.('')
    try {
      if (discordToken.trim()) {
        const saved = await workframeAuthApi.storeWorkspaceCredential(workspaceId, {
          provider: 'discord',
          api_key: discordToken.trim(),
          label: 'Discord',
        })
        if (!saved.ok) {
          onError?.(saved.error ?? 'Failed to save Discord bot token')
          return false
        }
        setDiscordToken('')
      }
      if (telegramToken.trim()) {
        const saved = await workframeAuthApi.storeWorkspaceCredential(workspaceId, {
          provider: 'telegram',
          api_key: telegramToken.trim(),
          label: 'Telegram',
        })
        if (!saved.ok) {
          onError?.(saved.error ?? 'Failed to save Telegram bot token')
          return false
        }
        setTelegramToken('')
      }
      await workframeAuthApi.patchWorkspaceIntegrations(workspaceId, {
        messaging: {
          discord: {
            home_channel: discord.home_channel.trim(),
            allowed_users: discord.allowed_users.trim(),
          },
          telegram: {
            home_channel: telegram.home_channel.trim(),
            allowed_users: telegram.allowed_users.trim(),
          },
        },
      })
      await load()
      return true
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Failed to save messaging settings')
      return false
    }
  }, [discord, load, onError, discordToken, telegram, telegramToken, workspaceId])

  useEffect(() => {
    onBindSave?.(saveAll)
  }, [onBindSave, saveAll])

  if (loading) {
    return <p className="wf-user-settings__hint">Loading messaging channels…</p>
  }

  return (
    <div className="wf-onboarding-form">
      <section className="wf-wizard-section">
        <h2 className="wf-wizard-section__title">Discord</h2>
        <p className="wf-wizard-section__hint">
          Shared bot for the workframe — token is vault-encrypted and synced to the gateway.
        </p>
        <div className="wf-dialog-field">
          <Label htmlFor="wf-discord-token">Bot token</Label>
          <SecretInput
            id="wf-discord-token"
            value={discordToken}
            onChange={(e) => setDiscordToken(e.target.value)}
            saved={discord.bot_token_configured}
            emptyPlaceholder="Paste bot token"
            disabled={disabled}
          />
        </div>
        <div className="wf-onboarding-form__row wf-onboarding-form__row--2col">
          <div className="wf-dialog-field">
            <Label htmlFor="wf-discord-home">Home channel ID</Label>
            <Input
              id="wf-discord-home"
              value={discord.home_channel}
              onChange={(e) => setDiscord((c) => ({ ...c, home_channel: e.target.value }))}
              placeholder="123456789012345678"
              disabled={disabled}
            />
          </div>
          <div className="wf-dialog-field">
            <Label htmlFor="wf-discord-allow">Seed allowlist (optional)</Label>
            <Input
              id="wf-discord-allow"
              value={discord.allowed_users}
              onChange={(e) => setDiscord((c) => ({ ...c, allowed_users: e.target.value }))}
              placeholder="user ids, comma-separated"
              disabled={disabled}
            />
          </div>
        </div>
      </section>

      <section className="wf-wizard-section">
        <h2 className="wf-wizard-section__title">Telegram</h2>
        <p className="wf-wizard-section__hint">
          Shared bot for the workframe — members link their Telegram user ID on the profile step.
        </p>
        <div className="wf-dialog-field">
          <Label htmlFor="wf-telegram-token">Bot token</Label>
          <SecretInput
            id="wf-telegram-token"
            value={telegramToken}
            onChange={(e) => setTelegramToken(e.target.value)}
            saved={telegram.bot_token_configured}
            emptyPlaceholder="Paste bot token"
            disabled={disabled}
          />
        </div>
        <div className="wf-onboarding-form__row wf-onboarding-form__row--2col">
          <div className="wf-dialog-field">
            <Label htmlFor="wf-telegram-home">Home chat ID</Label>
            <Input
              id="wf-telegram-home"
              value={telegram.home_channel}
              onChange={(e) => setTelegram((c) => ({ ...c, home_channel: e.target.value }))}
              placeholder="-1001234567890"
              disabled={disabled}
            />
          </div>
          <div className="wf-dialog-field">
            <Label htmlFor="wf-telegram-allow">Seed allowlist (optional)</Label>
            <Input
              id="wf-telegram-allow"
              value={telegram.allowed_users}
              onChange={(e) => setTelegram((c) => ({ ...c, allowed_users: e.target.value }))}
              placeholder="user ids, comma-separated"
              disabled={disabled}
            />
          </div>
        </div>
      </section>
    </div>
  )
}
