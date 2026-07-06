import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import { OAuthProviderRow } from '@/components/onboarding/OAuthProviderRow'
import { SignInBrandIcon } from '@/components/settings/SignInBrandIcon'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { SecretInput } from '@/components/ui/SecretInput'
import { WorkframeNotice } from '@/components/ui/WorkframeNotice'
import { formatWorkframeErrorMessage } from '@/lib/workframeErrors'
import { workframeAuthApi } from '@/lib/workframeAuthApi'

type AdminOAuthSetupProps = {
  disabled?: boolean
  onBindSave?: (save: () => Promise<boolean>) => void
  afterGithub?: ReactNode
}

function OAuthField({
  label,
  hint,
  children,
  fullWidth,
}: {
  label: string
  hint?: string
  children: ReactNode
  fullWidth?: boolean
}) {
  return (
    <div className={`wf-sign-in-app__field${fullWidth ? ' wf-sign-in-app__field--full' : ''}`}>
      <Label>{label}</Label>
      {children}
      {hint ? <p className="wf-sign-in-app__hint">{hint}</p> : null}
    </div>
  )
}

export function AdminOAuthSetup({ disabled, onBindSave, afterGithub }: AdminOAuthSetupProps) {
  const [error, setError] = useState<string | null>(null)
  const [googleOn, setGoogleOn] = useState(false)
  const [githubOn, setGithubOn] = useState(false)
  const [discordOn, setDiscordOn] = useState(false)
  const [telegramOn, setTelegramOn] = useState(false)
  const [googleClientId, setGoogleClientId] = useState('')
  const [googleClientSecret, setGoogleClientSecret] = useState('')
  const [githubClientId, setGithubClientId] = useState('')
  const [githubClientSecret, setGithubClientSecret] = useState('')
  const [discordClientId, setDiscordClientId] = useState('')
  const [discordClientSecret, setDiscordClientSecret] = useState('')
  const [telegramBotUsername, setTelegramBotUsername] = useState('')
  const [telegramBotToken, setTelegramBotToken] = useState('')
  const [telegramDomain, setTelegramDomain] = useState('')
  const [googleHasSecret, setGoogleHasSecret] = useState(false)
  const [githubHasSecret, setGithubHasSecret] = useState(false)
  const [discordHasSecret, setDiscordHasSecret] = useState(false)
  const [telegramHasToken, setTelegramHasToken] = useState(false)

  const appBase = useMemo(() => {
    const base = import.meta.env.VITE_APP_BASE_URL || window.location.origin
    return base.replace(/\/$/, '')
  }, [])

  const googleCallback = `${appBase}/api/auth/google/callback`
  const githubCallback = `${appBase}/api/oauth/github/callback`
  const discordCallback = `${appBase}/api/oauth/discord/callback`

  useEffect(() => {
    void workframeAuthApi.getInstallStack().then((cfg) => {
      const go = cfg.google_oauth
      const gh = cfg.github_oauth
      const dc = cfg.discord_oauth
      const tg = cfg.telegram_login
      if (go?.client_id) {
        setGoogleOn(true)
        setGoogleClientId(go.client_id)
      }
      setGoogleHasSecret(Boolean(go?.has_secret))
      if (gh?.client_id) {
        setGithubOn(true)
        setGithubClientId(gh.client_id)
      }
      setGithubHasSecret(Boolean(gh?.has_secret))
      if (dc?.client_id) {
        setDiscordOn(true)
        setDiscordClientId(dc.client_id)
      }
      setDiscordHasSecret(Boolean(dc?.has_secret))
      if (tg?.bot_username) {
        setTelegramOn(true)
        setTelegramBotUsername(tg.bot_username)
      }
      setTelegramHasToken(Boolean(tg?.has_token))
      if (tg?.domain) setTelegramDomain(tg.domain)
      else {
        try {
          setTelegramDomain(new URL(appBase).hostname)
        } catch {
          setTelegramDomain('')
        }
      }
    }).catch(() => {})
  }, [appBase])

  const save = useCallback(async () => {
    setError(null)
    try {
      const payload: Record<string, unknown> = {}
      payload.google_oauth = googleOn && googleClientId.trim()
        ? {
            client_id: googleClientId.trim(),
            ...(googleClientSecret.trim() ? { client_secret: googleClientSecret.trim() } : {}),
          }
        : { client_id: '', client_secret: '' }
      payload.github_oauth = githubOn && githubClientId.trim()
        ? {
            client_id: githubClientId.trim(),
            ...(githubClientSecret.trim() ? { client_secret: githubClientSecret.trim() } : {}),
          }
        : { client_id: '', client_secret: '' }
      payload.discord_oauth = discordOn && discordClientId.trim()
        ? {
            client_id: discordClientId.trim(),
            ...(discordClientSecret.trim() ? { client_secret: discordClientSecret.trim() } : {}),
          }
        : { client_id: '', client_secret: '' }
      payload.telegram_login = telegramOn && telegramBotUsername.trim()
        ? {
            bot_username: telegramBotUsername.trim().replace(/^@/, ''),
            ...(telegramBotToken.trim() ? { bot_token: telegramBotToken.trim() } : {}),
          }
        : { bot_username: '', bot_token: '' }
      await workframeAuthApi.patchInstallStack(payload)
      const cfg = await workframeAuthApi.getInstallStack()
      setGoogleHasSecret(Boolean(cfg.google_oauth?.has_secret))
      setGithubHasSecret(Boolean(cfg.github_oauth?.has_secret))
      setDiscordHasSecret(Boolean(cfg.discord_oauth?.has_secret))
      setTelegramHasToken(Boolean(cfg.telegram_login?.has_token))
      setGoogleClientSecret('')
      setGithubClientSecret('')
      setDiscordClientSecret('')
      setTelegramBotToken('')
      return true
    } catch (err) {
      setError(formatWorkframeErrorMessage(err, 'Save sign-in apps'))
      return false
    }
  }, [
    discordClientId,
    discordClientSecret,
    discordOn,
    githubClientId,
    githubClientSecret,
    githubOn,
    googleClientId,
    googleClientSecret,
    googleOn,
    telegramBotToken,
    telegramBotUsername,
    telegramOn,
  ])

  useEffect(() => {
    onBindSave?.(save)
  }, [onBindSave, save])

  return (
    <div className="wf-sign-in-apps">
      {error ? <WorkframeNotice message={error} tone="caution" /> : null}
      <ul className="wf-sign-in-apps__list">
        <OAuthProviderRow
          label="Google"
          description="Member sign-in and Google-backed features."
          icon={<SignInBrandIcon id="google" />}
          enabled={googleOn}
          disabled={disabled}
          onToggle={setGoogleOn}
        >
          <OAuthField label="Redirect URI" hint="Add this exact URL in Google Cloud Console → OAuth client." fullWidth>
            <Input readOnly value={googleCallback} />
          </OAuthField>
          <div className="wf-sign-in-app__grid">
            <OAuthField label="Client ID">
              <Input
                value={googleClientId}
                onChange={(e) => setGoogleClientId(e.target.value)}
                placeholder="….apps.googleusercontent.com"
                disabled={disabled}
                autoComplete="off"
              />
            </OAuthField>
            <OAuthField label="Client secret" hint="Leave blank to keep the saved secret.">
              <SecretInput
                value={googleClientSecret}
                onChange={(e) => setGoogleClientSecret(e.target.value)}
                saved={googleHasSecret}
                emptyPlaceholder="Paste client secret"
                disabled={disabled}
              />
            </OAuthField>
          </div>
        </OAuthProviderRow>

        <OAuthProviderRow
          label="GitHub"
          description="Let members connect GitHub — use a Workframe OAuth app, not personal access tokens."
          icon={<SignInBrandIcon id="github" />}
          enabled={githubOn}
          disabled={disabled}
          onToggle={setGithubOn}
        >
          <p className="wf-sign-in-app__link-row">
            <a className="text-primary underline" href="https://github.com/settings/developers" target="_blank" rel="noreferrer">
              GitHub Developer Settings
            </a>
            {' — register an OAuth app with the URLs below.'}
          </p>
          <div className="wf-sign-in-app__grid">
            <OAuthField label="Homepage URL">
              <Input readOnly value={appBase} />
            </OAuthField>
            <OAuthField label="Callback URL">
              <Input readOnly value={githubCallback} />
            </OAuthField>
          </div>
          <div className="wf-sign-in-app__grid">
            <OAuthField label="Client ID">
              <Input
                value={githubClientId}
                onChange={(e) => setGithubClientId(e.target.value)}
                placeholder="Ov23li…"
                disabled={disabled}
                autoComplete="off"
              />
            </OAuthField>
            <OAuthField label="Client secret" hint="Leave blank to keep the saved secret.">
              <SecretInput
                value={githubClientSecret}
                onChange={(e) => setGithubClientSecret(e.target.value)}
                saved={githubHasSecret}
                emptyPlaceholder="Paste client secret"
                disabled={disabled}
              />
            </OAuthField>
          </div>
        </OAuthProviderRow>

        {afterGithub}

        <OAuthProviderRow
          label="Discord"
          description="Link member Discord accounts — OAuth identify scope, not bot tokens."
          icon={<SignInBrandIcon id="discord" />}
          enabled={discordOn}
          disabled={disabled}
          onToggle={setDiscordOn}
        >
          <p className="wf-sign-in-app__link-row">
            <a className="text-primary underline" href="https://discord.com/developers/applications" target="_blank" rel="noreferrer">
              Discord Developer Portal
            </a>
            {' — OAuth2 app with redirect below.'}
          </p>
          <OAuthField label="Redirect URI" fullWidth>
            <Input readOnly value={discordCallback} />
          </OAuthField>
          <div className="wf-sign-in-app__grid">
            <OAuthField label="Client ID">
              <Input
                value={discordClientId}
                onChange={(e) => setDiscordClientId(e.target.value)}
                placeholder="Application client ID"
                disabled={disabled}
                autoComplete="off"
              />
            </OAuthField>
            <OAuthField label="Client secret" hint="Leave blank to keep the saved secret.">
              <SecretInput
                value={discordClientSecret}
                onChange={(e) => setDiscordClientSecret(e.target.value)}
                saved={discordHasSecret}
                emptyPlaceholder="Paste client secret"
                disabled={disabled}
              />
            </OAuthField>
          </div>
        </OAuthProviderRow>

        <OAuthProviderRow
          label="Telegram"
          description="Login with Telegram — one BotFather bot for this Workframe URL."
          icon={<SignInBrandIcon id="telegram" />}
          enabled={telegramOn}
          disabled={disabled}
          onToggle={setTelegramOn}
        >
          <p className="wf-sign-in-app__link-row">
            <a className="text-primary underline" href="https://t.me/BotFather" target="_blank" rel="noreferrer">
              @BotFather
            </a>
            {` — create a bot, then /setdomain `}
            <strong>{telegramDomain || 'your-domain'}</strong>
            {` for this install.`}
          </p>
          <OAuthField label="Domain (set in BotFather)" fullWidth>
            <Input readOnly value={telegramDomain || appBase} />
          </OAuthField>
          <div className="wf-sign-in-app__grid">
            <OAuthField label="Bot username">
              <Input
                value={telegramBotUsername}
                onChange={(e) => setTelegramBotUsername(e.target.value)}
                placeholder="MyWorkframeBot"
                disabled={disabled}
                autoComplete="off"
              />
            </OAuthField>
            <OAuthField label="Bot token" hint="Leave blank to keep the saved token.">
              <SecretInput
                value={telegramBotToken}
                onChange={(e) => setTelegramBotToken(e.target.value)}
                saved={telegramHasToken}
                emptyPlaceholder="Paste bot token"
                disabled={disabled}
              />
            </OAuthField>
          </div>
        </OAuthProviderRow>
      </ul>
    </div>
  )
}
