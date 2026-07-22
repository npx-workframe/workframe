import { EmailOtpVerification } from '@/components/auth/EmailOtpVerification'
import { ConciergeSmtpStep } from '@/components/onboarding/ConciergeSmtpStep'
import { SettingsPanelBody } from '@/components/workspace/SettingsPanelBody'
import { continueFromPublishStep } from '@/components/onboarding/conciergeFlowPublish'
import { ConciergeWizardFooter } from '@/components/onboarding/ConciergeWizardFooter'
import { ConciergeWizardPanels } from '@/components/onboarding/ConciergeWizardPanels'
import { OnboardingAuthGate } from '@/components/onboarding/OnboardingAuthGate'
import { OnboardingLaunchScreen } from '@/components/onboarding/OnboardingLaunchScreen'
import { OnboardingWizardShell } from '@/components/onboarding/OnboardingWizardShell'
import { BootScreen } from '@/components/shell/BootScreen'
import { WorkframeNotice } from '@/components/ui/WorkframeNotice'
import { useConciergeFlow } from '@/components/onboarding/useConciergeFlow'

export type { ConciergeStep } from '@/components/onboarding/onboardingWizardSteps'

type ConciergeFlowProps = {
  projectName: string
  onComplete: () => void
  inviteToken?: string
  inviteEmail?: string
}

export function ConciergeFlow({ projectName, onComplete, inviteToken = '', inviteEmail = '' }: ConciergeFlowProps) {
  const flow = useConciergeFlow({ projectName, onComplete, inviteToken, inviteEmail })

  if (!flow.bootstrapDone && !flow.isInvitee) {
    return <BootScreen label="Loading setup wizard" />
  }

  if (flow.ownerSignInRequired) {
    return (
      <OnboardingAuthGate title="Sign in to continue setup" description="Sign in as the Workframe admin to resume setup.">
        <EmailOtpVerification
          initialEmail={flow.adminEmail}
          startStep="email"
          purpose="signin"
          variant="wizard"
          onVerified={flow.handleOwnerSignedIn}
        />
      </OnboardingAuthGate>
    )
  }

  if (flow.isInvitee && !flow.inviteeAuthed) {
    return (
      <OnboardingAuthGate title={`Join ${projectName}`} description="Verify your invite email to continue.">
        <EmailOtpVerification
          initialEmail={inviteEmail}
          startStep="email"
          skipEmailStep={Boolean(inviteEmail.trim())}
          autoSendCode={Boolean(inviteEmail.trim())}
          inviteToken={inviteToken}
          purpose="signin"
          variant="wizard"
          onVerified={flow.handleInviteeVerified}
        />
      </OnboardingAuthGate>
    )
  }

  if (flow.launching) {
    return (
      <OnboardingLaunchScreen
        projectName={projectName}
        steps={flow.launchSteps}
        error={flow.launchError}
        onRetry={() => void flow.finishInstall()}
      />
    )
  }

  const footer = (
    <ConciergeWizardFooter
      step={flow.step}
      busy={flow.busy}
      isInvitee={flow.isInvitee}
      deploymentMode={flow.deploymentMode}
      workspaceId={flow.workspaceId}
      publicUrl={flow.publicUrl}
      canKeepAdminSetup={flow.canKeepAdminSetup}
      smtpSetupComplete={flow.smtpSetupComplete}
      canContinueFromSmtp={flow.canContinueFromSmtp}
      adminVerified={flow.adminVerified}
      adminEmail={flow.adminEmail}
      onTestSmtp={() => void flow.testSmtpOnly()}
      onContinueFromSmtp={() => void flow.continueFromSmtp()}
      onSkipIntegrations={() => void flow.skipIntegrations()}
      onSaveIntegrations={() => void flow.saveIntegrations()}
      onSaveBilling={() => void flow.saveBilling()}
      onSaveWorkframe={() => void flow.saveWorkframe()}
      onSaveProfile={() => void flow.saveProfile()}
      onSaveAgentModel={() => void flow.saveAgentModel()}
      onSelectAgentModel={() => flow.setAgentModelTab('model')}
      agentModelTab={flow.agentModelTab}
      agentModelsComplete={flow.agentModelsComplete}
      connectedProviderCount={flow.connectedProviders.length}
      onSaveAgent={() => void flow.saveAgent()}
      onFinishInstall={() => void flow.finishInstall()}
      onSendInvites={() => void flow.sendInvites()}
      onSetupPublicHttps={() => void flow.setupPublicHttps()}
      onTestPublicUrl={() => void flow.testPublicUrl()}
      onContinuePublish={() =>
        void continueFromPublishStep({
          publicUrl: flow.publicUrl,
          setPublicUrl: flow.setPublicUrl,
          patchInstallStackWhenAllowed: flow.patchInstallStackWhenAllowed,
          setStep: flow.setStep,
          setBusy: flow.setBusy,
          setError: flow.setError,
        })
      }
      onGetStarted={() => void flow.continueFromIntro()}
    />
  )

  return (
    <OnboardingWizardShell
      projectName={flow.workframeName.trim() || projectName}
      brandLogoUrl={flow.showBrandLogo ? flow.logoUrl : undefined}
      step={flow.currentRailStep}
      steps={flow.wizardSteps}
      maxReachableIndex={flow.maxReachableIndex}
      onStepSelect={flow.goToRailStep}
      title={flow.title}
      description={flow.description || undefined}
      footer={footer}
    >
      {flow.error?.message?.trim() ? (
        <WorkframeNotice info={flow.error} className="wf-notice--wizard" />
      ) : null}

      {flow.step === 'smtp' ? (
        <SettingsPanelBody compact>
          <ConciergeSmtpStep
          busy={flow.busy}
          smtpPhase={flow.smtpPhase}
          smtpHost={flow.smtpHost}
          smtpPort={flow.smtpPort}
          smtpUser={flow.smtpUser}
          smtpPass={flow.smtpPass}
          smtpHasPassword={flow.smtpHasPassword}
          smtpFrom={flow.smtpFrom}
          smtpSetupComplete={flow.smtpSetupComplete}
          smtpTested={Boolean(flow.stack?.smtp?.tested)}
          onSmtpHostChange={flow.setSmtpHost}
          onSmtpPortChange={flow.setSmtpPort}
          onSmtpUserChange={flow.setSmtpUser}
          onSmtpPassChange={flow.setSmtpPass}
          onSmtpFromChange={flow.setSmtpFrom}
          onMarkSmtpDirty={flow.markSmtpDirty}
        />
        </SettingsPanelBody>
      ) : flow.step === 'admin_auth' ? (
        <SettingsPanelBody compact authOtp>
          <EmailOtpVerification
            initialEmail={flow.adminEmail}
            startStep={flow.adminOtpStep}
            initialDevOtp={flow.adminAuthDevOtp}
            initialAuthNotice={flow.adminAuthNotice}
            inviteToken={inviteToken}
            emailInputId="wf-concierge-admin-email"
            purpose="register"
            variant="wizard"
            skipEmailStep={Boolean(flow.adminEmail.trim())}
            googleOAuthEnabled={Boolean(flow.stack?.google_oauth?.enabled)}
            onGoogleSignIn={() => void flow.startGoogleSignIn()}
            onStepChange={flow.setAdminOtpStep}
            onVerified={flow.handleAdminRegistered}
          />
        </SettingsPanelBody>
      ) : (
        <ConciergeWizardPanels
          step={flow.step}
          busy={flow.busy}
          isInvitee={flow.isInvitee}
          adminEmail={flow.adminEmail}
          credentialMode={flow.credentialMode}
          workspaceId={flow.workspaceId}
          mission={flow.mission}
          workframeName={flow.workframeName}
          workframeTagline={flow.workframeTagline}
          logoUrl={flow.logoUrl}
          displayName={flow.displayName}
          tagline={flow.tagline}
          bio={flow.bio}
          avatarUrl={flow.avatarUrl}
          agentName={flow.agentName}
          agentTagline={flow.agentTagline}
          agentSoul={flow.agentSoul}
          agentAvatar={flow.agentAvatar}
          agentPrimaryModel={flow.agentPrimaryModel}
          agentModelTab={flow.agentModelTab}
          agentSteps={flow.agentSteps}
          inviteEmails={flow.inviteEmails}
          publicUrl={flow.publicUrl}
          httpsStatus={flow.httpsStatus}
          resolveWorkframeName={flow.resolveWorkframeName}
          onAdminEmailChange={flow.setAdminEmail}
          onAdminEmailBlur={() => void flow.persistAdminEmail()}
          onPickMode={(mode) => void flow.pickMode(mode)}
          onCredentialModeChange={flow.setCredentialMode}
          onLogoUrlChange={flow.setLogoUrl}
          onWorkframeNameChange={flow.setWorkframeName}
          onWorkframeTaglineChange={flow.setWorkframeTagline}
          onMissionChange={flow.setMission}
          onDisplayNameChange={flow.setDisplayName}
          onTaglineChange={flow.setTagline}
          onBioChange={flow.setBio}
          onAvatarUrlChange={flow.setAvatarUrl}
          onAgentNameChange={flow.setAgentName}
          onAgentTaglineChange={flow.setAgentTagline}
          onAgentSoulChange={flow.setAgentSoul}
          onAgentAvatarChange={flow.setAgentAvatar}
          onAgentModelTabChange={flow.setAgentModelTab}
          onAgentPrimaryModelChange={flow.setAgentPrimaryModel}
          onAgentFallbackChainChange={flow.setAgentFallbackChain}
          onAgentProvidersConnected={flow.refreshAgentModelStep}
          onInviteEmailsChange={flow.setInviteEmails}
          onPublicUrlChange={flow.setPublicUrl}
          onBindOAuthSave={flow.bindOAuthSave}
          onError={flow.setError}
        />
      )}
    </OnboardingWizardShell>
  )
}
