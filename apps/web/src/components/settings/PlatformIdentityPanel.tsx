import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'

import { SignInBrandIcon } from '@/components/settings/SignInBrandIcon'
import { Button } from '@/components/ui/button'
import { WorkframeNotice } from '@/components/ui/WorkframeNotice'
import { formatWorkframeErrorMessage } from '@/lib/workframeErrors'
import { workframeAuthApi } from '@/lib/workframeAuthApi'

type PlatformIdentityPanelProps = {
  workspaceId?: string
  disabled?: boolean
  onLinked?: () => void
  /** Hide section chrome when embedded in a tabbed settings shell. */
  embedded?: boolean
}

type PlatformId = 'discord' | 'telegram'

const PLATFORM_META: Record<
  PlatformId,
  { label: string; blurb: string }
> = {
  discord: {
    label: 'Discord',
    blurb: 'OAuth account for messaging identity and bot allowlists.',
  },
  telegram: {
    label: 'Telegram',
    blurb: 'Login widget for messaging identity and bot allowlists.',
  },
}

declare global {
  interface Window {
    onTelegramAuth?: (user: Record<string, string | number>) => void
  }
}

function platformState(configured: boolean, linkedId: string): { text: string; linked: boolean } {
  if (linkedId) return { text: 'Linked', linked: true }
  if (!configured) return { text: 'Admin setup', linked: false }
  return { text: 'Not linked', linked: false }
}

function platformDetail(configured: boolean, linkedId: string, embedded: boolean): string {
  if (linkedId) return `ID ${linkedId}`
  if (!configured) {
    return embedded ? 'Ask admin to enable.' : 'Not enabled on this workframe yet. Ask your admin to turn it on under Workframe → Integrations.'
  }
  return embedded ? 'Not linked' : 'Connect below to link your personal account.'
}

export function PlatformIdentityPanel({
  workspaceId,
  disabled,
  onLinked,
  embedded = false,
}: PlatformIdentityPanelProps) {
  const telegramMountRef = useRef<HTMLDivElement | null>(null)
  const [platformIds, setPlatformIds] = useState<Record<string, string>>({})
  const [telegramBot, setTelegramBot] = useState('')
  const [telegramEnabled, setTelegramEnabled] = useState(false)
  const [discordEnabled, setDiscordEnabled] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)

  const reload = useCallback(async () => {
    try {
      const [me, stack] = await Promise.all([
        workframeAuthApi.getMe(),
        workframeAuthApi.getInstallStack(),
      ])
      const ids = me.user.platform_ids ?? {}
      setPlatformIds(ids)
      setDiscordEnabled(Boolean(stack.discord_oauth?.enabled))
      setTelegramEnabled(Boolean(stack.telegram_login?.enabled))
      setTelegramBot(stack.telegram_login?.bot_username ?? '')
    } catch {
      // best-effort
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  const connectDiscord = async () => {
    setBusy(true)
    setError(null)
    setStatus(null)
    try {
      const result = await workframeAuthApi.startProviderOAuth('discord', workspaceId)
      if (result.redirect_url) {
        window.location.assign(result.redirect_url)
        return
      }
      if (!result.ok) {
        setError(result.message || result.error || 'Could not start Discord connect')
        return
      }
      setStatus('Discord connect started — finish in the opened window.')
      await reload()
      onLinked?.()
    } catch (err) {
      setError(formatWorkframeErrorMessage(err, 'Connect Discord'))
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (!telegramEnabled || !telegramBot || !telegramMountRef.current) return

    window.onTelegramAuth = (user) => {
      void (async () => {
        setBusy(true)
        setError(null)
        try {
          const result = await workframeAuthApi.linkTelegram(user)
          if (!result.ok) {
            setError(result.error || 'Telegram link failed')
            return
          }
          if (result.platform_ids) setPlatformIds(result.platform_ids)
          setStatus('Telegram account linked.')
          onLinked?.()
          await reload()
        } catch (err) {
          setError(formatWorkframeErrorMessage(err, 'Link Telegram'))
        } finally {
          setBusy(false)
        }
      })()
    }

    const node = telegramMountRef.current
    node.innerHTML = ''
    const script = document.createElement('script')
    script.async = true
    script.src = 'https://telegram.org/js/telegram-widget.js?22'
    script.setAttribute('data-telegram-login', telegramBot.replace(/^@/, ''))
    script.setAttribute('data-size', 'medium')
    script.setAttribute('data-onauth', 'onTelegramAuth(user)')
    script.setAttribute('data-request-access', 'write')
    node.appendChild(script)

    return () => {
      node.innerHTML = ''
      delete window.onTelegramAuth
    }
  }, [onLinked, reload, telegramBot, telegramEnabled])

  const discordId = platformIds.discord?.trim() ?? ''
  const telegramId = platformIds.telegram?.trim() ?? ''

  const rows: Array<{
    id: PlatformId
    linkedId: string
    configured: boolean
    action?: ReactNode
  }> = [
    {
      id: 'discord',
      linkedId: discordId,
      configured: discordEnabled,
      action:
        discordEnabled && !discordId ? (
          <Button type="button" size="sm" disabled={disabled || busy} onClick={() => void connectDiscord()}>
            Connect with Discord
          </Button>
        ) : null,
    },
    {
      id: 'telegram',
      linkedId: telegramId,
      configured: telegramEnabled,
      action:
        telegramEnabled && !telegramId ? (
          <div ref={telegramMountRef} className="wf-platform-identity__telegram" />
        ) : null,
    },
  ]

  return (
    <section className={`wf-platform-identity${embedded ? ' wf-platform-identity--embedded' : ''}`}>
      {!embedded ? (
        <>
          <h2 className="wf-wizard-section__title">Messaging identity</h2>
          <p className="wf-wizard-section__hint">
            Personal Discord and Telegram accounts — merged into bot allowlists, not workspace bot tokens.
          </p>
        </>
      ) : null}

      {error ? <WorkframeNotice message={error} tone="caution" /> : null}
      {status ? <p className="wf-user-settings__hint">{status}</p> : null}

      <ul className="wf-sign-in-apps__list">
        {rows.map(({ id, linkedId, configured, action }) => {
          const meta = PLATFORM_META[id]
          const state = platformState(configured, linkedId)
          return (
            <li key={id} className={`wf-sign-in-app wf-platform-link${state.linked ? ' is-on' : ''}`}>
              <div className="wf-sign-in-app__head">
                <div className="wf-sign-in-app__icon" aria-hidden="true">
                  <SignInBrandIcon id={id} />
                </div>
                <div className="wf-sign-in-app__copy">
                  <div className="wf-sign-in-app__title-row">
                    <strong>{meta.label}</strong>
                    <span className={`wf-sign-in-app__state${state.linked ? ' is-on' : ''}`}>{state.text}</span>
                  </div>
                  <p className="wf-sign-in-app__desc">{platformDetail(configured, linkedId, embedded) || meta.blurb}</p>
                </div>
              </div>
              {action ? <div className="wf-sign-in-app__body">{action}</div> : null}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
