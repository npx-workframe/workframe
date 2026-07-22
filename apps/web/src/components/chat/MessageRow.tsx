import { useState } from 'react'
import { ArrowUpRight, Reply } from 'lucide-react'

import type { ChatMessage, ChatReaction, ChatSegment } from '@/lib/chatTypes'
import { formatModelAttribution } from '@/lib/chatTypes'
import { MessageActions, MessageReactions } from '@/components/chat/MessageActions'
import { ThinkingBlock } from '@/components/chat/ThinkingBlock'
import { WaitHint } from '@/components/chat/WaitHint'
import { ToolRunCard } from '@/components/chat/ToolRunCard'
import { MarkdownContent } from '@/components/markdown/MarkdownContent'
import { AgentAvatar } from '@/components/ui/AgentAvatar'
import { Button } from '@/components/ui/button'
import { WorkframeNotice } from '@/components/ui/WorkframeNotice'
import { useWorkspacePanels } from '@/contexts/WorkspacePanelsContext'
import { formatRelativeTime } from '@/lib/formatRelativeTime'
import { workspaceRawUrl } from '@/lib/filesApi'
import type { WorkframeNoticeAction } from '@/lib/workframeErrors'
import { cn } from '@/lib/utils'

type MessageRowProps = {
  message: ChatMessage
  waitMessageId?: string | null
  reactions?: ChatReaction[]
  onReply?: (message: ChatMessage) => void
  onToggleReaction?: (messageId: string, emoji: string) => void
  onJumpToMessage?: (messageId: string) => void
}

function MarkdownBody({ text }: { text: string }) {
  return (
    <MarkdownContent
      text={text}
      wrapperClass="wf-markdown wf-message__markdown wf-syntax"
    />
  )
}

function MessageImage({ segment }: { segment: Extract<ChatSegment, { kind: 'image' }> }) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null)
  const src = /^(?:https?:|data:|blob:)/i.test(segment.path)
    ? segment.path
    : workspaceRawUrl(segment.path)
  const label = segment.alt ?? segment.name ?? 'Attached image'
  const failed = failedSrc === src

  return (
    <figure className="wf-message__image-wrap">
      {failed ? (
        <div className="wf-message__image-fallback" role="img" aria-label={`${label} unavailable`}>
          <span aria-hidden="true">Image</span>
          <strong>Attachment unavailable</strong>
        </div>
      ) : (
        <img
          className="wf-message__image"
          src={src}
          alt={label}
          loading="lazy"
          onError={() => setFailedSrc(src)}
        />
      )}
    </figure>
  )
}

function SegmentBlock({
  segment,
  live,
  onNoticeAction,
}: {
  segment: ChatSegment
  live?: boolean
  onNoticeAction?: (action: WorkframeNoticeAction) => void
}) {
  if (segment.kind === 'concierge') {
    return (
      <WorkframeNotice
        info={segment.notice}
        onAction={
          segment.notice.action && onNoticeAction
            ? () => onNoticeAction(segment.notice.action!)
            : undefined
        }
        actionLabel={segment.notice.actionLabel}
      />
    )
  }
  if (segment.kind === 'thinking') {
    return <ThinkingBlock text={segment.text} live={live} />
  }
  if (segment.kind === 'tool') {
    return <ToolRunCard segment={segment} />
  }
  if (segment.kind === 'image') {
    return <MessageImage segment={segment} />
  }
  return <MarkdownBody text={segment.text} />
}

export function MessageRow({
  message,
  waitMessageId = null,
  reactions = [],
  onReply,
  onToggleReaction,
  onJumpToMessage,
}: MessageRowProps) {
  const isUser = message.role === 'user'
  const { openChatSettings, openUserSettings } = useWorkspacePanels()
  const canInteract = !message.ephemeral && message.authorId !== 'system'
  const modelAttribution = !isUser ? formatModelAttribution(message.modelId, message.llmProvider) : ''

  const handleNoticeAction = (action: WorkframeNoticeAction) => {
    if (action.type === 'open_settings') {
      if (action.tab === 'model') {
        openChatSettings('models')
        return
      }
      openUserSettings('connect', action.tab === 'providers' ? 'providers' : undefined)
      return
    }
    if (action.type === 'external_link') {
      window.open(action.url, '_blank', 'noopener,noreferrer')
    }
  }

  return (
    <article
      className={cn('wf-message', isUser && 'wf-message--user', message.ephemeral && 'wf-message--ephemeral')}
      data-author={message.authorId}
    >
      {canInteract ? (
        <MessageActions
          onReply={onReply ? () => onReply(message) : undefined}
          onReact={onToggleReaction ? (emoji) => onToggleReaction(message.id, emoji) : undefined}
        />
      ) : null}

      <div className={cn('wf-message__header', isUser && 'wf-message__header--user')}>
        {isUser ? (
          <AgentAvatar
            src={message.avatarUrl}
            name={message.authorName}
            color={message.color}
            size="sm"
            className="wf-message__avatar"
          />
        ) : null}
        {!isUser ? (
          <AgentAvatar
            src={message.avatarUrl}
            name={message.authorName}
            initials={message.initials}
            color={message.color}
            size="sm"
            className="wf-message__avatar"
          />
        ) : null}
        <div className="wf-message__meta">
          <div className="wf-message__meta-primary">
            <span className="wf-message__author">{message.authorName}</span>
            <time className="wf-message__time" dateTime={message.timestamp}>
              {formatRelativeTime(message.timestamp)}
            </time>
          </div>
          {modelAttribution ? (
            <span className="wf-message__attribution" title={message.modelId ?? modelAttribution}>
              {modelAttribution}
            </span>
          ) : null}
        </div>
      </div>

      {message.replyTo ? (
        <Button
          type="button"
          variant="toolbar"
          size="toolbarText"
          className="wf-message__reply-context"
          onClick={() => onJumpToMessage?.(message.replyTo!.id)}
          disabled={!onJumpToMessage}
          aria-label={`Jump to replied message from ${message.replyTo.authorName}`}
        >
          <span className="wf-message__reply-context-icon" aria-hidden="true">
            <Reply />
          </span>
          <span className="wf-message__reply-context-copy">
            <span className="wf-message__reply-context-author">Reply to {message.replyTo.authorName}</span>
            <span className="wf-message__reply-context-preview">{message.replyTo.preview}</span>
          </span>
          <ArrowUpRight className="wf-message__reply-context-jump" aria-hidden="true" />
        </Button>
      ) : null}

      <div className="wf-message__segments">
        {message.segments.length === 0 && message.id === waitMessageId ? <WaitHint /> : null}
        {message.segments.map((segment, index) => (
          <SegmentBlock
            key={`${message.id}-${index}`}
            segment={segment}
            live={message.ephemeral}
            onNoticeAction={handleNoticeAction}
          />
        ))}
      </div>

      <MessageReactions
        reactions={reactions}
        onToggle={onToggleReaction ? (emoji) => onToggleReaction(message.id, emoji) : undefined}
      />
    </article>
  )
}
