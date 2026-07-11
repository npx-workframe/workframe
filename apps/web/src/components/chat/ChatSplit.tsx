import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { Composer, type ComposerHandle } from '@/components/chat/Composer'
import { CommandModelPickerMount } from '@/components/chat/CommandModelPickerMount'
import { CommandDialogsProvider } from '@/contexts/CommandDialogsContext'
import type { MentionAgent } from '@/components/chat/MentionPalette'
import { MessageList } from '@/components/chat/MessageList'
import { useHermesSession } from '@/contexts/HermesSessionContext'
import { useWorkspacePanels } from '@/contexts/WorkspacePanelsContext'
import { useVerticalSplit } from '@/hooks/useVerticalSplit'
import { useDebouncedCallback } from '@/hooks/useDebouncedCallback'
import { isAgentChatRoom } from '@/lib/agentProfile'
import { isProjectRoom } from '@/lib/roomChat'
import {
  createLiveTurnBatcher,
  liveTurnStatusText,
  liveTurnToChatMessage,
  watchRoomLive,
  type RoomLiveFrame,
} from '@/lib/roomLive'
import { mergeRoomMessageHistory } from '@/lib/chatMerge'
import type { ChatMessage } from '@/lib/chatTypes'
import { systemNoticeChatMessage } from '@/lib/chatTypes'
import { ProviderRequiredDialog } from '@/components/dialogs/ProviderRequiredDialog'
import { WorkframeNotice } from '@/components/ui/WorkframeNotice'
import {
  formatWorkframeError,
  formatWorkframeErrorMessage,
  noticeMessage,
} from '@/lib/workframeErrors'
import { showWorkframeError } from '@/lib/workframeErrorToast'
import { resolveUserAvatarUrl } from '@/lib/avatarResolve'
import { mentionHandleFromLabel } from '@/lib/mentionHandle'
import { resolveAgentAvatarUrl } from '@/lib/avatarResolve'
import { useCrew } from '@/hooks/useCrew'
import { workframeAuthApi, watchWorkspaceEvents } from '@/lib/workframeAuthApi'
import {
  readCachedProjectRoomMessages,
  writeCachedProjectRoomMessages,
} from '@/lib/workspacePersist'
import { cn } from '@/lib/utils'

function roomMessageToChatMessage(
  message: {
    id: string
    sender_user_id?: string | null
    sender_agent_id?: string | null
    sender_agent_slug?: string | null
    sender_agent_name?: string | null
    model?: string | null
    llm_provider?: string | null
    content: string
    created_at?: string
  },
  meUserId: string,
  memberNames: Record<string, string>,
  memberAvatars: Record<string, string | null | undefined>,
  agentNames: Record<string, string>,
  agentSlugs: Record<string, string>,
): ChatMessage {
  const isUser = Boolean(message.sender_user_id)
  const agentSlug =
    String(message.sender_agent_slug || '').trim() ||
    (message.sender_agent_id ? agentSlugs[message.sender_agent_id] : '') ||
    ''
  const authorId = isUser
    ? (message.sender_user_id || 'system')
    : (agentSlug || message.sender_agent_id || 'system')
  const authorName = message.sender_user_id
    ? (message.sender_user_id === meUserId ? 'You' : memberNames[message.sender_user_id] || 'Member')
    : (message.sender_agent_name ||
      (message.sender_agent_id ? agentNames[message.sender_agent_id] : '') ||
      'Agent')

  return {
    id: message.id,
    authorId,
    authorName,
    role: isUser ? 'user' : 'agent',
    segments: [{ kind: 'text', text: message.content }],
    timestamp: message.created_at ? new Date(Number(message.created_at) * 1000).toISOString() : new Date().toISOString(),
    tokens: 0,
    ...(message.model ? { modelId: message.model } : {}),
    ...(message.llm_provider ? { llmProvider: message.llm_provider } : {}),
    avatarUrl: message.sender_user_id ? resolveUserAvatarUrl(memberAvatars[message.sender_user_id]) : undefined,
  }
}

export function ChatSplit() {
  const { activeRoom } = useWorkspacePanels()
  const [providerDialogOpen, setProviderDialogOpen] = useState(false)
  const {
    agentDisplayName,
    nativeAgentName,
    sessionReady,
    connectError,
    turnActive,
    turnStatus,
    messages,
    sendMessage,
    attachImage,
  } = useHermesSession()
  const [composerMinPx, setComposerMinPx] = useState(0)
  const [roomMessages, setRoomMessages] = useState<ChatMessage[] | null>(null)
  const [liveTurns, setLiveTurns] = useState<Record<string, ChatMessage>>({})
  const [roomLoading, setRoomLoading] = useState(false)
  const [roomError, setRoomError] = useState('')
  const [roomMentionAgents, setRoomMentionAgents] = useState<MentionAgent[]>([])
  const [spaceTurnActive, setSpaceTurnActive] = useState(false)
  const [spaceTurnStatus, setSpaceTurnStatus] = useState<string | null>(null)
  const [spaceWaitTurnId, setSpaceWaitTurnId] = useState<string | null>(null)
  const roomRevisionRef = useRef('')
  const reloadGenRef = useRef(0)
  const activeHumanRoomIdRef = useRef<string | null>(null)
  const roomStateByIdRef = useRef<Record<string, ChatMessage[]>>({})
  const roomMessagesRef = useRef<ChatMessage[] | null>(null)
  const liveTurnsRef = useRef<Record<string, ChatMessage>>({})
  const meUserIdRef = useRef('')
  const meAvatarRef = useRef<string | null>(null)
  const liveMetaRef = useRef<Record<string, { agentName: string; agentSlug: string; modelId?: string; llmProvider?: string }>>({})
  const liveBatcherRef = useRef(createLiveTurnBatcher((updates) => {
    setLiveTurns((prev) => ({ ...prev, ...updates }))
  }))
  const composerRef = useRef<ComposerHandle>(null)
  const projectName = import.meta.env.VITE_WORKFRAME_PROJECT?.trim() || 'Workframe'
  const { crew } = useCrew(projectName)
  const crewRef = useRef(crew)
  crewRef.current = crew
  roomMessagesRef.current = roomMessages
  liveTurnsRef.current = liveTurns

  const {
    composerHeight,
    composerMinPx: minPx,
    onSashPointerDown,
    onSashPointerMove,
    onSashPointerUp,
    collapseComposer,
    expandComposer,
  } = useVerticalSplit(120, composerMinPx)

  const isCollapsed = minPx > 0 && composerHeight <= minPx + 2

  const humanRoom = activeRoom && !isAgentChatRoom(activeRoom) ? activeRoom : null
  const projectRoom = humanRoom && isProjectRoom(humanRoom) ? humanRoom : null

  const displayRoomMessages = useMemo(() => {
    const base = roomMessages ?? []
    const live = Object.values(liveTurns)
    if (!live.length) return base
    const ids = new Set(base.map((message) => message.id))
    return [...base, ...live.filter((message) => !ids.has(message.id))]
  }, [roomMessages, liveTurns])

  const persistRoomSnapshot = useCallback((roomId: string) => {
    const msgs = roomMessagesRef.current
    if (!msgs?.length) return
    roomStateByIdRef.current[roomId] = msgs
    writeCachedProjectRoomMessages(roomId, msgs)
  }, [])

  const hydrateRoomState = useCallback((roomId: string): ChatMessage[] => {
    const mem = roomStateByIdRef.current[roomId]
    if (mem?.length) return mem
    return readCachedProjectRoomMessages(roomId)
  }, [])

  const roomLocalSnapshot = useCallback(
    (roomId: string) => [
      ...(activeHumanRoomIdRef.current === roomId
        ? (roomMessagesRef.current ?? [])
        : hydrateRoomState(roomId)),
      ...Object.values(liveTurnsRef.current),
    ],
    [hydrateRoomState],
  )

  const dmWaitMessageId = useMemo(() => {
    if (!turnActive) return null
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const row = messages[i]
      if (row.ephemeral && row.role !== 'user') return row.id
    }
    return null
  }, [turnActive, messages])

  const displayAgentMessages = useMemo(() => {
    if (!connectError) return messages
    const noticeId = connectError.code ?? 'connect-error'
    const stableId = `sys-notice-${noticeId}`
    if (messages.some((row) => row.id === stableId)) return messages
    return [
      ...messages,
      systemNoticeChatMessage(connectError, {
        id: stableId,
        authorName: nativeAgentName,
      }),
    ]
  }, [connectError, messages, nativeAgentName])

  const reloadRoomMessages = useCallback(async (roomId: string, opts?: { silent?: boolean }) => {
    const gen = ++reloadGenRef.current
    if (!opts?.silent) setRoomLoading(true)
    setRoomError('')
    try {
      const [messagesResponse, membersResponse, meResponse] = await Promise.all([
        workframeAuthApi.listRoomMessages(roomId),
        workframeAuthApi.listRoomMembers(roomId),
        workframeAuthApi.getMe(),
      ])
      if (gen !== reloadGenRef.current) return null
      meUserIdRef.current = meResponse.user.user_id
      meAvatarRef.current = meResponse.user.avatar_url ?? null
      const memberNames = (membersResponse.members ?? []).reduce<Record<string, string>>((acc, member) => {
        if (member.user_id) acc[member.user_id] = member.display_name || member.email || member.user_id
        return acc
      }, {})
      const memberAvatars = (membersResponse.members ?? []).reduce<Record<string, string | null | undefined>>((acc, member) => {
        if (member.user_id) acc[member.user_id] = member.avatar_url
        return acc
      }, {})
      const agentNames = (membersResponse.members ?? []).reduce<Record<string, string>>((acc, member) => {
        if (member.agent_profile_id) {
          acc[member.agent_profile_id] = member.display_name || member.handle || member.hermes_profile || 'Agent'
        }
        return acc
      }, {})
      const agentSlugs = (membersResponse.members ?? []).reduce<Record<string, string>>((acc, member) => {
        if (member.agent_profile_id && member.hermes_profile) {
          acc[member.agent_profile_id] = member.hermes_profile
        }
        return acc
      }, {})
      const mentionAgents = (membersResponse.members ?? []).reduce<MentionAgent[]>((acc, member) => {
        if (!member.agent_profile_id || !member.hermes_profile) return acc
        const slug = member.hermes_profile
        let name = member.display_name || member.handle || slug
        let handle =
          member.mention_handle ||
          mentionHandleFromLabel(name, slug)
        const nativeCrew = crewRef.current.find((row) => row.is_native && row.profile === slug)
        if (nativeCrew?.display_name) {
          name = nativeCrew.display_name
          handle = mentionHandleFromLabel(nativeCrew.display_name, slug)
        }
        acc.push({
          slug,
          name,
          handle,
          tagline: nativeCrew?.tagline || undefined,
          role: member.role || nativeCrew?.role || undefined,
          avatarUrl: resolveAgentAvatarUrl({
            avatar_url: member.avatar_url,
            avatar_id: member.avatar_id,
            profile: slug,
            key: slug,
          }),
          agent_profile_id: member.agent_profile_id,
        })
        return acc
      }, [])
      setRoomMentionAgents(mentionAgents)
      const rows = (messagesResponse.messages ?? []).map((message) =>
        roomMessageToChatMessage(message, meResponse.user.user_id, memberNames, memberAvatars, agentNames, agentSlugs),
      )
      const localBase =
        activeHumanRoomIdRef.current === roomId
          ? (roomMessagesRef.current ?? [])
          : hydrateRoomState(roomId)
      const serverTotal = messagesResponse.total ?? rows.length
      if (opts?.silent && rows.length === 0 && localBase.length > 0 && serverTotal === 0) {
        return localBase
      }
      const merged = mergeRoomMessageHistory(rows, roomLocalSnapshot(roomId))
      if (gen !== reloadGenRef.current) return null
      if (activeHumanRoomIdRef.current === roomId) {
        roomMessagesRef.current = merged
        setRoomMessages(merged)
      }
      roomStateByIdRef.current[roomId] = merged
      writeCachedProjectRoomMessages(roomId, merged)
      return merged
    } catch (err) {
      if (!opts?.silent) setRoomMessages([])
      setRoomError(err instanceof Error ? err.message : 'Failed to load room messages')
      return null
    } finally {
      if (!opts?.silent && gen === reloadGenRef.current) setRoomLoading(false)
    }
  }, [hydrateRoomState, roomLocalSnapshot])

  const scheduleRoomReload = useDebouncedCallback((roomId: string) => {
    void reloadRoomMessages(roomId, { silent: true })
  }, 450)

  const handleRoomLive = useCallback(
    (frame: RoomLiveFrame) => {
      if (frame.type === 'turn.started' || frame.type === 'turn.snapshot') {
        const agentName = frame.agent_name || frame.agent_slug
        const modelId = frame.type === 'turn.started' ? String(frame.model ?? '').trim() : ''
        const llmProvider = frame.type === 'turn.started' ? String(frame.llm_provider ?? '').trim() : ''
        liveMetaRef.current[frame.turn_id] = {
          agentName,
          agentSlug: frame.agent_slug,
          ...(modelId ? { modelId } : {}),
          ...(llmProvider ? { llmProvider } : {}),
        }
        // ponytail: SSE connect replays empty in-memory snapshots — skip UI, keep meta.
        if (frame.type === 'turn.snapshot' && !frame.segments?.length) return
        const meta = liveMetaRef.current[frame.turn_id]
        const message = liveTurnToChatMessage(
          frame.turn_id,
          frame.agent_slug,
          agentName,
          frame.type === 'turn.snapshot' ? frame.segments : [],
          { modelId: meta?.modelId, llmProvider: meta?.llmProvider },
        )
        liveBatcherRef.current.push(frame.turn_id, message)
        if (frame.type === 'turn.started') setSpaceWaitTurnId(frame.turn_id)
        setSpaceTurnActive(true)
        if (frame.type === 'turn.snapshot' && frame.status && frame.status !== 'starting') {
          setSpaceTurnStatus(liveTurnStatusText(agentName, frame.status))
        } else if (frame.type === 'turn.started') {
          setSpaceTurnStatus(null)
        }
        return
      }

      if (frame.type === 'turn.update') {
        const meta = liveMetaRef.current[frame.turn_id]
        if (!meta) return
        const message = liveTurnToChatMessage(
          frame.turn_id,
          meta.agentSlug,
          meta.agentName,
          frame.segments,
          { modelId: meta.modelId, llmProvider: meta.llmProvider },
        )
        liveBatcherRef.current.push(frame.turn_id, message)
        setSpaceTurnActive(true)
        if (frame.segments.length) setSpaceWaitTurnId(null)
        setSpaceTurnStatus(liveTurnStatusText(meta.agentName, frame.status))
        return
      }

      if (frame.type === 'turn.complete') {
        liveBatcherRef.current.flush()
        const messageId = String(frame.message_id ?? '').trim()
        const liveMsg = liveTurnsRef.current[frame.turn_id]
        if (messageId && liveMsg && humanRoom) {
          const promoted = { ...liveMsg, id: messageId, ephemeral: false }
          const merged = mergeRoomMessageHistory(roomMessagesRef.current ?? [], [promoted])
          roomMessagesRef.current = merged
          setRoomMessages(merged)
          roomStateByIdRef.current[humanRoom.id] = merged
          writeCachedProjectRoomMessages(humanRoom.id, merged)
        }
        delete liveMetaRef.current[frame.turn_id]
        setSpaceWaitTurnId((id) => (id === frame.turn_id ? null : id))
        setLiveTurns((prev) => {
          const next = { ...prev }
          delete next[frame.turn_id]
          if (!Object.keys(next).length) {
            setSpaceTurnActive(false)
            setSpaceTurnStatus(null)
          }
          return next
        })
        if (humanRoom) void reloadRoomMessages(humanRoom.id, { silent: true })
        return
      }

      if (frame.type === 'turn.error') {
        const meta = liveMetaRef.current[frame.turn_id]
        const agentName = meta?.agentName || 'Agent'
        const agentSlug = meta?.agentSlug || 'agent'
        const message = liveTurnToChatMessage(
          frame.turn_id,
          agentSlug,
          agentName,
          frame.segments?.length
            ? frame.segments
            : [{ kind: 'text', text: frame.error }],
        )
        liveBatcherRef.current.flush()
        liveBatcherRef.current.push(frame.turn_id, { ...message, ephemeral: false })
        delete liveMetaRef.current[frame.turn_id]
        setSpaceWaitTurnId((id) => (id === frame.turn_id ? null : id))
        setLiveTurns((prev) => {
          const next = { ...prev, [frame.turn_id]: { ...message, ephemeral: false } }
          return next
        })
        setSpaceTurnActive(false)
        setSpaceTurnStatus(null)
        if (humanRoom) void reloadRoomMessages(humanRoom.id, { silent: true })
      }
    },
    [humanRoom, reloadRoomMessages],
  )

  useEffect(() => {
    const prevId = activeHumanRoomIdRef.current
    const nextId = humanRoom?.id ?? null

    if (prevId && prevId !== nextId) {
      persistRoomSnapshot(prevId)
      reloadGenRef.current += 1
      setLiveTurns({})
      liveMetaRef.current = {}
      liveBatcherRef.current.cancel()
    }

    activeHumanRoomIdRef.current = nextId

    if (!humanRoom) {
      setRoomMessages(null)
      roomMessagesRef.current = null
      setRoomLoading(false)
      setRoomError('')
      roomRevisionRef.current = ''
      setSpaceTurnActive(false)
      setSpaceTurnStatus(null)
      setSpaceWaitTurnId(null)
      return
    }

    const roomId = humanRoom.id
    roomRevisionRef.current = ''
    const initial = hydrateRoomState(roomId)
    roomMessagesRef.current = initial
    setRoomMessages(initial)
    setRoomLoading(initial.length === 0)
    void reloadRoomMessages(roomId, { silent: initial.length > 0 })
  }, [humanRoom?.id, hydrateRoomState, persistRoomSnapshot, reloadRoomMessages])

  useEffect(() => {
    const roomId = activeHumanRoomIdRef.current
    if (!roomId || humanRoom?.id !== roomId || !roomMessages?.length) return
    roomStateByIdRef.current[roomId] = roomMessages
    const timer = window.setTimeout(() => {
      writeCachedProjectRoomMessages(roomId, roomMessages)
    }, 400)
    return () => window.clearTimeout(timer)
  }, [humanRoom?.id, roomMessages])

  useEffect(() => {
    if (!humanRoom?.workspace_id) return
    const closeEvents = watchWorkspaceEvents(humanRoom.workspace_id, (frame) => {
      const revision = frame.revision ?? ''
      if (revision && revision === roomRevisionRef.current) return
      roomRevisionRef.current = revision
      scheduleRoomReload(humanRoom.id)
    })
    return () => closeEvents()
  }, [humanRoom?.id, humanRoom?.workspace_id, scheduleRoomReload])

  useEffect(() => {
    if (!projectRoom) return
    return watchRoomLive(projectRoom.id, handleRoomLive)
  }, [projectRoom, handleRoomLive])

  useEffect(() => () => liveBatcherRef.current.cancel(), [])

  const sendRoomChatMessage = useCallback(
    (text: string) => {
      if (!humanRoom) return
      const trimmed = text.trim()
      if (!trimmed) return

      const optimisticId = `local-${Date.now()}`
      setRoomMessages((prev) => {
        const next = [
          ...(prev ?? []),
          {
            id: optimisticId,
            authorId: meUserIdRef.current || 'you',
            authorName: 'You',
            role: 'user' as const,
            segments: [{ kind: 'text' as const, text: trimmed }],
            timestamp: new Date().toISOString(),
            tokens: 0,
            avatarUrl: resolveUserAvatarUrl(meAvatarRef.current),
          },
        ]
        roomMessagesRef.current = next
        roomStateByIdRef.current[humanRoom.id] = next
        return next
      })

      void workframeAuthApi
        .sendRoomMessage(humanRoom.id, { content: trimmed })
        .then(() => reloadRoomMessages(humanRoom.id, { silent: true }))
        .catch((err) => {
          const info = formatWorkframeError(err, 'Send message')
          setRoomError(formatWorkframeErrorMessage(err, 'Send message'))
          showWorkframeError(info, { id: info.code ?? 'room-send' })
          void reloadRoomMessages(humanRoom.id, { silent: true })
        })
    },
    [humanRoom, reloadRoomMessages],
  )

  if (humanRoom) {
    return (
      <CommandDialogsProvider>
      <div className="wf-chat-split">
        {roomError ? (
          <div className="wf-chat-split__error-banner">
            <WorkframeNotice message={roomError} />
          </div>
        ) : null}
        <div className="wf-chat-split__messages">
          {roomLoading && roomMessages === null ? (
            <p className="wf-message-list__empty">Loading {humanRoom.name}…</p>
          ) : null}
          <MessageList
            nativeAgentName={agentDisplayName}
            messagesOverride={displayRoomMessages}
            waitMessageId={spaceWaitTurnId}
            onReplyToAgent={
              projectRoom
                ? (slug) => {
                    const agent = roomMentionAgents.find((row) => row.slug === slug)
                    composerRef.current?.insertMention(agent?.handle || slug)
                  }
                : undefined
            }
          />
        </div>

        <div
          className={cn('wf-chat-split__sash', isCollapsed && 'wf-chat-split__sash--collapsed')}
          role="separator"
          aria-orientation="horizontal"
          aria-label="Resize composer"
          onPointerDown={onSashPointerDown}
          onPointerMove={onSashPointerMove}
          onPointerUp={onSashPointerUp}
          onDoubleClick={() => (isCollapsed ? expandComposer() : collapseComposer())}
        />

        <div className="wf-chat-split__composer" style={{ height: composerHeight }}>
          <Composer
            ref={composerRef}
            onMinHeightChange={setComposerMinPx}
            showModelPicker={false}
            mentionAgents={projectRoom ? roomMentionAgents : []}
            onSend={sendRoomChatMessage}
            onAttachImage={() => {}}
            disabled={roomLoading && roomMessages === null}
            turnActive={spaceTurnActive}
            turnStatus={spaceTurnStatus}
            placeholder={
              projectRoom
                ? `Message ${humanRoom.name}… @agent to invoke`
                : `Message ${humanRoom.name}…`
            }
          />
        </div>
      </div>
      <CommandModelPickerMount />
      </CommandDialogsProvider>
    )
  }

  return (
    <CommandDialogsProvider>
    <div className="wf-chat-split">
      <ProviderRequiredDialog
        open={providerDialogOpen}
        onOpenChange={setProviderDialogOpen}
        errorMessage={connectError ? noticeMessage(connectError) : undefined}
        onConnected={() => setProviderDialogOpen(false)}
      />
      <div className="wf-chat-split__messages">
        <MessageList
          nativeAgentName={agentDisplayName}
          messagesOverride={displayAgentMessages}
          waitMessageId={dmWaitMessageId}
        />
      </div>

      <div
        className={cn('wf-chat-split__sash', isCollapsed && 'wf-chat-split__sash--collapsed')}
        role="separator"
        aria-orientation="horizontal"
        aria-label="Resize composer"
        onPointerDown={onSashPointerDown}
        onPointerMove={onSashPointerMove}
        onPointerUp={onSashPointerUp}
        onDoubleClick={() => (isCollapsed ? expandComposer() : collapseComposer())}
      />

      <div className="wf-chat-split__composer" style={{ height: composerHeight }}>
        <Composer
          onMinHeightChange={setComposerMinPx}
          onSend={(text) => void sendMessage(text)}
          onAttachImage={(file) => void attachImage(file)}
          disabled={!sessionReady || turnActive}
          turnActive={turnActive}
          turnStatus={turnStatus}
          placeholder={`Message ${agentDisplayName}…`}
        />
      </div>
    </div>
    <CommandModelPickerMount />
    </CommandDialogsProvider>
  )
}
