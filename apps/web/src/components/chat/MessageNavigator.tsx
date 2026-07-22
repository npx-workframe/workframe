import type { CSSProperties } from 'react'

import type { ChatMessage } from '@/lib/chatTypes'
import { chatMessagePreview } from '@/lib/chatTypes'
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
        const preview = chatMessagePreview(message, 72)
        const width = Math.max(8, Math.min(20, 7 + Math.round(preview.length / 8)))
        return (
          <button
            key={message.id}
            type="button"
            className={cn(
              'wf-message-navigator__marker',
              message.role === 'user' && 'wf-message-navigator__marker--user',
            )}
            style={{ '--wf-message-marker-width': `${width}px` } as CSSProperties}
            aria-label={`Jump to message ${index + 1} from ${message.authorName}: ${preview}`}
            aria-current={message.id === activeMessageId ? 'true' : undefined}
            title={`${message.authorName}: ${preview}`}
            onClick={() => onJump(message.id)}
          />
        )
      })}
    </nav>
  )
}
