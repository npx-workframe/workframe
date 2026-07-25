import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import type { DockviewApi } from 'dockview'

import { PANEL_IDS } from '@/lib/panelControlConfig'
import { readPersistedRailExpanded } from '@/lib/workspaceLayoutPersist'
import { restoreWorkspacePanel, setupWorkspacePanelTracking } from '@/lib/workspacePanelRestore'
import {
  createWorkspaceLayoutController,
  getWorkspaceLayoutController,
  type ApplyLayoutOptions,
} from '@/lib/workspaceLayout'
import { WORKSPACE_PANEL_ORDER } from '@/lib/workspaceLayoutTokens'
import {
  enforceSingleWorkspacePanel,
  focusWorkspacePanel,
  getFocusedWorkspacePanelId,
} from '@/lib/workspaceMobileLayout'
import { useMobileWorkspaceLayout } from '@/hooks/useMobileWorkspaceLayout'
import type { WorkspaceRoom } from '@/lib/workframeAuthApi'

type WorkspacePanelsContextValue = {
  closedPanelIds: ReadonlySet<string>
  railExpanded: boolean
  mobileLayout: boolean
  activeWorkspacePanelId: string | null
  activeRoom: WorkspaceRoom | null
  userSettingsOpen: boolean
  userSettingsTab: 'profile' | 'connect' | 'agents' | 'appearance'
  userSettingsConnectTab: 'providers' | 'messaging'
  onLogout?: () => void | Promise<void>
  openPanel: (panelId: string) => void
  focusWorkspacePanel: (panelId: string) => void
  openUserSettings: (
    tab?: 'profile' | 'connect' | 'agents' | 'appearance',
    connectTab?: 'providers' | 'messaging',
  ) => void
  closeUserSettings: () => void
  openAgentSettings: (profile: string, displayName: string) => void
  registerOpenAgentSettings: (fn: ((profile: string, displayName: string) => void | Promise<void>) | null) => void
  registerOpenChatSettings: (fn: ((agentTab?: 'identity' | 'instructions' | 'models') => void) | null) => void
  openChatSettings: (agentTab?: 'identity' | 'instructions' | 'models') => void
  rebalanceLayout: (options?: ApplyLayoutOptions) => void
  setRailExpanded: (expanded: boolean) => void
  setActiveRoom: (room: WorkspaceRoom | null) => void
  registerWorkspaceApi: (
    api: DockviewApi,
    projectName: string,
    root?: HTMLElement | null,
    options?: { restoredLayout?: boolean },
  ) => () => void
}

const WorkspacePanelsContext = createContext<WorkspacePanelsContextValue | null>(null)

export function WorkspacePanelsProvider({
  children,
  onLogout,
}: {
  children: ReactNode
  onLogout?: () => void | Promise<void>
}) {
  const mobileLayout = useMobileWorkspaceLayout()
  const [closedPanelIds, setClosedPanelIds] = useState<ReadonlySet<string>>(() => new Set())
  const [railExpanded, setRailExpandedState] = useState(() => {
    const persisted = readPersistedRailExpanded()
    if (persisted !== undefined) return persisted
    return typeof window === 'undefined' || window.innerWidth >= 1280
  })
  const [workspaceApi, setWorkspaceApi] = useState<DockviewApi | null>(null)
  const [projectName, setProjectName] = useState('Workframe')
  const [activeWorkspacePanelId, setActiveWorkspacePanelId] = useState<string | null>(PANEL_IDS.chat)
  const prevMobileLayoutRef = useRef(mobileLayout)
  const [activeRoom, setActiveRoomState] = useState<WorkspaceRoom | null>(null)
  const [userSettingsOpen, setUserSettingsOpen] = useState(false)
  const [userSettingsTab, setUserSettingsTab] = useState<'profile' | 'connect' | 'agents' | 'appearance'>('profile')
  const [userSettingsConnectTab, setUserSettingsConnectTab] = useState<'providers' | 'messaging'>('providers')
  const openAgentSettingsRef = useRef<((profile: string, displayName: string) => void | Promise<void>) | null>(null)
  const openChatSettingsRef = useRef<((agentTab?: 'identity' | 'instructions' | 'models') => void) | null>(null)

  const registerOpenAgentSettings = useCallback(
    (fn: ((profile: string, displayName: string) => void | Promise<void>) | null) => {
      openAgentSettingsRef.current = fn
    },
    [],
  )

  const registerOpenChatSettings = useCallback(
    (fn: ((agentTab?: 'identity' | 'instructions' | 'models') => void) | null) => {
      openChatSettingsRef.current = fn
    },
    [],
  )

  const openAgentSettings = useCallback((profile: string, displayName: string) => {
    void openAgentSettingsRef.current?.(profile, displayName)
  }, [])

  const openChatSettings = useCallback((agentTab?: 'identity' | 'instructions' | 'models') => {
    openChatSettingsRef.current?.(agentTab)
  }, [])

  const openUserSettings = useCallback((
    tab: 'profile' | 'connect' | 'agents' | 'appearance' = 'profile',
    connectTab: 'providers' | 'messaging' = 'providers',
  ) => {
    setUserSettingsTab(tab)
    if (tab === 'connect') setUserSettingsConnectTab(connectTab)
    setUserSettingsOpen(true)
  }, [])

  const closeUserSettings = useCallback(() => {
    setUserSettingsOpen(false)
  }, [])

  const registerWorkspaceApi = useCallback(
    (
      api: DockviewApi,
      name: string,
      root?: HTMLElement | null,
      options?: { restoredLayout?: boolean },
    ) => {
      setWorkspaceApi(api)
      setProjectName(name)
      setClosedPanelIds(
        new Set(WORKSPACE_PANEL_ORDER.filter((panelId) => !api.getPanel(panelId))),
      )

      const controller = createWorkspaceLayoutController(api, root ?? null)
      controller.state.railExpanded = railExpanded

      if (options?.restoredLayout) {
        requestAnimationFrame(() => controller.hydrateFromDockview())
      } else {
        controller.layout('init')
        requestAnimationFrame(() => controller.layout('init'))
      }

      const unwatch = controller.watch()
      const untrack = setupWorkspacePanelTracking(api, {
        onPanelClosed: (panelId) => {
          if (panelId === PANEL_IDS.crew) return
          setClosedPanelIds((current) => {
            const next = new Set(current)
            next.add(panelId)
            return next
          })
        },
        onPanelOpened: (panelId) => {
          if (panelId === PANEL_IDS.crew) return
          setClosedPanelIds((current) => {
            if (!current.has(panelId)) return current
            const next = new Set(current)
            next.delete(panelId)
            return next
          })
        },
      })

      return () => {
        untrack()
        unwatch()
        controller.dispose()
      }
    },
    [railExpanded],
  )

  const rebalanceLayout = useCallback((options?: ApplyLayoutOptions) => {
    getWorkspaceLayoutController()?.layout('panel-change', options)
  }, [])

  const setRailExpanded = useCallback((expanded: boolean) => {
    setRailExpandedState(expanded)
    getWorkspaceLayoutController()?.setRailExpanded(expanded)
  }, [])

  const setActiveRoom = useCallback((room: WorkspaceRoom | null) => {
    setActiveRoomState(room)
  }, [])

  const focusWorkspacePanelById = useCallback(
    (panelId: string) => {
      if (!workspaceApi || panelId === PANEL_IDS.crew) return
      if (mobileLayout) {
        const focused = focusWorkspacePanel(workspaceApi, panelId, projectName)
        if (focused) setActiveWorkspacePanelId(focused)
        return
      }
      restoreWorkspacePanel(workspaceApi, panelId, projectName)
      setActiveWorkspacePanelId(panelId)
    },
    [mobileLayout, projectName, workspaceApi],
  )

  const openPanel = useCallback(
    (panelId: string) => {
      focusWorkspacePanelById(panelId)
    },
    [focusWorkspacePanelById],
  )

  useEffect(() => {
    if (!workspaceApi) return

    if (mobileLayout) {
      setRailExpandedState(false)
      getWorkspaceLayoutController()?.setRailExpanded(false)
    }

    const enteredMobile = mobileLayout && !prevMobileLayoutRef.current
    const leftMobile = !mobileLayout && prevMobileLayoutRef.current
    prevMobileLayoutRef.current = mobileLayout

    if (enteredMobile) {
      const focused = enforceSingleWorkspacePanel(workspaceApi, projectName, activeWorkspacePanelId)
      if (focused) setActiveWorkspacePanelId(focused)
      return
    }

    if (leftMobile) {
      getWorkspaceLayoutController()?.layout('viewport')
      setActiveWorkspacePanelId(getFocusedWorkspacePanelId(workspaceApi))
    }
  }, [activeWorkspacePanelId, mobileLayout, projectName, workspaceApi])

  useEffect(() => {
    if (!workspaceApi || !mobileLayout) return
    setActiveWorkspacePanelId(getFocusedWorkspacePanelId(workspaceApi))
  }, [closedPanelIds, mobileLayout, workspaceApi])

  const value = useMemo(
    () => ({
      closedPanelIds,
      railExpanded,
      mobileLayout,
      activeWorkspacePanelId,
      activeRoom,
      userSettingsOpen,
      userSettingsTab,
      userSettingsConnectTab,
      onLogout,
      openPanel,
      focusWorkspacePanel: focusWorkspacePanelById,
      openUserSettings,
      closeUserSettings,
      openAgentSettings,
      registerOpenAgentSettings,
      registerOpenChatSettings,
      openChatSettings,
      rebalanceLayout,
      setRailExpanded,
      setActiveRoom,
      registerWorkspaceApi,
    }),
    [closedPanelIds, railExpanded, mobileLayout, activeWorkspacePanelId, activeRoom, userSettingsOpen, userSettingsTab, userSettingsConnectTab, onLogout, openPanel, focusWorkspacePanelById, openUserSettings, closeUserSettings, openAgentSettings, registerOpenAgentSettings, registerOpenChatSettings, openChatSettings, rebalanceLayout, registerWorkspaceApi, setActiveRoom, setRailExpanded],
  )

  return (
    <WorkspacePanelsContext.Provider value={value}>{children}</WorkspacePanelsContext.Provider>
  )
}

export function useWorkspacePanels() {
  const context = useContext(WorkspacePanelsContext)
  if (!context) {
    throw new Error('useWorkspacePanels must be used within WorkspacePanelsProvider')
  }
  return context
}
