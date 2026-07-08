import type { MutableRefObject } from 'react'

import { AGENT_SAVE_STEP_LABELS } from '@/components/onboarding/OnboardingLaunchScreen'
import type { ConciergeStep } from '@/components/onboarding/onboardingWizardSteps'
import { defaultAgentSoul } from '@/components/onboarding/conciergeFlowUtils'
import type { OperationStep } from '@/components/ui/OperationProgress'
import { fetchHermesModels } from '@/lib/hermesCatalogApi'
import { formatWorkframeError, type WorkframeNoticeInfo } from '@/lib/workframeErrors'
import { agentAvatarPersistPayload, logoAvatarPersistPayload, userAvatarPersistPayload } from '@/lib/presetAssets'
import { workframeAuthApi } from '@/lib/workframeAuthApi'

export type ConciergeSaveDeps = {
  workspaceId: string
  credentialMode: 'byok' | 'workspace'
  mission: string
  workframeTagline: string
  logoUrl: string
  displayName: string
  tagline: string
  bio: string
  avatarUrl: string
  agentName: string
  agentTagline: string
  agentSoul: string
  agentAvatar: string
  agentPrimaryModel: string
  connectedProviders: string[]
  isInvitee: boolean
  deploymentMode: string
  oauthSaveRef: MutableRefObject<(() => Promise<boolean>) | null>
  resolveWorkframeName: () => string
  ensureAdminSession: () => Promise<boolean>
  reloadStack: () => Promise<unknown>
  finishInviteeOnboarding: () => Promise<void>
  finishInstall: (options?: { alreadyLaunching?: boolean }) => Promise<void>
  setBusy: (busy: boolean) => void
  setError: (error: WorkframeNoticeInfo | null) => void
  setStep: (step: ConciergeStep) => void
  setAgentModelTab: (tab: 'keys' | 'model') => void
  setAgentPrimaryModel: (model: string) => void
  setAgentSteps: (steps: OperationStep[]) => void
}

export function createConciergeSaveHandlers(deps: ConciergeSaveDeps) {
  async function saveIntegrations(skipOAuth = false) {
    deps.setBusy(true)
    deps.setError(null)
    try {
      if (!(await deps.ensureAdminSession())) return
      if (!skipOAuth) {
        const oauthSave = deps.oauthSaveRef.current
        if (oauthSave) {
          const ok = await oauthSave()
          if (!ok) return
        }
      }
      await deps.reloadStack()
      if (deps.workspaceId) {
        await workframeAuthApi.patchWorkspaceIntegrations(deps.workspaceId, {
          admin_integrations_done: true,
        })
      }
      deps.setStep('profile')
    } catch (err) {
      deps.setError(formatWorkframeError(err, 'Save integrations'))
    } finally {
      deps.setBusy(false)
    }
  }

  async function skipIntegrations() {
    await saveIntegrations(true)
  }

  async function saveBilling() {
    if (!deps.workspaceId) {
      deps.setStep('integrations')
      return
    }
    deps.setBusy(true)
    try {
      if (!(await deps.ensureAdminSession())) return
      await workframeAuthApi.patchWorkspaceIntegrations(deps.workspaceId, {
        credential_mode: deps.credentialMode,
        admin_integrations_done: true,
      })
      deps.setStep('integrations')
    } catch (err) {
      deps.setError(formatWorkframeError(err, 'Save billing'))
    } finally {
      deps.setBusy(false)
    }
  }

  async function saveWorkframe() {
    if (!deps.workspaceId) return
    deps.setBusy(true)
    try {
      if (!(await deps.ensureAdminSession())) return
      const logo = deps.logoUrl ? logoAvatarPersistPayload(deps.logoUrl) : null
      await workframeAuthApi.patchWorkspace(deps.workspaceId, {
        display_name: deps.resolveWorkframeName(),
        description: deps.mission,
        ...(logo ?? {}),
        tagline: deps.workframeTagline,
      })
      await workframeAuthApi.patchWorkspaceIntegrations(deps.workspaceId, {
        admin_onboarding_done: true,
      })
      deps.setStep('billing')
    } catch (err) {
      deps.setError(formatWorkframeError(err, 'Save workframe'))
    } finally {
      deps.setBusy(false)
    }
  }

  async function saveProfile() {
    deps.setBusy(true)
    try {
      const avatar = deps.avatarUrl ? userAvatarPersistPayload(deps.avatarUrl) : null
      await workframeAuthApi.updateMe({
        display_name: deps.displayName || undefined,
        tagline: deps.tagline || undefined,
        bio: deps.bio || undefined,
        ...(avatar ?? {}),
      })
      deps.setStep('agent')
    } catch (err) {
      deps.setError(formatWorkframeError(err, 'Save profile'))
    } finally {
      deps.setBusy(false)
    }
  }

  async function saveAgentModel() {
    if (!deps.workspaceId) return
    deps.setBusy(true)
    deps.setError(null)
    try {
      const models = await fetchHermesModels(undefined, deps.workspaceId, { selectionOnly: true })
      const primary = (deps.agentPrimaryModel || models.primary || '').trim()
      if (!primary) {
        deps.setError({
          tone: 'caution',
          message: 'Choose a primary model for your agent.',
          hint:
            deps.credentialMode === 'byok' && !deps.connectedProviders.length
              ? 'Connect at least one LLM provider key, then pick a model from the refreshed list.'
              : 'Select a primary model before continuing.',
        })
        if (deps.credentialMode === 'byok' && !deps.connectedProviders.length) {
          deps.setAgentModelTab('keys')
        } else {
          deps.setAgentModelTab('model')
        }
        return
      }
      deps.setAgentPrimaryModel(primary)
      if (deps.isInvitee) {
        await deps.finishInviteeOnboarding()
        return
      }
      if (deps.deploymentMode === 'single_user_local') {
        await deps.finishInstall()
        return
      }
      deps.setStep('invites')
    } catch (err) {
      deps.setError(formatWorkframeError(err, 'Save agent model'))
    } finally {
      deps.setBusy(false)
    }
  }

  async function saveAgent() {
    if (!deps.workspaceId) return
    deps.setBusy(true)
    deps.setError(null)
    deps.setAgentSteps(AGENT_SAVE_STEP_LABELS.map((entry, index) => ({
      ...entry,
      status: index === 0 ? 'active' : 'pending',
    })))
    try {
      const soul = deps.agentSoul.trim() || defaultAgentSoul(deps.agentName, deps.resolveWorkframeName())
      const avatar = deps.agentAvatar ? agentAvatarPersistPayload(deps.agentAvatar) : null
      await workframeAuthApi.patchNativeAgent({
        workspace_id: deps.workspaceId,
        display_name: deps.agentName,
        tagline: deps.agentTagline,
        ...(avatar ?? {}),
        soul,
      })
      deps.setAgentSteps(AGENT_SAVE_STEP_LABELS.map((entry) => ({ ...entry, status: 'done' })))
      deps.setStep('agent_model')
    } catch (err) {
      deps.setAgentSteps(
        AGENT_SAVE_STEP_LABELS.map((entry) => ({
          ...entry,
          status: 'error',
          detail: err instanceof Error ? err.message : 'Failed',
        })),
      )
      deps.setError(formatWorkframeError(err, 'Save agent'))
    } finally {
      deps.setBusy(false)
      if (!deps.isInvitee) {
        window.setTimeout(() => deps.setAgentSteps([]), 600)
      }
    }
  }

  return {
    saveIntegrations,
    skipIntegrations,
    saveBilling,
    saveWorkframe,
    saveProfile,
    saveAgentModel,
    saveAgent,
  }
}
