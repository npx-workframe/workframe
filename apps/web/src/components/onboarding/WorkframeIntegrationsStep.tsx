import { useCallback, useEffect, useRef } from 'react'

import { AdminOAuthSetup } from '@/components/onboarding/AdminOAuthSetup'
import { AdminStripeSetup } from '@/components/onboarding/AdminStripeSetup'

type WorkframeIntegrationsStepProps = {
  disabled?: boolean
  onBindOAuthSave?: (save: () => Promise<boolean>) => void
  onError?: (message: string) => void
}

export function WorkframeIntegrationsStep({
  disabled,
  onBindOAuthSave,
}: WorkframeIntegrationsStepProps) {
  const stripeSaveRef = useRef<(() => Promise<boolean>) | null>(null)
  const oauthSaveRef = useRef<(() => Promise<boolean>) | null>(null)

  const bindCompositeSave = useCallback(() => {
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
    bindCompositeSave()
  }, [bindCompositeSave])

  return (
    <div className="wf-wizard-panel wf-onboarding-form">
      <section className="wf-sign-in-apps-section">
        <header className="wf-sign-in-apps-section__header">
          <h2 className="wf-wizard-section__title">Sign-in</h2>
          <p className="wf-wizard-section__hint">OAuth apps for member sign-in — Google, GitHub, Discord, Telegram, and Stripe Connect.</p>
        </header>
        <AdminOAuthSetup
          disabled={disabled}
          afterGithub={
            <AdminStripeSetup
              inline
              disabled={disabled}
              onBindSave={(save) => {
                stripeSaveRef.current = save
                bindCompositeSave()
              }}
            />
          }
          onBindSave={(save) => {
            oauthSaveRef.current = save
            bindCompositeSave()
          }}
        />
      </section>
    </div>
  )
}
