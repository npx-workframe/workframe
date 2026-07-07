import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import { BootScreen } from '@/components/shell/BootScreen'
import { DesktopTitleBar } from '@/components/shell/DesktopTitleBar'
import { SetupAuthGate } from '@/components/auth/SetupAuthGate'
import { InstallShell } from '@/components/install/InstallShell'
import { ConciergeFlow } from '@/components/onboarding/ConciergeFlow'
import { AppShell } from '@/components/shell/AppShell'
import { DockviewWorkspace } from '@/components/workspace/DockviewWorkspace'
import { AgentRouteProvider } from '@/contexts/AgentRouteContext'
import { BrowserWorkspaceProvider } from '@/contexts/BrowserWorkspaceContext'
import { HermesSessionProvider } from '@/contexts/HermesSessionContext'
import { WorkspacePanelsProvider } from '@/contexts/WorkspacePanelsContext'
import { useSiteMeta } from '@/hooks/useSiteMeta'
import { useWorkspaceBranding } from '@/hooks/useWorkspaceBranding'
import { getInitialTheme, applyTheme } from '@/lib/theme'
import { isElectronRuntime } from '@/lib/runtime'
import { ButtonShowcasePage } from '@/pages/dev/ButtonShowcasePage'
import { ThemeShowcasePage } from '@/pages/dev/ThemeShowcasePage'
import { WORKFRAME_SESSION_EXPIRED } from '@/lib/authenticatedFetch'
import { clearStoredSessionTokens } from '@/lib/workframeSession'
import { workframeAuthApi } from '@/lib/workframeAuthApi'

console.log('[workframe] App module loaded')

applyTheme(getInitialTheme())

type AppPhase = 'boot' | 'install' | 'onboarding' | 'auth' | 'shell'

function WorkframeShell({ projectName, onLogout }: { projectName: string; onLogout: () => void | Promise<void> }) {
  const branding = useWorkspaceBranding(projectName)
  return (
    <BrowserWorkspaceProvider projectName={projectName}>
      <AgentRouteProvider>
        <WorkspacePanelsProvider onLogout={onLogout}>
          <HermesSessionProvider>
            <AppShell
              projectName={branding.name}
              subtitle={branding.tagline || 'Workframe UI'}
              brandLogoUrl={branding.logoUrl}
              mainFill
            >
              <DockviewWorkspace />
            </AppShell>
          </HermesSessionProvider>
        </WorkspacePanelsProvider>
      </AgentRouteProvider>
    </BrowserWorkspaceProvider>
  )
}

function isButtonShowcasePath(): boolean {
  const params = new URLSearchParams(window.location.search)
  if (params.get('wf-dev') === 'buttons') return true
  const path = window.location.pathname
  return path === '/dev/buttons' || path.endsWith('/dev/buttons')
}

function isThemeShowcasePath(): boolean {
  const params = new URLSearchParams(window.location.search)
  if (params.get('wf-dev') === 'theme') return true
  const path = window.location.pathname
  return path === '/dev/theme' || path.endsWith('/dev/theme')
}

function App() {
  if (isButtonShowcasePath()) {
    return <ButtonShowcasePage />
  }

  if (isThemeShowcasePath()) {
    return <ThemeShowcasePage />
  }

  const projectName = import.meta.env.VITE_WORKFRAME_PROJECT?.trim() || 'Workframe'
  useSiteMeta()
  const inviteToken = useMemo(() => {
    const params = new URLSearchParams(window.location.search)
    return params.get('invite_token')?.trim() || ''
  }, [])
  const inviteEmail = useMemo(() => {
    const params = new URLSearchParams(window.location.search)
    return params.get('email')?.trim() || ''
  }, [])

  const [phase, setPhase] = useState<AppPhase>('boot')
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [onboardingComplete, setOnboardingComplete] = useState(false)
  const [installWindowActive, setInstallWindowActive] = useState(false)
  const installWindowRef = useRef(false)
  const resolvingPhaseRef = useRef(false)

  const navigate = useCallback((path: string) => {
    window.history.pushState({}, '', path)
  }, [])

  const markInstallWindow = useCallback((active: boolean) => {
    installWindowRef.current = active
    setInstallWindowActive(active)
  }, [])

  const resolvePhase = useCallback(async () => {
    if (resolvingPhaseRef.current) return
    resolvingPhaseRef.current = true
    try {
    const path = window.location.pathname
    let installStatus: Awaited<ReturnType<typeof workframeAuthApi.getInstallStatus>> | null = null

    try {
      installStatus = await workframeAuthApi.getInstallStatus()
      const inInstallWindow = installStatus.install_window_open && !installStatus.install_complete
      markInstallWindow(inInstallWindow)
      if (inInstallWindow) {
        clearStoredSessionTokens()
        try {
          await workframeAuthApi.logout()
        } catch {
          // best-effort — clears HttpOnly session cookie when present
        }
      }
    } catch {
      markInstallWindow(false)
    }

    if (installWindowRef.current && installStatus) {
      if (!installStatus.hermes_present || !installStatus.setup_complete) {
        if (!path.endsWith('/install')) navigate('/install')
        setPhase('install')
        return
      }
      if (!path.endsWith('/onboarding')) navigate('/onboarding')
      setPhase('onboarding')
      return
    }

    if (path === '/install' || path.endsWith('/install')) {
      setPhase('install')
      return
    }

    if (path === '/onboarding' || path.endsWith('/onboarding') || inviteToken) {
      try {
        await workframeAuthApi.restoreSession()
        const onboarding = await workframeAuthApi.getOnboarding()
        if (onboarding.complete) {
          setIsAuthenticated(true)
          setOnboardingComplete(true)
          if (path === '/onboarding' || path.endsWith('/onboarding')) {
            navigate('/')
          }
          setPhase('shell')
          return
        }
        setIsAuthenticated(true)
      } catch {
        // Install finished but no cookie — ConciergeFlow shows owner sign-in before PATCH routes.
        if (installStatus?.install_complete && !inviteToken) {
          setIsAuthenticated(false)
          setPhase('onboarding')
          return
        }
      }
      setPhase('onboarding')
      return
    }

    try {
      const me = await workframeAuthApi.restoreSession()
      void me
      setIsAuthenticated(true)
      const onboarding = await workframeAuthApi.getOnboarding()
      const complete = Boolean(onboarding.complete)
      setOnboardingComplete(complete)
      markInstallWindow(false)
      setPhase(complete ? 'shell' : 'onboarding')
    } catch {
      setIsAuthenticated(false)
      setOnboardingComplete(false)
      markInstallWindow(false)
      setPhase(inviteToken ? 'onboarding' : 'auth')
    }
    } finally {
      resolvingPhaseRef.current = false
    }
  }, [inviteToken, markInstallWindow, navigate])

  useEffect(() => {
    void resolvePhase()
    const onPop = () => {
      void resolvePhase()
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [resolvePhase])

  useEffect(() => {
    const onSessionExpired = () => {
      if (installWindowRef.current) {
        // expected while first-run onboarding runs without a session
        return
      }
      setOnboardingComplete(false)
      setIsAuthenticated(false)
      setPhase((current) => {
        if (current === 'boot' || current === 'auth') return current
        return 'boot'
      })
      void resolvePhase()
    }
    window.addEventListener(WORKFRAME_SESSION_EXPIRED, onSessionExpired)
    return () => window.removeEventListener(WORKFRAME_SESSION_EXPIRED, onSessionExpired)
  }, [resolvePhase])

  const handleAuthenticated = useCallback(async () => {
    try {
      await workframeAuthApi.restoreSession()
    } catch {
      // Gate already verified; best-effort refresh before Hermes connects.
    }
    try {
      const onboarding = await workframeAuthApi.getOnboarding()
      setOnboardingComplete(Boolean(onboarding.complete))
      setPhase(onboarding.complete ? 'shell' : 'onboarding')
    } catch {
      setOnboardingComplete(true)
      setPhase('shell')
    }
    setIsAuthenticated(true)
  }, [])

  const handleOnboardingComplete = useCallback(() => {
    setOnboardingComplete(true)
    setIsAuthenticated(true)
    navigate('/')
    setPhase('shell')
  }, [navigate])

  const handleInstallReady = useCallback(() => {
    navigate('/onboarding')
    setPhase('onboarding')
  }, [navigate])

  const handleLogout = useCallback(async () => {
    try {
      await workframeAuthApi.logout()
    } catch (error) {
      console.warn('[workframe] logout failed', error)
    } finally {
      setOnboardingComplete(false)
      setIsAuthenticated(false)
      setPhase('auth')
    }
  }, [])

  let content: ReactNode

  if (phase === 'boot') {
    content = <BootScreen label={`Loading ${projectName}`} />
  } else if (phase === 'install') {
    content = <InstallShell projectName={projectName} onReady={handleInstallReady} />
  } else if (phase === 'onboarding' && (!isAuthenticated || !onboardingComplete)) {
    content = (
      <ConciergeFlow
        projectName={projectName}
        onComplete={handleOnboardingComplete}
        inviteToken={inviteToken}
        inviteEmail={inviteEmail}
      />
    )
  } else if (!isAuthenticated && installWindowActive) {
    content = (
      <ConciergeFlow
        projectName={projectName}
        onComplete={handleOnboardingComplete}
        inviteToken={inviteToken}
        inviteEmail={inviteEmail}
      />
    )
  } else if (!isAuthenticated) {
    content = <SetupAuthGate projectName={projectName} onAuthenticated={handleAuthenticated} />
  } else if (!onboardingComplete) {
    content = (
      <ConciergeFlow
        projectName={projectName}
        onComplete={handleOnboardingComplete}
        inviteToken={inviteToken}
        inviteEmail={inviteEmail}
      />
    )
  } else {
    content = <WorkframeShell projectName={projectName} onLogout={handleLogout} />
  }

  if (!isElectronRuntime()) return content

  return (
    <div className="wf-desktop-frame">
      <DesktopTitleBar title={projectName} />
      <div className="wf-desktop-frame__body">{content}</div>
    </div>
  )
}

export default App
