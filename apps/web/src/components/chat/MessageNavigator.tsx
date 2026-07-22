import { type CSSProperties, type PointerEvent, useState } from 'react'

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
  const [hoveredMarkerIndex, setHoveredMarkerIndex] = useState<number | null>(null)
  const [focusedMarkerIndex, setFocusedMarkerIndex] = useState<number | null>(null)

  if (messages.length < 2) return null

  const markerItems = navigatorMessages(messages, activeMessageId)
  const interactionIndex = hoveredMarkerIndex ?? focusedMarkerIndex

  const handlePointerMove = (event: PointerEvent<HTMLElement>) => {
    const pointerY = event.clientY - event.currentTarget.getBoundingClientRect().top
    const markerElements = event.currentTarget.querySelectorAll<HTMLElement>(
      ':scope > .wf-message-navigator__marker',
    )
    let closestIndex: number | null = null
    let closestDistance = Number.POSITIVE_INFINITY

    markerElements.forEach((marker, markerIndex) => {
      const distance = Math.abs(pointerY - (marker.offsetTop + marker.offsetHeight / 2))
      if (distance < closestDistance) {
        closestDistance = distance
        closestIndex = markerIndex
      }
    })

    setHoveredMarkerIndex((currentIndex) =>
      currentIndex === closestIndex ? currentIndex : closestIndex,
    )
  }

  return (
    <nav
      className="wf-message-navigator"
      aria-label="Jump to message"
      onPointerMove={handlePointerMove}
      onPointerLeave={() => setHoveredMarkerIndex(null)}
    >
      {markerItems.map(({ message, index }, markerIndex) => {
        const labelPreview = chatMessagePreview(message, 72)
        const cardPreview = chatMessagePreview(message, 180)
        const position = (index / Math.max(1, messages.length - 1)) * 100
        const signedDistance = interactionIndex === null ? 0 : markerIndex - interactionIndex
        const distance = interactionIndex === null ? null : Math.abs(signedDistance)
        const shift =
          interactionIndex === null || signedDistance === 0
            ? 0
            : Math.sign(signedDistance) * (Math.abs(signedDistance) === 1 ? 4 : 6)
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
            style={{ '--wf-message-marker-shift': `${shift}px` } as CSSProperties}
            data-proximity={distance !== null && distance <= 2 ? distance : undefined}
            aria-label={`Jump to message ${index + 1} from ${message.authorName}: ${labelPreview}`}
            aria-current={message.id === activeMessageId ? 'true' : undefined}
            onFocus={() => setFocusedMarkerIndex(markerIndex)}
            onBlur={() => setFocusedMarkerIndex(null)}
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
