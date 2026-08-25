import type { ConciergeStep } from '@/components/onboarding/onboardingWizardSteps'
import type { StackConfig } from '@/lib/workframeAuthApi'

const ALLOWED_RESUME_STEPS: ConciergeStep[] = [
  'intro',
  'theme',
  'welcome',
  'publish',
  'smtp',
  'admin_auth',
  'workframe',
  'billing',
  'integrations',
  'profile',
  'agent',
  'agent_model',
  'invites',
  'done',
]

const PRE_DEPLOYMENT_STEPS: ConciergeStep[] = [
  'theme',
  'publish',
  'smtp',
  'admin_auth',
  'workframe',
  'billing',
  'integrations',
  'profile',
  'agent',
  'agent_model',
  'invites',
]

export type ConciergeResumeInput = {
  resumeRaw: string
  installAdminVerified: boolean
  smtpAdminEmail: string
  deploymentChosen: boolean
  smtpSetupComplete: boolean
}

export function resolveConciergeResumeStep(input: ConciergeResumeInput): ConciergeStep | null {
  const resumeRaw = String(input.resumeRaw || '').trim()
  if (!resumeRaw) return null

  let resumeStep = resumeRaw as ConciergeStep
  if (resumeStep === 'admin_auth' && input.installAdminVerified) {
    resumeStep = 'workframe'
  } else if (resumeStep === 'admin_auth' && !input.smtpSetupComplete) {
    resumeStep = 'smtp'
  } else if (
    resumeStep === 'smtp'
    && input.installAdminVerified
    && input.smtpSetupComplete
  ) {
    resumeStep = 'workframe'
  }

  if (!input.deploymentChosen && PRE_DEPLOYMENT_STEPS.includes(resumeStep)) {
    resumeStep = input.smtpAdminEmail ? 'welcome' : 'intro'
  }
  if (!input.smtpAdminEmail && resumeStep !== 'intro') {
    resumeStep = 'intro'
  }

  if (!ALLOWED_RESUME_STEPS.includes(resumeStep) || resumeStep === 'intro') {
    return null
  }
  return resumeStep
}

export function stackHasSmtpAdminEmail(cfg: StackConfig | null | undefined): string {
  return String(cfg?.smtp?.admin_email || '').trim()
}
