import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import { OAuthProviderRow } from '@/components/onboarding/OAuthProviderRow'
import { SignInBrandIcon } from '@/components/settings/SignInBrandIcon'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { SecretInput } from '@/components/ui/SecretInput'
import { WorkframeNotice } from '@/components/ui/WorkframeNotice'
import { formatWorkframeErrorMessage } from '@/lib/workframeErrors'
import { workframeAuthApi } from '@/lib/workframeAuthApi'

type AdminStripeSetupProps = {
  disabled?: boolean
  onBindSave?: (save: () => Promise<boolean>) => void
  /** Render only the list row (for embedding in AdminOAuthSetup). */
  inline?: boolean
}

function StripeField({
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

export function AdminStripeSetup({ disabled, onBindSave, inline }: AdminStripeSetupProps) {
  const [error, setError] = useState<string | null>(null)
  const [stripeOn, setStripeOn] = useState(false)
  const [clientId, setClientId] = useState('')
  const [platformSecret, setPlatformSecret] = useState('')
  const [hasSecret, setHasSecret] = useState(false)

  const appBase = useMemo(() => {
    const base = import.meta.env.VITE_APP_BASE_URL || window.location.origin
    return base.replace(/\/$/, '')
  }, [])

  const stripeCallback = `${appBase}/api/oauth/stripe/callback`

  useEffect(() => {
    void workframeAuthApi.getInstallStack().then((cfg) => {
      const st = cfg.stripe_connect
      if (st?.client_id) {
        setStripeOn(true)
        setClientId(st.client_id)
      }
      setHasSecret(Boolean(st?.has_secret))
    }).catch(() => {})
  }, [])

  const save = useCallback(async () => {
    setError(null)
    try {
      const payload: Record<string, unknown> = {}
      payload.stripe_connect = stripeOn && clientId.trim()
        ? {
            client_id: clientId.trim(),
            ...(platformSecret.trim() ? { client_secret: platformSecret.trim() } : {}),
          }
        : { client_id: '', client_secret: '' }
      await workframeAuthApi.patchInstallStack(payload)
      const cfg = await workframeAuthApi.getInstallStack()
      setHasSecret(Boolean(cfg.stripe_connect?.has_secret))
      setPlatformSecret('')
      return true
    } catch (err) {
      setError(formatWorkframeErrorMessage(err, 'Save Stripe Connect'))
      return false
    }
  }, [clientId, platformSecret, stripeOn])

  useEffect(() => {
    onBindSave?.(save)
  }, [onBindSave, save])

  const stripeRow = (
    <OAuthProviderRow
      label="Stripe Connect"
      description="Let members connect Stripe accounts for payments, billing, and agent commerce tools."
      icon={<SignInBrandIcon id="stripe" />}
      enabled={stripeOn}
      disabled={disabled}
      onToggle={setStripeOn}
    >
      <p className="wf-sign-in-app__link-row">
        <a
          className="text-primary underline"
          href="https://dashboard.stripe.com/settings/connect"
          target="_blank"
          rel="noreferrer"
        >
          Stripe Dashboard → Connect
        </a>
        {' — enable OAuth, add the redirect URI below, then copy your Connect client ID (ca_…) and platform secret key (sk_…).'}
      </p>
      <StripeField label="Redirect URI" hint="Add this exact URL under Connect → OAuth settings." fullWidth>
        <Input readOnly value={stripeCallback} />
      </StripeField>
      <div className="wf-sign-in-app__grid">
        <StripeField label="Connect client ID" hint="Starts with ca_">
          <Input
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            placeholder="ca_…"
            disabled={disabled}
            autoComplete="off"
          />
        </StripeField>
        <StripeField
          label="Platform secret key"
          hint="Your platform sk_test_… or sk_live_… key — leave blank to keep the saved key."
        >
          <SecretInput
            value={platformSecret}
            onChange={(e) => setPlatformSecret(e.target.value)}
            saved={hasSecret}
            emptyPlaceholder="sk_test_… or sk_live_…"
            disabled={disabled}
          />
        </StripeField>
      </div>
    </OAuthProviderRow>
  )

  if (inline) {
    return stripeRow
  }

  return (
    <div className="wf-sign-in-apps">
      {error ? <WorkframeNotice message={error} tone="caution" /> : null}
      <ul className="wf-sign-in-apps__list">{stripeRow}</ul>
    </div>
  )
}
