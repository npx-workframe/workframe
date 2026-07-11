import { useCallback, type Dispatch, type SetStateAction } from 'react'

import { ensureRoomBind } from '@/lib/chatApi'
import { formatWorkframeError, type WorkframeNoticeInfo } from '@/lib/workframeErrors'
import { showWorkframeError } from '@/lib/workframeErrorToast'
import { WORKFRAME_UI_BINDING_VERSION } from '@/lib/chatSession'
import type { ChatMessage } from '@/lib/chatTypes'
import { notifyHermesModelsChanged } from '@/lib/hermesCatalogApi'
import {
  clearCachedMessages,
  clearCachedRoomBind,
  readCachedMessages,
  readCachedRoomBind,
  writeActiveLane,
  writeCachedMessages,
  writeCachedRoomBind,
} from '@/lib/workspacePersist'

import type { BoundSessionPayload, HermesSessionRefs } from './hermesSessionRefs'

type UseHermesSessionBindOptions = {
  refs: HermesSessionRefs
  agentDisplayName: string
  activeProfile: string
  setActiveRoute: (profile: string) => void
  setAgentDisplayName: (name: string) => void
  setProfile: (profile: string) => void
  setStateDbSessionId: (id: string | null) => void
  setGatewaySessionId: (id: string | null) => void
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>
  setConnectError: (error: WorkframeNoticeInfo | null) => void
  setSessionReady: (ready: boolean) => void
  completeTurn: () => void
}

export function useHermesSessionBind({
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
}: UseHermesSessionBindOptions) {
  const {
    profileRef,
    templateProfileRef,
    roomIdRef,
    gatewaySidRef,
    stateDbSidRef,
    nativeProfileRef,
    bindGenRef,
    llmReadyRef,
  } = refs

  const bindingVersion = useCallback((templateProf: string) => {
    const template = (templateProf || templateProfileRef.current || '').trim()
    const native = nativeProfileRef.current.trim()
    return template && native && template === native ? WORKFRAME_UI_BINDING_VERSION : undefined
  }, [nativeProfileRef, templateProfileRef])

  const bindRoomSession = useCallback(
    async (roomId: string, forceNew = false) => {
      const bound = await ensureRoomBind({
        room_id: roomId,
        source_id: refs.sourceIdRef.current,
        client_id: refs.clientIdRef.current,
        new_session: forceNew,
        title: forceNew ? `Session with ${agentDisplayName}` : undefined,
        binding_version: bindingVersion(templateProfileRef.current),
      })
      const sessionId = String(bound.sessionId || '').trim()
      if (!sessionId) throw new Error('Session creation failed')
      return {
        sessionId,
        profile: bound.profile,
        templateProfile: bound.templateProfile,
        agentDisplayName: bound.agentDisplayName,
        llmReady: bound.llmReady,
        messages: bound.messages,
      }
    },
    [agentDisplayName, bindingVersion, refs.clientIdRef, refs.sourceIdRef, templateProfileRef],
  )

  const requireBoundSessionId = useCallback((): string => {
    const sid = String(stateDbSidRef.current || '').trim()
    if (!sid) throw new Error('No bound session — reopen the agent room')
    return sid
  }, [stateDbSidRef])

  const applyBoundSession = useCallback(
    (roomId: string, templateProf: string, bound: BoundSessionPayload) => {
      const runtimeProf = bound.profile || templateProf
      const crewProf = bound.templateProfile || templateProf
      const gatewaySid = `api:${runtimeProf}:${bound.sessionId}`
      stateDbSidRef.current = bound.sessionId
      gatewaySidRef.current = gatewaySid
      profileRef.current = runtimeProf
      templateProfileRef.current = crewProf
      roomIdRef.current = roomId
      if (bound.agentDisplayName) setAgentDisplayName(bound.agentDisplayName)
      setProfile(runtimeProf)
      setStateDbSessionId(bound.sessionId)
      setGatewaySessionId(gatewaySid)
      setMessages(bound.messages)
      writeActiveLane({ roomId })
      writeCachedMessages(roomId, bound.sessionId, bound.messages)
      writeCachedRoomBind(roomId, {
        sessionId: bound.sessionId,
        profile: runtimeProf,
        templateProfile: crewProf,
        agentDisplayName: bound.agentDisplayName || '',
        llmReady: llmReadyRef.current ?? true,
      })
      setConnectError(null)
      setSessionReady(true)
      notifyHermesModelsChanged(runtimeProf)
    },
    [
      gatewaySidRef,
      llmReadyRef,
      profileRef,
      roomIdRef,
      setAgentDisplayName,
      setConnectError,
      setGatewaySessionId,
      setMessages,
      setProfile,
      setSessionReady,
      setStateDbSessionId,
      stateDbSidRef,
      templateProfileRef,
    ],
  )

  const useSessionForRoom = useCallback(
    async (roomId: string, displayName: string) => {
      const gen = ++bindGenRef.current
      console.log('[workframe] useSessionForRoom:', roomId)
      setConnectError(null)
      roomIdRef.current = roomId
      setAgentDisplayName(displayName)

      const cachedBind = readCachedRoomBind(roomId)
      if (cachedBind) {
        const cachedMessages = readCachedMessages(roomId, cachedBind.sessionId)
        llmReadyRef.current = cachedBind.llmReady
        const templateProf = cachedBind.templateProfile || cachedBind.profile
        if (templateProf && templateProf !== activeProfile) {
          setActiveRoute(templateProf)
        }
        applyBoundSession(roomId, templateProf, {
          sessionId: cachedBind.sessionId,
          profile: cachedBind.profile || templateProf,
          templateProfile: templateProf,
          agentDisplayName: cachedBind.agentDisplayName || displayName,
          messages: cachedMessages,
        })
      } else {
        setSessionReady(false)
        setStateDbSessionId(null)
        setGatewaySessionId(null)
        stateDbSidRef.current = null
        gatewaySidRef.current = null
        setMessages([])
      }

      try {
        const bound = await bindRoomSession(roomId)
        if (gen !== bindGenRef.current) return
        if (!bound.sessionId) throw new Error('Session creation failed')
        llmReadyRef.current = bound.llmReady
        const templateProf = bound.templateProfile || bound.profile
        if (templateProf && templateProf !== activeProfile) {
          setActiveRoute(templateProf)
        }
        applyBoundSession(roomId, templateProf, {
          sessionId: bound.sessionId,
          profile: bound.profile || templateProf,
          templateProfile: templateProf,
          agentDisplayName: bound.agentDisplayName || displayName,
          messages: bound.messages,
        })
      } catch (err) {
        if (gen !== bindGenRef.current) return
        if (cachedBind) {
          console.warn('[workframe] bind revalidate failed; keeping cached session', err)
          return
        }
        roomIdRef.current = ''
        stateDbSidRef.current = null
        gatewaySidRef.current = null
        setStateDbSessionId(null)
        setGatewaySessionId(null)
        const info = formatWorkframeError(err, 'Session bootstrap')
        setConnectError(info)
        showWorkframeError(info, { id: 'session-bootstrap' })
        setSessionReady(false)
      }
    },
    [
      activeProfile,
      applyBoundSession,
      bindGenRef,
      bindRoomSession,
      gatewaySidRef,
      llmReadyRef,
      roomIdRef,
      setActiveRoute,
      setAgentDisplayName,
      setConnectError,
      setGatewaySessionId,
      setMessages,
      setSessionReady,
      setStateDbSessionId,
      stateDbSidRef,
    ],
  )

  const startNewSession = useCallback(async () => {
    if (refs.turnActiveRef.current) completeTurn()
    const roomId = roomIdRef.current
    if (!roomId) throw new Error('No agent room selected')
    const gen = ++bindGenRef.current
    clearCachedMessages(roomId)
    clearCachedRoomBind(roomId)
    setConnectError(null)

    try {
      const bound = await bindRoomSession(roomId, true)
      if (gen !== bindGenRef.current) return
      if (!bound.sessionId) throw new Error('Session creation failed')
      llmReadyRef.current = bound.llmReady
      const templateProf = bound.templateProfile || bound.profile || templateProfileRef.current
      applyBoundSession(roomId, templateProf, {
        sessionId: bound.sessionId,
        profile: bound.profile || templateProf,
        templateProfile: templateProf,
        agentDisplayName: bound.agentDisplayName,
        messages: bound.messages,
      })
      refs.prevRoomKeyRef.current = roomId
    } catch (err) {
      if (gen !== bindGenRef.current) return
      const info = formatWorkframeError(err, 'New session')
      setConnectError(info)
      showWorkframeError(info, { id: 'new-session' })
      throw err
    }
  }, [
    applyBoundSession,
    bindGenRef,
    bindRoomSession,
    completeTurn,
    llmReadyRef,
    refs.prevRoomKeyRef,
    refs.turnActiveRef,
    roomIdRef,
    setConnectError,
    templateProfileRef,
  ])

  return {
    bindingVersion,
    bindRoomSession,
    requireBoundSessionId,
    applyBoundSession,
    useSessionForRoom,
    startNewSession,
  }
}

export type HermesSessionBindApi = ReturnType<typeof useHermesSessionBind>
