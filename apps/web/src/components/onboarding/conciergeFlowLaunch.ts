import type { ConciergeStep } from '@/components/onboarding/onboardingWizardSteps'
import { buildFinishInstallSteps, defaultAgentSoul } from '@/components/onboarding/conciergeFlowUtils'
import type { OperationStep } from '@/components/ui/OperationProgress'
import { formatWorkframeErrorMessage } from '@/lib/workframeErrors'
import { workframeAuthApi } from '@/lib/workframeAuthApi'

export type ConciergeLaunchDeps = {
  workspaceId: string
  inviteEmails: string
  isInvitee: boolean
  deploymentMode: string
  adminVerified: boolean
  adminEmail: string
  displayName: string
  bio: string
  agentName: string
  agentTagline: string
  agentSoul: string
  resolveWorkframeName: () => string
  onComplete: () => void
  setLaunching: (launching: boolean) => void
  setLaunchError: (error: string | null) => void
  setLaunchSteps: (steps: OperationStep[] | ((current: OperationStep[]) => OperationStep[])) => void
  setBusy: (busy: boolean) => void
  setStep: (step: ConciergeStep) => void
}

export function createConciergeLaunchHandlers(deps: ConciergeLaunchDeps) {
  async function finishInviteeOnboarding() {
    if (!deps.workspaceId) {
      deps.setLaunchError(formatWorkframeErrorMessage(new Error('workspace_missing'), 'Finish join'))
      return
    }
    deps.setLaunching(true)
    deps.setLaunchError(null)
    deps.setLaunchSteps(
      buildFinishInstallSteps(undefined, 'pending').map((entry, index) => ({
        ...entry,
        status: index === 0 ? 'active' : 'pending',
      })),
    )
    deps.setBusy(true)
    try {
      const result = await workframeAuthApi.bootstrapAgentFromTemplate('workframe-agent', {
        workspace_id: deps.workspaceId,
        display_name: deps.agentName,
        tagline: deps.agentTagline,
        soul: deps.agentSoul.trim() || defaultAgentSoul(deps.agentName, deps.resolveWorkframeName()),
        bind_session: true,
      })
      if (!result.ok || !result.room_id) {
        throw new Error(result.error || 'Agent bootstrap failed')
      }
      deps.setLaunchSteps(buildFinishInstallSteps(result.steps as Array<{ step?: string; ok?: boolean; error?: string }>, 'done'))
      deps.setStep('done')
      await new Promise((resolve) => window.setTimeout(resolve, 350))
      deps.onComplete()
    } catch (err) {
      const message = formatWorkframeErrorMessage(err, 'Finish join')
      deps.setLaunchError(message)
      deps.setLaunchSteps((current) =>
        current.map((entry) =>
          entry.status === 'active' ? { ...entry, status: 'error', detail: message } : entry,
        ),
      )
    } finally {
      deps.setBusy(false)
      deps.setLaunching(false)
    }
  }

  async function finishInstall(options?: { alreadyLaunching?: boolean }) {
    if (deps.isInvitee) {
      await finishInviteeOnboarding()
      return
    }
    if (deps.deploymentMode !== 'single_user_local' && !deps.adminVerified) {
      const message = formatWorkframeErrorMessage(new Error('no_session'), 'Finish setup')
      deps.setLaunchError(message)
      deps.setStep('smtp')
      return
    }
    if (!options?.alreadyLaunching) {
      deps.setLaunching(true)
      deps.setLaunchError(null)
      deps.setLaunchSteps(
        buildFinishInstallSteps().map((entry, index) => ({
          ...entry,
          status: index === 0 ? 'active' : 'pending',
        })),
      )
    } else {
      deps.setLaunchSteps((current) => {
        const next = current.filter((entry) => entry.id !== 'finalize')
        const firstPending = next.findIndex((entry) => entry.status === 'pending')
        return next.map((entry, index) =>
          index === firstPending ? { ...entry, status: 'active' } : entry,
        )
      })
    }
    deps.setBusy(true)
    try {
      if (deps.deploymentMode === 'single_user_local' && !deps.isInvitee) {
        const email = deps.adminEmail.trim().toLowerCase()
        if (!email || !email.includes('@')) {
          throw new Error('email_required')
        }
        const payload = {
          display_name: deps.displayName || email.split('@')[0] || 'Owner',
          email,
          bio: deps.bio,
          workframe_name: deps.resolveWorkframeName(),
          agent_name: deps.agentName,
          agent_tagline: deps.agentTagline,
          agent_soul: deps.agentSoul.trim() || deps.bio,
        }
        const result = await workframeAuthApi.completeInstall(payload)
        if (!result.ok) {
          throw new Error(result.error || 'Finish setup failed')
        }
        deps.setLaunchSteps(buildFinishInstallSteps(result.steps, 'active'))
        await new Promise((resolve) => window.setTimeout(resolve, 450))
        deps.setLaunchSteps(buildFinishInstallSteps(result.steps, 'done'))
        deps.setStep('done')
        await new Promise((resolve) => window.setTimeout(resolve, 350))
        deps.onComplete()
        return
      }
      const payload = {
        bio: deps.bio,
        workframe_name: deps.resolveWorkframeName(),
        agent_name: deps.agentName,
        agent_tagline: deps.agentTagline,
        agent_soul: deps.agentSoul.trim() || deps.bio,
      }
      const result = await workframeAuthApi.completeInstall(payload)
      if (!result.ok) {
        throw new Error(result.error || 'Finish setup failed')
      }
      deps.setLaunchSteps(buildFinishInstallSteps(result.steps, 'active'))
      await new Promise((resolve) => window.setTimeout(resolve, 450))
      deps.setLaunchSteps(buildFinishInstallSteps(result.steps, 'done'))
      deps.setStep('done')
      await new Promise((resolve) => window.setTimeout(resolve, 350))
      deps.onComplete()
    } catch (err) {
      const message = formatWorkframeErrorMessage(err, 'Finish setup')
      deps.setLaunchError(message)
      deps.setLaunchSteps((current) =>
        current.map((entry) =>
          entry.status === 'active'
            ? { ...entry, status: 'error', detail: message }
            : entry.status === 'pending'
              ? entry
              : entry,
        ),
      )
    } finally {
      deps.setBusy(false)
    }
  }

  async function sendInvites() {
    if (!deps.workspaceId) return
    const emails = deps.inviteEmails.split(/[,\s]+/).map((e) => e.trim()).filter(Boolean)
    deps.setLaunching(true)
    deps.setLaunchError(null)
    deps.setLaunchSteps(
      buildFinishInstallSteps(undefined, 'pending', { includeInvites: true }).map((entry, index) => ({
        ...entry,
        status: index === 0 ? 'active' : 'pending',
      })),
    )
    try {
      for (let index = 0; index < emails.length; index += 1) {
        const email = emails[index]!
        deps.setLaunchSteps((current) =>
          current.map((entry) =>
            entry.id === 'invites'
              ? { ...entry, status: 'active', detail: `Sending ${index + 1} of ${emails.length}…` }
              : entry,
          ),
        )
        await workframeAuthApi.createWorkspaceInvite(deps.workspaceId, { email, role: 'member' })
      }
      if (emails.length) {
        deps.setLaunchSteps((current) =>
          current.map((entry) =>
            entry.id === 'invites' ? { ...entry, status: 'done', detail: `${emails.length} sent` } : entry,
          ),
        )
      } else {
        deps.setLaunchSteps((current) => current.filter((entry) => entry.id !== 'invites'))
      }
      await finishInstall({ alreadyLaunching: true })
    } catch (err) {
      const message = formatWorkframeErrorMessage(err, 'Send invites')
      deps.setLaunchError(message)
      deps.setLaunchSteps((current) =>
        current.map((entry) =>
          entry.status === 'active' ? { ...entry, status: 'error', detail: message } : entry,
        ),
      )
      deps.setLaunching(true)
    }
  }

  return { finishInviteeOnboarding, finishInstall, sendInvites }
}
