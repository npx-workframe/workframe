import { authStartNotice } from '@/components/auth/EmailOtpVerification'
import type { ConciergeStep } from '@/components/onboarding/onboardingWizardSteps'
import type { SmtpProgressPhase } from '@/components/onboarding/conciergeFlowUtils'
import { formatWorkframeError, type WorkframeNoticeInfo } from '@/lib/workframeErrors'
import { workframeAuthApi } from '@/lib/workframeAuthApi'

export type ConciergeSmtpDeps = {
  smtpPort: string
  smtpFrom: string
  smtpPass: string
  smtpHost: string
  smtpUser: string
  adminEmail: string
  smtpHasPassword: boolean
  smtpSetupComplete: boolean
  smtpFieldsDirty: boolean
  canKeepAdminSetup: boolean
  adminVerified: boolean
  patchInstallStackWhenAllowed: (data: Record<string, unknown>) => Promise<boolean>
  reloadStack: () => Promise<unknown>
  setSmtpHasPassword: (value: boolean) => void
  setSmtpPass: (value: string) => void
  setSmtpFieldsDirty: (value: boolean) => void
  setSmtpPhase: (phase: SmtpProgressPhase | null) => void
  setBusy: (busy: boolean) => void
  setError: (error: WorkframeNoticeInfo | null) => void
  setAdminAuthDevOtp: (otp: string) => void
  setAdminAuthNotice: (notice: string | null) => void
  setAdminOtpStep: (step: 'email' | 'otp') => void
  setStep: (step: ConciergeStep) => void
}

export function createConciergeSmtpHandlers(deps: ConciergeSmtpDeps) {
  async function saveSmtpForInstall(requirePassword = false): Promise<boolean> {
    const port = Number(deps.smtpPort) || 587
    const from = deps.smtpFrom.trim()
    const password = deps.smtpPass.trim()
    const resolvedAdminEmail = deps.adminEmail.trim()
    if (requirePassword && !resolvedAdminEmail) {
      throw new Error('Admin email is required')
    }
    if (requirePassword && !password && !deps.smtpHasPassword) {
      throw new Error('SMTP password is required')
    }
    const patched = await deps.patchInstallStackWhenAllowed({
      smtp: {
        host: deps.smtpHost,
        port,
        user: deps.smtpUser,
        ...(resolvedAdminEmail ? { admin_email: resolvedAdminEmail } : {}),
        ...(password ? { password } : {}),
        ...(from ? { from } : {}),
        secure: port === 465 ? 'ssl' : 'starttls',
      },
    })
    if (!patched) return false
    if (password) {
      deps.setSmtpHasPassword(true)
      deps.setSmtpPass('')
    }
    await deps.reloadStack()
    return true
  }

  async function testSmtpOnly(): Promise<boolean> {
    deps.setBusy(true)
    deps.setError(null)
    deps.setSmtpPhase('setup')
    try {
      deps.setSmtpPhase('smtp')
      const ok = await saveSmtpForInstall(true)
      if (!ok) return false
      const testEmail = deps.adminEmail.trim()
      if (!testEmail) {
        throw new Error('Admin email is required')
      }
      deps.setSmtpPhase('test-email')
      const test = await workframeAuthApi.testInstallEmail(testEmail)
      if (!test.ok) throw new Error('Test email failed')
      await deps.reloadStack()
      deps.setSmtpFieldsDirty(false)
      deps.setError(null)
      return true
    } catch (err) {
      deps.setError(formatWorkframeError(err, 'SMTP test'))
      return false
    } finally {
      deps.setBusy(false)
      deps.setSmtpPhase(null)
    }
  }

  async function proceedToAdminOtp() {
    deps.setBusy(true)
    deps.setError(null)
    try {
      const ok = await saveSmtpForInstall(false)
      if (!ok) return
      if (!deps.adminEmail.trim()) {
        throw new Error('Admin email is required')
      }
      const start = await workframeAuthApi.startEmailVerification(deps.adminEmail.trim())
      const { devOtp, notice } = authStartNotice(start, deps.adminEmail.trim())
      deps.setAdminAuthDevOtp(devOtp)
      deps.setAdminAuthNotice(notice)
      deps.setAdminOtpStep('otp')
      deps.setStep('admin_auth')
    } catch (err) {
      deps.setError(formatWorkframeError(err, 'Send verification code'))
    } finally {
      deps.setBusy(false)
    }
  }

  async function persistAdminEmail() {
    const email = deps.adminEmail.trim()
    if (!email) return
    await deps.patchInstallStackWhenAllowed({ smtp: { admin_email: email } })
  }

  async function continueFromSmtp() {
    if (deps.canKeepAdminSetup) {
      deps.setBusy(true)
      deps.setError(null)
      try {
        if (deps.smtpHost.trim()) {
          const ok = await saveSmtpForInstall(false)
          if (!ok) return
        }
        deps.setSmtpFieldsDirty(false)
        deps.setStep('workframe')
      } catch (err) {
        deps.setError(formatWorkframeError(err, 'Save SMTP'))
      } finally {
        deps.setBusy(false)
      }
      return
    }
    if (deps.adminVerified) {
      deps.setBusy(true)
      deps.setError(null)
      try {
        if (deps.smtpHost.trim()) {
          const ok = await saveSmtpForInstall(false)
          if (!ok) return
        }
        deps.setSmtpFieldsDirty(false)
        deps.setStep('workframe')
      } catch (err) {
        deps.setError(formatWorkframeError(err, 'Save SMTP'))
      } finally {
        deps.setBusy(false)
      }
      return
    }
    if (deps.smtpFieldsDirty && deps.smtpSetupComplete) {
      deps.setError({
        tone: 'caution',
        message: 'SMTP settings changed.',
        hint: 'Send a test email to confirm your changes before continuing.',
      })
      return
    }
    if (!deps.smtpSetupComplete) {
      deps.setError({
        tone: 'caution',
        message: 'Send a test email before continuing.',
        hint: 'Use “Send test email” once to verify SMTP. After that you can move between steps without testing again.',
      })
      return
    }
    await proceedToAdminOtp()
  }

  return { testSmtpOnly, persistAdminEmail, continueFromSmtp }
}
