import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'

import { ScrollArea } from '@/components/ui/scroll-area'
import { Divider } from '@/components/ui/divider'
import { MessageRow } from '@/components/chat/MessageRow'
import { MessageNavigator } from '@/components/chat/MessageNavigator'
import { findAgentByProfile } from '@/lib/hermesProfile'
import { fetchChatMessages } from '@/lib/chatApi'
import type { ChatMessage, ChatReaction } from '@/lib/chatTypes'
import { useCrew } from '@/hooks/useCrew'
import { resolveUserAvatarUrl } from '@/lib/avatarResolve'
import { workframeAuthApi } from '@/lib/workframeAuthApi'
import { formatWorkframeError } from '@/lib/workframeErrors'
import { showWorkframeError } from '@/lib/workframeErrorToast'
import { nativeProfileSlug } from '@/lib/workframeProfile'

type MessageListProps = {
  nativeAgentName?: string
  projectName?: string
  messagesOverride?: ChatMessage[] | null
  sessionId?: string | null
  waitMessageId?: string | null
  interactionScope?: string
  onReply?: (message: ChatMessage) => void
}

export function MessageList({
  nativeAgentName = 'Workframe Agent',
  projectName = import.meta.env.VITE_WORKFRAME_PROJECT?.trim() || 'Workframe',
  messagesOverride = null,
  sessionId = null,
  waitMessageId = null,
  interactionScope = '',
  onReply,
}: MessageListProps) {
  const nativeSlug = nativeProfileSlug()
  const { crew } = useCrew(projectName)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [userAvatarUrl, setUserAvatarUrl] = useState<string | null>(null)
  const [reactionSelf, setReactionSelf] = useState({ userId: '', displayName: 'You', avatarUrl: null as string | null })
  const [reactions, setReactions] = useState<Record<string, ChatReaction[]>>({})
  const [activeMessageId, setActiveMessageId] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const rowRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  const initialScrollRef = useRef(true)
  const stickToBottomRef = useRef(true)

  useEffect(() => {
    let cancelled = false
    void workframeAuthApi.getMe().then((response) => {
      if (!cancelled) {
        setUserAvatarUrl(response.user.avatar_url ?? null)
        setReactionSelf({
          userId: response.user.user_id,
          displayName: response.user.display_name?.trim() || 'You',
          avatarUrl: response.user.avatar_url ?? null,
        })
      }
    }).catch(() => {
      if (!cancelled) setUserAvatarUrl(null)
    })
    return () => {
      cancelled = true
    }
  }, [])

  const enrichMessages = useMemo(
    () => (rows: ChatMessage[]) =>
      rows.map((message) => {
        if (message.role === 'user') {
          if (message.avatarUrl) {
            return message
          }
          return { ...message, avatarUrl: resolveUserAvatarUrl(userAvatarUrl) }
        }

        const agent = findAgentByProfile(crew, message.authorId)
          ?? crew.find((member) => member.display_name.toLowerCase() === message.authorName.toLowerCase())
        const authorName = agent?.display_name || message.authorName || nativeAgentName
        return {
          ...message,
          authorId: agent?.profile ?? message.authorId,
          authorName,
          color: agent?.color ?? message.color,
          avatarUrl: agent?.avatarUrl ?? null,
          initials: agent?.code,
        }
      }),
    [crew, nativeAgentName, userAvatarUrl],
  )

  useEffect(() => {
    if (messagesOverride !== null) return
    let cancelled = false
    void fetchChatMessages(nativeSlug, sessionId ?? undefined)
      .then(({ messages: rows }) => {
        if (!cancelled) setMessages(enrichMessages(rows))
      })
      .catch(() => {
        if (!cancelled) setMessages([])
      })
    return () => {
      cancelled = true
    }
  }, [enrichMessages, messagesOverride, nativeSlug, sessionId])

  const displayMessages = useMemo(() => {
    const source = messagesOverride ?? messages
    return enrichMessages(source)
  }, [enrichMessages, messages, messagesOverride])

  const applyReactionRows = useCallback((rows: Array<{
    message_id: string
    emoji: string
    count: number
    reacted: boolean
    reactors?: Array<{ user_id: string; display_name: string; avatar_url?: string | null }>
  }>) => {
    const next: Record<string, ChatReaction[]> = {}
    rows.forEach((row) => {
      const list = next[row.message_id] ?? []
      list.push({
        emoji: row.emoji,
        count: row.count,
        reacted: row.reacted,
        reactors: (row.reactors ?? []).map((reactor) => ({
          userId: reactor.user_id,
          displayName: reactor.display_name,
          avatarUrl: reactor.avatar_url,
        })),
      })
      next[row.message_id] = list
    })
    setReactions(next)
  }, [])

  useEffect(() => {
    let cancelled = false
    if (!interactionScope) return () => { cancelled = true }
    void workframeAuthApi.listMessageReactions(interactionScope)
      .then((response) => {
        if (!cancelled) applyReactionRows(response.reactions ?? [])
      })
      .catch(() => {
        if (!cancelled) setReactions({})
      })
    return () => { cancelled = true }
  }, [applyReactionRows, interactionScope])

  const toggleReaction = useCallback((messageId: string, emoji: string) => {
    if (!interactionScope || !messageId || messageId.startsWith('local-')) return
    setReactions((current) => {
      const list = current[messageId] ?? []
      const existing = list.find((row) => row.emoji === emoji)
      const nextRow = existing
        ? {
            ...existing,
            count: Math.max(0, existing.count + (existing.reacted ? -1 : 1)),
            reacted: !existing.reacted,
            reactors: existing.reacted
              ? existing.reactors.filter((reactor) => reactor.userId !== reactionSelf.userId)
              : [
                  ...existing.reactors,
                  ...(!reactionSelf.userId || existing.reactors.some((reactor) => reactor.userId === reactionSelf.userId)
                    ? []
                    : [reactionSelf]),
                ],
          }
        : { emoji, count: 1, reacted: true, reactors: reactionSelf.userId ? [reactionSelf] : [] }
      const nextList = [
        ...list.filter((row) => row.emoji !== emoji),
        ...(nextRow.count > 0 ? [nextRow] : []),
      ]
      return { ...current, [messageId]: nextList }
    })
    void workframeAuthApi.toggleMessageReaction(interactionScope, messageId, emoji)
      .then((response) => {
        setReactions((current) => ({
          ...current,
          [messageId]: (response.reactions ?? []).map((row) => ({
            emoji: row.emoji,
            count: row.count,
            reacted: row.reacted,
            reactors: (row.reactors ?? []).map((reactor) => ({
              userId: reactor.user_id,
              displayName: reactor.display_name,
              avatarUrl: reactor.avatar_url,
            })),
          })),
        }))
      })
      .catch((error) => {
        void workframeAuthApi.listMessageReactions(interactionScope)
          .then((response) => applyReactionRows(response.reactions ?? []))
          .catch(() => undefined)
        showWorkframeError(formatWorkframeError(error, 'Message reaction'), { id: 'message-reaction' })
      })
  }, [applyReactionRows, interactionScope, reactionSelf])

  const updateActiveMessage = useCallback((host: HTMLDivElement) => {
    const anchor = host.getBoundingClientRect().top + host.clientHeight * 0.34
    let active = displayMessages[0]?.id ?? ''
    for (const message of displayMessages) {
      const row = rowRefs.current.get(message.id)
      if (!row) continue
      if (row.getBoundingClientRect().top <= anchor) active = message.id
      else break
    }
    setActiveMessageId(active)
  }, [displayMessages])

  const jumpToMessage = useCallback((messageId: string) => {
    const row = rowRefs.current.get(messageId)
    if (!row) return
    row.scrollIntoView({ behavior: 'auto', block: 'center' })
    setActiveMessageId(messageId)
  }, [])

  useLayoutEffect(() => {
    const host = scrollRef.current
    if (!host) return
    host.scrollTo({
      top: host.scrollHeight,
      behavior: initialScrollRef.current ? 'auto' : 'smooth',
    })
    stickToBottomRef.current = true
    initialScrollRef.current = false
    setActiveMessageId(displayMessages.at(-1)?.id ?? '')
  }, [displayMessages])

  return (
    <div className="wf-message-list-shell">
      <ScrollArea
        ref={scrollRef}
        axis="vertical"
        inset="md"
        className="wf-message-list"
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        onScroll={(event) => {
          const host = event.currentTarget
          stickToBottomRef.current = host.scrollHeight - host.scrollTop - host.clientHeight < 64
          updateActiveMessage(host)
        }}
        onLoadCapture={(event) => {
          if (!(event.target instanceof HTMLImageElement) || !stickToBottomRef.current) return
          requestAnimationFrame(() => {
            const host = scrollRef.current
            if (host) host.scrollTop = host.scrollHeight
          })
        }}
      >
        {displayMessages.length === 0 ? (
          <p className="wf-message-list__empty">No messages yet — say hello to your agent.</p>
        ) : null}
        {displayMessages.map((message, index, arr) => (
          <div
            key={message.id}
            ref={(node) => {
              if (node) rowRefs.current.set(message.id, node)
              else rowRefs.current.delete(message.id)
            }}
            className="wf-message-row"
            data-message-id={message.id}
          >
            <MessageRow
              message={message}
              waitMessageId={waitMessageId}
              reactions={interactionScope ? (reactions[message.id] ?? []) : []}
              onReply={message.id.startsWith('local-') ? undefined : onReply}
              onToggleReaction={interactionScope && !message.id.startsWith('local-') ? toggleReaction : undefined}
              onJumpToMessage={jumpToMessage}
            />
            {index < arr.length - 1 ? <Divider className="wf-message-row__divider" /> : null}
          </div>
        ))}
        <div ref={bottomRef} className="wf-message-list__anchor" aria-hidden="true" />
      </ScrollArea>
      <MessageNavigator
        messages={displayMessages}
        activeMessageId={activeMessageId}
        onJump={jumpToMessage}
      />
    </div>
  )
}
