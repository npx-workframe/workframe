import { AgentAvatar } from '@/components/ui/AgentAvatar'
import { cn } from '@/lib/utils'

type RailItemProps = {
  expanded: boolean
  active?: boolean
  ariaLabel: string
  title?: string
  primary: string
  secondary?: string | null
  avatarSrc?: string | null
  avatarName: string
  avatarInitials?: string
  avatarColor?: string
  onClick: () => void
  className?: string
}

export function RailItem({
  expanded,
  active,
  ariaLabel,
  title,
  primary,
  secondary,
  avatarSrc,
  avatarName,
  avatarInitials,
  avatarColor,
  onClick,
  className,
}: RailItemProps) {
  return (
    <button
      type="button"
      className={cn('wf-agent-rail__item', active && 'wf-agent-rail__item--active', className)}
      aria-label={ariaLabel}
      aria-current={active ? 'true' : undefined}
      title={expanded ? title : primary}
      onClick={onClick}
    >
      <AgentAvatar
        src={avatarSrc || undefined}
        name={avatarName}
        initials={avatarInitials || primary.slice(0, 2)}
        color={avatarColor}
        size="rail"
        className="wf-agent-rail__avatar"
      />
      {expanded ? (
        <span className="wf-agent-rail__meta">
          <span className="wf-agent-rail__name">{primary}</span>
          {secondary ? <span className="wf-agent-rail__role">{secondary}</span> : null}
        </span>
      ) : null}
    </button>
  )
}
