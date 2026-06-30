import { ReducedProfileCard } from '@/components/ui/ReducedProfileCard'
import { cn } from '@/lib/utils'

type AgentListItemProps = {
  name: string
  tagline?: string
  avatarUrl?: string | null
  onClick?: () => void
}

export function AgentListItem({ name, tagline, avatarUrl, onClick }: AgentListItemProps) {
  if (onClick) {
    return (
      <button
        type="button"
        className={cn('wf-agent-list-item', 'w-full text-left')}
        onClick={onClick}
      >
        <ReducedProfileCard asAgent name={name} tagline={tagline} avatarUrl={avatarUrl} />
      </button>
    )
  }

  return <ReducedProfileCard asAgent name={name} tagline={tagline} avatarUrl={avatarUrl} />
}
