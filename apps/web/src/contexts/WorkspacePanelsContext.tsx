import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import type { DockviewApi } from 'dockview'

import { PANEL_IDS } from '@/lib/panelControlConfig'
import { restoreWorkspacePanel, setupWorkspacePanelTracking } from '@/lib/workspacePanelRestore'
import {
  createWorkspaceLayoutController,
  getWorkspaceLayoutController,
  type ApplyLayoutOptions,
} from '@/lib/workspaceLayout'
import type { WorkspaceRoom } from '@/lib/workframeAuthApi'

type WorkspacePanelsContextValue = {
  closedPanelIds: ReadonlySet<string>
  railExpanded: boolean
  activeRoom: WorkspaceRoom | null
  userSettingsOpen: boolean
  userSettingsTab: 'profile' | 'connect' | 'agents' | 'appearance'
  userSettingsConnectTab: 'providers' | 'models' | 'messaging'
  onLogout?: () => void | Promise<void>
  openPanel: (panelId: string) => void
  openUserSettings: (
    tab?: 'profile' | 'connect' | 'agents' | 'appearance',
    connectTab?: 'providers' | 'models' | 'messaging',
  ) => void
  closeUserSettings: () => void
  openAgentSettings: (profile: string, displayName: string) => void
  registerOpenAgentSettings: (fn: ((profile: string, displayName: string) => void | Promise<void>) | null) => void
  registerOpenChatSettings: (fn: (() => void) | null) => void
  openChatSettings: () => void
  rebalanceLayout: (options?: ApplyLayoutOptions) => void
  setRailExpanded: (expanded: boolean) => void
  setActiveRoom: (room: WorkspaceRoom | null) => void
  registerWorkspaceApi: (
    api: DockviewApi,
    projectName: string,
    root?: HTMLElement | null,
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
  const [closedPanelIds, setClosedPanelIds] = useState<ReadonlySet<string>>(() => new Set())
  const [railExpanded, setRailExpandedState] = useState(true)
  const [workspaceApi, setWorkspaceApi] = useState<DockviewApi | null>(null)
  const [projectName, setProjectName] = useState('Workframe')
  const [activeRoom, setActiveRoomState] = useState<WorkspaceRoom | null>(null)
  const [userSettingsOpen, setUserSettingsOpen] = useState(false)
  const [userSettingsTab, setUserSettingsTab] = useState<'profile' | 'connect' | 'agents' | 'appearance'>('profile')
  const [userSettingsConnectTab, setUserSettingsConnectTab] = useState<'providers' | 'models' | 'messaging'>('providers')
  const openAgentSettingsRef = useRef<((profile: string, displayName: string) => void | Promise<void>) | null>(null)
  const openChatSettingsRef = useRef<(() => void) | null>(null)

  const registerOpenAgentSettings = useCallback(
    (fn: ((profile: string, displayName: string) => void | Promise<void>) | null) => {
      openAgentSettingsRef.current = fn
    },
    [],
  )

  const registerOpenChatSettings = useCallback((fn: (() => void) | null) => {
    openChatSettingsRef.current = fn
  }, [])

  const openAgentSettings = useCallback((profile: string, displayName: string) => {
    void openAgentSettingsRef.current?.(profile, displayName)
  }, [])

  const openChatSettings = useCallback(() => {
    openChatSettingsRef.current?.()
  }, [])

  const openUserSettings = useCallback((
    tab: 'profile' | 'connect' | 'agents' | 'appearance' = 'profile',
    connectTab: 'providers' | 'models' | 'messaging' = 'providers',
  ) => {
    setUserSettingsTab(tab)
    if (tab === 'connect') setUserSettingsConnectTab(connectTab)
    setUserSettingsOpen(true)
  }, [])

  const closeUserSettings = useCallback(() => {
    setUserSettingsOpen(false)
  }, [])

  const registerWorkspaceApi = useCallback(
    (api: DockviewApi, name: string, root?: HTMLElement | null) => {
      setWorkspaceApi(api)
      setProjectName(name)
      setClosedPanelIds(new Set())
      setRailExpandedState(true)

      const controller = createWorkspaceLayoutController(api, root ?? null)
      controller.layout('init')
      requestAnimationFrame(() => controller.layout('init'))

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
    [],
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

  const openPanel = useCallback(
    (panelId: string) => {
      if (!workspaceApi || panelId === PANEL_IDS.crew) return
      restoreWorkspacePanel(workspaceApi, panelId, projectName)
    },
    [projectName, workspaceApi],
  )

  const value = useMemo(
    () => ({
      closedPanelIds,
      railExpanded,
      activeRoom,
      userSettingsOpen,
      userSettingsTab,
      userSettingsConnectTab,
      onLogout,
      openPanel,
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
    [closedPanelIds, railExpanded, activeRoom, userSettingsOpen, userSettingsTab, userSettingsConnectTab, onLogout, openPanel, openUserSettings, closeUserSettings, openAgentSettings, registerOpenAgentSettings, registerOpenChatSettings, openChatSettings, rebalanceLayout, registerWorkspaceApi, setActiveRoom, setRailExpanded],
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
