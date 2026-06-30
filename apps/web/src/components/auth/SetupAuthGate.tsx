import { useEffect, useMemo, useState } from 'react'

import {
  EmailOtpVerification,
  emailOtpCopy,
  normalizeOtp,
  type EmailOtpStep,
} from '@/components/auth/EmailOtpVerification'
import { DialogFrame } from '@/components/dialogs/DialogFrame'
import { WorkframeNotice } from '@/components/ui/WorkframeNotice'
import { formatWorkframeErrorMessage } from '@/lib/workframeErrors'
import { isElectronRuntime } from '@/lib/runtime'
import { workframeAuthApi } from '@/lib/workframeAuthApi'

type GateStep = 'checking' | EmailOtpStep

type SetupAuthGateProps = {
  projectName: string
  onAuthenticated: () => void
}

export function SetupAuthGate({ projectName, onAuthenticated }: SetupAuthGateProps) {
  const [step, setStep] = useState<GateStep>('checking')
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string | null>(null)

  const inviteToken = useMemo(() => {
    const params = new URLSearchParams(window.location.search)
    return params.get('invite_token')?.trim() || ''
  }, [])
  const inviteEmail = useMemo(() => {
    const params = new URLSearchParams(window.location.search)
    return params.get('email')?.trim() || ''
  }, [])

  useEffect(() => {
    void initializeGate()
  }, [])

  async function ensureCanonicalHost() {
    try {
      const meta = await workframeAuthApi.getMeta()
      const base = meta.app_base_url?.trim()
      if (!base) return
      const canonical = new URL(base)
      if (window.location.host !== canonical.host) {
        window.location.replace(
          `${canonical.origin}${window.location.pathname}${window.location.search}${window.location.hash}`,
        )
        await new Promise<void>(() => {})
      }
    } catch {
      // Meta is best-effort; continue on the current host.
    }
  }

  async function initializeGate() {
    setError(null)
    setStep('checking')

    try {
      await ensureCanonicalHost()
      try {
        const setup = await workframeAuthApi.getSetupStatus()
        if (!setup.setup_complete) {
          await workframeAuthApi.completeSetup({
            workframe_name: projectName,
            agent_name: `${projectName} Agent`,
          })
        }
      } catch {
        // ponytail: API auto-bootstrap may already have seeded the workspace.
      }

      const params = new URLSearchParams(window.location.search)
      const linkEmail = params.get('email')?.trim()
      const linkCode = params.get('code')?.trim()
      const linkInviteToken = params.get('invite_token')?.trim() || inviteToken
      const linkInviteEmail = params.get('invite_email')?.trim() || inviteEmail || linkEmail

      const acceptInviteIfNeeded = async () => {
        if (!linkInviteToken) return
        await workframeAuthApi.acceptWorkspaceInvite(linkInviteToken)
      }

      try {
        await workframeAuthApi.restoreSession()
        await acceptInviteIfNeeded()
        window.history.replaceState({}, '', window.location.pathname)
        onAuthenticated()
        return
      } catch {
        // fall through to verification flow
      }

      if (linkEmail && linkCode) {
        setEmail(linkEmail)
        setStep('verifying')
        try {
          await workframeAuthApi.verifyEmailCode(linkEmail, normalizeOtp(linkCode))
          if (linkInviteToken) await workframeAuthApi.acceptWorkspaceInvite(linkInviteToken)
          window.history.replaceState({}, '', window.location.pathname)
          onAuthenticated()
          return
        } catch (err) {
          setError(formatWorkframeErrorMessage(err, 'Verification code'))
          setStep('otp')
        }
      }

      if (linkInviteEmail) {
        setEmail(linkInviteEmail)
      }

      setStep('email')
    } catch (err) {
      setError(formatWorkframeErrorMessage(err, 'Load authentication'))
      setStep('email')
    }
  }

  const title = 'Sign in to continue'
  const description =
    step === 'checking' ? 'Checking your session…' : emailOtpCopy(step, email, '', 'signin')
  const modal = !isElectronRuntime()

  if (step === 'checking') {
    return (
      <DialogFrame
        open
        modal={modal}
        onOpenChange={() => {}}
        title={title}
        description={description}
        showClose={false}
        contentClassName="wf-auth-dialog"
      >
        {error ? <WorkframeNotice message={error} className="wf-auth__alert wf-auth__alert--error" /> : null}
        <div className="wf-auth__status">Checking session…</div>
      </DialogFrame>
    )
  }

  return (
    <DialogFrame
      open
      modal={modal}
      onOpenChange={() => {}}
      title={title}
      description={description}
      showClose={false}
      contentClassName="wf-auth-dialog"
    >
      <EmailOtpVerification
        initialEmail={email}
        startStep={step}
        inviteToken={inviteToken}
        purpose="signin"
        onVerified={() => {
          window.history.replaceState({}, '', window.location.pathname)
          onAuthenticated()
        }}
      />
    </DialogFrame>
  )
}
