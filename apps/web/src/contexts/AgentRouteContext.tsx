import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { loadWorkframeRuntimeConfig } from '@/lib/workframeProfile'
import { fetchRoutes, type WorkframeRoute } from '@/lib/workframeRoutes'

function getActiveProfileStorageKey(): string {
  const projectName = import.meta.env.VITE_WORKFRAME_PROJECT?.trim() || 'Workframe'
  return `workframe.activeProfile:${projectName}`
}

const ACTIVE_PROFILE_STORAGE_KEY = getActiveProfileStorageKey()

export type AgentRouteState = {
  routes: WorkframeRoute[]
  activeRoute: WorkframeRoute | null
  activeProfile: string
  routesLoading: boolean
  routesError: string | null
  setActiveRoute: (profile: string) => void
  reloadRoutes: (opts?: { silent?: boolean }) => Promise<void>
}

const AgentRouteContext = createContext<AgentRouteState | null>(null)

export function AgentRouteProvider({ children }: { children: ReactNode }) {
  const [routes, setRoutes] = useState<WorkframeRoute[]>([])
  const [activeProfile, setActiveProfile] = useState(() => {
    try {
      return window.localStorage.getItem(ACTIVE_PROFILE_STORAGE_KEY) || ''
    } catch {
      return ''
    }
  })
  const [routesLoading, setRoutesLoading] = useState(true)
  const [routesError, setRoutesError] = useState<string | null>(null)

  const reloadRoutes = useCallback(async (opts?: { silent?: boolean }): Promise<void> => {
    if (!opts?.silent) setRoutesLoading(true)
    try {
      const { defaultProfile, routes: rows } = await fetchRoutes()
      setRoutes(rows)
      setRoutesError(null)
      setActiveProfile((current) => {
        if (current && rows.some((r) => r.profile === current)) return current
        const preferred = defaultProfile || rows[0]?.profile || ''
        return preferred
      })
    } catch (err) {
      if (!opts?.silent) {
        setRoutes([])
        setRoutesError(err instanceof Error ? err.message : 'Failed to load routes')
      }
    } finally {
      if (!opts?.silent) setRoutesLoading(false)
    }
  }, [])

  useEffect(() => {
    void reloadRoutes()
    void loadWorkframeRuntimeConfig().catch(() => {})

    const interval = setInterval(() => {
      void reloadRoutes({ silent: true })
    }, 10000)
    return () => clearInterval(interval)
  }, [reloadRoutes])

  useEffect(() => {
    try {
      if (activeProfile) {
        window.localStorage.setItem(ACTIVE_PROFILE_STORAGE_KEY, activeProfile)
      } else {
        window.localStorage.removeItem(ACTIVE_PROFILE_STORAGE_KEY)
      }
    } catch {
      // Ignore storage failures.
    }
  }, [activeProfile])

  const setActiveRoute = useCallback((profile: string) => {
    setActiveProfile(profile)
  }, [])

  const activeRoute = useMemo(
    () => routes.find((r) => r.profile === activeProfile) ?? null,
    [routes, activeProfile],
  )

  const value = useMemo<AgentRouteState>(
    () => ({
      routes,
      activeRoute,
      activeProfile,
      routesLoading,
      routesError,
      setActiveRoute,
      reloadRoutes,
    }),
    [routes, activeRoute, activeProfile, routesLoading, routesError, setActiveRoute, reloadRoutes],
  )

  return <AgentRouteContext.Provider value={value}>{children}</AgentRouteContext.Provider>
}

export function useAgentRoute(): AgentRouteState {
  const ctx = useContext(AgentRouteContext)
  if (!ctx) throw new Error('useAgentRoute must be used within AgentRouteProvider')
  return ctx
}
