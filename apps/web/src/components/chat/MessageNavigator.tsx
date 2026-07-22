import type { ChatMessage } from '@/lib/chatTypes'
import { chatMessagePreview } from '@/lib/chatTypes'
import { formatRelativeTime } from '@/lib/formatRelativeTime'
import { cn } from '@/lib/utils'

type MessageNavigatorProps = {
  messages: ChatMessage[]
  activeMessageId: string
  onJump: (messageId: string) => void
}

const MAX_MARKERS = 48

function navigatorMessages(messages: ChatMessage[], activeMessageId: string) {
  if (messages.length <= MAX_MARKERS) {
    return messages.map((message, index) => ({ message, index }))
  }

  const samples = Array.from({ length: MAX_MARKERS }, (_, index) =>
    Math.round((index * (messages.length - 1)) / (MAX_MARKERS - 1)),
  )
  const activeIndex = messages.findIndex((message) => message.id === activeMessageId)

  if (activeIndex >= 0 && !samples.includes(activeIndex)) {
    const nearestSample = samples.reduce((nearest, sample, index) =>
      Math.abs(sample - activeIndex) < Math.abs(samples[nearest] - activeIndex) ? index : nearest,
    0)
    samples[nearestSample] = activeIndex
    samples.sort((a, b) => a - b)
  }

  return samples.map((index) => ({ message: messages[index], index }))
}

export function MessageNavigator({ messages, activeMessageId, onJump }: MessageNavigatorProps) {
  if (messages.length < 2) return null
  return (
    <nav className="wf-message-navigator" aria-label="Jump to message">
      {navigatorMessages(messages, activeMessageId).map(({ message, index }) => {
        const labelPreview = chatMessagePreview(message, 72)
        const cardPreview = chatMessagePreview(message, 180)
        const position = (index / Math.max(1, messages.length - 1)) * 100
        return (
          <button
            key={message.id}
            type="button"
            className={cn(
              'wf-message-navigator__marker',
              message.role === 'user' && 'wf-message-navigator__marker--user',
              position <= 12 && 'wf-message-navigator__marker--preview-top',
              position >= 88 && 'wf-message-navigator__marker--preview-bottom',
            )}
            aria-label={`Jump to message ${index + 1} from ${message.authorName}: ${labelPreview}`}
            aria-current={message.id === activeMessageId ? 'true' : undefined}
            onClick={() => onJump(message.id)}
          >
            <span className="wf-message-navigator__preview" aria-hidden="true">
              <span className="wf-message-navigator__preview-head">
                <strong>{message.authorName}</strong>
                <time dateTime={message.timestamp}>{formatRelativeTime(message.timestamp)}</time>
              </span>
              <span className="wf-message-navigator__preview-copy">{cardPreview}</span>
            </span>
          </button>
        )
      })}
    </nav>
  )
}
