import { useCallback, useEffect, type Dispatch, type SetStateAction } from 'react'

import { streamProfileMessage, type ProfileStreamEvent } from '@/lib/chatApi'
import {
  appendTextSegment,
  appendThinkingSegment,
  completeTool,
  setFinalTextSegment,
  upsertRunningTool,
} from '@/lib/chatLiveSegments'
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
import { findAgentByProfile, type WorkframeAgent } from '@/lib/hermesProfile'
import {
  emptyAgentReplyText,
  formatWorkframeError,
  noticeFromStreamPayload,
  noticeMessage,
  streamErrorText,
  type WorkframeNoticeInfo,
} from '@/lib/workframeErrors'
import type { WorkframeRoute } from '@/lib/workframeRoutes'

import type { HermesSessionRefs } from './hermesSessionRefs'
import type { HermesSessionBindApi } from './useHermesSessionBind'

type UseHermesSessionStreamOptions = {
  refs: HermesSessionRefs
  bind: HermesSessionBindApi
  completeTurn: () => void
  sessionReady: boolean
  turnActive: boolean
  profile: string
  activeProfile: string
  agentDisplayName: string
  routes: WorkframeRoute[]
  crew: WorkframeAgent[]
  setActiveRoute: (profile: string) => void
  setTurnActive: (active: boolean) => void
  setTurnStatus: (status: string | null) => void
  setConnectError: (error: string | null) => void
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>
}

export function useHermesSessionStream({
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
}: UseHermesSessionStreamOptions) {
  const {
    profileRef,
    templateProfileRef,
    roomIdRef,
    gatewaySidRef,
    turnActiveRef,
    streamMessageIdRef,
    pendingOutboundRef,
    finalizedTurnIdsRef,
    llmReadyRef,
  } = refs
  const { bindingVersion, requireBoundSessionId } = bind

  const finalizeTurn = useCallback(
    (assistantId: string, _text: string) => {
      if (finalizedTurnIdsRef.current.has(assistantId)) return
      finalizedTurnIdsRef.current.add(assistantId)
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, ephemeral: false } : m)),
      )
      completeTurn()
    },
    [completeTurn, finalizedTurnIdsRef, setMessages],
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
    [setMessages, streamMessageIdRef],
  )

  const beginTurn = useCallback((assistantId: string) => {
    turnActiveRef.current = true
    setTurnActive(true)
    streamMessageIdRef.current = assistantId
    setTurnStatus('Sending...')
  }, [setTurnActive, setTurnStatus, streamMessageIdRef, turnActiveRef])

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
    [gatewaySidRef, patchStream, setTurnStatus, turnActiveRef],
  )

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
    [handleEvent, setMessages, streamMessageIdRef],
  )

  const sendMessage = useCallback(
    async (text: string) => {
      if (!sessionReady) return
      let outbound = text.trim()
      if (!outbound) return

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
          source_id: refs.sourceIdRef.current,
          client_id: refs.clientIdRef.current,
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
    [
      agentDisplayName,
      applyStreamEvent,
      beginTurn,
      bindingVersion,
      crew,
      finalizeTurn,
      llmReadyRef,
      pendingOutboundRef,
      profileRef,
      refs.clientIdRef,
      refs.sourceIdRef,
      requireBoundSessionId,
      roomIdRef,
      routes,
      sessionReady,
      setActiveRoute,
      setConnectError,
      setMessages,
      setTurnActive,
      setTurnStatus,
      streamMessageIdRef,
      templateProfileRef,
      turnActiveRef,
      finalizedTurnIdsRef,
    ],
  )

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
          source_id: refs.sourceIdRef.current,
          client_id: refs.clientIdRef.current,
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
    [
      agentDisplayName,
      applyStreamEvent,
      beginTurn,
      bindingVersion,
      crew,
      finalizeTurn,
      finalizedTurnIdsRef,
      gatewaySidRef,
      profileRef,
      refs.clientIdRef,
      refs.sourceIdRef,
      requireBoundSessionId,
      roomIdRef,
      sessionReady,
      setConnectError,
      setMessages,
      setTurnActive,
      setTurnStatus,
      streamMessageIdRef,
      templateProfileRef,
      turnActiveRef,
    ],
  )

  useEffect(() => {
    if (!sessionReady || turnActive) return
    const pending = pendingOutboundRef.current
    if (!pending || profile !== activeProfile) return
    pendingOutboundRef.current = null
    void sendMessage(pending)
  }, [activeProfile, pendingOutboundRef, profile, sendMessage, sessionReady, turnActive])

  return { sendMessage, attachImage }
}
