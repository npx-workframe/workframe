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
import {
  ensureRoomBind,
  fetchChatMessages,
  streamProfileMessage,
  type ProfileStreamEvent,
} from '@/lib/chatApi'
import { isAgentChatRoom, resolveHermesProfileSlug } from '@/lib/agentProfile'
import {
  appendTextSegment,
  appendThinkingSegment,
  completeTool,
  setFinalTextSegment,
  upsertRunningTool,
} from '@/lib/chatLiveSegments'
import { finalizeChatHandoff } from '@/lib/chatMerge'
import {
  getOrCreateClientId,
  markBindingSchema,
  WORKFRAME_UI_BINDING_VERSION,
} from '@/lib/chatSession'
import type { ChatMessage, ChatSegment } from '@/lib/chatTypes'
import {
  emptyAgentStreamMessage,
  userChatMessage,
  userImageChatMessage,
} from '@/lib/chatTypes'
import { uploadBinaryFile } from '@/lib/filesApi'
import { attachImagePath } from '@/lib/hermesGatewayApi'
import {
  eventText,
  eventToolName,
  type HermesEventFrame,
} from '@/lib/hermesEvents'
import { formatWorkframeError, formatWorkframeErrorMessage, noticeMessage, emptyAgentReplyText, streamErrorText, noticeFromStreamPayload, type WorkframeNoticeInfo } from '@/lib/workframeErrors'
import { notifyHermesModelsChanged } from '@/lib/hermesCatalogApi'
import { loadWorkframeRuntimeConfig, nativeProfileSlug } from '@/lib/workframeProfile'
import { findAgentByProfile } from '@/lib/hermesProfile'
import { workframeAuthApi } from '@/lib/workframeAuthApi'
import {
  clearCachedMessages,
  clearCachedRoomBind,
  readCachedMessages,
  readCachedRoomBind,
  writeActiveLane,
  writeCachedMessages,
  writeCachedRoomBind,
} from '@/lib/workspacePersist'

// ─── Types ───────────────────────────────────────────────────────────────────

export type HermesSessionState = {
  profile: string
  agentDisplayName: string
  nativeAgentName: string
  stateDbSessionId: string | null
  gatewaySessionId: string | null
  sessionReady: boolean
  connectError: string | null
  turnActive: boolean
  turnStatus: string | null
  messages: ChatMessage[]
  startNewSession: () => Promise<void>
  resumeSession: (sessionId: string) => Promise<void>
  reloadHistory: () => Promise<void>
  sendMessage: (text: string) => Promise<void>
  attachImage: (file: File) => Promise<void>
}



const HermesSessionContext = createContext<HermesSessionState | null>(null)

export function HermesSessionProvider({ children }: { children: ReactNode }) {
  const { activeRoute, activeProfile, routes, setActiveRoute } = useAgentRoute()
  const { activeRoom } = useWorkspacePanels()
  const projectName = import.meta.env.VITE_WORKFRAME_PROJECT?.trim() || 'Workframe'
  const { crew } = useCrew(projectName)
  const agentRoom = isAgentChatRoom(activeRoom) ? activeRoom : null
  const activeHermesProfile = agentRoom ? resolveHermesProfileSlug(agentRoom, activeProfile) : ''

  // ── State ──
  const [profile, setProfile] = useState('')
  const [agentDisplayName, setAgentDisplayName] = useState('Workframe Agent')
  const [nativeAgentName, setNativeAgentName] = useState('Workframe Agent')
  const [stateDbSessionId, setStateDbSessionId] = useState<string | null>(null)
  const [gatewaySessionId, setGatewaySessionId] = useState<string | null>(null)
  const [sessionReady, setSessionReady] = useState(false)
  const [connectError, setConnectError] = useState<string | null>(null)
  const [turnActive, setTurnActive] = useState(false)
  const [turnStatus, setTurnStatus] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])

  // ── Refs (stable across renders) ──
  const profileRef = useRef('')
  const templateProfileRef = useRef('')
  const roomIdRef = useRef('')
  const gatewaySidRef = useRef<string | null>(null)
  const stateDbSidRef = useRef<string | null>(null)
  const turnActiveRef = useRef(false)
  const streamMessageIdRef = useRef<string | null>(null)
  const pendingOutboundRef = useRef<string | null>(null)
  const sourceIdRef = useRef('ui')
  const clientIdRef = useRef('default')
  const nativeProfileRef = useRef('')
  const finalizedTurnIdsRef = useRef(new Set<string>())
  const prevRoomKeyRef = useRef('')
  const bindGenRef = useRef(0)
  const initRef = useRef(false)
  const llmReadyRef = useRef<boolean | null>(null)

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

  // ── Binding version: native template uses v2 (runtime u-* slugs map to same template) ──
  const bindingVersion = useCallback((templateProf: string) => {
    const template = (templateProf || templateProfileRef.current || '').trim()
    const native = nativeProfileRef.current.trim()
    return template && native && template === native ? WORKFRAME_UI_BINDING_VERSION : undefined
  }, [])

  // ── Bind room → Hermes session (room SSOT — server derives profile from room) ──
  const bindRoomSession = useCallback(
    async (roomId: string, forceNew = false) => {
      const bound = await ensureRoomBind({
        room_id: roomId,
        source_id: sourceIdRef.current,
        client_id: clientIdRef.current,
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
    [agentDisplayName, bindingVersion],
  )

  // ── Get or create session for a room+profile ──
  const requireBoundSessionId = useCallback((): string => {
    const sid = String(stateDbSidRef.current || '').trim()
    if (!sid) throw new Error('No bound session — reopen the agent room')
    return sid
  }, [])

  // ── Load history from BFF ──
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
      const { messages: rows } = await fetchChatMessages(prof, sessionId, sourceIdRef.current)
      console.log('[workframe] loaded', rows.length, 'messages')
      setMessages((prev) => (mergeLocal ? finalizeChatHandoff(rows, prev) : rows))
      if (roomId) writeCachedMessages(roomId, sessionId, rows)
    } catch (err) {
      console.error('[workframe] loadHistory error:', err)
    }
  }, [])

  // ── Open session for an agent room: bind once per room, load history from bind. ──
  const applyBoundSession = useCallback(
    (
      roomId: string,
      templateProf: string,
      bound: {
        sessionId: string
        profile: string
        templateProfile: string
        agentDisplayName: string
        messages: ChatMessage[]
      },
    ) => {
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
    [],
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
        setConnectError(formatWorkframeErrorMessage(err, 'Session bootstrap'))
        setSessionReady(false)
      }
    },
    [activeProfile, applyBoundSession, bindRoomSession, setActiveRoute],
  )

  // ── Effect: open session on agent room change ──
  const useSessionForRoomRef = useRef(useSessionForRoom)
  useSessionForRoomRef.current = useSessionForRoom

  // One-time initialization on mount
  if (!initRef.current) {
    initRef.current = true
    try {
      const url = new URL(window.location.href)
      const src = (url.searchParams.get('source') || url.searchParams.get('wf_source') || '').trim()
      if (src) sourceIdRef.current = src
    } catch {}
    clientIdRef.current = getOrCreateClientId()
  }

  useEffect(() => {
    if (!agentRoom) {
      roomIdRef.current = ''
      profileRef.current = ''
      prevRoomKeyRef.current = ''
      gatewaySidRef.current = null
      stateDbSidRef.current = null
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
    if (prevRoomKeyRef.current === roomId) return
    prevRoomKeyRef.current = roomId

    console.log('[workframe] bind:room', roomId)
    nativeProfileRef.current = nativeProfileSlug()
    const hintProf = resolveHermesProfileSlug(agentRoom, activeProfile)
    if (hintProf && hintProf === nativeProfileRef.current) {
      markBindingSchema(hintProf, `${sourceIdRef.current}:${clientIdRef.current}`)
    }

    void loadWorkframeRuntimeConfig().then((runtime) => {
      nativeProfileRef.current = runtime.nativeProfile
      setNativeAgentName(runtime.projectName ? `${runtime.projectName} Agent` : 'Workframe Agent')
    })
    void useSessionForRoomRef.current(roomId, roomDisplayName)
  }, [agentRoom, activeProfile, roomDisplayName])

  useEffect(() => {
    const roomId = roomIdRef.current
    const sessionId = stateDbSidRef.current
    if (!roomId || !sessionId || !messages.length) return
    const timer = window.setTimeout(() => {
      writeCachedMessages(roomId, sessionId, messages)
    }, 400)
    return () => window.clearTimeout(timer)
  }, [messages])

  // ── Turn management ──
  const completeTurn = useCallback(() => {
    turnActiveRef.current = false
    setTurnActive(false)
    streamMessageIdRef.current = null
    setTurnStatus(null)
    setMessages((prev) => prev.map((m) => (m.ephemeral ? { ...m, ephemeral: false } : m)))
  }, [])

  const finalizeTurn = useCallback(
    (assistantId: string, _text: string) => {
      if (finalizedTurnIdsRef.current.has(assistantId)) return
      finalizedTurnIdsRef.current.add(assistantId)
      // Preserve the full segment stream (thinking, tool runs, text). The text
      // was already accumulated into segments by `appendTextSegment` during
      // streaming — the clobber that used to live here dropped tool/thinking
      // segments and lost the agent's evidence trail.
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, ephemeral: false } : m)),
      )
      completeTurn()
    },
    [completeTurn],
  )

  const patchStream = useCallback(
    (updater: (segments: ChatSegment[]) => ChatSegment[]) => {
      const id = streamMessageIdRef.current
      if (!id) return
      setMessages((prev) => {
        if (!prev.some((m) => m.id === id)) return prev
        return prev.map((m) => (m.id === id ? { ...m, segments: updater(m.segments) } : m))
      })
    },
    [],
  )

  const beginTurn = useCallback((assistantId: string) => {
    turnActiveRef.current = true
    setTurnActive(true)
    streamMessageIdRef.current = assistantId
    setTurnStatus('Sending...')
  }, [])

  // ── Hermes event handler ──
  const handleEvent = useCallback(
    (frame: HermesEventFrame) => {
      if (gatewaySidRef.current && frame.sessionId && frame.sessionId !== gatewaySidRef.current) return
      if (!turnActiveRef.current) return

      const { type, payload } = frame
      const toolName = eventToolName(payload)
      const isInternalThinking = toolName === '_thinking'

      switch (type) {
        case 'message.start':
          setTurnStatus('Running...')
          break
        case 'status.update':
          setTurnStatus(eventText(payload) || null)
          break
        case 'thinking.delta':
        case 'reasoning.delta':
          patchStream((s) => appendThinkingSegment(s, eventText(payload)))
          setTurnStatus('Thinking...')
          break
        case 'tool.start':
          patchStream((s) => upsertRunningTool(s, toolName))
          setTurnStatus(`Running ${toolName}...`)
          break
        case 'tool.progress':
          if (isInternalThinking) { setTurnStatus('Thinking...'); break }
          patchStream((s) => upsertRunningTool(s, toolName, eventText(payload)))
          break
        case 'tool.complete':
          if (isInternalThinking) { setTurnStatus(null); break }
          patchStream((s) => completeTool(s, toolName, String(payload.summary ?? payload.result_text ?? payload.output ?? '')))
          setTurnStatus(null)
          break
        case 'tool.generating':
          setTurnStatus(`Running ${toolName}...`)
          break
        case 'message.delta':
        case 'assistant.delta':
        case 'assistant.message':
        case 'message.final':
          patchStream((s) => appendTextSegment(s, eventText(payload)))
          setTurnStatus('Writing...')
          break
        case 'message.complete':
          patchStream((s) => setFinalTextSegment(s, eventText(payload)))
          setTurnStatus(null)
          break
        case 'error':
          patchStream((s) => appendTextSegment(s, streamErrorText(payload)))
          setTurnStatus(null)
          break
      }
    },
    [patchStream],
  )

  // ── Stream event adapter ──
  const applyStreamEvent = useCallback(
    (evt: ProfileStreamEvent) => {
      const { event, data } = evt
      switch (event) {
        case 'run.started': {
          handleEvent({ type: 'status.update', sessionId: '', payload: { text: 'Running...' } })
          const streamId = streamMessageIdRef.current
          const model = String(data.model ?? '').trim()
          const llmProv = String(data.llm_provider ?? '').trim()
          if (streamId && (model || llmProv)) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === streamId
                  ? {
                      ...m,
                      ...(model ? { modelId: model } : {}),
                      ...(llmProv ? { llmProvider: llmProv } : {}),
                    }
                  : m,
              ),
            )
          }
          break
        }
        case 'message.started':
          handleEvent({ type: 'message.start', sessionId: '', payload: data })
          break
        case 'thinking.delta':
        case 'reasoning.delta':
          handleEvent({ type: 'thinking.delta', sessionId: '', payload: { text: String(data.delta ?? data.text ?? data.content ?? '') } })
          break
        case 'message.delta':
        case 'assistant.delta':
          handleEvent({ type: 'message.delta', sessionId: '', payload: { text: String(data.delta ?? data.text ?? '') } })
          break
        case 'message.complete':
        case 'assistant.completed':
          handleEvent({ type: 'message.complete', sessionId: '', payload: { text: String(data.content ?? data.text ?? '') } })
          break
        case 'tool.started':
          handleEvent({ type: 'tool.start', sessionId: '', payload: { tool_name: data.tool_name, preview: data.preview } })
          break
        case 'tool.completed':
          handleEvent({ type: 'tool.complete', sessionId: '', payload: { tool_name: data.tool_name, output: data.preview ?? data.output ?? '' } })
          break
        case 'tool.failed':
          handleEvent({ type: 'tool.complete', sessionId: '', payload: { tool_name: data.tool_name, output: data.preview ?? 'Tool failed' } })
          break
        case 'tool.progress':
          handleEvent({ type: 'tool.progress', sessionId: '', payload: { tool_name: data.tool_name, preview: data.delta ?? data.preview ?? '' } })
          break
        case 'error':
        case 'run.failed':
          handleEvent({ type: 'error', sessionId: '', payload: data })
          break
        case 'done':
          break
      }
    },
    [handleEvent],
  )

  // ── Send message ──
  const sendMessage = useCallback(
    async (text: string) => {
      if (!sessionReady) return
      let outbound = text.trim()
      if (!outbound) return

      // Route command: /profile message
      const routeMatch = outbound.match(/^\/([a-z][a-z0-9-]*)\s+([\s\S]*)$/)
      if (routeMatch && routes.some((r) => r.profile === routeMatch[1])) {
        const targetProfile = routeMatch[1]
        outbound = routeMatch[2].trim()
        if (!outbound) return
        if (targetProfile !== profileRef.current) {
          pendingOutboundRef.current = outbound
          setActiveRoute(targetProfile)
          return
        }
      }

      const prof = profileRef.current
      const templateProf = templateProfileRef.current || prof
      const crewProf = templateProf
      const display = agentDisplayName
      const timeLabel = new Date().toISOString()
      const userId = `u-${Date.now()}`
      const assistantId = `a-${Date.now()}`
      finalizedTurnIdsRef.current.delete(assistantId)

      const crewAgent = findAgentByProfile(crew, crewProf)
      const streamAvatar = crewAgent?.avatarUrl ?? null

      setMessages((prev) => [
        ...prev,
        userChatMessage(userId, outbound, timeLabel),
        emptyAgentStreamMessage(assistantId, crewProf, display, timeLabel, streamAvatar),
      ])
      beginTurn(assistantId)

      try {
        const roomId = roomIdRef.current
        const sid = requireBoundSessionId()
        let finalText = ''
        let streamError = ''
        let conciergeNotice: WorkframeNoticeInfo | null = null

        await streamProfileMessage({
          profile: prof,
          session_id: sid,
          room_id: roomId,
          source_id: sourceIdRef.current,
          client_id: clientIdRef.current,
          binding_version: bindingVersion(templateProf),
          text: outbound,
        }, (evt) => {
          applyStreamEvent(evt)
          if (evt.event === 'concierge') {
            conciergeNotice = noticeFromStreamPayload(evt.data)
            finalText = noticeMessage(conciergeNotice)
          }
          if (evt.event === 'assistant.delta' || evt.event === 'message.delta') {
            finalText += String(evt.data.delta ?? evt.data.text ?? '')
          }
          if (evt.event === 'error' || evt.event === 'run.failed') {
            conciergeNotice = noticeFromStreamPayload(evt.data)
            streamError = noticeMessage(conciergeNotice)
            finalText = streamError
          }
          if (evt.event === 'assistant.completed' || evt.event === 'message.complete') {
            finalText = String(evt.data.content ?? evt.data.text ?? finalText)
          }
          if (evt.event === 'done') {
            finalizeTurn(assistantId, finalText)
          }
        })

        finalizeTurn(assistantId, finalText)

        if (conciergeNotice || !finalText.trim()) {
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== assistantId) return m
              if (conciergeNotice) {
                return {
                  ...m,
                  ephemeral: false,
                  segments: [{ kind: 'concierge', notice: conciergeNotice }],
                }
              }
              if (m.segments.length > 0) return m
              return {
                ...m,
                segments: [{
                  kind: 'text',
                  text: emptyAgentReplyText({
                    streamError,
                    llmReady: llmReadyRef.current ?? undefined,
                  }),
                }],
              }
            }),
          )
        }
      } catch (err) {
        turnActiveRef.current = false
        setTurnActive(false)
        streamMessageIdRef.current = null
        setTurnStatus(null)
        const info = formatWorkframeError(err, 'Send message')
        setConnectError(noticeMessage(info))
        setMessages((prev) => prev.filter((m) => m.id !== assistantId))
      }
    },
    [sessionReady, routes, crew, agentDisplayName, beginTurn, requireBoundSessionId, applyStreamEvent, finalizeTurn, bindingVersion],
  )

  // ── Pending outbound (after lane switch) ──
  useEffect(() => {
    if (!sessionReady || turnActive) return
    const pending = pendingOutboundRef.current
    if (!pending || profile !== activeProfile) return
    pendingOutboundRef.current = null
    void sendMessage(pending)
  }, [sessionReady, turnActive, profile, activeProfile, sendMessage])

  // ── Attach image ──
  const attachImage = useCallback(
    async (file: File) => {
      if (!sessionReady) return
      const prof = profileRef.current
      const templateProf = templateProfileRef.current || prof
      const crewProf = templateProf
      const display = agentDisplayName
      const timeLabel = new Date().toISOString()
      const userId = `u-${Date.now()}`
      const assistantId = `a-${Date.now()}`
      finalizedTurnIdsRef.current.delete(assistantId)
      const safeName = file.name.replace(/[^\w.-]+/g, '_') || 'paste.png'
      const relPath = `.workframe/chat-uploads/${Date.now()}-${safeName}`

      const crewAgent = findAgentByProfile(crew, crewProf)
      const streamAvatar = crewAgent?.avatarUrl ?? null

      setMessages((prev) => [
        ...prev,
        userImageChatMessage(userId, relPath, safeName, timeLabel),
        emptyAgentStreamMessage(assistantId, crewProf, display, timeLabel, streamAvatar),
      ])
      beginTurn(assistantId)

      try {
        const uploadedPath = await uploadBinaryFile(relPath, file)
        const workspacePath = `/workspace/${uploadedPath.replace(/^\/+/, '')}`
        const gwSid = gatewaySidRef.current || ''
        const attachedText = gwSid && !gwSid.startsWith('api:')
          ? (await attachImagePath(gwSid, workspacePath)).text?.trim() || ''
          : ''
        const submitText = attachedText || `[User attached image: ${safeName}]`
        const roomId = roomIdRef.current
        const sid = requireBoundSessionId()
        let finalText = ''

        await streamProfileMessage({
          profile: prof,
          session_id: sid,
          room_id: roomId,
          source_id: sourceIdRef.current,
          client_id: clientIdRef.current,
          binding_version: bindingVersion(templateProf),
          text: submitText,
        }, (evt) => {
          applyStreamEvent(evt)
          if (evt.event === 'assistant.delta' || evt.event === 'message.delta') {
            finalText += String(evt.data.delta ?? evt.data.text ?? '')
          }
          if (evt.event === 'assistant.completed' || evt.event === 'message.complete') {
            finalText = String(evt.data.content ?? evt.data.text ?? '')
          }
          if (evt.event === 'done') {
            finalizeTurn(assistantId, finalText)
          }
        })
        finalizeTurn(assistantId, finalText)
      } catch (err) {
        turnActiveRef.current = false
        setTurnActive(false)
        streamMessageIdRef.current = null
        setTurnStatus(null)
        const info = formatWorkframeError(err, 'Image upload')
        setConnectError(noticeMessage(info))
        setMessages((prev) => prev.filter((m) => m.id !== assistantId))
      }
    },
    [sessionReady, crew, agentDisplayName, beginTurn, requireBoundSessionId, applyStreamEvent, finalizeTurn, bindingVersion],
  )

  // ── New session ──
  const startNewSession = useCallback(async () => {
    if (turnActiveRef.current) completeTurn()
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
      prevRoomKeyRef.current = roomId
    } catch (err) {
      if (gen !== bindGenRef.current) return
      setConnectError(formatWorkframeErrorMessage(err, 'New session'))
      throw err
    }
  }, [applyBoundSession, bindRoomSession, completeTurn])

  const resumeSession = useCallback(async (sessionId: string) => {
    if (turnActiveRef.current) completeTurn()
    const roomId = roomIdRef.current
    if (!roomId) throw new Error('No agent room selected')
    const sid = sessionId.trim()
    if (!sid) throw new Error('session_id required')
    const templateProf = templateProfileRef.current || activeHermesProfile || profileRef.current
    const gen = ++bindGenRef.current

    const data = await workframeAuthApi.activateRoomSession(roomId, {
      session_id: sid,
      profile: templateProf || undefined,
      source_id: sourceIdRef.current,
      client_id: clientIdRef.current,
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
  }, [activeHermesProfile, bindingVersion, completeTurn, loadHistory])

  // ── Reload history ──
  const reloadHistory = useCallback(async () => {
    const sid = stateDbSidRef.current
    const roomId = roomIdRef.current
    const prof = profileRef.current
    if (sid && prof && roomId) await loadHistory(prof, sid, true)
  }, [loadHistory])

  // ── Context value ──
  const value = useMemo<HermesSessionState>(
    () => ({
      profile, agentDisplayName, nativeAgentName,
      stateDbSessionId, gatewaySessionId, sessionReady, connectError,
      turnActive, turnStatus, messages,
      startNewSession, resumeSession, reloadHistory, sendMessage, attachImage,
    }),
    [profile, agentDisplayName, nativeAgentName, stateDbSessionId, gatewaySessionId,
     sessionReady, connectError, turnActive, turnStatus, messages,
     startNewSession, resumeSession, reloadHistory, sendMessage, attachImage],
  )

  return <HermesSessionContext.Provider value={value}>{children}</HermesSessionContext.Provider>
}

export function useHermesSession(): HermesSessionState {
  const ctx = useContext(HermesSessionContext)
  if (!ctx) throw new Error('useHermesSession must be used within HermesSessionProvider')
  return ctx
}
