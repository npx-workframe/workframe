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
import { WorkframeNotice } from '@/components/ui/WorkframeNotice'
import { ProviderRequiredDialog } from '@/components/dialogs/ProviderRequiredDialog'
import { formatWorkframeErrorMessage, isProviderSetupError } from '@/lib/workframeErrors'
import { cn } from '@/lib/utils'
import { resolveUserAvatarUrl } from '@/lib/avatarResolve'
import { mentionHandleFromLabel } from '@/lib/mentionHandle'
import { resolveAgentAvatarUrl } from '@/lib/avatarResolve'
import { useCrew } from '@/hooks/useCrew'
import { workframeAuthApi, watchWorkspaceEvents } from '@/lib/workframeAuthApi'
import type { ChatMessage } from '@/lib/chatTypes'

function roomMessageToChatMessage(
  message: {
    id: string
    sender_user_id?: string | null
    sender_agent_id?: string | null
    sender_agent_slug?: string | null
    sender_agent_name?: string | null
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
    avatarUrl: message.sender_user_id ? resolveUserAvatarUrl(memberAvatars[message.sender_user_id]) : undefined,
  }
}

export function ChatSplit() {
  const { activeRoom } = useWorkspacePanels()
  const [providerDialogOpen, setProviderDialogOpen] = useState(false)
  const {
    agentDisplayName,
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
  const roomRevisionRef = useRef('')
  const meUserIdRef = useRef('')
  const meAvatarRef = useRef<string | null>(null)
  const liveMetaRef = useRef<Record<string, { agentName: string; agentSlug: string }>>({})
  const liveBatcherRef = useRef(createLiveTurnBatcher((updates) => {
    setLiveTurns((prev) => ({ ...prev, ...updates }))
  }))
  const composerRef = useRef<ComposerHandle>(null)
  const projectName = import.meta.env.VITE_WORKFRAME_PROJECT?.trim() || 'Workframe'
  const { crew } = useCrew(projectName)

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

  const reloadRoomMessages = useCallback(async (roomId: string, opts?: { silent?: boolean }) => {
    if (!opts?.silent) setRoomLoading(true)
    setRoomError('')
    try {
      const [messagesResponse, membersResponse, meResponse] = await Promise.all([
        workframeAuthApi.listRoomMessages(roomId),
        workframeAuthApi.listRoomMembers(roomId),
        workframeAuthApi.getMe(),
      ])
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
        const nativeCrew = crew.find((row) => row.is_native && row.profile === slug)
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
      setRoomMessages(rows)
      return rows
    } catch (err) {
      if (!opts?.silent) setRoomMessages([])
      setRoomError(err instanceof Error ? err.message : 'Failed to load room messages')
      return null
    } finally {
      if (!opts?.silent) setRoomLoading(false)
    }
  }, [crew])

  const scheduleRoomReload = useDebouncedCallback((roomId: string) => {
    void reloadRoomMessages(roomId, { silent: true })
  }, 450)

  const handleRoomLive = useCallback(
    (frame: RoomLiveFrame) => {
      if (frame.type === 'turn.started' || frame.type === 'turn.snapshot') {
        const agentName = frame.agent_name || frame.agent_slug
        liveMetaRef.current[frame.turn_id] = { agentName, agentSlug: frame.agent_slug }
        const message = liveTurnToChatMessage(
          frame.turn_id,
          frame.agent_slug,
          agentName,
          frame.type === 'turn.snapshot' ? frame.segments : [],
        )
        liveBatcherRef.current.push(frame.turn_id, message)
        setSpaceTurnActive(true)
        setSpaceTurnStatus(liveTurnStatusText(agentName, frame.type === 'turn.snapshot' ? frame.status : 'starting'))
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
        )
        liveBatcherRef.current.push(frame.turn_id, message)
        setSpaceTurnActive(true)
        setSpaceTurnStatus(liveTurnStatusText(meta.agentName, frame.status))
        return
      }

      if (frame.type === 'turn.complete') {
        liveBatcherRef.current.cancel()
        delete liveMetaRef.current[frame.turn_id]
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
        liveBatcherRef.current.push(frame.turn_id, { ...message, ephemeral: false })
        delete liveMetaRef.current[frame.turn_id]
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
    if (!humanRoom) {
      setRoomMessages(null)
      setLiveTurns({})
      liveMetaRef.current = {}
      setRoomLoading(false)
      setRoomError('')
      roomRevisionRef.current = ''
      setSpaceTurnActive(false)
      setSpaceTurnStatus(null)
      return
    }
    roomRevisionRef.current = ''
    void reloadRoomMessages(humanRoom.id)
  }, [humanRoom, reloadRoomMessages])

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
      setRoomMessages((prev) => [
        ...(prev ?? []),
        {
          id: optimisticId,
          authorId: meUserIdRef.current || 'you',
          authorName: 'You',
          role: 'user',
          segments: [{ kind: 'text', text: trimmed }],
          timestamp: new Date().toISOString(),
          tokens: 0,
          avatarUrl: resolveUserAvatarUrl(meAvatarRef.current),
        },
      ])

      void workframeAuthApi
        .sendRoomMessage(humanRoom.id, { content: trimmed })
        .then(() => reloadRoomMessages(humanRoom.id, { silent: true }))
        .catch((err) => {
          setRoomError(formatWorkframeErrorMessage(err, 'Send message'))
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
            disabled={roomLoading}
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
      {connectError ? (
        <div className="wf-chat-split__error-banner">
          <WorkframeNotice
            message={connectError}
            actionLabel={isProviderSetupError(connectError) ? 'Connect provider' : undefined}
            onAction={
              isProviderSetupError(connectError)
                ? () => setProviderDialogOpen(true)
                : undefined
            }
          />
        </div>
      ) : null}
      <ProviderRequiredDialog
        open={providerDialogOpen}
        onOpenChange={setProviderDialogOpen}
        errorMessage={connectError}
        onConnected={() => setProviderDialogOpen(false)}
      />
      <div className="wf-chat-split__messages">
        <MessageList nativeAgentName={agentDisplayName} messagesOverride={messages} />
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
