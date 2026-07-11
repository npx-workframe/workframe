import { useCallback, useEffect, useRef } from 'react'

import { AdminOAuthSetup } from '@/components/onboarding/AdminOAuthSetup'
import { AdminStripeSetup } from '@/components/onboarding/AdminStripeSetup'
import { WorkspaceMessagingPanel } from '@/components/onboarding/WorkspaceMessagingPanel'
import { SettingsSection } from '@/components/settings/SettingsSection'
import { SmtpSettingsFields } from '@/components/settings/SmtpSettingsFields'

type IntegrationsStackProps = {
  variant: 'onboarding' | 'settings'
  disabled?: boolean
  workspaceId?: string
  onBindOAuthSave?: (save: () => Promise<boolean>) => void
  onBindStripeSave?: (save: () => Promise<boolean>) => void
  onBindSmtpSave?: (save: () => Promise<boolean>) => void
  onBindMessagingSave?: (save: () => Promise<boolean>) => void
  onError?: (message: string) => void
}

export function IntegrationsStack({
  variant,
  disabled,
  workspaceId,
  onBindOAuthSave,
  onBindStripeSave,
  onBindSmtpSave,
  onBindMessagingSave,
  onError,
}: IntegrationsStackProps) {
  const stripeSaveRef = useRef<(() => Promise<boolean>) | null>(null)
  const oauthSaveRef = useRef<(() => Promise<boolean>) | null>(null)

  const bindOnboardingComposite = useCallback(() => {
    onBindOAuthSave?.(async () => {
      if (stripeSaveRef.current) {
        const stripeOk = await stripeSaveRef.current()
        if (!stripeOk) return false
      }
      if (oauthSaveRef.current) {
        return oauthSaveRef.current()
      }
      return true
    })
  }, [onBindOAuthSave])

  useEffect(() => {
    if (variant !== 'onboarding') return
    bindOnboardingComposite()
  }, [bindOnboardingComposite, variant])

  if (variant === 'onboarding') {
    return (
      <section className="wf-sign-in-apps-section">
        <header className="wf-sign-in-apps-section__header">
          <h2 className="wf-wizard-section__title">Sign-in</h2>
          <p className="wf-wizard-section__hint">
            OAuth apps for member sign-in — Google, GitHub, Discord, Telegram, and Stripe Connect.
          </p>
        </header>
        <AdminOAuthSetup
          disabled={disabled}
          afterGithub={
            <AdminStripeSetup
              inline
              disabled={disabled}
              onBindSave={(save) => {
                stripeSaveRef.current = save
                bindOnboardingComposite()
              }}
            />
          }
          onBindSave={(save) => {
            oauthSaveRef.current = save
            bindOnboardingComposite()
          }}
        />
      </section>
    )
  }

  return (
    <>
      <SettingsSection
        title="Email delivery"
        hint="SMTP for invites, sign-in codes, and notifications. Password is vault-encrypted on the stack."
      >
        <SmtpSettingsFields disabled={disabled} onBindSave={onBindSmtpSave} onError={onError} />
      </SettingsSection>

      <SettingsSection
        title="Payments partner"
        hint="Stripe Connect OAuth — members connect their own Stripe accounts for billing and commerce tools."
      >
        <AdminStripeSetup disabled={disabled} onBindSave={onBindStripeSave} />
      </SettingsSection>

      <SettingsSection
        title="Sign-in apps"
        hint="OAuth apps for member sign-in — Google, GitHub, Discord, and Telegram Login."
      >
        <AdminOAuthSetup disabled={disabled} onBindSave={onBindOAuthSave} />
      </SettingsSection>

      {workspaceId ? (
        <SettingsSection
          title="Agent messaging"
          hint="Shared bot tokens and home channels for Discord and Telegram — separate from member sign-in OAuth."
        >
          <WorkspaceMessagingPanel
            workspaceId={workspaceId}
            disabled={disabled}
            onBindSave={onBindMessagingSave}
            onError={onError}
          />
        </SettingsSection>
      ) : null}
    </>
  )
}
