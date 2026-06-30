import type { ChatMessage, ChatSegment } from '@/lib/chatTypes'
import { ThinkingBlock } from '@/components/chat/ThinkingBlock'
import { ToolRunCard } from '@/components/chat/ToolRunCard'
import { MarkdownContent } from '@/components/markdown/MarkdownContent'
import { AgentAvatar } from '@/components/ui/AgentAvatar'
import { formatRelativeTime } from '@/lib/formatRelativeTime'
import { cn } from '@/lib/utils'

type MessageRowProps = {
  message: ChatMessage
  onReplyToAgent?: (slug: string) => void
}

function MarkdownBody({ text }: { text: string }) {
  return (
    <MarkdownContent
      text={text}
      wrapperClass="wf-markdown wf-message__markdown wf-syntax"
    />
  )
}

function SegmentBlock({ segment, live }: { segment: ChatSegment; live?: boolean }) {
  if (segment.kind === 'thinking') {
    return <ThinkingBlock text={segment.text} defaultOpen={Boolean(live)} live={live} />
  }
  if (segment.kind === 'tool') {
    return <ToolRunCard segment={segment} />
  }
  if (segment.kind === 'image') {
    const src = segment.path.startsWith('http')
      ? segment.path
      : `/api/files/raw?path=${encodeURIComponent(segment.path)}`
    return (
      <figure className="wf-message__image-wrap">
        <img
          className="wf-message__image"
          src={src}
          alt={segment.alt ?? segment.name ?? 'Attached image'}
          loading="lazy"
        />
        {segment.name ? <figcaption className="wf-message__image-caption">{segment.name}</figcaption> : null}
      </figure>
    )
  }
  return <MarkdownBody text={segment.text} />
}

export function MessageRow({ message, onReplyToAgent }: MessageRowProps) {
  const isUser = message.role === 'user'
  const canReply = !isUser && Boolean(onReplyToAgent && message.authorId && message.authorId !== 'system')

  return (
    <article
      className={cn('wf-message', isUser && 'wf-message--user', message.ephemeral && 'wf-message--ephemeral')}
      data-author={message.authorId}
    >
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
          <span className="wf-message__author">{message.authorName}</span>
          <time className="wf-message__time" dateTime={message.timestamp}>
            {formatRelativeTime(message.timestamp)}
          </time>
        </div>
      </div>

      <div className="wf-message__segments">
        {message.segments.length === 0 && message.ephemeral ? (
          <p className="wf-message__live-hint">Waiting for agent…</p>
        ) : null}
        {message.segments.map((segment, index) => (
          <SegmentBlock key={`${message.id}-${index}`} segment={segment} live={message.ephemeral} />
        ))}
      </div>

      {canReply && onReplyToAgent ? (
        <div className="wf-message__footer">
          <button
            type="button"
            className="wf-message__reply"
            onClick={() => onReplyToAgent(message.authorId)}
          >
            Reply
          </button>
        </div>
      ) : null}
    </article>
  )
}
