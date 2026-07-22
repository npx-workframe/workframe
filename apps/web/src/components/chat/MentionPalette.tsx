import {
  forwardRef,
  useImperativeHandle,
  useMemo,
  useRef,
} from 'react'

import { PopoverMenu, type PopoverItem, type PopoverMenuHandle } from '@/components/chat/PopoverMenu'

export type MentionAgent = {
  slug: string
  name: string
  handle: string
  kind: 'agent' | 'contact'
  tagline?: string
  role?: string
  avatarUrl?: string | null
  agent_profile_id?: string
  user_id?: string
}

type MentionPaletteProps = {
  anchor: HTMLTextAreaElement | null
  isOpen: boolean
  query: string
  agents: MentionAgent[]
  onPick: (agent: MentionAgent) => void
}

export type MentionPaletteHandle = PopoverMenuHandle

export const MentionPalette = forwardRef<MentionPaletteHandle, MentionPaletteProps>(
  function MentionPalette({ anchor, isOpen, query, agents, onPick }, ref) {
    const menuRef = useRef<PopoverMenuHandle>(null)

    useImperativeHandle(
      ref,
      () => ({
        up: () => menuRef.current?.up(),
        down: () => menuRef.current?.down(),
        accept: () => menuRef.current?.accept(),
      }),
      [],
    )

    const items: PopoverItem[] = useMemo(
      () =>
        agents.map((agent) => ({
          id: agent.slug,
          name: `@${agent.handle}`,
          description: [
            agent.name,
            agent.tagline || agent.role || (agent.kind === 'agent' ? 'Agent' : 'Contact'),
          ].filter(Boolean).join(' · '),
          avatarUrl: agent.avatarUrl,
          avatarName: agent.name,
        })),
      [agents],
    )

    if (!isOpen) return null

    return (
      <PopoverMenu
        ref={menuRef}
        anchor={anchor}
        isOpen={isOpen}
        onClose={() => {}}
        header={{ label: 'People & agents', hint: '↑↓ navigate · Tab complete' }}
        items={items}
        filter={query}
        emptyMessage={query ? `No people or agents match @${query}` : 'No people or agents in this room'}
        onSelect={(item) => {
          const agent = agents.find((row) => row.slug === item.id)
          if (agent) onPick(agent)
        }}
      />
    )
  },
)
