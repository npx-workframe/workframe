import { ReducedProfileCard } from '@/components/ui/ReducedProfileCard'

type AgentListItemProps = {
  name: string
  tagline?: string
  avatarUrl?: string | null
  onClick?: () => void
}

export function AgentListItem({ name, tagline, avatarUrl, onClick }: AgentListItemProps) {
  return (
    <ReducedProfileCard
      asAgent
      name={name}
      tagline={tagline}
      avatarUrl={avatarUrl}
      onClick={onClick}
    />
  )
}
