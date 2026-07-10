import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import { WfActionButton } from '@/components/ui/WfActionButton'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { WorkframeNotice } from '@/components/ui/WorkframeNotice'
import { formatWorkframeErrorMessage } from '@/lib/workframeErrors'
import { workframeAuthApi, type AuthStartResponse, type SessionProfile } from '@/lib/workframeAuthApi'

export const OTP_LENGTH = 6
const RESEND_COOLDOWN_SECONDS = 30

export type EmailOtpStep = 'email' | 'otp' | 'verifying'

export type EmailOtpVerificationProps = {
  initialEmail?: string
  startStep?: EmailOtpStep
  inviteToken?: string
  emailInputId?: string
  purpose?: 'signin' | 'register'
  initialDevOtp?: string
  initialAuthNotice?: string | null
  googleOAuthEnabled?: boolean
  onGoogleSignIn?: () => void
  onVerified: (profile: SessionProfile) => void
  onFooterChange?: (footer: ReactNode) => void
  onStepChange?: (step: EmailOtpStep) => void
  layout?: 'inline' | 'footer'
  variant?: 'default' | 'wizard'
  skipEmailStep?: boolean
}

export function authStartNotice(result: AuthStartResponse, targetEmail: string) {
  if (result.otp_code) {
    return {
      devOtp: result.otp_code,
      notice: result.email_sent
        ? `We sent a verification code to ${targetEmail}. (Dev harness also shows the code below.)`
        : result.email_error
          ? `Email not sent (${result.email_error}). Use the dev code below.`
          : 'SMTP is not configured locally — use the dev code below.',
    }
  }
  if (result.email_sent) {
    return { devOtp: '', notice: `We sent a verification code to ${targetEmail}.` }
  }
  return {
    devOtp: '',
    notice: result.email_error
      ? `Could not send email: ${result.email_error}`
      : 'Could not send verification email. Check SMTP settings and try again.',
  }
}

export function normalizeOtp(value: string) {
  return value.replace(/\D/g, '').slice(0, OTP_LENGTH)
}

function resultNoticeClass(notice: string) {
  return notice.startsWith('Could not send') ? 'wf-auth__alert--error' : 'wf-auth__alert--info'
}

export function emailOtpCopy(step: EmailOtpStep, email: string, devOtpHint: string, purpose: 'signin' | 'register') {
  if (step === 'otp' || step === 'verifying') {
    if (devOtpHint) return 'No email was sent — enter the dev code shown below.'
    return `Enter the six-digit code sent to ${email}.`
  }
  return purpose === 'register'
    ? 'Register with your email to become the Workframe admin.'
    : 'Sign in with your email to open Workframe.'
}

export function EmailOtpVerification({
  initialEmail = '',
  startStep = 'email',
  inviteToken = '',
  emailInputId = 'wf-auth-email',
  purpose = 'signin',
  initialDevOtp = '',
  initialAuthNotice = null,
  googleOAuthEnabled = false,
  onGoogleSignIn,
  onVerified,
  onFooterChange,
  onStepChange,
  layout = 'inline',
  variant = 'default',
  skipEmailStep = false,
}: EmailOtpVerificationProps) {
  const resolvedStartStep = skipEmailStep && initialEmail.trim() && startStep === 'email' ? 'otp' : startStep
  const [step, setStep] = useState<EmailOtpStep>(resolvedStartStep)
  const [email, setEmail] = useState(initialEmail)
  const [otp, setOtp] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [resendCooldown, setResendCooldown] = useState(startStep === 'otp' ? RESEND_COOLDOWN_SECONDS : 0)
  const [devOtpHint, setDevOtpHint] = useState(initialDevOtp)
  const [authNotice, setAuthNotice] = useState<string | null>(initialAuthNotice)
  const otpRefs = useRef<Array<HTMLInputElement | null>>([])
  const onGoogleSignInRef = useRef(onGoogleSignIn)
  onGoogleSignInRef.current = onGoogleSignIn

  const otpDigits = useMemo(
    () => Array.from({ length: OTP_LENGTH }, (_, index) => otp[index] ?? ''),
    [otp],
  )
  const useFooter = layout === 'footer' && Boolean(onFooterChange)
  const wizardOtp = variant === 'wizard' && (step === 'otp' || step === 'verifying')

  useEffect(() => {
    setEmail(initialEmail)
  }, [initialEmail])

  useEffect(() => {
    const next = skipEmailStep && initialEmail.trim() && startStep === 'email' ? 'otp' : startStep
    setStep(next)
  }, [initialEmail, skipEmailStep, startStep])

  useEffect(() => {
    onStepChange?.(step)
  }, [onStepChange, step])

  useEffect(() => {
    if (resendCooldown <= 0) return
    const timer = window.setTimeout(() => setResendCooldown((value) => value - 1), 1000)
    return () => window.clearTimeout(timer)
  }, [resendCooldown])

  useEffect(() => {
    if (step === 'otp') {
      const nextIndex = otp.length >= OTP_LENGTH ? OTP_LENGTH - 1 : otp.length
      otpRefs.current[nextIndex]?.focus()
    }
  }, [otp.length, step])

  function applyAuthStartResult(result: AuthStartResponse, targetEmail: string) {
    if (result.otp_code) {
      setDevOtpHint(result.otp_code)
      setAuthNotice(
        result.email_sent
          ? `We sent a verification code to ${targetEmail}. (Dev harness also shows the code below.)`
          : result.email_error
            ? `Email not sent (${result.email_error}). Use the dev code below.`
            : 'SMTP is not configured locally — use the dev code below.',
      )
      return
    }

    setDevOtpHint('')
    if (result.email_sent) {
      setAuthNotice(`We sent a verification code to ${targetEmail}.`)
      return
    }

    setAuthNotice(
      result.email_error
        ? `Could not send email: ${result.email_error}`
        : 'Could not send verification email. Check SMTP settings and try again.',
    )
  }

  async function verifyAndFinish(nextEmail: string, code: string) {
    const verified = await workframeAuthApi.verifyEmailCode(nextEmail, code)
    if (!verified.user) {
      try {
        await workframeAuthApi.getMe()
      } catch (err) {
        const message = err instanceof Error ? err.message : ''
        if (message === 'no_session') {
          throw new Error(
            'Sign-in succeeded but no session was saved. Use the same URL host as your invite link (127.0.0.1, not localhost).',
          )
        }
        throw err
      }
    }
    if (inviteToken) {
      await workframeAuthApi.acceptWorkspaceInvite(inviteToken)
    }
    onVerified(verified)
  }

  async function handleEmailSubmit(event?: React.FormEvent<HTMLFormElement>) {
    event?.preventDefault()
    if (!email.trim()) return

    setError(null)
    setAuthNotice(null)
    setBusy(true)

    try {
      const trimmed = email.trim()
      const result = await workframeAuthApi.startEmailVerification(trimmed)
      setEmail(trimmed)
      setOtp('')
      applyAuthStartResult(result, trimmed)
      setResendCooldown(RESEND_COOLDOWN_SECONDS)
      setStep('otp')
    } catch (err) {
      setError(formatWorkframeErrorMessage(err, 'Send verification code'))
    } finally {
      setBusy(false)
    }
  }

  async function handleOtpSubmit(event?: React.FormEvent<HTMLFormElement>, code: string = otp) {
    event?.preventDefault()
    if (code.length !== OTP_LENGTH) return

    setError(null)
    setBusy(true)
    setStep('verifying')

    try {
      await verifyAndFinish(email.trim(), code)
    } catch (err) {
      setError(formatWorkframeErrorMessage(err, 'Verification code'))
      setStep(code.length === OTP_LENGTH ? 'otp' : 'email')
      setOtp(normalizeOtp(code))
    } finally {
      setBusy(false)
    }
  }

  async function handleResend() {
    if (busy || resendCooldown > 0) return

    setError(null)
    setBusy(true)

    try {
      const result = await workframeAuthApi.startEmailVerification(email.trim())
      applyAuthStartResult(result, email.trim())
      setResendCooldown(RESEND_COOLDOWN_SECONDS)
    } catch (err) {
      setError(formatWorkframeErrorMessage(err, 'Resend verification code'))
    } finally {
      setBusy(false)
    }
  }

  function applyOtpDigits(index: number, rawValue: string) {
    const digits = rawValue.replace(/\D/g, '')
    const current = otpDigits.slice()

    if (!digits) {
      current[index] = ''
      setOtp(current.join(''))
      return
    }

    let cursor = index
    for (const digit of digits) {
      if (cursor >= OTP_LENGTH) break
      current[cursor] = digit
      cursor += 1
    }

    const nextValue = current.join('')
    setOtp(nextValue)

    const focusIndex = Math.min(cursor, OTP_LENGTH - 1)
    otpRefs.current[focusIndex]?.focus()

    if (nextValue.length === OTP_LENGTH) {
      window.setTimeout(() => {
        void handleOtpSubmit(undefined, nextValue)
      }, 0)
    }
  }

  function handleOtpDigitChange(index: number, rawValue: string) {
    applyOtpDigits(index, rawValue)
  }

  function handleOtpPaste(index: number, event: React.ClipboardEvent<HTMLInputElement>) {
    const pasted = event.clipboardData.getData('text')
    const digits = normalizeOtp(pasted)
    if (!digits) return

    event.preventDefault()
    applyOtpDigits(index, digits)
  }

  function handleOtpKeyDown(index: number, event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Backspace' && !otpDigits[index] && index > 0) {
      otpRefs.current[index - 1]?.focus()
      return
    }

    if (event.key === 'ArrowLeft' && index > 0) {
      event.preventDefault()
      otpRefs.current[index - 1]?.focus()
      return
    }

    if (event.key === 'ArrowRight' && index < OTP_LENGTH - 1) {
      event.preventDefault()
      otpRefs.current[index + 1]?.focus()
    }
  }

  useEffect(() => {
    if (startStep === 'otp' && initialDevOtp) setDevOtpHint(initialDevOtp)
    if (startStep === 'otp' && initialAuthNotice) setAuthNotice(initialAuthNotice)
  }, [initialAuthNotice, initialDevOtp, startStep])

  const footer = useMemo(() => {
    if (!useFooter) return null
    if (step === 'email') {
      return (
        <>
          {googleOAuthEnabled && onGoogleSignInRef.current ? (
            <WfActionButton wizardSize disabled={busy} onClick={() => onGoogleSignInRef.current?.()}>
              Continue with Google
            </WfActionButton>
          ) : null}
          <WfActionButton
            wizardSize
            tone="primary"
            type="submit"
            form="wf-email-otp-email-form"
            disabled={busy || !email.trim()}
          >
            {busy ? 'Sending…' : 'Send code'}
          </WfActionButton>
        </>
      )
    }
    return (
      <>
        <WfActionButton
          wizardSize
          tone="primary"
          type="submit"
          form="wf-email-otp-code-form"
          disabled={busy || otp.length !== OTP_LENGTH}
        >
          {step === 'verifying' || busy ? 'Verifying…' : 'Verify code'}
        </WfActionButton>
        {!skipEmailStep ? (
          <WfActionButton wizardSize disabled={busy} onClick={() => setStep('email')}>
            Use another email
          </WfActionButton>
        ) : null}
        <WfActionButton
          wizardSize
          tone={resendCooldown > 0 ? 'inactive' : 'default'}
          onClick={() => void handleResend()}
          disabled={busy || resendCooldown > 0}
        >
          {resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend code'}
        </WfActionButton>
      </>
    )
  }, [useFooter, step, busy, email, otp.length, resendCooldown, googleOAuthEnabled, skipEmailStep])

  useEffect(() => {
    if (useFooter && onFooterChange) onFooterChange(footer)
  }, [footer, onFooterChange, useFooter])

  return (
    <>
      {error ? <WorkframeNotice message={error} className="wf-auth__alert wf-auth__alert--error" /> : null}
      {authNotice && !error && !(wizardOtp && (step === 'otp' || step === 'verifying')) ? (
        <div
          className={`wf-auth__alert ${devOtpHint ? 'wf-auth__alert--info' : resultNoticeClass(authNotice)}`}
        >
          {authNotice}
        </div>
      ) : null}

      {step === 'email' && !skipEmailStep ? (
        <form id="wf-email-otp-email-form" className="wf-auth__form" onSubmit={handleEmailSubmit}>
          {purpose === 'register' ? (
            <p className="wf-auth__muted">This registers you as the Workframe admin.</p>
          ) : null}
          <div className="wf-auth__field">
            <Label htmlFor={emailInputId}>Email</Label>
            <Input
              id={emailInputId}
              type="email"
              autoComplete="email"
              inputMode="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              disabled={busy}
              required
            />
          </div>
          {!useFooter ? (
            <div className="wf-auth__row">
              {googleOAuthEnabled && onGoogleSignIn ? (
                <Button type="button" variant="outline" disabled={busy} onClick={onGoogleSignIn}>
                  Continue with Google
                </Button>
              ) : null}
              <Button type="submit" disabled={busy || !email.trim()}>
                {busy ? 'Sending…' : 'Send code'}
              </Button>
            </div>
          ) : null}
        </form>
      ) : null}

      {step === 'otp' || step === 'verifying' ? (
        <div className={wizardOtp ? 'wf-auth-otp-panel' : undefined}>
          {wizardOtp && authNotice && !error ? (
            <div
              className={`wf-auth-otp-panel__notice ${devOtpHint ? 'wf-auth__alert--info' : resultNoticeClass(authNotice)}`}
            >
              {authNotice}
            </div>
          ) : null}
          <form
            id="wf-email-otp-code-form"
            className={`wf-auth__form${wizardOtp ? ' wf-auth-otp-panel__form' : ''}`}
            onSubmit={handleOtpSubmit}
          >
            <div className={`wf-auth__field${wizardOtp ? ' wf-auth-otp-panel__field' : ''}`}>
              <Label htmlFor="wf-otp-0" className={wizardOtp ? 'wf-auth-otp-panel__label' : undefined}>
                Verification code
              </Label>
              <div className="wf-auth__otp" role="group" aria-label="Six digit verification code">
                {otpDigits.map((digit, index) => (
                  <Input
                    key={index}
                    id={index === 0 ? 'wf-otp-0' : `wf-otp-${index}`}
                    ref={(node) => {
                      otpRefs.current[index] = node
                    }}
                    className="wf-auth__otp-input"
                    type="text"
                    inputMode="numeric"
                    autoComplete={index === 0 ? 'one-time-code' : 'off'}
                    maxLength={1}
                    value={digit}
                    disabled={busy}
                    onChange={(event) => handleOtpDigitChange(index, event.target.value)}
                    onPaste={(event) => handleOtpPaste(index, event)}
                    onKeyDown={(event) => handleOtpKeyDown(index, event)}
                  />
                ))}
              </div>
              {devOtpHint ? (
                <div className="wf-auth__dev-code" aria-live="polite">
                  <span className="wf-auth__dev-code-label">Dev code</span>
                  <span className="wf-auth__dev-code-value">{devOtpHint}</span>
                </div>
              ) : null}
            </div>
            {!useFooter ? (
              <div className={wizardOtp ? 'wf-auth-otp-panel__actions' : undefined}>
                <div className="wf-auth__row">
                  <WfActionButton
                    wizardSize
                    tone="primary"
                    type="submit"
                    disabled={busy || otp.length !== OTP_LENGTH}
                  >
                    {step === 'verifying' || busy ? 'Verifying…' : 'Verify code'}
                  </WfActionButton>
                  {!skipEmailStep ? (
                    <WfActionButton wizardSize disabled={busy} onClick={() => setStep('email')}>
                      Use another email
                    </WfActionButton>
                  ) : null}
                </div>
                <div className={`wf-auth__row${wizardOtp ? ' wf-auth-otp-panel__resend' : ' wf-auth__row--between'}`}>
                  <span className="wf-auth__muted">
                    {resendCooldown > 0 ? `Resend available in ${resendCooldown}s` : 'Need a fresh code?'}
                  </span>
                  <WfActionButton
                    wizardSize
                    tone={resendCooldown > 0 ? 'inactive' : 'default'}
                    onClick={() => void handleResend()}
                    disabled={busy || resendCooldown > 0}
                  >
                    {resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend code'}
                  </WfActionButton>
                </div>
              </div>
            ) : (
              <p className="wf-auth__muted">
                {resendCooldown > 0 ? `Resend available in ${resendCooldown}s` : 'Need a fresh code? Use Resend in the footer.'}
              </p>
            )}
          </form>
        </div>
      ) : null}
    </>
  )
}
