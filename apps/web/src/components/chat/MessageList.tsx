import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'

import { ScrollArea } from '@/components/ui/scroll-area'
import { Divider } from '@/components/ui/divider'
import { MessageRow } from '@/components/chat/MessageRow'
import { findAgentByProfile } from '@/lib/hermesProfile'
import { fetchChatMessages } from '@/lib/chatApi'
import type { ChatMessage } from '@/lib/chatTypes'
import { useCrew } from '@/hooks/useCrew'
import { resolveUserAvatarUrl } from '@/lib/avatarResolve'
import { workframeAuthApi } from '@/lib/workframeAuthApi'
import { nativeProfileSlug } from '@/lib/workframeProfile'

type MessageListProps = {
  nativeAgentName?: string
  projectName?: string
  messagesOverride?: ChatMessage[] | null
  sessionId?: string | null
  waitMessageId?: string | null
  onReplyToAgent?: (slug: string) => void
}

export function MessageList({
  nativeAgentName = 'Workframe Agent',
  projectName = import.meta.env.VITE_WORKFRAME_PROJECT?.trim() || 'Workframe',
  messagesOverride = null,
  sessionId = null,
  waitMessageId = null,
  onReplyToAgent,
}: MessageListProps) {
  const nativeSlug = nativeProfileSlug()
  const { crew } = useCrew(projectName)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [userAvatarUrl, setUserAvatarUrl] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const initialScrollRef = useRef(true)

  useEffect(() => {
    let cancelled = false
    void workframeAuthApi.getMe().then((response) => {
      if (!cancelled) setUserAvatarUrl(response.user.avatar_url ?? null)
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

  useLayoutEffect(() => {
    const anchor = bottomRef.current
    if (!anchor) return
    anchor.scrollIntoView({
      block: 'end',
      behavior: initialScrollRef.current ? 'auto' : 'smooth',
    })
    initialScrollRef.current = false
  }, [displayMessages])

  return (
    <ScrollArea axis="vertical" className="wf-message-list" role="log" aria-live="polite" aria-relevant="additions">
      {displayMessages.length === 0 ? (
        <p className="wf-message-list__empty">No messages yet — say hello to your agent.</p>
      ) : null}
      {displayMessages.map((message, index, arr) => (
        <div key={message.id} className="wf-message-row">
          <MessageRow message={message} waitMessageId={waitMessageId} onReplyToAgent={onReplyToAgent} />
          {index < arr.length - 1 ? <Divider className="wf-message-row__divider" /> : null}
        </div>
      ))}
      <div ref={bottomRef} className="wf-message-list__anchor" aria-hidden="true" />
    </ScrollArea>
  )
}
