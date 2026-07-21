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
  | 'agent'
  | 'agent_model'
  | 'invites'
  | 'publish'
  | 'done'

/** Map internal steps onto wizard-rail ids (admin OTP shares the SMTP rail step). */
export function wizardRailStep(step: ConciergeStep): string {
  return step
}

const INVITEE_STEPS: WizardStepItem[] = [
  { id: 'profile', label: 'Your Identity', group: 'Join' },
  { id: 'agent_model', label: 'Provider & model', group: 'Join' },
]

export function buildWizardSteps(
  deploymentMode: string,
  modeChosen: boolean,
  isInvitee: boolean,
): WizardStepItem[] {
  if (isInvitee) return INVITEE_STEPS

  if (!modeChosen) {
    return [
      { id: 'intro', label: 'Welcome', group: 'Setup' },
      { id: 'welcome', label: 'Deployment', group: 'Setup' },
    ]
  }

  const steps: WizardStepItem[] = [
    { id: 'intro', label: 'Welcome', group: 'Setup' },
    { id: 'welcome', label: 'Deployment', group: 'Setup' },
  ]

  if (deploymentMode === 'public_multi_user') {
    steps.push({ id: 'publish', label: 'Public URL', group: 'Setup' })
  }

  if (deploymentMode !== 'single_user_local') {
    steps.push(
      { id: 'smtp', label: 'Email delivery', group: 'Setup' },
      { id: 'admin_auth', label: 'Verify email', group: 'Setup' },
    )
  }

  steps.push(
    { id: 'workframe', label: 'Workframe Profile', group: 'Workframe' },
    { id: 'billing', label: 'Billing Model', group: 'Workframe' },
    { id: 'integrations', label: 'Integrations', group: 'Workframe' },
    { id: 'profile', label: 'Your Identity', group: 'User Profile' },
    { id: 'agent', label: 'Your Agent', group: 'User Profile' },
    { id: 'agent_model', label: "Agent's Model", group: 'User Profile' },
  )

  if (deploymentMode !== 'single_user_local') {
    steps.push({ id: 'invites', label: 'Your Team', group: 'User Profile' })
  }

  return steps
}

export function stepMeta(step: ConciergeStep, projectName: string, isInvitee: boolean) {
  switch (step) {
    case 'intro':
      return {
        title: `Set up ${projectName}`,
        description: 'Enter the admin email to register the owner account, then continue through deployment, SMTP, and email verification.',
      }
    case 'welcome':
      return { title: 'Deployment', description: 'Choose who will use this Workframe install.' }
    case 'smtp':
      return { title: 'Email delivery', description: 'Configure and test SMTP for sign-in codes, invites, and notifications.' }
    case 'admin_auth':
      return { title: 'Verify admin email', description: 'Enter the temporary code sent to your admin email.' }
    case 'integrations':
      return { title: 'Integrations', description: 'Optional — member sign-in (OAuth) and agent messaging bots.' }
    case 'billing':
      return { title: 'Billing Model', description: 'Choose BYOK (each member’s keys) or company-pays (shared keys).' }
    case 'workframe':
      return { title: 'Workframe Profile', description: 'Name, logo, and mission shown across your Workframe.' }
    case 'profile':
      return {
        title: isInvitee ? `Join ${projectName}` : 'Your Identity',
        description: isInvitee ? 'Set how teammates see you in chat and rooms.' : 'Your display name and avatar in Workframe.',
      }
    case 'agent':
      return { title: 'Your Agent', description: 'Your concierge agent — name, avatar, and operating instructions.' }
    case 'agent_model':
      return isInvitee
        ? {
            title: 'Provider & model',
            description: 'Connect your LLM key (BYOK) or pick a model when your workspace shares billing.',
          }
        : {
            title: "Agent's Model",
            description: 'Choose the primary model for your native agent. Connect integration keys first when using BYOK.',
          }
    case 'invites':
      return { title: 'Your Team', description: 'Send email invites now, or skip and invite later in Workframe Settings.' }
    case 'publish':
      return { title: 'Public URL', description: 'Point DNS at this server, enable HTTPS, then test the connection.' }
    default:
      return { title: projectName, description: '' }
  }
}

const MODE_LABELS: Record<string, string> = {
  single_user_local: 'Just me on this environment',
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
  agentPrimaryModel: string
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
        return ctx.adminEmail.trim()
          ? { ...step, configured: true, detail: truncate(ctx.adminEmail, 42) }
          : step
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
            detail: host
              ? `${host} · verified`
              : ctx.smtpUser.trim() || 'Admin verified',
          }
        }
        if (smtpReady) {
          return {
            ...step,
            configured: Boolean(ctx.stack?.smtp?.setup_complete),
            detail: host
              ? `${host}${ctx.stack?.smtp?.setup_complete ? ' · ready' : ctx.stack?.smtp?.tested ? ' · tested' : ''}`
              : 'Configure SMTP',
          }
        }
        return step
      }
      case 'admin_auth':
        return ctx.adminVerified
          ? { ...step, configured: true, detail: truncate(ctx.adminEmail, 42) || 'Verified' }
          : { ...step, detail: ctx.adminEmail.trim() ? truncate(ctx.adminEmail, 42) : 'Code required' }
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
          detail: ctx.credentialMode === 'workspace' ? 'Company-pays' : 'BYOK',
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
      case 'agent':
        return {
          ...step,
          configured: Boolean(ctx.agentName.trim()),
          detail: ctx.agentTagline.trim() || ctx.agentName.trim() || undefined,
        }
      case 'agent_model': {
        const detail = truncate(ctx.agentPrimaryModel, 42)
        return ctx.agentPrimaryModel.trim()
          ? { ...step, configured: true, detail }
          : { ...step, detail: ctx.connectedProviders.length ? 'Choose model' : 'Connect keys' }
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
  return railId as ConciergeStep
}
