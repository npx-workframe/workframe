import type { WizardStepItem } from '@/components/onboarding/OnboardingWizardShell'

export type ConciergeStep =
  | 'intro'
  | 'welcome'
  | 'smtp'
  | 'admin_auth'
  | 'integrations'
  | 'billing'
  | 'workframe'
  | 'profile'
  | 'providers'
  | 'agent'
  | 'invites'
  | 'publish'
  | 'done'

/** Map internal steps onto wizard-rail ids (admin OTP shares the SMTP rail step). */
export function wizardRailStep(step: ConciergeStep): string {
  if (step === 'admin_auth') return 'smtp'
  return step
}

const INVITEE_STEPS: WizardStepItem[] = [
  { id: 'profile', label: 'Your profile', group: 'You' },
  { id: 'providers', label: 'Model keys', group: 'You' },
  { id: 'agent', label: 'Native agent', group: 'You' },
]

export function buildWizardSteps(
  deploymentMode: string,
  modeChosen: boolean,
  isInvitee: boolean,
): WizardStepItem[] {
  if (isInvitee) return INVITEE_STEPS

  if (!modeChosen) {
    return [
      { id: 'intro', label: 'Welcome', group: 'Start' },
      { id: 'welcome', label: 'Deployment', group: 'Start' },
    ]
  }

  const steps: WizardStepItem[] = [
    { id: 'intro', label: 'Welcome', group: 'Start' },
    { id: 'welcome', label: 'Deployment', group: 'Start' },
  ]

  if (deploymentMode === 'public_multi_user') {
    steps.push({ id: 'publish', label: 'Public URL', group: 'Start' })
  }

  if (deploymentMode !== 'single_user_local') {
    steps.push({ id: 'smtp', label: 'Email & admin', group: 'Access' })
  }

  steps.push(
    { id: 'integrations', label: 'Integrations', group: 'Workframe' },
    { id: 'billing', label: 'Model billing', group: 'Workframe' },
    { id: 'workframe', label: 'Business profile', group: 'Workframe' },
    { id: 'profile', label: 'Your profile', group: 'You' },
    { id: 'providers', label: 'Model keys', group: 'You' },
    { id: 'agent', label: 'Native agent', group: 'You' },
  )

  if (deploymentMode !== 'public_multi_user') {
    steps.push({ id: 'invites', label: 'Invite team', group: 'Finish' })
  }

  return steps
}

export function stepMeta(step: ConciergeStep, projectName: string, isInvitee: boolean) {
  switch (step) {
    case 'intro':
      return { title: `Set up ${projectName}`, description: '' }
    case 'welcome':
      return { title: 'Deployment', description: 'Who will use this install?' }
    case 'smtp':
      return { title: 'Email & admin', description: 'SMTP for sign-in codes, then verify your email.' }
    case 'admin_auth':
      return { title: 'Verify admin', description: '' }
    case 'integrations':
      return { title: 'Integrations', description: 'Optional — sign-in OAuth and messaging.' }
    case 'billing':
      return { title: 'Model billing', description: 'Who pays for LLM usage?' }
    case 'workframe':
      return { title: 'Business profile', description: '' }
    case 'profile':
      return { title: isInvitee ? `Join ${projectName}` : 'Your profile', description: '' }
    case 'providers':
      return { title: 'Model keys', description: 'Optional before first chat.' }
    case 'agent':
      return { title: 'Native agent', description: '' }
    case 'invites':
      return { title: 'Invite team', description: '' }
    case 'publish':
      return { title: 'Public URL', description: 'DNS, HTTPS, then test connection.' }
    default:
      return { title: projectName, description: '' }
  }
}

const MODE_LABELS: Record<string, string> = {
  single_user_local: 'Just me on this machine',
  trusted_team: 'My team on Docker',
  public_multi_user: 'Public on the web',
}

export type WizardStatusContext = {
  deploymentMode: string
  modeChosen: boolean
  stack: {
    smtp?: { host?: string; port?: number; configured?: boolean; tested?: boolean; setup_complete?: boolean }
    google_oauth?: { enabled?: boolean; client_id?: string; has_secret?: boolean }
    github_oauth?: { enabled?: boolean; client_id?: string; has_secret?: boolean }
    discord_oauth?: { enabled?: boolean; client_id?: string; has_secret?: boolean }
    telegram_login?: { enabled?: boolean; bot_username?: string; has_token?: boolean }
  } | null
  smtpHost: string
  smtpUser: string
  adminEmail: string
  adminVerified: boolean
  workspaceIntegrations?: {
    github_oauth_configured?: boolean
    messaging?: {
      discord?: { bot_token_configured?: boolean; home_channel?: string }
      telegram?: { bot_token_configured?: boolean; home_channel?: string }
    }
  }
  credentialMode: 'byok' | 'workspace'
  mission: string
  workframeName: string
  workframeTagline: string
  displayName: string
  userTagline: string
  connectedProviders: string[]
  agentName: string
  agentTagline: string
  inviteEmails: string
  publicUrl: string
}

function truncate(text: string, max = 36): string {
  const t = text.trim()
  if (t.length <= max) return t
  return `${t.slice(0, max - 1)}…`
}

function joinParts(parts: string[], max = 2): string {
  const clean = parts.filter(Boolean)
  if (!clean.length) return ''
  if (clean.length <= max) return clean.join(', ')
  return `${clean.slice(0, max).join(', ')} +${clean.length - max}`
}

/** Attach configured summaries to wizard rail steps from live wizard state. */
export function enrichWizardSteps(steps: WizardStepItem[], ctx: WizardStatusContext): WizardStepItem[] {
  return steps.map((step) => {
    switch (step.id) {
      case 'intro':
        return { ...step, configured: true, detail: 'Started' }
      case 'welcome':
        return ctx.modeChosen
          ? { ...step, configured: true, detail: MODE_LABELS[ctx.deploymentMode] ?? ctx.deploymentMode }
          : step
      case 'smtp': {
        const host = ctx.smtpHost.trim() || ctx.stack?.smtp?.host?.trim() || ''
        const smtpReady = Boolean(ctx.stack?.smtp?.configured || host)
        if (ctx.adminVerified) {
          return {
            ...step,
            configured: true,
            detail: ctx.adminEmail.trim() || ctx.smtpUser.trim() || 'Admin verified',
          }
        }
        if (smtpReady) {
          return {
            ...step,
            configured: Boolean(ctx.stack?.smtp?.setup_complete),
            detail: host
              ? `${host}${ctx.stack?.smtp?.setup_complete ? ' · ready' : ctx.stack?.smtp?.tested ? ' · tested' : ''}${ctx.adminEmail ? ` → ${ctx.adminEmail}` : ''}`
              : 'Verify admin',
          }
        }
        return step
      }
      case 'integrations': {
        const parts: string[] = []
        if (ctx.stack?.google_oauth?.enabled) parts.push('Google')
        if (ctx.stack?.github_oauth?.enabled) parts.push('GitHub')
        if (ctx.stack?.discord_oauth?.enabled) parts.push('Discord')
        if (ctx.stack?.telegram_login?.enabled) parts.push('Telegram')
        const ws = ctx.workspaceIntegrations
        if (ws?.github_oauth_configured && !ctx.stack?.github_oauth?.enabled) parts.push('GitHub')
        const detail = joinParts(parts)
        return detail ? { ...step, configured: true, detail } : { ...step, detail: 'Optional' }
      }
      case 'billing':
        return {
          ...step,
          configured: true,
          detail: ctx.credentialMode === 'workspace' ? 'Company pays' : 'Each user BYOK',
        }
      case 'workframe': {
        const detail = ctx.workframeTagline.trim()
          ? truncate(ctx.workframeTagline)
          : ctx.workframeName.trim()
            ? truncate(ctx.workframeName)
            : 'Logo & tagline'
        return {
          ...step,
          configured: Boolean(ctx.workframeTagline.trim() || ctx.workframeName.trim()),
          detail,
        }
      }
      case 'profile': {
        const detail = ctx.userTagline.trim() || ctx.displayName.trim() || undefined
        return { ...step, configured: Boolean(detail), detail }
      }
      case 'providers': {
        const detail = joinParts(ctx.connectedProviders)
        return detail
          ? { ...step, configured: true, detail }
          : { ...step, detail: 'Optional' }
      }
      case 'agent':
        return {
          ...step,
          configured: Boolean(ctx.agentName.trim()),
          detail: ctx.agentTagline.trim() || ctx.agentName.trim() || undefined,
        }
      case 'invites': {
        const emails = ctx.inviteEmails.split(/[,\s]+/).map((e) => e.trim()).filter(Boolean)
        return emails.length
          ? { ...step, configured: true, detail: `${emails.length} invite${emails.length === 1 ? '' : 's'}` }
          : { ...step, detail: 'Optional' }
      }
      case 'publish':
        return ctx.publicUrl.trim()
          ? { ...step, configured: true, detail: truncate(ctx.publicUrl, 42) }
          : { ...step, detail: 'Set public URL' }
      default:
        return step
    }
  })
}

/** Map wizard rail id → internal concierge step (admin OTP shares smtp rail). */
export function railStepToConciergeStep(
  railId: string,
  _currentStep: ConciergeStep,
  _adminVerified: boolean,
): ConciergeStep {
  if (railId === 'smtp') return 'smtp'
  return railId as ConciergeStep
}
