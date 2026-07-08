import {
  EmailOtpVerification,
  type EmailOtpStep,
} from '@/components/auth/EmailOtpVerification'
import { SecretInput } from '@/components/ui/SecretInput'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { SessionProfile } from '@/lib/workframeAuthApi'
import { SMTP_PROGRESS, type SmtpProgressPhase } from '@/components/onboarding/conciergeFlowUtils'

function SmtpProgressList({ phase }: { phase: SmtpProgressPhase | null }) {
  if (!phase) return null
  const activeIdx = SMTP_PROGRESS.findIndex((s) => s.id === phase)
  return (
    <ul className="wf-onboarding-progress" aria-live="polite" aria-busy="true">
      {SMTP_PROGRESS.map((s, i) => {
        const done = i < activeIdx
        const current = i === activeIdx
        return (
          <li key={s.id} className={done ? 'is-done' : current ? 'is-current' : ''}>
            <span className="wf-onboarding-progress__icon" aria-hidden="true">
              {done ? '✓' : current ? '…' : ''}
            </span>
            <span>{s.label}</span>
          </li>
        )
      })}
    </ul>
  )
}

type ConciergeSmtpStepProps = {
  mode: 'smtp' | 'admin_auth'
  busy: boolean
  smtpPhase: SmtpProgressPhase | null
  smtpHost: string
  smtpPort: string
  smtpUser: string
  smtpPass: string
  smtpHasPassword: boolean
  smtpFrom: string
  adminEmail: string
  adminOtpStep: EmailOtpStep
  adminAuthDevOtp: string
  adminAuthNotice: string | null
  inviteToken: string
  googleOAuthEnabled: boolean
  onSmtpHostChange: (value: string) => void
  onSmtpPortChange: (value: string) => void
  onSmtpUserChange: (value: string) => void
  onSmtpPassChange: (value: string) => void
  onSmtpFromChange: (value: string) => void
  onMarkSmtpDirty: () => void
  onGoogleSignIn: () => void
  onAdminOtpStepChange: (step: EmailOtpStep) => void
  onAdminVerified: (profile: SessionProfile) => void
}

export function ConciergeSmtpStep({
  mode,
  busy,
  smtpPhase,
  smtpHost,
  smtpPort,
  smtpUser,
  smtpPass,
  smtpHasPassword,
  smtpFrom,
  adminEmail,
  adminOtpStep,
  adminAuthDevOtp,
  adminAuthNotice,
  inviteToken,
  googleOAuthEnabled,
  onSmtpHostChange,
  onSmtpPortChange,
  onSmtpUserChange,
  onSmtpPassChange,
  onSmtpFromChange,
  onMarkSmtpDirty,
  onGoogleSignIn,
  onAdminOtpStepChange,
  onAdminVerified,
}: ConciergeSmtpStepProps) {
  return (
    <div
      className={`wf-wizard-panel wf-onboarding-form wf-onboarding-compact${mode === 'admin_auth' ? ' wf-wizard-panel--auth-otp' : ''}`}
    >
      {mode === 'smtp' ? (
        <>
          {busy && smtpPhase ? <SmtpProgressList phase={smtpPhase} /> : null}
          <div className="wf-onboarding-form__row wf-onboarding-form__row--2col">
            <div className="wf-dialog-field">
              <Label htmlFor="wf-smtp-host">SMTP host</Label>
              <Input
                id="wf-smtp-host"
                value={smtpHost}
                onChange={(e) => {
                  onMarkSmtpDirty()
                  onSmtpHostChange(e.target.value)
                }}
                placeholder="smtp.sendgrid.net"
                disabled={busy}
              />
            </div>
            <div className="wf-dialog-field">
              <div className="wf-dialog-field__label-row">
                <Label htmlFor="wf-smtp-port">Port</Label>
                <span className="wf-dialog-field__hint wf-dialog-field__hint--inline">
                  465 SSL · 587 STARTTLS
                </span>
              </div>
              <Input
                id="wf-smtp-port"
                value={smtpPort}
                onChange={(e) => {
                  onMarkSmtpDirty()
                  onSmtpPortChange(e.target.value)
                }}
                placeholder="587"
                disabled={busy}
              />
            </div>
          </div>
          <div className="wf-onboarding-form__row wf-onboarding-form__row--2col">
            <div className="wf-dialog-field">
              <Label htmlFor="wf-smtp-user">Username</Label>
              <Input
                id="wf-smtp-user"
                value={smtpUser}
                onChange={(e) => {
                  onMarkSmtpDirty()
                  onSmtpUserChange(e.target.value)
                }}
                disabled={busy}
              />
            </div>
            <div className="wf-dialog-field">
              <Label htmlFor="wf-smtp-pass">Password</Label>
              <SecretInput
                id="wf-smtp-pass"
                value={smtpPass}
                onChange={(e) => {
                  onMarkSmtpDirty()
                  onSmtpPassChange(e.target.value)
                }}
                saved={smtpHasPassword}
                emptyPlaceholder="SMTP password or API key"
                disabled={busy}
              />
            </div>
          </div>
          <div className="wf-dialog-field">
            <Label htmlFor="wf-smtp-from">From address</Label>
            <Input
              id="wf-smtp-from"
              value={smtpFrom}
              onChange={(e) => {
                onMarkSmtpDirty()
                onSmtpFromChange(e.target.value)
              }}
              placeholder={smtpUser || 'same as username'}
              disabled={busy}
            />
            <p className="wf-dialog-field__hint">Leave blank to use the login email as the sender.</p>
          </div>
        </>
      ) : (
        <EmailOtpVerification
          initialEmail={adminEmail}
          startStep={adminOtpStep}
          initialDevOtp={adminAuthDevOtp}
          initialAuthNotice={adminAuthNotice}
          inviteToken={inviteToken}
          emailInputId="wf-concierge-admin-email"
          purpose="register"
          variant="wizard"
          googleOAuthEnabled={googleOAuthEnabled}
          onGoogleSignIn={onGoogleSignIn}
          onStepChange={onAdminOtpStepChange}
          onVerified={onAdminVerified}
        />
      )}
    </div>
  )
}
