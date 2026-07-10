import type { ReactNode } from 'react'

import type { ConciergeStep } from '@/components/onboarding/onboardingWizardSteps'
import { WfActionButton } from '@/components/ui/WfActionButton'

type ConciergeWizardFooterProps = {
  step: ConciergeStep
  busy: boolean
  isInvitee: boolean
  deploymentMode: string
  workspaceId: string
  publicUrl: string
  canKeepAdminSetup: boolean
  smtpSetupComplete: boolean
  canContinueFromSmtp: boolean
  adminVerified: boolean
  adminEmail: string
  onTestSmtp: () => void
  onContinueFromSmtp: () => void
  onSkipIntegrations: () => void
  onSaveIntegrations: () => void
  onSaveBilling: () => void
  onSaveWorkframe: () => void
  onSaveProfile: () => void
  onSaveAgentModel: () => void
  onSelectAgentModel: () => void
  agentModelTab: 'keys' | 'model'
  agentModelsComplete: boolean
  connectedProviderCount: number
  onSaveAgent: () => void
  onFinishInstall: () => void
  onSendInvites: () => void
  onSetupPublicHttps: () => void
  onTestPublicUrl: () => void
  onContinuePublish: () => void
  onGetStarted: () => void
}

export function ConciergeWizardFooter({
  step,
  busy,
  isInvitee,
  deploymentMode,
  workspaceId,
  publicUrl,
  canKeepAdminSetup,
  smtpSetupComplete,
  canContinueFromSmtp,
  adminVerified,
  adminEmail,
  onTestSmtp,
  onContinueFromSmtp,
  onSkipIntegrations,
  onSaveIntegrations,
  onSaveBilling,
  onSaveWorkframe,
  onSaveProfile,
  onSaveAgentModel,
  onSelectAgentModel,
  agentModelTab,
  agentModelsComplete,
  connectedProviderCount,
  onSaveAgent,
  onFinishInstall,
  onSendInvites,
  onSetupPublicHttps,
  onTestPublicUrl,
  onContinuePublish,
  onGetStarted,
}: ConciergeWizardFooterProps): ReactNode {
  switch (step) {
    case 'intro':
      return (
        <WfActionButton
          wizardSize
          tone="primary"
          disabled={busy || !adminEmail.trim()}
          onClick={onGetStarted}
        >
          Get started
        </WfActionButton>
      )
    case 'smtp':
      return (
        <div
          className={`wf-wizard-footer-actions${canKeepAdminSetup ? ' wf-wizard-footer-actions--cluster' : ''}`}
        >
          <WfActionButton
            wizardSize
            tone={canKeepAdminSetup || smtpSetupComplete ? 'default' : 'primary'}
            className="wf-wizard-footer-actions__btn"
            disabled={busy}
            onClick={onTestSmtp}
          >
            {busy ? 'Working…' : 'Send test email'}
          </WfActionButton>
          <WfActionButton
            wizardSize
            tone={canKeepAdminSetup || smtpSetupComplete ? 'primary' : 'inactive'}
            className="wf-wizard-footer-actions__btn"
            disabled={busy || !canContinueFromSmtp}
            onClick={onContinueFromSmtp}
          >
            {canKeepAdminSetup
              ? 'Continue with current setup'
              : adminVerified
                ? 'Continue'
                : 'Continue to verification'}
          </WfActionButton>
        </div>
      )
    case 'admin_auth':
      return null
    case 'integrations':
      return (
        <>
          <WfActionButton wizardSize disabled={busy} onClick={onSkipIntegrations}>
            Skip
          </WfActionButton>
          <WfActionButton wizardSize tone="primary" disabled={busy} onClick={onSaveIntegrations}>
            Continue
          </WfActionButton>
        </>
      )
    case 'billing':
      return (
        <WfActionButton wizardSize tone="primary" disabled={busy} onClick={onSaveBilling}>
          Continue
        </WfActionButton>
      )
    case 'workframe':
      return (
        <WfActionButton wizardSize tone="primary" disabled={busy} onClick={onSaveWorkframe}>
          Continue
        </WfActionButton>
      )
    case 'profile':
      return (
        <WfActionButton wizardSize tone="primary" disabled={busy} onClick={onSaveProfile}>
          Continue
        </WfActionButton>
      )
    case 'agent_model':
      if (!workspaceId) return null
      if (agentModelTab === 'keys') {
        return (
          <WfActionButton
            wizardSize
            tone="primary"
            disabled={busy || connectedProviderCount < 1}
            onClick={onSelectAgentModel}
          >
            Select Model
          </WfActionButton>
        )
      }
      return (
        <WfActionButton
          wizardSize
          tone="primary"
          disabled={busy || !agentModelsComplete}
          onClick={onSaveAgentModel}
        >
          {busy
            ? 'Saving…'
            : isInvitee || deploymentMode === 'single_user_local'
              ? 'Launch Workframe'
              : 'Continue'}
        </WfActionButton>
      )
    case 'agent':
      return (
        <WfActionButton wizardSize tone="primary" disabled={busy} onClick={onSaveAgent}>
          {busy ? 'Saving agent…' : 'Continue'}
        </WfActionButton>
      )
    case 'invites':
      return (
        <>
          <WfActionButton wizardSize disabled={busy} onClick={onFinishInstall}>
            {busy ? 'Finishing…' : 'Skip'}
          </WfActionButton>
          <WfActionButton wizardSize tone="primary" disabled={busy} onClick={onSendInvites}>
            {busy ? 'Sending invites…' : 'Send invites'}
          </WfActionButton>
        </>
      )
    case 'publish':
      return (
        <div className="wf-wizard-footer-actions wf-wizard-footer-actions--cluster">
          <WfActionButton
            wizardSize
            tone="primary"
            className="wf-wizard-footer-actions__btn"
            disabled={busy || !publicUrl.trim()}
            onClick={onSetupPublicHttps}
          >
            {busy ? 'Setting up…' : 'Set up HTTPS'}
          </WfActionButton>
          <WfActionButton
            wizardSize
            className="wf-wizard-footer-actions__btn"
            disabled={busy || !publicUrl.trim()}
            onClick={onTestPublicUrl}
          >
            Test connection
          </WfActionButton>
          <WfActionButton
            wizardSize
            className="wf-wizard-footer-actions__btn"
            disabled={busy || !publicUrl.trim()}
            onClick={onContinuePublish}
          >
            Continue
          </WfActionButton>
        </div>
      )
    default:
      return null
  }
}
