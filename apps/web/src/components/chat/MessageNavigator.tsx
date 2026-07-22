import type { CSSProperties } from 'react'

import type { ChatMessage } from '@/lib/chatTypes'
import { chatMessagePreview } from '@/lib/chatTypes'
import { cn } from '@/lib/utils'

type MessageNavigatorProps = {
  messages: ChatMessage[]
  activeMessageId: string
  onJump: (messageId: string) => void
}

export function MessageNavigator({ messages, activeMessageId, onJump }: MessageNavigatorProps) {
  if (messages.length < 2) return null
  return (
    <nav className="wf-message-navigator" aria-label="Jump to message">
      {messages.map((message, index) => {
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
