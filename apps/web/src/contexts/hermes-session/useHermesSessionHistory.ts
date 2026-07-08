import { useCallback, useEffect, type Dispatch, type SetStateAction } from 'react'

import { fetchChatMessages } from '@/lib/chatApi'
import { finalizeChatHandoff } from '@/lib/chatMerge'
import type { ChatMessage } from '@/lib/chatTypes'
import { workframeAuthApi } from '@/lib/workframeAuthApi'
import {
  readCachedMessages,
  writeActiveLane,
  writeCachedMessages,
  writeCachedRoomBind,
} from '@/lib/workspacePersist'

import type { HermesSessionBindApi } from './useHermesSessionBind'
import type { HermesSessionRefs } from './hermesSessionRefs'

type UseHermesSessionHistoryOptions = {
  refs: HermesSessionRefs
  bind: HermesSessionBindApi
  agentDisplayName: string
  activeHermesProfile: string
  setAgentDisplayName: (name: string) => void
  setProfile: (profile: string) => void
  setStateDbSessionId: (id: string | null) => void
  setGatewaySessionId: (id: string | null) => void
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>
  setConnectError: (error: string | null) => void
  setSessionReady: (ready: boolean) => void
  messages: ChatMessage[]
  completeTurn: () => void
}

export function useHermesSessionHistory({
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
}: UseHermesSessionHistoryOptions) {
  const {
    profileRef,
    templateProfileRef,
    roomIdRef,
    gatewaySidRef,
    stateDbSidRef,
    bindGenRef,
    llmReadyRef,
  } = refs
  const { bindingVersion } = bind

  const loadHistory = useCallback(async (prof: string, sessionId: string, mergeLocal = false) => {
    const roomId = roomIdRef.current
    if (roomId) {
      const cached = readCachedMessages(roomId, sessionId)
      if (cached.length) {
        setMessages((prev) => (mergeLocal ? finalizeChatHandoff(cached, prev) : cached))
      }
    }
    try {
      console.log('[workframe] loadHistory:', prof, sessionId.substring(0, 40))
      const { messages: rows } = await fetchChatMessages(prof, sessionId, refs.sourceIdRef.current)
      console.log('[workframe] loaded', rows.length, 'messages')
      setMessages((prev) => (mergeLocal ? finalizeChatHandoff(rows, prev) : rows))
      if (roomId) writeCachedMessages(roomId, sessionId, rows)
    } catch (err) {
      console.error('[workframe] loadHistory error:', err)
    }
  }, [refs.sourceIdRef, roomIdRef, setMessages])

  const reloadHistory = useCallback(async () => {
    const sid = stateDbSidRef.current
    const roomId = roomIdRef.current
    const prof = profileRef.current
    if (sid && prof && roomId) await loadHistory(prof, sid, true)
  }, [loadHistory, profileRef, roomIdRef, stateDbSidRef])

  const resumeSession = useCallback(async (sessionId: string) => {
    if (refs.turnActiveRef.current) completeTurn()
    const roomId = roomIdRef.current
    if (!roomId) throw new Error('No agent room selected')
    const sid = sessionId.trim()
    if (!sid) throw new Error('session_id required')
    const templateProf = templateProfileRef.current || activeHermesProfile || profileRef.current
    const gen = ++bindGenRef.current

    const data = await workframeAuthApi.activateRoomSession(roomId, {
      session_id: sid,
      profile: templateProf || undefined,
      source_id: refs.sourceIdRef.current,
      client_id: refs.clientIdRef.current,
      binding_version: bindingVersion(templateProf),
    })
    if (gen !== bindGenRef.current) return

    const runtimeProf = data.profile
    const gatewaySid = `api:${runtimeProf}:${sid}`
    const cachedMessages = readCachedMessages(roomId, sid)
    if (cachedMessages.length) setMessages(cachedMessages)
    stateDbSidRef.current = sid
    gatewaySidRef.current = gatewaySid
    profileRef.current = runtimeProf
    templateProfileRef.current = data.template_profile || templateProf
    if (data.agent_display_name) setAgentDisplayName(data.agent_display_name)
    setProfile(runtimeProf)
    setStateDbSessionId(sid)
    setGatewaySessionId(gatewaySid)
    writeCachedRoomBind(roomId, {
      sessionId: sid,
      profile: runtimeProf,
      templateProfile: data.template_profile || templateProf,
      agentDisplayName: data.agent_display_name || agentDisplayName,
      llmReady: llmReadyRef.current ?? true,
    })
    await loadHistory(runtimeProf, sid, false)
    writeActiveLane({ roomId })
    setConnectError(null)
    setSessionReady(true)
  }, [
    activeHermesProfile,
    agentDisplayName,
    bindGenRef,
    bindingVersion,
    completeTurn,
    gatewaySidRef,
    llmReadyRef,
    loadHistory,
    profileRef,
    refs.clientIdRef,
    refs.sourceIdRef,
    refs.turnActiveRef,
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
  ])

  useEffect(() => {
    const roomId = roomIdRef.current
    const sessionId = stateDbSidRef.current
    if (!roomId || !sessionId || !messages.length) return
    const timer = window.setTimeout(() => {
      writeCachedMessages(roomId, sessionId, messages)
    }, 400)
    return () => window.clearTimeout(timer)
  }, [messages, roomIdRef, stateDbSidRef])

  return { loadHistory, reloadHistory, resumeSession }
}
