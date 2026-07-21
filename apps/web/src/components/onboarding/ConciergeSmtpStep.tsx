import { SecretInput } from '@/components/ui/SecretInput'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { SMTP_PROGRESS, type SmtpProgressPhase } from '@/components/onboarding/conciergeFlowUtils'

function SmtpSetupStatus({
  host,
  setupComplete,
  tested,
}: {
  host: string
  setupComplete: boolean
  tested: boolean
}) {
  const label = setupComplete ? 'Ready' : tested ? 'Tested' : host.trim() ? 'Saved' : 'Not configured'
  const detail = host.trim() || 'Enter SMTP host and send a test email'
  return (
    <div className="wf-onboarding-smtp-status" aria-live="polite">
      <span
        className={`wf-onboarding-smtp-status__badge${setupComplete ? ' is-ready' : tested ? ' is-tested' : ''}`}
      >
        {label}
      </span>
      <span className="wf-onboarding-smtp-status__detail">{detail}</span>
    </div>
  )
}

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
  busy: boolean
  smtpPhase: SmtpProgressPhase | null
  smtpHost: string
  smtpPort: string
  smtpUser: string
  smtpPass: string
  smtpHasPassword: boolean
  smtpFrom: string
  smtpSetupComplete: boolean
  smtpTested: boolean
  onSmtpHostChange: (value: string) => void
  onSmtpPortChange: (value: string) => void
  onSmtpUserChange: (value: string) => void
  onSmtpPassChange: (value: string) => void
  onSmtpFromChange: (value: string) => void
  onMarkSmtpDirty: () => void
}

export function ConciergeSmtpStep({
  busy,
  smtpPhase,
  smtpHost,
  smtpPort,
  smtpUser,
  smtpPass,
  smtpHasPassword,
  smtpFrom,
  smtpSetupComplete,
  smtpTested,
  onSmtpHostChange,
  onSmtpPortChange,
  onSmtpUserChange,
  onSmtpPassChange,
  onSmtpFromChange,
  onMarkSmtpDirty,
}: ConciergeSmtpStepProps) {
  return (
    <>
      {busy && smtpPhase ? (
        <SmtpProgressList phase={smtpPhase} />
      ) : (
        <SmtpSetupStatus host={smtpHost} setupComplete={smtpSetupComplete} tested={smtpTested} />
      )}
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
  )
}
