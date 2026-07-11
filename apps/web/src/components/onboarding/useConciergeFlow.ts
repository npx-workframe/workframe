import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  emailOtpCopy,
  type EmailOtpStep,
} from '@/components/auth/EmailOtpVerification'
import { runPublicHttpsSetup } from '@/components/onboarding/PublicUrlWizardStep'
import { createConciergeLaunchHandlers } from '@/components/onboarding/conciergeFlowLaunch'
import { createConciergeSaveHandlers } from '@/components/onboarding/conciergeFlowSave'
import { createConciergeSmtpHandlers } from '@/components/onboarding/conciergeFlowSmtp'
import {
  buildWizardSteps,
  enrichWizardSteps,
  railStepToConciergeStep,
  stepMeta,
  wizardRailStep,
  type ConciergeStep,
} from '@/components/onboarding/onboardingWizardSteps'
import {
  defaultAgentSoul,
  normalizePublicUrl,
  preferAdminEmailOverSmtpLogin,
  resolveSmtpAdminEmail,
  type SmtpProgressPhase,
} from '@/components/onboarding/conciergeFlowUtils'
import { type OperationStep } from '@/components/ui/OperationProgress'
import { formatWorkframeError, type WorkframeNoticeInfo } from '@/lib/workframeErrors'
import { DEFAULT_USER_AVATAR, DEFAULT_WORKSPACE_LOGO } from '@/lib/workframeAssets'
import { logoAvatarPickerValue, pickRandomPreset } from '@/lib/presetAssets'
import type { FallbackEntry } from '@/lib/hermesCatalogApi'
import {
  workframeAuthApi,
  type ProviderConnectRow,
  type SessionProfile,
  type StackConfig,
  type WorkspaceDetail,
} from '@/lib/workframeAuthApi'
import { fetchWorkframeMeta } from '@/lib/workframeMetaApi'
import { syncSessionInstallScope } from '@/lib/workframeSession'

type UseConciergeFlowOptions = {
  projectName: string
  onComplete: () => void
  inviteToken?: string
  inviteEmail?: string
}
export function useConciergeFlow({
  projectName,
  onComplete,
  inviteToken = '',
  inviteEmail = '',
}: UseConciergeFlowOptions) {
  const isInvitee = Boolean(inviteToken.trim())
  const [inviteeAuthed, setInviteeAuthed] = useState(false)
  const [step, setStep] = useState<ConciergeStep>(isInvitee ? 'profile' : 'intro')
  const [busy, setBusy] = useState(false)
  const [smtpPhase, setSmtpPhase] = useState<SmtpProgressPhase | null>(null)
  const [error, setError] = useState<WorkframeNoticeInfo | null>(null)
  const [stack, setStack] = useState<StackConfig | null>(null)
  const [deploymentMode, setDeploymentMode] = useState<string>('trusted_team')
  const [modeChosen, setModeChosen] = useState(false)
  const [smtpHost, setSmtpHost] = useState('')
  const [smtpPort, setSmtpPort] = useState('587')
  const [smtpUser, setSmtpUser] = useState('')
  const [smtpPass, setSmtpPass] = useState('')
  const [smtpHasPassword, setSmtpHasPassword] = useState(false)
  const [smtpFrom, setSmtpFrom] = useState('')
  const [adminEmail, setAdminEmail] = useState(inviteEmail)
  const [adminAuthNotice, setAdminAuthNotice] = useState<string | null>(null)
  const [adminAuthDevOtp, setAdminAuthDevOtp] = useState('')
  const [adminOtpStep, setAdminOtpStep] = useState<EmailOtpStep>('otp')
  const [adminVerified, setAdminVerified] = useState(false)
  const [hasAdminSession, setHasAdminSession] = useState(false)
  const [smtpFieldsDirty, setSmtpFieldsDirty] = useState(false)
  const [visitedMaxIndex, setVisitedMaxIndex] = useState(0)
  const [workspaceIntegrations, setWorkspaceIntegrations] = useState<WorkspaceDetail['integrations']>()
  const [connectedProviders, setConnectedProviders] = useState<string[]>([])
  const [credentialMode, setCredentialMode] = useState<'byok' | 'workspace'>('byok')
  const [workspaceId, setWorkspaceId] = useState('')
  const [mission, setMission] = useState('')
  const [workframeName, setWorkframeName] = useState(projectName)
  const [workframeTagline, setWorkframeTagline] = useState('')
  const [logoUrl, setLogoUrl] = useState(() => pickRandomPreset('logo') || DEFAULT_WORKSPACE_LOGO)
  const [displayName, setDisplayName] = useState('')
  const [tagline, setTagline] = useState('')
  const [bio, setBio] = useState('')
  const [avatarUrl, setAvatarUrl] = useState(() => pickRandomPreset('user') || DEFAULT_USER_AVATAR)
  const [agentName, setAgentName] = useState(`${projectName} Agent`)
  const [agentTagline, setAgentTagline] = useState('Workframe Manager')
  const [agentSoul, setAgentSoul] = useState('')
  const [agentAvatar, setAgentAvatar] = useState(() => pickRandomPreset('agent') || DEFAULT_USER_AVATAR)
  const [inviteEmails, setInviteEmails] = useState('')
  const [publicUrl, setPublicUrl] = useState('')
  const [httpsStatus, setHttpsStatus] = useState<string | null>(null)
  const [agentPrimaryModel, setAgentPrimaryModel] = useState('')
  const [agentFallbackChain, setAgentFallbackChain] = useState<FallbackEntry[]>([])
  const [agentModelTab, setAgentModelTab] = useState<'keys' | 'model'>('keys')
  const [agentSteps, setAgentSteps] = useState<OperationStep[]>([])
  const [launching, setLaunching] = useState(false)
  const [launchSteps, setLaunchSteps] = useState<OperationStep[]>([])
  const [launchError, setLaunchError] = useState<string | null>(null)
  const [ownerSignInRequired, setOwnerSignInRequired] = useState(false)
  const [bootstrapDone, setBootstrapDone] = useState(false)
  const oauthSaveRef = useRef<(() => Promise<boolean>) | null>(null)
  const bindOAuthSave = useCallback((save: (() => Promise<boolean>) | null) => {
    oauthSaveRef.current = save
  }, [])

  const resolveWorkframeName = useCallback(
    () => workframeName.trim() || projectName,
    [workframeName, projectName],
  )

  const patchInstallStackWhenAllowed = useCallback(async (data: Record<string, unknown>) => {
    const status = await workframeAuthApi.getInstallStatus()
    if (status.install_window_open && !status.install_complete) {
      await workframeAuthApi.patchInstallStack(data)
      return true
    }
    const session = await workframeAuthApi.peekSession()
    if (!session) {
      setOwnerSignInRequired(true)
      return false
    }
    await workframeAuthApi.patchInstallStack(data)
    return true
  }, [])

  const ensureAdminSession = useCallback(async (): Promise<boolean> => {
    let session = await workframeAuthApi.peekSession()
    if (session) return true
    try {
      session = await workframeAuthApi.restoreSession()
      if (session) return true
    } catch {
      // HttpOnly cookie may still be valid on retry
    }
    setStep('admin_auth')
    setError(formatWorkframeError({ error: 'no_session' }, 'Sign in'))
    return false
  }, [])

  const markSmtpDirty = useCallback(() => setSmtpFieldsDirty(true), [])

  const reloadStack = useCallback(async (): Promise<StackConfig | null> => {
    try {
      const session = await workframeAuthApi.peekSession()
      const cfg = await workframeAuthApi.getInstallStack()
      setStack(cfg)
      if (cfg.deployment_mode) {
        setDeploymentMode(cfg.deployment_mode)
        setModeChosen(true)
      }
      if (cfg.app_base_url) setPublicUrl(cfg.app_base_url)
      if (cfg.smtp) {
        const resolvedEmail = resolveSmtpAdminEmail(cfg.smtp, session?.user?.email ?? undefined)
        if (resolvedEmail) {
          setAdminEmail((prev) => preferAdminEmailOverSmtpLogin(prev, resolvedEmail, cfg.smtp?.user))
        }
        setSmtpHasPassword(Boolean(cfg.smtp.has_password))
        if (cfg.smtp.host) {
          setSmtpHost(cfg.smtp.host)
          setSmtpPort(String(cfg.smtp.port || 587))
          if (cfg.smtp.user) setSmtpUser(cfg.smtp.user)
          if (cfg.smtp.from) setSmtpFrom(cfg.smtp.from)
        }
      }
      return cfg
    } catch {
      const session = await workframeAuthApi.peekSession()
      if (session) return null
      try {
        const status = await workframeAuthApi.getInstallStatus()
        if (status.install_complete) setOwnerSignInRequired(true)
      } catch {
        // best-effort — wizard steps surface errors on save
      }
      return null
    }
  }, [])

  const reloadWorkspaceStatus = useCallback(async (wsId: string) => {
    if (!wsId) return
    try {
      const [ws, providers] = await Promise.all([
        workframeAuthApi.getWorkspace(wsId),
        workframeAuthApi.listProviders(wsId),
      ])
      setWorkspaceIntegrations(ws.workspace?.integrations)
      if (ws.workspace?.credential_mode) {
        setCredentialMode(ws.workspace.credential_mode)
      }
      if (ws.workspace) {
        if (ws.workspace.display_name) setWorkframeName(ws.workspace.display_name)
        setMission(ws.workspace.description ?? '')
        if (ws.workspace.avatar_url) setLogoUrl(logoAvatarPickerValue(ws.workspace.avatar_url))
        setWorkframeTagline(ws.workspace.tagline ?? '')
      }
      const connected = (providers.providers ?? [])
        .filter((row: ProviderConnectRow) => row.connected && row.category === 'llm')
        .map((row: ProviderConnectRow) => row.label)
      setConnectedProviders(connected)
    } catch {
      // rail summaries are best-effort
    }
  }, [])

  useEffect(() => {
    if (step !== 'agent_model') return
    setAgentModelTab('keys')
  }, [step])

  const agentModelsComplete = useMemo(() => {
    const primary = agentPrimaryModel.trim()
    const fb0 = agentFallbackChain[0]?.model?.trim() ?? ''
    const fb1 = agentFallbackChain[1]?.model?.trim() ?? ''
    return Boolean(primary && fb0 && fb1)
  }, [agentFallbackChain, agentPrimaryModel])

  const hasLlmProvider = connectedProviders.length > 0

  useEffect(() => {
    void fetchWorkframeMeta()
      .then((meta) => {
        if (meta.install_id) syncSessionInstallScope(meta.install_id)
      })
      .catch(() => {
        // best-effort — cookie auth still works
      })
  }, [])

  useEffect(() => {
    setWorkframeName(projectName)
  }, [projectName])

  useEffect(() => {
    if (!agentSoul) {
      setAgentSoul(defaultAgentSoul(agentName, resolveWorkframeName()))
    }
  }, [agentName, agentSoul, resolveWorkframeName])

  useEffect(() => {
    const trimmed = workframeName.trim()
    if (!trimmed || trimmed === projectName) return
    setAgentName((current) => (current === `${projectName} Agent` ? `${trimmed} Agent` : current))
  }, [workframeName, projectName])

  useEffect(() => {
    void (async () => {
      try {
        if (isInvitee) {
          try {
            await workframeAuthApi.restoreSession()
            try {
              await workframeAuthApi.acceptWorkspaceInvite(inviteToken)
            } catch {
              // already a member
            }
            const me = await workframeAuthApi.getMe()
            setWorkspaceId(me.current_workspace?.id || me.default_workspace?.id || '')
            setInviteeAuthed(true)
          } catch {
            // no session — OTP gate below
          }
          return
        }
        try {
          const status = await workframeAuthApi.getInstallStatus()
          const session = await workframeAuthApi.peekSession()
          if (status.install_complete && !session) {
            setOwnerSignInRequired(true)
            return
          }
        } catch {
          // continue — reloadStack may still succeed during install window
        }
        const cfg = await reloadStack()
        let session = await workframeAuthApi.peekSession()
        if (!session) {
          try {
            session = await workframeAuthApi.restoreSession()
          } catch {
            // pre-verify install path
          }
        }
        const wizard = cfg?.wizard
        const smtpAdmin = String(cfg?.smtp?.admin_email || '').trim()
        if (smtpAdmin) {
          setAdminEmail(smtpAdmin)
        }
        const installAdminVerified = Boolean(
          wizard?.admin_verified || cfg?.smtp?.admin_verified,
        )
        const ownerClaimed = Boolean(wizard?.owner_claimed)
        if (session || ownerClaimed) {
          setHasAdminSession(Boolean(session))
        }
        if (installAdminVerified) {
          setAdminVerified(true)
        }
        if (cfg?.deployment_mode) {
          setModeChosen(true)
        }
        const resumeRaw = String(wizard?.resume_step || '').trim()
        let resumeStep = (
          resumeRaw === 'admin_auth' && installAdminVerified
            ? 'workframe'
            : resumeRaw === 'smtp' && installAdminVerified && cfg?.smtp?.setup_complete
              ? 'workframe'
              : resumeRaw
        ) as ConciergeStep
        const deploymentChosen = Boolean(cfg?.deployment_mode)
        if (
          !deploymentChosen
          && ['publish', 'smtp', 'admin_auth', 'workframe', 'billing', 'integrations', 'profile', 'agent', 'agent_model', 'invites'].includes(
            resumeStep,
          )
        ) {
          resumeStep = ownerClaimed || smtpAdmin ? 'welcome' : 'intro'
        }
        if (!ownerClaimed && !smtpAdmin && resumeStep !== 'intro') {
          resumeStep = 'intro'
        }
        const allowedSteps: ConciergeStep[] = [
          'intro', 'welcome', 'publish', 'smtp', 'admin_auth', 'workframe', 'billing',
          'integrations', 'profile', 'agent', 'agent_model', 'invites', 'done',
        ]
        if (allowedSteps.includes(resumeStep) && resumeStep !== 'intro') {
          setStep(resumeStep)
        }
        try {
          const me = await workframeAuthApi.getMe()
          const wsId = me.current_workspace?.id || me.default_workspace?.id || ''
          if (wsId) setWorkspaceId(wsId)
          if (me.user.email) {
            setAdminEmail((prev) =>
              preferAdminEmailOverSmtpLogin(prev, me.user.email || '', cfg?.smtp?.user),
            )
          }
          if (me.ok && installAdminVerified) {
            setAdminVerified(true)
            setHasAdminSession(true)
          }

          const onboarding = await workframeAuthApi.getOnboarding()
          if (onboarding.complete) {
            onComplete()
          }
        } catch {
          // signed-out install path — user completes SMTP + OTP first
        }
      } finally {
        setBootstrapDone(true)
      }
    })()
  }, [inviteEmail, inviteToken, isInvitee, onComplete, reloadStack])

  useEffect(() => {
    if (!bootstrapDone || isInvitee) return
    void workframeAuthApi.getInstallStatus()
      .then((status) => {
        if (!status.install_window_open || status.install_complete) return
        return patchInstallStackWhenAllowed({ wizard_step: step })
      })
      .catch(() => {})
  }, [bootstrapDone, isInvitee, patchInstallStackWhenAllowed, step])

  const smtpReady = useMemo(
    () => Boolean(stack?.smtp?.configured || stack?.smtp?.has_password || smtpHost.trim()),
    [stack?.smtp?.configured, stack?.smtp?.has_password, smtpHost],
  )

  const smtpSetupComplete = useMemo(
    () => Boolean(stack?.smtp?.setup_complete),
    [stack?.smtp?.setup_complete],
  )

  const canKeepAdminSetup = useMemo(
    () => smtpSetupComplete && adminVerified && !smtpFieldsDirty,
    [adminVerified, smtpFieldsDirty, smtpSetupComplete],
  )

  const canContinueFromSmtp = useMemo(() => {
    if (canKeepAdminSetup) return true
    if (adminVerified) return true
    if (!adminEmail.trim()) return false
    return smtpSetupComplete
  }, [adminVerified, adminEmail, canKeepAdminSetup, smtpSetupComplete])

  useEffect(() => {
    if (isInvitee || modeChosen) return
    if (step === 'smtp' || step === 'admin_auth' || step === 'publish') {
      setStep(adminEmail.trim() ? 'welcome' : 'intro')
    }
  }, [adminEmail, isInvitee, modeChosen, step])

  useEffect(() => {
    if (step !== 'smtp') return
    void workframeAuthApi.peekSession().then((session) => {
      setHasAdminSession(Boolean(session))
      if (session?.user?.email) {
        setAdminEmail((prev) => preferAdminEmailOverSmtpLogin(prev, session.user.email || '', smtpUser))
      }
    })
  }, [smtpUser, step])

  const unlockedMaxIndex = useMemo(() => {
    const steps = buildWizardSteps(deploymentMode, modeChosen, isInvitee)
    if (!steps.length) return 0
    const idx = (id: string) => steps.findIndex((s) => s.id === id)
    if (isInvitee) {
      if (inviteeAuthed && workspaceId) return steps.length - 1
      return Math.max(idx('profile'), 0)
    }
    let max = 0
    if (modeChosen) max = Math.max(max, idx('welcome'))
    if (deploymentMode === 'single_user_local' && modeChosen && adminVerified) {
      max = Math.max(max, idx('workframe'))
    }
    if (deploymentMode !== 'single_user_local' && modeChosen) {
      max = Math.max(max, idx('smtp'))
    }
    if (smtpReady && adminVerified) {
      max = Math.max(max, idx('workframe'))
    }
    if (adminVerified && workspaceId) {
      max = steps.length - 1
    }
    return max
  }, [adminVerified, deploymentMode, inviteeAuthed, isInvitee, modeChosen, smtpReady, workspaceId])

  const maxReachableIndex = Math.max(visitedMaxIndex, unlockedMaxIndex)

  useEffect(() => {
    if (step === 'admin_auth' && adminVerified) {
      setStep('workframe')
    }
  }, [adminVerified, step])

  // ponytail: admin_auth without a sent OTP (resume) — back to SMTP form
  useEffect(() => {
    if (step !== 'admin_auth' || adminVerified) return
    if (adminAuthNotice || adminAuthDevOtp) return
    setAdminOtpStep('email')
    setStep('smtp')
  }, [step, adminVerified, adminAuthNotice, adminAuthDevOtp])

  useEffect(() => {
    if (workspaceId) void reloadWorkspaceStatus(workspaceId)
  }, [workspaceId, reloadWorkspaceStatus, step])

  useEffect(() => {
    const rail = wizardRailStep(step)
    const idx = buildWizardSteps(deploymentMode, modeChosen, isInvitee).findIndex((s) => s.id === rail)
    if (idx >= 0) setVisitedMaxIndex((prev) => Math.max(prev, idx))
  }, [step, deploymentMode, modeChosen, isInvitee])

  async function pickMode(mode: string) {
    setBusy(true)
    setError(null)
    try {
      setDeploymentMode(mode)
      setModeChosen(true)
      const patched = await patchInstallStackWhenAllowed({ deployment_mode: mode })
      if (!patched) return
      if (mode === 'single_user_local') {
        const email = adminEmail.trim().toLowerCase()
        if (!email || !email.includes('@')) {
          setError(formatWorkframeError({ error: 'email_required' }, 'Choose deployment'))
          return
        }
        await workframeAuthApi.completeSetup({
          workframe_name: resolveWorkframeName(),
          agent_name: agentName,
        })
        await patchInstallStackWhenAllowed({ smtp: { admin_email: email } })
        if (!hasAdminSession) {
          await workframeAuthApi.localBootstrap(displayName || email.split('@')[0] || 'Owner', email)
        }
        const me = await workframeAuthApi.getMe()
        setWorkspaceId(me.current_workspace?.id || me.default_workspace?.id || '')
        setAdminVerified(true)
        setHasAdminSession(true)
        setStep('workframe')
      } else if (mode === 'public_multi_user') {
        setStep('publish')
      } else {
        await workframeAuthApi.completeSetup({
          workframe_name: resolveWorkframeName(),
          agent_name: agentName,
        })
        setStep('smtp')
      }
    } catch (err) {
      setError(formatWorkframeError(err, 'Save mode'))
    } finally {
      setBusy(false)
    }
  }

  const startGoogleSignIn = useCallback(async () => {
    setBusy(true)
    setError(null)
    try {
      const result = await workframeAuthApi.startGoogleAuth(adminEmail.trim(), inviteToken)
      window.location.href = result.auth_url
    } catch (err) {
      setError(formatWorkframeError(err, 'Google sign-in'))
      setBusy(false)
    }
  }, [adminEmail, inviteToken])


  const { finishInviteeOnboarding, finishInstall, sendInvites } = createConciergeLaunchHandlers({
    workspaceId,
    inviteEmails,
    isInvitee,
    deploymentMode,
    adminVerified,
    adminEmail,
    agentPrimaryModel,
    displayName,
    bio,
    agentName,
    agentTagline,
    agentSoul,
    resolveWorkframeName,
    onComplete,
    setLaunching,
    setLaunchError,
    setLaunchSteps,
    setBusy,
    setStep,
  })

  const {
    saveIntegrations,
    skipIntegrations,
    saveBilling,
    saveWorkframe,
    saveProfile,
    saveAgentModel,
    saveAgent,
  } = createConciergeSaveHandlers({
    workspaceId,
    credentialMode,
    mission,
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
    agentFallbackChain,
    connectedProviders,
    isInvitee,
    deploymentMode,
    oauthSaveRef,
    resolveWorkframeName,
    ensureAdminSession,
    reloadStack,
    finishInviteeOnboarding,
    finishInstall,
    setBusy,
    setError,
    setStep,
    setAgentModelTab,
    setAgentPrimaryModel,
    setAgentSteps,
  })

  const { testSmtpOnly, persistAdminEmail, continueFromSmtp } = createConciergeSmtpHandlers({
    smtpPort,
    smtpFrom,
    smtpPass,
    smtpHost,
    smtpUser,
    adminEmail,
    smtpHasPassword,
    smtpSetupComplete,
    smtpFieldsDirty,
    canKeepAdminSetup,
    adminVerified,
    patchInstallStackWhenAllowed,
    reloadStack,
    setSmtpHasPassword,
    setSmtpPass,
    setSmtpFieldsDirty,
    setSmtpPhase,
    setBusy,
    setError,
    setAdminAuthDevOtp,
    setAdminAuthNotice,
    setAdminOtpStep,
    setStep,
  })

  async function continueFromIntro() {
    const email = adminEmail.trim().toLowerCase()
    if (!email || !email.includes('@')) {
      setError(formatWorkframeError({ error: 'email_required' }, 'Admin email'))
      return
    }
    setBusy(true)
    setError(null)
    try {
      const profile = await workframeAuthApi.registerInstallAdmin(
        displayName || email.split('@')[0] || 'Owner',
        email,
      )
      setWorkspaceId(profile.current_workspace?.id || profile.default_workspace?.id || '')
      setHasAdminSession(true)
      setStep('welcome')
    } catch (err) {
      setError(formatWorkframeError(err, 'Admin email'))
    } finally {
      setBusy(false)
    }
  }

  function handleAdminRegistered(profile: SessionProfile) {
    setWorkspaceId(profile.current_workspace?.id || profile.default_workspace?.id || '')
    setAdminAuthNotice(null)
    setAdminAuthDevOtp('')
    setAdminVerified(true)
    setHasAdminSession(true)
    setSmtpFieldsDirty(false)
    if (deploymentMode === 'public_multi_user') {
      void workframeAuthApi
        .completeSetup({
          workframe_name: resolveWorkframeName(),
          agent_name: agentName,
        })
        .catch(() => {})
    }
    setStep('workframe')
  }

  function handleOwnerSignedIn(profile: SessionProfile) {
    setOwnerSignInRequired(false)
    setWorkspaceId(profile.current_workspace?.id || profile.default_workspace?.id || '')
    if (profile.user.email) setAdminEmail(profile.user.email)
    setAdminVerified(true)
    setHasAdminSession(true)
    void reloadStack()
    if (!modeChosen) {
      setStep('intro')
      return
    }
    if (deploymentMode === 'single_user_local') {
      setStep('workframe')
    } else if (deploymentMode === 'public_multi_user' && !smtpReady) {
      setStep('publish')
    } else if (!smtpReady) {
      setStep('smtp')
    } else {
      setStep('workframe')
    }
  }

  async function handleInviteeVerified(profile: SessionProfile) {
    const wsId = profile.current_workspace?.id || profile.default_workspace?.id || ''
    setWorkspaceId(wsId)
    setInviteeAuthed(true)
    setStep('profile')
    if (wsId) {
      await reloadWorkspaceStatus(wsId)
    }
  }

  useEffect(() => {
    if (!isInvitee || !inviteeAuthed || credentialMode !== 'workspace') return
    setAgentModelTab('model')
  }, [credentialMode, inviteeAuthed, isInvitee])

  async function testPublicUrl() {
    setBusy(true)
    try {
      const url = normalizePublicUrl(publicUrl)
      setPublicUrl(url)
      const patched = await patchInstallStackWhenAllowed({ app_base_url: url })
      if (!patched) return
      const result = await workframeAuthApi.testInstallUrl(url)
      if (!result.ok) {
        setError({
          tone: 'caution',
          message: result.error || 'Connection test failed',
          hint: result.hint || 'Confirm DNS points at this server, then try again.',
        })
      } else {
        setError({
          tone: 'info',
          message: 'Connection test passed.',
          hint: 'Your public URL is reachable from this install.',
        })
      }
    } catch (err) {
      setError(formatWorkframeError(err, 'URL test'))
    } finally {
      setBusy(false)
    }
  }

  async function setupPublicHttps() {
    setBusy(true)
    setHttpsStatus(null)
    try {
      const url = normalizePublicUrl(publicUrl)
      setPublicUrl(url)
      setHttpsStatus(await runPublicHttpsSetup(url))
    } finally {
      setBusy(false)
    }
  }

  const wizardSteps = useMemo(() => {
    const base = buildWizardSteps(deploymentMode, modeChosen, isInvitee)
    return enrichWizardSteps(base, {
      deploymentMode,
      modeChosen,
      stack,
      smtpHost,
      smtpUser,
      adminEmail,
      adminVerified,
      workspaceIntegrations,
      credentialMode,
      mission,
      workframeName,
      workframeTagline,
      displayName,
      userTagline: tagline,
      connectedProviders,
      agentName,
      agentTagline,
      agentPrimaryModel,
      inviteEmails,
      publicUrl,
    })
  }, [
    adminEmail,
    adminVerified,
    agentName,
    agentTagline,
    agentPrimaryModel,
    connectedProviders,
    credentialMode,
    deploymentMode,
    displayName,
    inviteEmails,
    isInvitee,
    mission,
    modeChosen,
    publicUrl,
    smtpHost,
    smtpUser,
    stack,
    tagline,
    workframeName,
    workframeTagline,
    workspaceIntegrations,
  ])

  const currentRailStep = wizardRailStep(step)

  const showBrandLogo = useMemo(() => {
    const workframeIdx = wizardSteps.findIndex((s) => s.id === 'workframe')
    if (workframeIdx < 0) return false
    return step === 'workframe' || visitedMaxIndex >= workframeIdx
  }, [step, visitedMaxIndex, wizardSteps])

  function goToRailStep(railId: string) {
    if (isInvitee && railId === 'smtp') return
    if (!modeChosen && (railId === 'smtp' || railId === 'publish')) return
    if (busy) return
    const targetIdx = wizardSteps.findIndex((s) => s.id === railId)
    if (targetIdx < 0 || targetIdx > maxReachableIndex) return
    setError(null)
    setStep(railStepToConciergeStep(railId, step, adminVerified))
  }
  const meta = stepMeta(step, projectName, isInvitee)
  const title = meta.title
  const description =
    step === 'admin_auth'
      ? emailOtpCopy(adminOtpStep, adminEmail, adminAuthDevOtp, 'register')
      : meta.description

  return {
    isInvitee,
    inviteToken,
    inviteEmail,
    projectName,
    bootstrapDone,
    ownerSignInRequired,
    inviteeAuthed,
    launching,
    launchSteps,
    launchError,
    step,
    busy,
    error,
    stack,
    smtpPhase,
    smtpHost,
    smtpPort,
    smtpUser,
    smtpPass,
    smtpHasPassword,
    smtpFrom,
    adminEmail,
    adminOtpStep,
    adminAuthDevOtp,
    adminAuthNotice,
    adminVerified,
    deploymentMode,
    workspaceId,
    credentialMode,
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
    agentFallbackChain,
    agentModelTab,
    agentModelsComplete,
    hasLlmProvider,
    connectedProviders,
    agentSteps,
    inviteEmails,
    publicUrl,
    httpsStatus,
    wizardSteps,
    currentRailStep,
    showBrandLogo,
    maxReachableIndex,
    title,
    description,
    smtpSetupComplete,
    canKeepAdminSetup,
    canContinueFromSmtp,
    resolveWorkframeName,
    patchInstallStackWhenAllowed,
    bindOAuthSave,
    setStep,
    setBusy,
    setError,
    setAdminEmail,
    setSmtpHost,
    setSmtpPort,
    setSmtpUser,
    setSmtpPass,
    setSmtpFrom,
    setAdminOtpStep,
    setCredentialMode,
    setLogoUrl,
    setWorkframeName,
    setWorkframeTagline,
    setMission,
    setDisplayName,
    setTagline,
    setBio,
    setAvatarUrl,
    setAgentName,
    setAgentTagline,
    setAgentSoul,
    setAgentAvatar,
    setAgentModelTab,
    setAgentPrimaryModel,
    setAgentFallbackChain,
    setInviteEmails,
    setPublicUrl,
    markSmtpDirty,
    pickMode,
    startGoogleSignIn,
    testSmtpOnly,
    continueFromSmtp,
    continueFromIntro,
    persistAdminEmail,
    saveIntegrations,
    skipIntegrations,
    saveBilling,
    saveWorkframe,
    saveProfile,
    saveAgentModel,
    saveAgent,
    refreshAgentModelStep: () => {
      if (workspaceId) void reloadWorkspaceStatus(workspaceId)
    },
    sendInvites,
    finishInstall,
    testPublicUrl,
    setupPublicHttps,
    goToRailStep,
    handleAdminRegistered,
    handleOwnerSignedIn,
    handleInviteeVerified,
  }
}
