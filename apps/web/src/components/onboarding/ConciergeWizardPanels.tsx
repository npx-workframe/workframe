import { OnboardingIdentityFields } from '@/components/onboarding/OnboardingIdentityFields'
import { PublicUrlWizardStep } from '@/components/onboarding/PublicUrlWizardStep'
import { WorkframeIntegrationsStep } from '@/components/onboarding/WorkframeIntegrationsStep'
import { ModelPickerPanel } from '@/components/settings/ModelPickerPanel'
import { OperationProgress, type OperationStep } from '@/components/ui/OperationProgress'
import { ProviderConnectPanel } from '@/components/workspace/ProviderConnectPanel'
import { SettingsPanelBody } from '@/components/workspace/SettingsPanelBody'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { FallbackEntry } from '@/lib/hermesCatalogApi'
import type { WorkframeNoticeInfo } from '@/lib/workframeErrors'
import { DEPLOYMENT_MODES, DEPLOYMENT_MODES_PLANNED, defaultAgentSoul } from '@/components/onboarding/conciergeFlowUtils'
import type { ConciergeStep } from '@/components/onboarding/onboardingWizardSteps'

type ConciergeWizardPanelsProps = {
  step: ConciergeStep
  busy: boolean
  isInvitee?: boolean
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
  onAdminEmailBlur: () => void
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
  onAgentFallbackChainChange: (chain: FallbackEntry[]) => void
  onAgentProvidersConnected: () => void
  onInviteEmailsChange: (value: string) => void
  onPublicUrlChange: (value: string) => void
  onBindOAuthSave: (save: (() => Promise<boolean>) | null) => void
  onError: (info: WorkframeNoticeInfo | null) => void
}

export function ConciergeWizardPanels({
  step,
  busy,
  isInvitee = false,
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
  onAdminEmailBlur,
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
  onAgentFallbackChainChange,
  onAgentProvidersConnected,
  onInviteEmailsChange,
  onPublicUrlChange,
  onBindOAuthSave,
  onError,
}: ConciergeWizardPanelsProps) {
  if (step === 'intro') {
    return (
      <SettingsPanelBody>
        <div className="wf-dialog-field">
          <Label htmlFor="wf-intro-admin-email">Admin email</Label>
          <Input
            id="wf-intro-admin-email"
            type="email"
            value={adminEmail}
            onChange={(e) => onAdminEmailChange(e.target.value)}
            onBlur={onAdminEmailBlur}
            placeholder="admin@company.com"
            disabled={busy}
            autoComplete="email"
          />
          <p className="wf-dialog-field__hint">
            Primary admin account for this install — used for sign-in codes and setup notifications.
          </p>
        </div>
      </SettingsPanelBody>
    )
  }

  if (step === 'welcome') {
    return (
      <div className="wf-wizard-mode-grid">
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
        {DEPLOYMENT_MODES_PLANNED.map((m) => (
          <div key={m.id} className="wf-wizard-mode-card is-inactive" aria-disabled="true">
            <strong>{m.title}</strong>
            <span>{m.blurb}</span>
          </div>
        ))}
      </div>
    )
  }

  if (step === 'integrations') {
    return (
      <SettingsPanelBody>
        <WorkframeIntegrationsStep
          disabled={busy}
          onBindOAuthSave={(save) => {
            onBindOAuthSave(save)
          }}
        />
      </SettingsPanelBody>
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
            <span>One shared key pool for all members. Admin manages integration keys.</span>
          </span>
        </label>
      </div>
    )
  }

  if (step === 'workframe') {
    return (
      <SettingsPanelBody>
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
      </SettingsPanelBody>
    )
  }

  if (step === 'profile') {
    return (
      <SettingsPanelBody>
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
      </SettingsPanelBody>
    )
  }

  if (step === 'agent_model' && workspaceId) {
    const workspaceBilling = isInvitee && credentialMode === 'workspace'
    const modelTabs = workspaceBilling
      ? [{ id: 'model' as const, label: 'Models' }]
      : [
          { id: 'keys' as const, label: isInvitee ? 'Your keys' : 'Providers' },
          { id: 'model' as const, label: 'Models' },
        ]
    return (
      <SettingsPanelBody
        tabs={modelTabs}
        activeTab={workspaceBilling ? 'model' : agentModelTab}
        onTabChange={(id) => onAgentModelTabChange(id as 'keys' | 'model')}
        tablistLabel="Model setup"
      >
        {!workspaceBilling && agentModelTab === 'keys' ? (
          <ProviderConnectPanel
            workspaceId={workspaceId}
            credentialScope={credentialMode === 'workspace' ? 'workspace' : 'user'}
            categories={['llm']}
            hint="none"
            layout="stack"
            scrollInner={false}
            disabled={busy}
            onConnected={onAgentProvidersConnected}
            onError={(message) => {
              const trimmed = message.trim()
              onError(trimmed ? { tone: 'caution', message: trimmed } : null)
            }}
          />
        ) : null}
        {(workspaceBilling || agentModelTab === 'model') ? (
          <ModelPickerPanel
            workspaceId={workspaceId}
            embedded
            selectionOnly
            value={agentPrimaryModel}
            onChanged={onAgentPrimaryModelChange}
            onFallbacksDraftChange={onAgentFallbackChainChange}
            onLoaded={(data) => {
              if (data.primary?.trim()) onAgentPrimaryModelChange(data.primary.trim())
              const chain = (data.fallback_chain ?? []).filter(
                (entry): entry is FallbackEntry => Boolean(entry?.provider?.trim() && entry?.model?.trim()),
              )
              if (chain.length) onAgentFallbackChainChange(chain)
            }}
            onError={(message) => {
              const trimmed = message.trim()
              onError(trimmed ? { tone: 'caution', message: trimmed } : null)
            }}
          />
        ) : null}
      </SettingsPanelBody>
    )
  }

  if (step === 'agent') {
    return (
      <SettingsPanelBody>
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
      </SettingsPanelBody>
    )
  }

  if (step === 'invites') {
    return (
      <SettingsPanelBody>
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
      </SettingsPanelBody>
    )
  }

  if (step === 'publish') {
    return (
      <SettingsPanelBody className="wf-publish-step">
        <PublicUrlWizardStep
          publicUrl={publicUrl}
          onPublicUrlChange={onPublicUrlChange}
          disabled={busy}
          httpsStatus={httpsStatus}
        />
      </SettingsPanelBody>
    )
  }

  return null
}
