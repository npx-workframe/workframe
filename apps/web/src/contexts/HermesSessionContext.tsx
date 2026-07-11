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

import { useAgentRoute } from '@/contexts/AgentRouteContext'
import { useWorkspacePanels } from '@/contexts/WorkspacePanelsContext'
import { useCrew } from '@/hooks/useCrew'
import { isAgentChatRoom, resolveHermesProfileSlug } from '@/lib/agentProfile'
import { getOrCreateClientId, markBindingSchema } from '@/lib/chatSession'
import type { ChatMessage } from '@/lib/chatTypes'
import { findAgentByProfile } from '@/lib/hermesProfile'
import { loadWorkframeRuntimeConfig, nativeProfileSlug } from '@/lib/workframeProfile'
import type { WorkframeNoticeInfo } from '@/lib/workframeErrors'

import { useHermesSessionRefs } from './hermes-session/hermesSessionRefs'
import type { HermesSessionState } from './hermes-session/types'
import { useHermesSessionBind } from './hermes-session/useHermesSessionBind'
import { useHermesSessionHistory } from './hermes-session/useHermesSessionHistory'
import { useHermesSessionStream } from './hermes-session/useHermesSessionStream'

export type { HermesSessionState } from './hermes-session/types'

const HermesSessionContext = createContext<HermesSessionState | null>(null)

export function HermesSessionProvider({ children }: { children: ReactNode }) {
  const { activeRoute, activeProfile, routes, setActiveRoute } = useAgentRoute()
  const { activeRoom } = useWorkspacePanels()
  const projectName = import.meta.env.VITE_WORKFRAME_PROJECT?.trim() || 'Workframe'
  const { crew } = useCrew(projectName)
  const agentRoom = isAgentChatRoom(activeRoom) ? activeRoom : null
  const activeHermesProfile = agentRoom ? resolveHermesProfileSlug(agentRoom, activeProfile) : ''

  const [profile, setProfile] = useState('')
  const [agentDisplayName, setAgentDisplayName] = useState('Workframe Agent')
  const [nativeAgentName, setNativeAgentName] = useState('Workframe Agent')
  const [stateDbSessionId, setStateDbSessionId] = useState<string | null>(null)
  const [gatewaySessionId, setGatewaySessionId] = useState<string | null>(null)
  const [sessionReady, setSessionReady] = useState(false)
  const [connectError, setConnectError] = useState<WorkframeNoticeInfo | null>(null)
  const [turnActive, setTurnActive] = useState(false)
  const [turnStatus, setTurnStatus] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])

  const refs = useHermesSessionRefs()

  const roomDisplayName = useMemo(() => {
    if (!agentRoom) return activeRoute?.displayName || 'Agent'
    const fromCrew = findAgentByProfile(crew, activeHermesProfile)?.display_name
    if (fromCrew) return fromCrew
    const roomName = agentRoom.name?.trim()
    if (roomName && !/^[0-9a-f-]{36}$/i.test(roomName) && !/^u-[a-z0-9-]+$/i.test(roomName)) {
      return roomName
    }
    return activeRoute?.displayName || 'Workframe Agent'
  }, [activeHermesProfile, activeRoute?.displayName, agentRoom, crew])

  const completeTurn = useCallback(() => {
    refs.turnActiveRef.current = false
    setTurnActive(false)
    refs.streamMessageIdRef.current = null
    setTurnStatus(null)
    setMessages((prev) => prev.map((m) => (m.ephemeral ? { ...m, ephemeral: false } : m)))
  }, [refs.streamMessageIdRef, refs.turnActiveRef])

  const bind = useHermesSessionBind({
    refs,
    agentDisplayName,
    activeProfile,
    setActiveRoute,
    setAgentDisplayName,
    setProfile,
    setStateDbSessionId,
    setGatewaySessionId,
    setMessages,
    setConnectError,
    setSessionReady,
    completeTurn,
  })

  const history = useHermesSessionHistory({
    refs,
    bind,
    agentDisplayName,
    activeHermesProfile,
    setAgentDisplayName,
    setProfile,
    setStateDbSessionId,
    setGatewaySessionId,
    setMessages,
    setConnectError,
    setSessionReady,
    messages,
    completeTurn,
  })

  const stream = useHermesSessionStream({
    refs,
    bind,
    completeTurn,
    sessionReady,
    turnActive,
    profile,
    activeProfile,
    agentDisplayName,
    routes,
    crew,
    setActiveRoute,
    setTurnActive,
    setTurnStatus,
    setConnectError,
    setMessages,
  })

  const useSessionForRoomRef = useRef(bind.useSessionForRoom)
  useSessionForRoomRef.current = bind.useSessionForRoom

  if (!refs.initRef.current) {
    refs.initRef.current = true
    try {
      const url = new URL(window.location.href)
      const src = (url.searchParams.get('source') || url.searchParams.get('wf_source') || '').trim()
      if (src) refs.sourceIdRef.current = src
    } catch {}
    refs.clientIdRef.current = getOrCreateClientId()
  }

  useEffect(() => {
    if (!agentRoom) {
      refs.roomIdRef.current = ''
      refs.profileRef.current = ''
      refs.prevRoomKeyRef.current = ''
      refs.gatewaySidRef.current = null
      refs.stateDbSidRef.current = null
      setProfile('')
      setAgentDisplayName('Workframe Agent')
      setNativeAgentName('Workframe Agent')
      setStateDbSessionId(null)
      setGatewaySessionId(null)
      setSessionReady(false)
      setConnectError(null)
      setTurnActive(false)
      setTurnStatus(null)
      setMessages([])
      return
    }

    const roomId = agentRoom.id
    if (refs.prevRoomKeyRef.current === roomId) return
    refs.prevRoomKeyRef.current = roomId

    console.log('[workframe] bind:room', roomId)
    refs.nativeProfileRef.current = nativeProfileSlug()
    const hintProf = resolveHermesProfileSlug(agentRoom, activeProfile)
    if (hintProf && hintProf === refs.nativeProfileRef.current) {
      markBindingSchema(hintProf, `${refs.sourceIdRef.current}:${refs.clientIdRef.current}`)
    }

    void loadWorkframeRuntimeConfig().then((runtime) => {
      refs.nativeProfileRef.current = runtime.nativeProfile
      setNativeAgentName(runtime.projectName ? `${runtime.projectName} Agent` : 'Workframe Agent')
    })
    void useSessionForRoomRef.current(roomId, roomDisplayName)
  }, [agentRoom, activeProfile, roomDisplayName, refs.clientIdRef, refs.gatewaySidRef, refs.nativeProfileRef, refs.prevRoomKeyRef, refs.profileRef, refs.roomIdRef, refs.sourceIdRef, refs.stateDbSidRef])

  const value = useMemo<HermesSessionState>(
    () => ({
      profile,
      agentDisplayName,
      nativeAgentName,
      stateDbSessionId,
      gatewaySessionId,
      sessionReady,
      connectError,
      turnActive,
      turnStatus,
      messages,
      startNewSession: bind.startNewSession,
      resumeSession: history.resumeSession,
      reloadHistory: history.reloadHistory,
      sendMessage: stream.sendMessage,
      attachImage: stream.attachImage,
    }),
    [
      profile,
      agentDisplayName,
      nativeAgentName,
      stateDbSessionId,
      gatewaySessionId,
      sessionReady,
      connectError,
      turnActive,
      turnStatus,
      messages,
      bind.startNewSession,
      history.resumeSession,
      history.reloadHistory,
      stream.sendMessage,
      stream.attachImage,
    ],
  )

  return <HermesSessionContext.Provider value={value}>{children}</HermesSessionContext.Provider>
}

export function useHermesSession(): HermesSessionState {
  const ctx = useContext(HermesSessionContext)
  if (!ctx) throw new Error('useHermesSession must be used within HermesSessionProvider')
  return ctx
}
