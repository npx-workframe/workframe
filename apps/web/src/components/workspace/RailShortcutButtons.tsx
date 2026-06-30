import type { LucideIcon } from 'lucide-react'

import { Divider } from '@/components/ui/divider'
import { railPanelShortcuts } from '@/lib/railPanelShortcuts'
import { cn } from '@/lib/utils'

type RailShortcutButtonsProps = {
  projectName: string
  closedPanelIds: ReadonlySet<string>
  expanded: boolean
  onOpen: (panelId: string) => void
  className?: string
  showDivider?: boolean
}

export function RailShortcutButtons({
  projectName,
  closedPanelIds,
  expanded,
  onOpen,
  className,
  showDivider = true,
}: RailShortcutButtonsProps) {
  const shortcuts = railPanelShortcuts(projectName).filter((shortcut) =>
    closedPanelIds.has(shortcut.id),
  )

  if (shortcuts.length === 0) return null

  return (
    <div className={cn('wf-agent-rail__shortcuts', className)}>
      {showDivider ? <Divider className="wf-agent-rail__shortcuts-divider" /> : null}
      {shortcuts.map((shortcut) => (
        <RailShortcutButton
          key={shortcut.id}
          label={shortcut.label}
          icon={shortcut.icon}
          expanded={expanded}
          onOpen={() => onOpen(shortcut.id)}
        />
      ))}
    </div>
  )
}

type RailShortcutButtonProps = {
  label: string
  icon: LucideIcon
  expanded: boolean
  onOpen: () => void
}

function RailShortcutButton({ label, icon: Icon, expanded, onOpen }: RailShortcutButtonProps) {
  return (
    <button
      type="button"
      className="wf-agent-rail__item wf-agent-rail__item--shortcut"
      aria-label={`Open ${label} panel`}
      title={expanded ? undefined : label}
      onClick={onOpen}
    >
      <span className="wf-agent-rail__shortcut-icon" aria-hidden="true">
        <Icon />
      </span>
      {expanded ? (
        <span className="wf-agent-rail__meta">
          <span className="wf-agent-rail__name">{label}</span>
        </span>
      ) : null}
    </button>
  )
}
