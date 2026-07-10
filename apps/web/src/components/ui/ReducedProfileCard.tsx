import { Bot, ChevronRight, User } from 'lucide-react'

import { cn } from '@/lib/utils'

export type ReducedProfileCardProps = {
  type?: string
  name: string
  tagline?: string
  avatarUrl?: string | null
  onClick?: () => void
  className?: string
  asAgent?: boolean
}

export function ReducedProfileCard({
  type,
  name,
  tagline,
  avatarUrl,
  onClick,
  className,
  asAgent = false,
}: ReducedProfileCardProps) {
  const interactive = Boolean(onClick)

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!interactive}
      className={cn(
        'wf-profile-entity-card',
        interactive && 'wf-profile-entity-card--interactive',
        className,
      )}
    >
      <span className="wf-profile-entity-card__avatar" aria-hidden="true">
        {avatarUrl ? (
          <img src={avatarUrl} alt="" className="wf-profile-entity-card__avatar-img" />
        ) : asAgent ? (
          <Bot className="wf-profile-entity-card__avatar-icon" />
        ) : (
          <User className="wf-profile-entity-card__avatar-icon" />
        )}
      </span>
      <span className="wf-profile-entity-card__copy">
        <span className="wf-profile-entity-card__name-row">
          <span className="wf-profile-entity-card__name">{name}</span>
          {type ? <span className="wf-profile-entity-card__badge">{type}</span> : null}
        </span>
        {tagline ? <span className="wf-profile-entity-card__tagline">{tagline}</span> : null}
      </span>
      {interactive ? (
        <ChevronRight className="wf-profile-entity-card__chevron" aria-hidden="true" />
      ) : null}
    </button>
  )
}
