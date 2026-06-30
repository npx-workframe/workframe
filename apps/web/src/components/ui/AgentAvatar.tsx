import { useState, type CSSProperties } from 'react'

import { crewInitials } from '@/lib/hermesProfile'
import { cn } from '@/lib/utils'

type AgentAvatarSize = 'xs' | 'sm' | 'md' | 'rail'

const SIZE_CLASS: Record<AgentAvatarSize, string> = {
  xs: 'wf-avatar wf-avatar--xs',
  sm: 'wf-avatar wf-avatar--sm',
  md: 'wf-avatar wf-avatar--md',
  rail: 'wf-avatar wf-avatar--rail',
}

type AgentAvatarProps = {
  src?: string | null
  name: string
  /** Profile badge (e.g. VI, AR) — preferred over derived initials. */
  initials?: string
  color?: string
  size?: AgentAvatarSize
  className?: string
}

export function AgentAvatar({
  src,
  name,
  initials,
  color = 'var(--wf-cyan)',
  size = 'md',
  className,
}: AgentAvatarProps) {
  const [imageFailed, setImageFailed] = useState(false)
  const style = { '--agent-color': color } as CSSProperties
  const badge = initials?.trim() || crewInitials(name)

  if (src && !imageFailed) {
    return (
      <img
        src={src}
        alt=""
        aria-hidden="true"
        className={cn(SIZE_CLASS[size], 'wf-avatar--image', className)}
        style={style}
        loading="lazy"
        decoding="async"
        onError={() => setImageFailed(true)}
      />
    )
  }

  return (
    <span className={cn(SIZE_CLASS[size], className)} style={style} aria-hidden="true">
      {badge}
    </span>
  )
}
