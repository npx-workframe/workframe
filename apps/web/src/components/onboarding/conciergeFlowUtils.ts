import { FINISH_INSTALL_STEP_LABELS } from '@/components/onboarding/OnboardingLaunchScreen'
import { stepsFromApiResults, type OperationStep } from '@/components/ui/OperationProgress'
import type { StackConfig } from '@/lib/workframeAuthApi'

export const DEPLOYMENT_MODES = [
  { id: 'single_user_local', title: 'Just me on this machine', blurb: 'Solo use — skip email sign-in.' },
  { id: 'trusted_team', title: 'My team on Docker', blurb: 'Teammates sign in with email verification.' },
  { id: 'public_multi_user', title: 'Public on the web', blurb: 'Shared URL — DNS, HTTPS, and full security.' },
] as const

export type SmtpProgressPhase = 'setup' | 'smtp' | 'test-email' | 'verify'

export const SMTP_PROGRESS: { id: SmtpProgressPhase; label: string }[] = [
  { id: 'setup', label: 'Prepare Workframe' },
  { id: 'smtp', label: 'Save SMTP settings' },
  { id: 'test-email', label: 'Send test email' },
  { id: 'verify', label: 'Start admin verification' },
]

export function normalizePublicUrl(url: string): string {
  const trimmed = url.trim().replace(/\/+$/, '')
  if (!trimmed) return ''
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  return `https://${trimmed}`
}

export function resolveSmtpAdminEmail(
  smtp: StackConfig['smtp'] | undefined,
  sessionEmail?: string,
): string {
  const stored = String(smtp?.admin_email || '').trim()
  if (stored) return stored
  return String(sessionEmail || '').trim()
}

export function preferAdminEmailOverSmtpLogin(
  current: string,
  candidate: string,
  smtpLogin?: string,
): string {
  const cur = current.trim()
  const cand = candidate.trim()
  const login = String(smtpLogin || '').trim().toLowerCase()
  if (!cand) return cur || current
  if (!cur) return cand
  if (login && cur.toLowerCase() === login && cand.toLowerCase() !== login) return cand
  return current
}

export function defaultAgentSoul(name: string, project: string) {
  return `You are ${name}, the Workframe Manager for ${project}. You help the owner run rooms, agents, and day-to-day work.`
}

export function buildFinishInstallSteps(
  apiSteps?: Array<{ step?: string; ok?: boolean; error?: string }>,
  finalize: 'pending' | 'active' | 'done' | 'error' = 'pending',
  options?: { includeInvites?: boolean },
): OperationStep[] {
  const invite = options?.includeInvites ? [{ id: 'invites', label: 'Send team invites' }] : []
  const core = FINISH_INSTALL_STEP_LABELS.filter((step) => step.id !== 'finalize')
  const labels = [...invite, ...core]
  const mapped = stepsFromApiResults(labels, apiSteps, labels.length)
  return [
    ...mapped,
    {
      id: 'finalize',
      label: 'Load Workframe',
      status: finalize,
    },
  ]
}
