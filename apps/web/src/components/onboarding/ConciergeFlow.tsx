import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import {
  authStartNotice,
  EmailOtpVerification,
  emailOtpCopy,
  type EmailOtpStep,
} from '@/components/auth/EmailOtpVerification'

import { OnboardingIdentityFields } from '@/components/onboarding/OnboardingIdentityFields'
import {
  AGENT_SAVE_STEP_LABELS,
  FINISH_INSTALL_STEP_LABELS,
  OnboardingLaunchScreen,
} from '@/components/onboarding/OnboardingLaunchScreen'
import { buildWizardSteps, enrichWizardSteps, railStepToConciergeStep, stepMeta, wizardRailStep, type ConciergeStep } from '@/components/onboarding/onboardingWizardSteps'
import { OnboardingWizardShell } from '@/components/onboarding/OnboardingWizardShell'
import { DialogFrame } from '@/components/dialogs/DialogFrame'
import { ThemeSwitcher } from '@/components/shell/ThemeSwitcher'
import { PlatformIdentityPanel } from '@/components/settings/PlatformIdentityPanel'
import { PublicUrlWizardStep } from '@/components/onboarding/PublicUrlWizardStep'
import { WorkframeIntegrationsStep } from '@/components/onboarding/WorkframeIntegrationsStep'
import { WfActionButton } from '@/components/ui/WfActionButton'
import { BootScreen } from '@/components/shell/BootScreen'
import { OperationProgress, stepsFromApiResults, type OperationStep } from '@/components/ui/OperationProgress'
import { SecretInput } from '@/components/ui/SecretInput'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { WorkframeNotice } from '@/components/ui/WorkframeNotice'
import { ModelPickerPanel } from '@/components/settings/ModelPickerPanel'
import { ProviderConnectPanel } from '@/components/workspace/ProviderConnectPanel'
import { formatWorkframeError, formatWorkframeErrorMessage, type WorkframeNoticeInfo } from '@/lib/workframeErrors'
import { DEFAULT_USER_AVATAR, DEFAULT_WORKSPACE_LOGO } from '@/lib/workframeAssets'
import { agentAvatarPersistPayload, logoAvatarPersistPayload, logoAvatarPickerValue, pickRandomPreset, userAvatarPersistPayload } from '@/lib/presetAssets'
import {
  workframeAuthApi,
  type ProviderConnectRow,
  type SessionProfile,
  type StackConfig,
  type WorkspaceDetail,
} from '@/lib/workframeAuthApi'
import { fetchWorkframeMeta } from '@/lib/workframeMetaApi'
import { isElectronRuntime } from '@/lib/runtime'
import { syncSessionInstallScope } from '@/lib/workframeSession'

export type { ConciergeStep } from '@/components/onboarding/onboardingWizardSteps'

type ConciergeFlowProps = {
  projectName: string
  onComplete: () => void
  inviteToken?: string
  inviteEmail?: string
}

const MODES = [
  { id: 'single_user_local', title: 'Just me on this machine', blurb: 'Solo use — skip email sign-in.' },
  { id: 'trusted_team', title: 'My team on Docker', blurb: 'Teammates sign in with email verification.' },
  { id: 'public_multi_user', title: 'Public on the web', blurb: 'Shared URL — DNS, HTTPS, and full security.' },
] as const

function normalizePublicUrl(url: string): string {
  const trimmed = url.trim().replace(/\/+$/, '')
  if (!trimmed) return ''
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  return `https://${trimmed}`
}

function defaultAgentSoul(name: string, project: string) {
  return `You are ${name}, the Workframe Manager for ${project}. You help the owner run rooms, agents, and day-to-day work.`
}

function OnboardingAuthGate({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <div className="wf-onboarding-page wf-onboarding-page--gate">
      <div className="wf-onboarding-page__theme">
        <ThemeSwitcher />
      </div>
      <DialogFrame
        open
        modal={!isElectronRuntime()}
        onOpenChange={() => {}}
        title={title}
        description={description}
        showClose={false}
        contentClassName="wf-auth-dialog"
      >
        {children}
      </DialogFrame>
    </div>
  )
}

type SmtpProgressPhase = 'setup' | 'smtp' | 'test-email' | 'verify'

const SMTP_PROGRESS: { id: SmtpProgressPhase; label: string }[] = [
  { id: 'setup', label: 'Prepare Workframe' },
  { id: 'smtp', label: 'Save SMTP settings' },
  { id: 'test-email', label: 'Send test email' },
  { id: 'verify', label: 'Start admin verification' },
]

function buildFinishInstallSteps(
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

function SmtpProgressList({ phase }: { phase: SmtpProgressPhase | null }) {
  if (!phase) return null
  const activeIdx = SMTP_PROGRESS.findIndex((s) => s.id === phase)
  return (
    <ul className="wf-onboarding-progress" aria-live="polite" aria-busy="true">
      {SMTP_PROGRESS.map((s, i) => {
        const done = i < activeIdx
        const current = i === activeIdx
        return (
          <li key={s.id} className={done ? 'is-done' : current ? 'is-current' : ''}>
            <span className="wf-onboarding-progress__icon" aria-hidden="true">
              {done ? '✓' : current ? '…' : ''}
            </span>
            <span>{s.label}</span>
          </li>
        )
      })}
    </ul>
  )
}

export function ConciergeFlow({ projectName, onComplete, inviteToken = '', inviteEmail = '' }: ConciergeFlowProps) {
  const isInvitee = Boolean(inviteToken && inviteEmail)
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
  const [providersTab, setProvidersTab] = useState<'keys' | 'accounts' | 'model'>('keys')
  const [agentSteps, setAgentSteps] = useState<OperationStep[]>([])
  const [launching, setLaunching] = useState(false)
  const [launchSteps, setLaunchSteps] = useState<OperationStep[]>([])
  const [launchError, setLaunchError] = useState<string | null>(null)
  const [ownerSignInRequired, setOwnerSignInRequired] = useState(false)
  const [bootstrapDone, setBootstrapDone] = useState(false)
  const oauthSaveRef = useRef<(() => Promise<boolean>) | null>(null)

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

  const reloadStack = useCallback(async () => {
    try {
      const cfg = await workframeAuthApi.getInstallStack()
      setStack(cfg)
      if (cfg.deployment_mode) {
        setDeploymentMode(cfg.deployment_mode)
        setModeChosen(true)
      }
      if (cfg.app_base_url) setPublicUrl(cfg.app_base_url)
      if (cfg.smtp) {
        if (cfg.smtp.admin_email) setAdminEmail(cfg.smtp.admin_email)
        setSmtpHasPassword(Boolean(cfg.smtp.has_password))
        if (cfg.smtp.host) {
          setSmtpHost(cfg.smtp.host)
          setSmtpPort(String(cfg.smtp.port || 587))
          if (cfg.smtp.user) setSmtpUser(cfg.smtp.user)
          if (cfg.smtp.from) setSmtpFrom(cfg.smtp.from)
        }
      }
    } catch {
      const session = await workframeAuthApi.peekSession()
      if (session) return
      try {
        const status = await workframeAuthApi.getInstallStatus()
        if (status.install_complete) setOwnerSignInRequired(true)
      } catch {
        // best-effort — wizard steps surface errors on save
      }
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
        await reloadStack()
        try {
          const me = await workframeAuthApi.getMe()
          const wsId = me.current_workspace?.id || me.default_workspace?.id || ''
          if (wsId) setWorkspaceId(wsId)
          if (me.user.email) setAdminEmail(me.user.email)
          if (me.ok) setAdminVerified(true)

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

  const smtpReady = useMemo(
    () => Boolean(stack?.smtp?.configured || stack?.smtp?.has_password || smtpHost.trim()),
    [stack?.smtp?.configured, stack?.smtp?.has_password, smtpHost],
  )

  const smtpSetupComplete = useMemo(
    () => Boolean(stack?.smtp?.setup_complete),
    [stack?.smtp?.setup_complete],
  )

  const canContinueFromSmtp = useMemo(() => {
    if (adminVerified) return true
    if (!adminEmail.trim()) return false
    return smtpSetupComplete
  }, [adminVerified, adminEmail, smtpSetupComplete])

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
      max = Math.max(max, idx('integrations'))
    }
    if (deploymentMode !== 'single_user_local' && modeChosen) {
      max = Math.max(max, idx('smtp'))
    }
    if (smtpReady && adminVerified) {
      max = Math.max(max, idx('integrations'))
    }
    if (adminVerified && workspaceId) {
      max = steps.length - 1
    }
    return max
  }, [adminVerified, deploymentMode, inviteeAuthed, isInvitee, modeChosen, smtpReady, workspaceId])

  const maxReachableIndex = Math.max(visitedMaxIndex, unlockedMaxIndex)

  useEffect(() => {
    if (step === 'admin_auth' && adminVerified) {
      setStep('integrations')
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
        await workframeAuthApi.completeSetup({
          workframe_name: resolveWorkframeName(),
          agent_name: agentName,
        })
        await workframeAuthApi.localBootstrap(displayName || 'Owner')
        const me = await workframeAuthApi.getMe()
        setWorkspaceId(me.current_workspace?.id || me.default_workspace?.id || '')
        setAdminVerified(true)
        setStep('integrations')
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

  async function saveSmtpForInstall(requirePassword = false): Promise<boolean> {
    const port = Number(smtpPort) || 587
    const from = smtpFrom.trim()
    const password = smtpPass.trim()
    if (requirePassword && !password && !smtpHasPassword) {
      throw new Error('SMTP password is required')
    }
    const patched = await patchInstallStackWhenAllowed({
      smtp: {
        host: smtpHost,
        port,
        user: smtpUser,
        admin_email: adminEmail.trim(),
        ...(password ? { password } : {}),
        ...(from ? { from } : {}),
        secure: port === 465 ? 'ssl' : 'starttls',
      },
    })
    if (!patched) return false
    if (password) {
      setSmtpHasPassword(true)
      setSmtpPass('')
    }
    await reloadStack()
    return true
  }

  async function testSmtpOnly(): Promise<boolean> {
    setBusy(true)
    setError(null)
    setSmtpPhase('setup')
    try {
      setSmtpPhase('smtp')
      const ok = await saveSmtpForInstall(true)
      if (!ok) return false
      if (!adminEmail.trim()) {
        throw new Error('Admin email is required')
      }
      setSmtpPhase('test-email')
      const test = await workframeAuthApi.testInstallEmail(adminEmail.trim())
      if (!test.ok) throw new Error('Test email failed')
      await reloadStack()
      return true
    } catch (err) {
      setError(formatWorkframeError(err, 'SMTP test'))
      return false
    } finally {
      setBusy(false)
      setSmtpPhase(null)
    }
  }

  async function proceedToAdminOtp() {
    setBusy(true)
    setError(null)
    try {
      const ok = await saveSmtpForInstall(false)
      if (!ok) return
      if (!adminEmail.trim()) {
        throw new Error('Admin email is required')
      }
      const start = await workframeAuthApi.startEmailVerification(adminEmail.trim())
      const { devOtp, notice } = authStartNotice(start, adminEmail.trim())
      setAdminAuthDevOtp(devOtp)
      setAdminAuthNotice(notice)
      setAdminOtpStep('otp')
      setStep('admin_auth')
    } catch (err) {
      setError(formatWorkframeError(err, 'Send verification code'))
    } finally {
      setBusy(false)
    }
  }

  async function persistAdminEmail() {
    const email = adminEmail.trim()
    if (!email) return
    await patchInstallStackWhenAllowed({ smtp: { admin_email: email } })
  }

  async function continueFromSmtp() {
    if (adminVerified) {
      setBusy(true)
      setError(null)
      try {
        if (smtpHost.trim()) {
          const ok = await saveSmtpForInstall(false)
          if (!ok) return
        }
        setStep('integrations')
      } catch (err) {
        setError(formatWorkframeError(err, 'Save SMTP'))
      } finally {
        setBusy(false)
      }
      return
    }
    if (!smtpSetupComplete) {
      setError({
        tone: 'caution',
        message: 'Send a test email before continuing.',
        hint: 'Use “Send test email” once to verify SMTP. After that you can move between steps without testing again.',
      })
      return
    }
    await proceedToAdminOtp()
  }

  function handleAdminRegistered(profile: SessionProfile) {
    setWorkspaceId(profile.current_workspace?.id || profile.default_workspace?.id || '')
    setAdminAuthNotice(null)
    setAdminAuthDevOtp('')
    setAdminVerified(true)
    setStep('integrations')
  }

  function handleOwnerSignedIn(profile: SessionProfile) {
    setOwnerSignInRequired(false)
    setWorkspaceId(profile.current_workspace?.id || profile.default_workspace?.id || '')
    if (profile.user.email) setAdminEmail(profile.user.email)
    setAdminVerified(true)
    void reloadStack()
    if (!modeChosen) {
      setStep('intro')
      return
    }
    if (deploymentMode === 'single_user_local') {
      setStep('integrations')
    } else if (deploymentMode === 'public_multi_user' && !smtpReady) {
      setStep('publish')
    } else if (!smtpReady) {
      setStep('smtp')
    } else {
      setStep('integrations')
    }
  }

  function handleInviteeVerified(profile: SessionProfile) {
    setWorkspaceId(profile.current_workspace?.id || profile.default_workspace?.id || '')
    setInviteeAuthed(true)
    setStep('profile')
  }

  async function saveIntegrations(skipOAuth = false) {
    setBusy(true)
    setError(null)
    try {
      if (!(await ensureAdminSession())) return
      if (!skipOAuth) {
        const oauthSave = oauthSaveRef.current
        if (oauthSave) {
          const ok = await oauthSave()
          if (!ok) return
        }
      }
      await reloadStack()
      if (workspaceId) {
        await workframeAuthApi.patchWorkspaceIntegrations(workspaceId, {
          admin_integrations_done: true,
        })
      }
      setStep('billing')
    } catch (err) {
      setError(formatWorkframeError(err, 'Save integrations'))
    } finally {
      setBusy(false)
    }
  }

  async function skipToBilling() {
    await saveIntegrations(true)
  }

  async function saveBilling() {
    if (!workspaceId) {
      setStep('workframe')
      return
    }
    setBusy(true)
    try {
      if (!(await ensureAdminSession())) return
      await workframeAuthApi.patchWorkspaceIntegrations(workspaceId, {
        credential_mode: credentialMode,
        admin_integrations_done: true,
      })
      setStep('workframe')
    } catch (err) {
      setError(formatWorkframeError(err, 'Save billing'))
    } finally {
      setBusy(false)
    }
  }

  async function saveWorkframe() {
    if (!workspaceId) return
    setBusy(true)
    try {
      if (!(await ensureAdminSession())) return
      const logo = logoUrl ? logoAvatarPersistPayload(logoUrl) : null
      await workframeAuthApi.patchWorkspace(workspaceId, {
        display_name: resolveWorkframeName(),
        description: mission,
        ...(logo ?? {}),
        tagline: workframeTagline,
      })
      await workframeAuthApi.patchWorkspaceIntegrations(workspaceId, {
        admin_onboarding_done: true,
      })
      setStep('profile')
    } catch (err) {
      setError(formatWorkframeError(err, 'Save workframe'))
    } finally {
      setBusy(false)
    }
  }

  async function saveProfile() {
    setBusy(true)
    try {
      const avatar = avatarUrl ? userAvatarPersistPayload(avatarUrl) : null
      await workframeAuthApi.updateMe({
        display_name: displayName || undefined,
        tagline: tagline || undefined,
        bio: bio || undefined,
        ...(avatar ?? {}),
      })
      setStep('providers')
    } catch (err) {
      setError(formatWorkframeError(err, 'Save profile'))
    } finally {
      setBusy(false)
    }
  }

  async function saveProviders() {
    setBusy(true)
    setError(null)
    try {
      setStep('agent')
    } catch (err) {
      setError(formatWorkframeError(err, 'Save providers'))
    } finally {
      setBusy(false)
    }
  }

  async function saveAgent() {
    if (!workspaceId) return
    setBusy(true)
    setError(null)
    setAgentSteps(AGENT_SAVE_STEP_LABELS.map((entry, index) => ({
      ...entry,
      status: index === 0 ? 'active' : 'pending',
    })))
    try {
      const soul = agentSoul.trim() || defaultAgentSoul(agentName, resolveWorkframeName())
      const avatar = agentAvatar ? agentAvatarPersistPayload(agentAvatar) : null
      await workframeAuthApi.patchNativeAgent({
        workspace_id: workspaceId,
        display_name: agentName,
        tagline: agentTagline,
        ...(avatar ?? {}),
        soul,
      })
      setAgentSteps(AGENT_SAVE_STEP_LABELS.map((entry) => ({ ...entry, status: 'done' })))
      if (isInvitee) {
        await finishInviteeOnboarding()
        return
      }
      if (deploymentMode === 'public_multi_user') {
        if (!adminVerified) {
          setStep('smtp')
          return
        }
        if (publicUrl.trim()) {
          await finishInstall()
        } else {
          setStep('publish')
        }
      } else {
        setStep('invites')
      }
    } catch (err) {
      setAgentSteps(
        AGENT_SAVE_STEP_LABELS.map((entry) => ({
          ...entry,
          status: 'error',
          detail: err instanceof Error ? err.message : 'Failed',
        })),
      )
      setError(formatWorkframeError(err, 'Save agent'))
    } finally {
      setBusy(false)
      if (!isInvitee) {
        window.setTimeout(() => setAgentSteps([]), 600)
      }
    }
  }

  async function sendInvites() {
    if (!workspaceId) return
    const emails = inviteEmails.split(/[,\s]+/).map((e) => e.trim()).filter(Boolean)
    setLaunching(true)
    setLaunchError(null)
    setLaunchSteps(
      buildFinishInstallSteps(undefined, 'pending', { includeInvites: true }).map((entry, index) => ({
        ...entry,
        status: index === 0 ? 'active' : 'pending',
      })),
    )
    try {
      for (let index = 0; index < emails.length; index += 1) {
        const email = emails[index]!
        setLaunchSteps((current) =>
          current.map((entry) =>
            entry.id === 'invites'
              ? { ...entry, status: 'active', detail: `Sending ${index + 1} of ${emails.length}…` }
              : entry,
          ),
        )
        await workframeAuthApi.createWorkspaceInvite(workspaceId, { email, role: 'member' })
      }
      if (emails.length) {
        setLaunchSteps((current) =>
          current.map((entry) =>
            entry.id === 'invites' ? { ...entry, status: 'done', detail: `${emails.length} sent` } : entry,
          ),
        )
      } else {
        setLaunchSteps((current) => current.filter((entry) => entry.id !== 'invites'))
      }
      await finishInstall({ alreadyLaunching: true })
    } catch (err) {
      const message = formatWorkframeErrorMessage(err, 'Send invites')
      setLaunchError(message)
      setLaunchSteps((current) =>
        current.map((entry) =>
          entry.status === 'active' ? { ...entry, status: 'error', detail: message } : entry,
        ),
      )
      setLaunching(true)
    }
  }

  async function finishInviteeOnboarding() {
    if (!workspaceId) {
      setLaunchError(formatWorkframeErrorMessage(new Error('workspace_missing'), 'Finish join'))
      return
    }
    setLaunching(true)
    setLaunchError(null)
    setLaunchSteps(
      buildFinishInstallSteps(undefined, 'pending').map((entry, index) => ({
        ...entry,
        status: index === 0 ? 'active' : 'pending',
      })),
    )
    setBusy(true)
    try {
      const result = await workframeAuthApi.bootstrapAgentFromTemplate('workframe-agent', {
        workspace_id: workspaceId,
        display_name: agentName,
        tagline: agentTagline,
        soul: agentSoul.trim() || defaultAgentSoul(agentName, resolveWorkframeName()),
        bind_session: true,
      })
      if (!result.ok || !result.room_id) {
        throw new Error(result.error || 'Agent bootstrap failed')
      }
      setLaunchSteps(buildFinishInstallSteps(result.steps as Array<{ step?: string; ok?: boolean; error?: string }>, 'done'))
      setStep('done')
      await new Promise((resolve) => window.setTimeout(resolve, 350))
      onComplete()
    } catch (err) {
      const message = formatWorkframeErrorMessage(err, 'Finish join')
      setLaunchError(message)
      setLaunchSteps((current) =>
        current.map((entry) =>
          entry.status === 'active' ? { ...entry, status: 'error', detail: message } : entry,
        ),
      )
    } finally {
      setBusy(false)
      setLaunching(false)
    }
  }

  async function finishInstall(options?: { alreadyLaunching?: boolean }) {
    if (isInvitee) {
      await finishInviteeOnboarding()
      return
    }
    if (deploymentMode !== 'single_user_local' && !adminVerified) {
      const message = formatWorkframeErrorMessage(new Error('no_session'), 'Finish setup')
      setLaunchError(message)
      setStep('smtp')
      return
    }
    if (!options?.alreadyLaunching) {
      setLaunching(true)
      setLaunchError(null)
      setLaunchSteps(
        buildFinishInstallSteps().map((entry, index) => ({
          ...entry,
          status: index === 0 ? 'active' : 'pending',
        })),
      )
    } else {
      setLaunchSteps((current) => {
        const next = current.filter((entry) => entry.id !== 'finalize')
        const firstPending = next.findIndex((entry) => entry.status === 'pending')
        return next.map((entry, index) =>
          index === firstPending ? { ...entry, status: 'active' } : entry,
        )
      })
    }
    setBusy(true)
    try {
      const payload =
        deploymentMode === 'single_user_local' && !isInvitee
          ? {
              display_name: displayName || 'Owner',
              email: adminEmail || 'owner@local.workframe',
              bio,
              workframe_name: resolveWorkframeName(),
              agent_name: agentName,
              agent_tagline: agentTagline,
              agent_soul: agentSoul.trim() || bio,
            }
          : {
              bio,
              workframe_name: resolveWorkframeName(),
              agent_name: agentName,
              agent_tagline: agentTagline,
              agent_soul: agentSoul.trim() || bio,
            }
      const result = await workframeAuthApi.completeInstall(payload)
      if (!result.ok) {
        throw new Error(result.error || 'Finish setup failed')
      }
      setLaunchSteps(buildFinishInstallSteps(result.steps, 'active'))
      await new Promise((resolve) => window.setTimeout(resolve, 450))
      setLaunchSteps(buildFinishInstallSteps(result.steps, 'done'))
      setStep('done')
      await new Promise((resolve) => window.setTimeout(resolve, 350))
      onComplete()
    } catch (err) {
      const message = formatWorkframeErrorMessage(err, 'Finish setup')
      setLaunchError(message)
      setLaunchSteps((current) =>
        current.map((entry) =>
          entry.status === 'active'
            ? { ...entry, status: 'error', detail: message }
            : entry.status === 'pending'
              ? entry
              : entry,
        ),
      )
    } finally {
      setBusy(false)
    }
  }

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
          message: `URL test: ${result.error || 'failed'}`,
          hint: result.hint,
        })
      } else {
        setError(null)
      }
    } catch (err) {
      setError(formatWorkframeError(err, 'URL test'))
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
      inviteEmails,
      publicUrl,
    })
  }, [
    adminEmail,
    adminVerified,
    agentName,
    agentTagline,
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

  let footer = null
  switch (step) {
    case 'intro':
      footer = (
        <WfActionButton wizardSize tone="primary" disabled={busy} onClick={() => setStep('welcome')}>
          Get started
        </WfActionButton>
      )
      break
    case 'smtp':
      footer = (
        <div className="wf-wizard-footer-actions">
          <WfActionButton
            wizardSize
            tone={smtpSetupComplete ? 'default' : 'primary'}
            className="wf-wizard-footer-actions__btn"
            disabled={busy}
            onClick={() => void testSmtpOnly()}
          >
            {busy ? 'Working…' : 'Send test email'}
          </WfActionButton>
          <WfActionButton
            wizardSize
            tone={smtpSetupComplete ? 'primary' : 'inactive'}
            className="wf-wizard-footer-actions__btn"
            disabled={busy || !canContinueFromSmtp}
            onClick={() => void continueFromSmtp()}
          >
            {adminVerified ? 'Continue' : 'Continue to verification'}
          </WfActionButton>
        </div>
      )
      break
    case 'admin_auth':
      break
    case 'integrations':
      footer = (
        <>
          <WfActionButton wizardSize disabled={busy} onClick={() => void skipToBilling()}>
            Skip
          </WfActionButton>
          <WfActionButton wizardSize tone="primary" disabled={busy} onClick={() => void saveIntegrations()}>
            Continue
          </WfActionButton>
        </>
      )
      break
    case 'billing':
      footer = (
        <WfActionButton wizardSize tone="primary" disabled={busy} onClick={() => void saveBilling()}>
          Continue
        </WfActionButton>
      )
      break
    case 'workframe':
      footer = (
        <WfActionButton wizardSize tone="primary" disabled={busy} onClick={() => void saveWorkframe()}>
          Continue
        </WfActionButton>
      )
      break
    case 'profile':
      footer = (
        <WfActionButton wizardSize tone="primary" disabled={busy} onClick={() => void saveProfile()}>
          Continue
        </WfActionButton>
      )
      break
    case 'providers':
      if (workspaceId) {
        footer = (
          <WfActionButton wizardSize tone="primary" disabled={busy} onClick={() => void saveProviders()}>
            Continue
          </WfActionButton>
        )
      }
      break
    case 'agent':
      footer = (
        <WfActionButton wizardSize tone="primary" disabled={busy} onClick={() => void saveAgent()}>
          {busy
            ? 'Saving agent…'
            : deploymentMode === 'public_multi_user' && adminVerified && publicUrl.trim()
              ? 'Launch Workframe'
              : 'Continue'}
        </WfActionButton>
      )
      break
    case 'invites':
      footer = (
        <>
          <WfActionButton wizardSize disabled={busy} onClick={() => void finishInstall()}>
            {busy ? 'Finishing…' : 'Skip'}
          </WfActionButton>
          <WfActionButton wizardSize tone="primary" disabled={busy} onClick={() => void sendInvites()}>
            {busy ? 'Sending invites…' : 'Send invites'}
          </WfActionButton>
        </>
      )
      break
    case 'publish':
      footer = (
        <>
          <WfActionButton wizardSize disabled={busy} onClick={() => void testPublicUrl()}>
            Test connection
          </WfActionButton>
          <WfActionButton
            wizardSize
            tone="primary"
            disabled={busy || !publicUrl.trim()}
            onClick={async () => {
              setBusy(true)
              try {
                const url = normalizePublicUrl(publicUrl)
                setPublicUrl(url)
                const patched = await patchInstallStackWhenAllowed({ app_base_url: url })
                if (!patched) return
                setStep('smtp')
              } catch (err) {
                setError(formatWorkframeError(err, 'Save public URL'))
              } finally {
                setBusy(false)
              }
            }}
          >
            Continue
          </WfActionButton>
        </>
      )
      break
    default:
      break
  }

  if (!bootstrapDone && !isInvitee) {
    return <BootScreen label="Loading setup wizard" />
  }

  if (ownerSignInRequired) {
    return (
      <OnboardingAuthGate title="Sign in to continue setup" description="Sign in as the Workframe admin to resume setup.">
        <EmailOtpVerification
          initialEmail={adminEmail}
          startStep="email"
          purpose="signin"
          onVerified={handleOwnerSignedIn}
        />
      </OnboardingAuthGate>
    )
  }

  if (isInvitee && !inviteeAuthed) {
    return (
      <OnboardingAuthGate title={`Join ${projectName}`} description="Verify your invite email to continue.">
        <EmailOtpVerification
          initialEmail={inviteEmail}
          startStep="email"
          inviteToken={inviteToken}
          purpose="signin"
          onVerified={handleInviteeVerified}
        />
      </OnboardingAuthGate>
    )
  }

  return launching ? (
    <OnboardingLaunchScreen
      projectName={projectName}
      steps={launchSteps}
      error={launchError}
    />
  ) : (
    <OnboardingWizardShell
      projectName={workframeName.trim() || projectName}
      brandLogoUrl={showBrandLogo ? logoUrl : undefined}
      step={currentRailStep}
      steps={wizardSteps}
      maxReachableIndex={maxReachableIndex}
      onStepSelect={goToRailStep}
      title={title}
      description={description || undefined}
      footer={footer}
    >
      {error ? <WorkframeNotice info={error} /> : null}

      {step === 'intro' ? (
        <div className="wf-wizard-panel">
          <ul className="wf-wizard-checklist">
            <li>Deployment mode and admin sign-in</li>
            <li>Integrations, billing (BYOK or company-pays)</li>
            <li>Workframe profile, your keys, and native agent</li>
          </ul>
        </div>
      ) : null}

      {step === 'welcome' ? (
        <div className="wf-wizard-mode-grid">
          {MODES.map((m) => (
            <button
              key={m.id}
              type="button"
              className="wf-wizard-mode-card"
              disabled={busy}
              onClick={() => void pickMode(m.id)}
            >
              <strong>{m.title}</strong>
              <span>{m.blurb}</span>
            </button>
          ))}
        </div>
      ) : null}

      {step === 'smtp' || step === 'admin_auth' ? (
        <div
          className={`wf-wizard-panel wf-onboarding-form wf-onboarding-compact${step === 'admin_auth' ? ' wf-wizard-panel--auth-otp' : ''}`}
        >
          {step === 'smtp' ? (
            <>
          {busy && smtpPhase ? <SmtpProgressList phase={smtpPhase} /> : null}
          <div className="wf-onboarding-form__row wf-onboarding-form__row--2col">
            <div className="wf-dialog-field">
              <Label htmlFor="wf-smtp-host">SMTP host</Label>
              <Input
                id="wf-smtp-host"
                value={smtpHost}
                onChange={(e) => setSmtpHost(e.target.value)}
                placeholder="smtp.sendgrid.net"
                disabled={busy}
              />
            </div>
            <div className="wf-dialog-field">
              <div className="wf-dialog-field__label-row">
                <Label htmlFor="wf-smtp-port">Port</Label>
                <span className="wf-dialog-field__hint wf-dialog-field__hint--inline">
                  465 SSL · 587 STARTTLS
                </span>
              </div>
              <Input
                id="wf-smtp-port"
                value={smtpPort}
                onChange={(e) => setSmtpPort(e.target.value)}
                placeholder="587"
                disabled={busy}
              />
            </div>
          </div>
          <div className="wf-onboarding-form__row wf-onboarding-form__row--2col">
            <div className="wf-dialog-field">
              <Label htmlFor="wf-smtp-user">Username</Label>
              <Input
                id="wf-smtp-user"
                value={smtpUser}
                onChange={(e) => setSmtpUser(e.target.value)}
                disabled={busy}
              />
            </div>
            <div className="wf-dialog-field">
              <Label htmlFor="wf-smtp-pass">Password</Label>
              <SecretInput
                id="wf-smtp-pass"
                value={smtpPass}
                onChange={(e) => setSmtpPass(e.target.value)}
                saved={smtpHasPassword}
                emptyPlaceholder="SMTP password or API key"
                disabled={busy}
              />
            </div>
          </div>
          <div className="wf-dialog-field">
            <Label htmlFor="wf-smtp-from">From address</Label>
            <Input
              id="wf-smtp-from"
              value={smtpFrom}
              onChange={(e) => setSmtpFrom(e.target.value)}
              placeholder={smtpUser || 'same as username'}
              disabled={busy}
            />
            <p className="wf-dialog-field__hint">Leave blank to use the login email as the sender.</p>
          </div>
          <div className="wf-dialog-field">
            <Label htmlFor="wf-smtp-admin">Admin email</Label>
            <Input
              id="wf-smtp-admin"
              type="email"
              value={adminEmail}
              onChange={(e) => setAdminEmail(e.target.value)}
              onBlur={() => void persistAdminEmail()}
              disabled={busy}
            />
          </div>
            </>
          ) : (
            <EmailOtpVerification
              initialEmail={adminEmail}
              startStep={adminOtpStep}
              initialDevOtp={adminAuthDevOtp}
              initialAuthNotice={adminAuthNotice}
              inviteToken={inviteToken}
              emailInputId="wf-concierge-admin-email"
              purpose="register"
              variant="wizard"
              googleOAuthEnabled={Boolean(stack?.google_oauth?.enabled)}
              onGoogleSignIn={() => void startGoogleSignIn()}
              onStepChange={setAdminOtpStep}
              onVerified={handleAdminRegistered}
            />
          )}
        </div>
      ) : null}

      {step === 'integrations' ? (
        <WorkframeIntegrationsStep
          disabled={busy}
          onBindOAuthSave={(save) => {
            oauthSaveRef.current = save
          }}
        />
      ) : null}

      {step === 'billing' ? (
        <div className="wf-wizard-choice-grid">
          <label className={`wf-wizard-choice-card${credentialMode === 'byok' ? ' is-selected' : ''}`}>
            <input type="radio" checked={credentialMode === 'byok'} onChange={() => setCredentialMode('byok')} />
            <span>
              <strong>BYOK — bring your own keys</strong>
              <span>Each member connects personal LLM keys. Usage bills to them.</span>
            </span>
          </label>
          <label className={`wf-wizard-choice-card${credentialMode === 'workspace' ? ' is-selected' : ''}`}>
            <input type="radio" checked={credentialMode === 'workspace'} onChange={() => setCredentialMode('workspace')} />
            <span>
              <strong>Company-pays — shared keys</strong>
              <span>One shared key pool for all members. Admin manages provider keys.</span>
            </span>
          </label>
        </div>
      ) : null}

      {step === 'workframe' ? (
        <div className="wf-wizard-panel wf-onboarding-form">
          <OnboardingIdentityFields
            avatarKind="logo"
            avatarUrl={logoUrl}
            onAvatarChange={setLogoUrl}
            avatarLabel="Logo"
            disabled={busy}
            primary={{
              id: 'wf-wf-name',
              label: 'Workframe name',
              value: workframeName,
              onChange: setWorkframeName,
            }}
            secondary={{
              id: 'wf-wf-tag',
              label: 'Workframe tagline',
              value: workframeTagline,
              onChange: setWorkframeTagline,
            }}
            body={{
              id: 'wf-wf-mission',
              label: 'Mission',
              value: mission,
              onChange: setMission,
              rows: 3,
            }}
          />
        </div>
      ) : null}

      {step === 'profile' ? (
        <div className="wf-wizard-panel wf-onboarding-form">
          <OnboardingIdentityFields
            avatarKind="user"
            avatarUrl={avatarUrl}
            onAvatarChange={setAvatarUrl}
            disabled={busy}
            primary={{
              id: 'wf-profile-name',
              label: 'Display name',
              value: displayName,
              onChange: setDisplayName,
            }}
            secondary={{
              id: 'wf-profile-tag',
              label: 'Tagline',
              value: tagline,
              onChange: setTagline,
            }}
            body={{
              id: 'wf-profile-bio',
              label: 'About you',
              value: bio,
              onChange: setBio,
              rows: 3,
            }}
          />
        </div>
      ) : null}

      {step === 'providers' && workspaceId ? (
        <div className="wf-wizard-panel wf-onboarding-form">
          <div className="wf-wizard-subtabs" role="tablist" aria-label="Model keys sections">
            {(
              [
                ['keys', 'Provider keys'],
                ['accounts', 'Linked accounts'],
                ['model', 'LLM models'],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={providersTab === id}
                className={`wf-wizard-subtabs__btn${providersTab === id ? ' is-active' : ''}`}
                onClick={() => setProvidersTab(id)}
              >
                {label}
              </button>
            ))}
          </div>
          {providersTab === 'keys' ? (
            <ProviderConnectPanel
              workspaceId={workspaceId}
              credentialScope="user"
              categories={['llm', 'dev', 'search']}
              hint="none"
              layout="tabs"
              disabled={busy}
            />
          ) : null}
          {providersTab === 'accounts' ? (
            <PlatformIdentityPanel workspaceId={workspaceId} disabled={busy} />
          ) : null}
          {providersTab === 'model' ? <ModelPickerPanel workspaceId={workspaceId} embedded /> : null}
        </div>
      ) : null}

      {step === 'agent' ? (
        <div className="wf-wizard-panel wf-onboarding-form">
          {agentSteps.length ? (
            <OperationProgress steps={agentSteps} title="Setting up your agent" className="wf-mb-4" />
          ) : null}
          <OnboardingIdentityFields
            avatarKind="agent"
            avatarUrl={agentAvatar}
            onAvatarChange={setAgentAvatar}
            disabled={busy}
            primary={{
              id: 'wf-agent-name',
              label: 'Name',
              value: agentName,
              onChange: setAgentName,
            }}
            secondary={{
              id: 'wf-agent-tag',
              label: 'Tagline',
              value: agentTagline,
              onChange: setAgentTagline,
            }}
            body={{
              id: 'wf-agent-soul',
              label: 'Soul / instructions',
              value: agentSoul,
              onChange: setAgentSoul,
              rows: 4,
              placeholder: defaultAgentSoul(agentName, resolveWorkframeName()),
            }}
          />
        </div>
      ) : null}

      {step === 'invites' ? (
        <div className="wf-wizard-panel wf-onboarding-form">
          <div className="wf-dialog-field">
            <Label htmlFor="wf-invite-emails">Email addresses</Label>
            <Input
              id="wf-invite-emails"
              value={inviteEmails}
              onChange={(e) => setInviteEmails(e.target.value)}
              placeholder="a@co.com, b@co.com"
            />
            <p className="wf-dialog-field__hint">Comma-separated. Skip to invite teammates later in Workframe Settings.</p>
          </div>
        </div>
      ) : null}

      {step === 'publish' ? (
        <PublicUrlWizardStep
          publicUrl={publicUrl}
          onPublicUrlChange={setPublicUrl}
          disabled={busy}
        />
      ) : null}
    </OnboardingWizardShell>
  )
}
