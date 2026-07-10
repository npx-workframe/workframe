import { WfActionButton } from '@/components/ui/WfActionButton'
import { Label } from '@/components/ui/label'
import { PanelFooter, PanelInlineNotice, PanelStatus } from '@/components/ui/PanelPrimitives'
import type { DeviceCodeOAuthStatus } from '@/hooks/useDeviceCodeOAuth'
import { deviceOAuthVerificationUri } from '@/lib/providerOAuth'
import { cn } from '@/lib/utils'

export type DeviceCodeOAuthPanelProps = {
  providerId: string
  providerLabel: string
  verificationUri: string | null
  userCode: string | null
  status: DeviceCodeOAuthStatus
  message: string
  copied: boolean
  presentation?: 'dialog' | 'inline'
  onCopyCode: () => void
  onCancel?: () => void
}

export function DeviceCodeOAuthPanel({
  providerId,
  providerLabel,
  verificationUri,
  userCode,
  status,
  message,
  copied,
  presentation = 'dialog',
  onCopyCode,
  onCancel,
}: DeviceCodeOAuthPanelProps) {
  const signInUri = verificationUri ?? deviceOAuthVerificationUri(providerId)
  const isError = status === 'error'
  const isConnected = status === 'connected'
  const showBody = !isError

  const statusLine =
    status === 'starting'
      ? 'Starting device sign-in…'
      : status === 'pending' && !userCode
        ? 'Preparing your code…'
        : status === 'pending'
          ? 'Waiting for sign-in — this updates automatically.'
          : isConnected
            ? message || `${providerLabel} is connected.`
            : ''

  const dismissLabel = isConnected ? 'Done' : isError ? 'Back' : 'Cancel'

  return (
    <div
      className={cn('wf-auth-otp-panel', presentation === 'inline' && 'wf-device-oauth-panel--inline')}
    >
      {showBody ? (
        <div className="wf-auth-otp-panel__notice">
          Sign in with your {providerLabel} account. Keep this open until connection completes.
        </div>
      ) : null}

      {isError && message ? <PanelInlineNotice tone="error">{message}</PanelInlineNotice> : null}

      {showBody ? (
        <div className="wf-auth__form wf-auth-otp-panel__form">
          {signInUri ? (
            <div className="wf-auth-otp-panel__field">
              <Label className="wf-auth-otp-panel__label">Sign-in page</Label>
              <div className="wf-auth-otp-panel__actions">
                <div className="wf-auth__row">
                  <a
                    href={signInUri}
                    target="_blank"
                    rel="noreferrer"
                    className="wf-action-btn wf-wizard-btn"
                    data-tone="primary"
                  >
                    Open sign-in page
                  </a>
                </div>
              </div>
            </div>
          ) : null}

          {userCode ? (
            <div className="wf-auth-otp-panel__field">
              <Label className="wf-auth-otp-panel__label">Device code</Label>
              <div className="wf-auth__dev-code" aria-live="polite">
                <span className="wf-auth__dev-code-label">Your code</span>
                <span className="wf-auth__dev-code-value">{userCode}</span>
              </div>
            </div>
          ) : (
            <div className="wf-auth-otp-panel__field">
              <Label className="wf-auth-otp-panel__label">Device code</Label>
              <PanelStatus>
                {status === 'starting' ? 'Preparing your code…' : 'Waiting for code…'}
              </PanelStatus>
            </div>
          )}

          {statusLine ? (
            <div className="wf-auth__row wf-auth-otp-panel__resend">
              <span className="wf-auth__muted">{statusLine}</span>
            </div>
          ) : null}
        </div>
      ) : null}

      {onCancel && presentation === 'inline' ? (
        <PanelFooter>
          <div className="wf-auth__row">
            {userCode && showBody ? (
              <WfActionButton wizardSize tone="primary" onClick={onCopyCode}>
                {copied ? 'Copied' : 'Copy code'}
              </WfActionButton>
            ) : null}
            <WfActionButton wizardSize onClick={onCancel}>
              {dismissLabel}
            </WfActionButton>
          </div>
        </PanelFooter>
      ) : userCode && showBody && presentation === 'dialog' ? (
        <div className="wf-auth-otp-panel__actions">
          <div className="wf-auth__row">
            <WfActionButton wizardSize tone="primary" onClick={onCopyCode}>
              {copied ? 'Copied' : 'Copy code'}
            </WfActionButton>
          </div>
        </div>
      ) : null}
    </div>
  )
}
