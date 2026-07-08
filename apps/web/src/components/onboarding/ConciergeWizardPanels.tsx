import { OnboardingIdentityFields } from '@/components/onboarding/OnboardingIdentityFields'
import { PublicUrlWizardStep } from '@/components/onboarding/PublicUrlWizardStep'
import { WorkframeIntegrationsStep } from '@/components/onboarding/WorkframeIntegrationsStep'
import { ModelPickerPanel } from '@/components/settings/ModelPickerPanel'
import { OperationProgress, type OperationStep } from '@/components/ui/OperationProgress'
import { ProviderConnectPanel } from '@/components/workspace/ProviderConnectPanel'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { WorkframeNoticeInfo } from '@/lib/workframeErrors'
import { DEPLOYMENT_MODES, defaultAgentSoul } from '@/components/onboarding/conciergeFlowUtils'
import type { ConciergeStep } from '@/components/onboarding/onboardingWizardSteps'

type ConciergeWizardPanelsProps = {
  step: ConciergeStep
  busy: boolean
  adminEmail: string
  credentialMode: 'byok' | 'workspace'
  workspaceId: string
  mission: string
  workframeName: string
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
  agentModelTab: 'keys' | 'model'
  agentSteps: OperationStep[]
  inviteEmails: string
  publicUrl: string
  httpsStatus: string | null
  resolveWorkframeName: () => string
  onAdminEmailChange: (value: string) => void
  onPickMode: (mode: string) => void
  onCredentialModeChange: (mode: 'byok' | 'workspace') => void
  onLogoUrlChange: (value: string) => void
  onWorkframeNameChange: (value: string) => void
  onWorkframeTaglineChange: (value: string) => void
  onMissionChange: (value: string) => void
  onDisplayNameChange: (value: string) => void
  onTaglineChange: (value: string) => void
  onBioChange: (value: string) => void
  onAvatarUrlChange: (value: string) => void
  onAgentNameChange: (value: string) => void
  onAgentTaglineChange: (value: string) => void
  onAgentSoulChange: (value: string) => void
  onAgentAvatarChange: (value: string) => void
  onAgentModelTabChange: (tab: 'keys' | 'model') => void
  onAgentPrimaryModelChange: (model: string) => void
  onInviteEmailsChange: (value: string) => void
  onPublicUrlChange: (value: string) => void
  onBindOAuthSave: (save: (() => Promise<boolean>) | null) => void
  onError: (info: WorkframeNoticeInfo) => void
}

export function ConciergeWizardPanels({
  step,
  busy,
  adminEmail,
  credentialMode,
  workspaceId,
  mission,
  workframeName,
  workframeTagline,
  logoUrl,
  displayName,
  tagline,
  bio,
  avatarUrl,
  agentName,
  agentTagline,
  agentSoul,
  agentAvatar,
  agentPrimaryModel,
  agentModelTab,
  agentSteps,
  inviteEmails,
  publicUrl,
  httpsStatus,
  resolveWorkframeName,
  onAdminEmailChange,
  onPickMode,
  onCredentialModeChange,
  onLogoUrlChange,
  onWorkframeNameChange,
  onWorkframeTaglineChange,
  onMissionChange,
  onDisplayNameChange,
  onTaglineChange,
  onBioChange,
  onAvatarUrlChange,
  onAgentNameChange,
  onAgentTaglineChange,
  onAgentSoulChange,
  onAgentAvatarChange,
  onAgentModelTabChange,
  onAgentPrimaryModelChange,
  onInviteEmailsChange,
  onPublicUrlChange,
  onBindOAuthSave,
  onError,
}: ConciergeWizardPanelsProps) {
  if (step === 'intro') {
    return (
      <div className="wf-wizard-panel">
        <ul className="wf-wizard-checklist">
          <li>Deployment mode and admin sign-in</li>
          <li>Integrations, billing (BYOK or company-pays)</li>
          <li>Workframe profile, your keys, and native agent</li>
        </ul>
      </div>
    )
  }

  if (step === 'welcome') {
    return (
      <div className="wf-wizard-mode-grid">
        <div className="wf-dialog-field wf-wizard-mode-grid__email">
          <Label htmlFor="wf-welcome-email">Your email</Label>
          <Input
            id="wf-welcome-email"
            type="email"
            value={adminEmail}
            onChange={(e) => onAdminEmailChange(e.target.value)}
            placeholder="you@company.com"
            disabled={busy}
            autoComplete="email"
          />
          <p className="wf-dialog-field__hint">
            Required for &quot;Just me on this machine&quot;. Other modes verify email on the Admin step.
          </p>
        </div>
        {DEPLOYMENT_MODES.map((m) => (
          <button
            key={m.id}
            type="button"
            className="wf-wizard-mode-card"
            disabled={busy}
            onClick={() => onPickMode(m.id)}
          >
            <strong>{m.title}</strong>
            <span>{m.blurb}</span>
          </button>
        ))}
      </div>
    )
  }

  if (step === 'integrations') {
    return (
      <WorkframeIntegrationsStep
        disabled={busy}
        onBindOAuthSave={(save) => {
          onBindOAuthSave(save)
        }}
      />
    )
  }

  if (step === 'billing') {
    return (
      <div className="wf-wizard-choice-grid" role="radiogroup" aria-label="Billing model">
        <label className={`wf-wizard-choice-card${credentialMode === 'byok' ? ' is-selected' : ''}`}>
          <input
            type="radio"
            className="wf-wizard-choice-card__input"
            name="wf-credential-mode"
            checked={credentialMode === 'byok'}
            onChange={() => onCredentialModeChange('byok')}
          />
          <span className="wf-wizard-choice-card__radio" aria-hidden="true" />
          <span className="wf-wizard-choice-card__body">
            <strong>BYOK — bring your own keys</strong>
            <span>Each member connects personal LLM keys. Usage bills to them.</span>
          </span>
        </label>
        <label className={`wf-wizard-choice-card${credentialMode === 'workspace' ? ' is-selected' : ''}`}>
          <input
            type="radio"
            className="wf-wizard-choice-card__input"
            name="wf-credential-mode"
            checked={credentialMode === 'workspace'}
            onChange={() => onCredentialModeChange('workspace')}
          />
          <span className="wf-wizard-choice-card__radio" aria-hidden="true" />
          <span className="wf-wizard-choice-card__body">
            <strong>Company-pays — shared keys</strong>
            <span>One shared key pool for all members. Admin manages provider keys.</span>
          </span>
        </label>
      </div>
    )
  }

  if (step === 'workframe') {
    return (
      <div className="wf-wizard-panel wf-onboarding-form">
        <OnboardingIdentityFields
          avatarKind="logo"
          avatarUrl={logoUrl}
          onAvatarChange={onLogoUrlChange}
          avatarLabel="Logo"
          disabled={busy}
          primary={{
            id: 'wf-wf-name',
            label: 'Workframe name',
            value: workframeName,
            onChange: onWorkframeNameChange,
          }}
          secondary={{
            id: 'wf-wf-tag',
            label: 'Workframe tagline',
            value: workframeTagline,
            onChange: onWorkframeTaglineChange,
          }}
          body={{
            id: 'wf-wf-mission',
            label: 'Mission',
            value: mission,
            onChange: onMissionChange,
            rows: 3,
          }}
        />
      </div>
    )
  }

  if (step === 'profile') {
    return (
      <div className="wf-wizard-panel wf-onboarding-form">
        <OnboardingIdentityFields
          avatarKind="user"
          avatarUrl={avatarUrl}
          onAvatarChange={onAvatarUrlChange}
          disabled={busy}
          primary={{
            id: 'wf-profile-name',
            label: 'Display name',
            value: displayName,
            onChange: onDisplayNameChange,
          }}
          secondary={{
            id: 'wf-profile-tag',
            label: 'Tagline',
            value: tagline,
            onChange: onTaglineChange,
          }}
          body={{
            id: 'wf-profile-bio',
            label: 'About you',
            value: bio,
            onChange: onBioChange,
            rows: 3,
          }}
        />
      </div>
    )
  }

  if (step === 'agent_model' && workspaceId) {
    return (
      <div className="wf-wizard-panel wf-onboarding-form">
        <div className="wf-wizard-subtabs" role="tablist" aria-label="Agent model sections">
          {(
            [
              ...(credentialMode === 'byok' ? [['keys', 'Provider keys'] as const] : []),
              ['model', 'LLM model'] as const,
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={agentModelTab === id}
              className={`wf-wizard-subtabs__btn${agentModelTab === id ? ' is-active' : ''}`}
              onClick={() => onAgentModelTabChange(id)}
            >
              {label}
            </button>
          ))}
        </div>
        {agentModelTab === 'keys' && credentialMode === 'byok' ? (
          <ProviderConnectPanel
            workspaceId={workspaceId}
            credentialScope="user"
            categories={['llm']}
            hint="none"
            layout="tabs"
            disabled={busy}
          />
        ) : null}
        {agentModelTab === 'model' ? (
          <ModelPickerPanel
            workspaceId={workspaceId}
            embedded
            selectionOnly
            value={agentPrimaryModel}
            onChanged={onAgentPrimaryModelChange}
            onLoaded={(data) => {
              if (data.primary?.trim()) onAgentPrimaryModelChange(data.primary.trim())
            }}
            onError={(message) => onError({ tone: 'caution', message })}
          />
        ) : null}
      </div>
    )
  }

  if (step === 'agent') {
    return (
      <div className="wf-wizard-panel wf-onboarding-form">
        {agentSteps.length ? (
          <OperationProgress steps={agentSteps} title="Setting up your agent" className="wf-mb-4" />
        ) : null}
        <OnboardingIdentityFields
          avatarKind="agent"
          avatarUrl={agentAvatar}
          onAvatarChange={onAgentAvatarChange}
          disabled={busy}
          primary={{
            id: 'wf-agent-name',
            label: 'Name',
            value: agentName,
            onChange: onAgentNameChange,
          }}
          secondary={{
            id: 'wf-agent-tag',
            label: 'Tagline',
            value: agentTagline,
            onChange: onAgentTaglineChange,
          }}
          body={{
            id: 'wf-agent-soul',
            label: 'Soul / instructions',
            value: agentSoul,
            onChange: onAgentSoulChange,
            rows: 4,
            placeholder: defaultAgentSoul(agentName, resolveWorkframeName()),
          }}
        />
      </div>
    )
  }

  if (step === 'invites') {
    return (
      <div className="wf-wizard-panel wf-onboarding-form">
        <div className="wf-dialog-field">
          <Label htmlFor="wf-invite-emails">Email addresses</Label>
          <Input
            id="wf-invite-emails"
            value={inviteEmails}
            onChange={(e) => onInviteEmailsChange(e.target.value)}
            placeholder="a@co.com, b@co.com"
          />
          <p className="wf-dialog-field__hint">Comma-separated. Skip to invite teammates later in Workframe Settings.</p>
        </div>
      </div>
    )
  }

  if (step === 'publish') {
    return (
      <PublicUrlWizardStep
        publicUrl={publicUrl}
        onPublicUrlChange={onPublicUrlChange}
        disabled={busy}
        httpsStatus={httpsStatus}
      />
    )
  }

  return null
}
