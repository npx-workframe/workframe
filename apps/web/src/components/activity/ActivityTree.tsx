import { useCallback, useEffect, useState } from 'react'
import { ChevronRight } from 'lucide-react'

import { AgentAvatar } from '@/components/ui/AgentAvatar'
import { ScrollArea } from '@/components/ui/scroll-area'
import { findAgentByProfile, type WorkframeAgent } from '@/lib/hermesProfile'
import { useCrew } from '@/hooks/useCrew'
import { formatRelativeTime } from '@/lib/formatRelativeTime'
import {
  isActivityGroup,
  type ActivityNode,
} from '@/lib/activityTypes'
import { cn } from '@/lib/utils'

type ActivityTreeProps = {
  nodes: ActivityNode[]
  className?: string
  projectName?: string
  activeSessionId?: string | null
  onItemClick?: (node: ActivityNode) => void
  onSessionActivate?: (node: ActivityNode) => void
}

export function ActivityTree({
  nodes,
  className,
  projectName = import.meta.env.VITE_WORKFRAME_PROJECT?.trim() || 'Workframe',
  activeSessionId = null,
  onItemClick,
  onSessionActivate,
}: ActivityTreeProps) {
  const { crew } = useCrew(projectName)

  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => {
    const initial = new Set<string>()
    for (const node of nodes) {
      if (isActivityGroup(node) && node.status === 'active') {
        initial.add(node.id)
      }
    }
    return initial
  })

  useEffect(() => {
    setExpandedIds((previous) => {
      const next = new Set(previous)
      for (const node of nodes) {
        if (isActivityGroup(node) && node.children?.length) {
          next.add(node.id)
        }
        if (isActivityGroup(node) && node.status === 'active') {
          next.add(node.id)
        }
      }
      return next
    })
  }, [nodes])

  const toggleExpanded = useCallback((id: string) => {
    setExpandedIds((previous) => {
      const next = new Set(previous)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  if (nodes.length === 0) {
    return (
      <div className={cn('wf-activity-tree wf-activity-tree--empty', className)}>
        <p className="wf-activity-tree__empty">No agent activity yet.</p>
      </div>
    )
  }

  return (
    <ScrollArea axis="vertical" className={cn('wf-activity-tree', className)}>
      <div className="wf-activity-tree__list" role="tree" aria-label="Agent activity">
        {nodes.map((node) => (
          <ActivityBranch
            key={node.id}
            node={node}
            depth={0}
            expandedIds={expandedIds}
            onToggle={toggleExpanded}
            crew={crew}
            activeSessionId={activeSessionId}
            onItemClick={onItemClick}
            onSessionActivate={onSessionActivate}
          />
        ))}
      </div>
    </ScrollArea>
  )
}

type ActivityBranchProps = {
  node: ActivityNode
  depth: number
  expandedIds: Set<string>
  onToggle: (id: string) => void
  crew: WorkframeAgent[]
  activeSessionId?: string | null
  onItemClick?: (node: ActivityNode) => void
  onSessionActivate?: (node: ActivityNode) => void
}

function ActivityBranch({ node, depth, expandedIds, onToggle, crew, activeSessionId, onItemClick, onSessionActivate }: ActivityBranchProps) {
  const grouped = isActivityGroup(node)
  const expanded = grouped && expandedIds.has(node.id)
  const showAgent = depth === 0
  const agent = findAgentByProfile(crew, node.profile)
  const headline = activityHeadline(node, grouped)

  return (
    <div className="wf-activity-tree__branch" role="treeitem" aria-expanded={grouped ? expanded : undefined}>
      <ActivityRow
        node={node}
        depth={depth}
        grouped={grouped}
        expanded={expanded}
        showAgent={showAgent}
        headline={headline}
        avatarUrl={agent?.avatarUrl ?? null}
        agentInitials={agent?.code}
        agentColor={agent?.color ?? node.agentColor}
        isCurrentSession={Boolean(activeSessionId && node.sessionId && node.sessionId === activeSessionId)}
        onToggle={grouped ? () => onToggle(node.id) : undefined}
        onItemClick={onItemClick}
        onSessionActivate={onSessionActivate}
      />

      {grouped && expanded ? (
        <div className="wf-activity-tree__children" role="group">
          {node.children.map((child) => (
            <ActivityBranch
              key={child.id}
              node={child}
              depth={depth + 1}
              expandedIds={expandedIds}
              onToggle={onToggle}
              crew={crew}
              activeSessionId={activeSessionId}
              onItemClick={onItemClick}
              onSessionActivate={onSessionActivate}
            />
          ))}
        </div>
      ) : null}
    </div>
  )
}

function toolNameFor(node: ActivityNode): string {
  return node.refs.toolName?.trim() || node.label.replace(/^(running )?tool:\s*/i, '').trim() || 'tool'
}

function activityHeadline(node: ActivityNode, grouped: boolean): string {
  if (node.source === 'message' || node.kind === 'tool_call') {
    const name = toolNameFor(node)
    return node.status === 'active' ? `running tool: ${name}` : `tool: ${name}`
  }

  if (grouped && node.children?.length) {
    const activeChild = node.children.find((child) => child.status === 'active')
    if (activeChild) {
      const name = toolNameFor(activeChild)
      return `running tool: ${name}`
    }
  }

  if (node.source === 'session') {
    if (node.label.trim()) return node.label
    if (/^chatting with @/i.test(node.label)) return node.label
    return 'chatting with @user'
  }

  return node.label
}

type ActivityRowProps = {
  node: ActivityNode
  depth: number
  grouped: boolean
  expanded: boolean
  showAgent: boolean
  headline: string
  avatarUrl: string | null
  agentInitials?: string
  agentColor: string
  isCurrentSession?: boolean
  onToggle?: () => void
  onItemClick?: (node: ActivityNode) => void
  onSessionActivate?: (node: ActivityNode) => void
}

function ActivityRow({
  node,
  depth,
  grouped,
  expanded,
  showAgent,
  headline,
  avatarUrl,
  agentInitials,
  agentColor,
  isCurrentSession = false,
  onToggle,
  onItemClick,
  onSessionActivate,
}: ActivityRowProps) {
  const paddingLeft = 8 + depth * 10
  const isActive = node.status === 'active'
  const rowClass = cn(
    'wf-activity-tree__row',
    grouped && 'wf-activity-tree__row--group',
    !grouped && onItemClick && node.toolCallId && node.sessionId && 'wf-activity-tree__row--clickable',
    !grouped && !onItemClick && 'wf-activity-tree__row--leaf',
    showAgent && 'wf-activity-tree__row--agent',
    !showAgent && 'wf-activity-tree__row--child',
    isActive && 'wf-activity-tree__row--active',
    isCurrentSession && 'wf-activity-tree__row--current',
  )

  const titleLine = showAgent ? node.agentName : headline

  const copy = (
    <>
      {showAgent ? (
        <AgentAvatar
          src={avatarUrl}
          name={node.agentName}
          initials={agentInitials}
          color={agentColor}
          size="xs"
          className="wf-activity-tree__avatar"
        />
      ) : null}

      <span className="wf-activity-tree__copy">
        <span className="wf-activity-tree__top">
          <span className={cn('wf-activity-tree__title', !showAgent && 'wf-activity-tree__title--child')} title={titleLine}>
            {titleLine}
          </span>
          <span className="wf-activity-tree__top-meta">
            {isActive ? <span className="wf-activity-tree__running">running</span> : null}
            <time className="wf-activity-tree__time" dateTime={node.ts}>
              {formatRelativeTime(node.ts)}
            </time>
          </span>
        </span>
        {showAgent && headline ? (
          <span className="wf-activity-tree__label" title={headline}>
            {headline}
          </span>
        ) : null}
      </span>
    </>
  )

  if (grouped && onToggle) {
    return (
      <div className={rowClass} style={{ paddingLeft }}>
        <button
          type="button"
          className="wf-activity-tree__main"
          onClick={() => onSessionActivate?.(node)}
          aria-label={`${node.agentName}: ${headline}`}
        >
          {copy}
        </button>
        <button
          type="button"
          className="wf-activity-tree__chevron-btn"
          onClick={onToggle}
          aria-expanded={expanded}
          aria-label={expanded ? 'Collapse session tools' : 'Expand session tools'}
        >
          <span className={cn('wf-activity-tree__chevron', expanded && 'wf-activity-tree__chevron--open')}>
            <ChevronRight aria-hidden="true" />
          </span>
        </button>
      </div>
    )
  }

  if (!grouped && node.source === 'session' && node.sessionId && onSessionActivate) {
    return (
      <button
        type="button"
        className={cn(rowClass, 'wf-activity-tree__row--clickable')}
        style={{ paddingLeft }}
        onClick={() => onSessionActivate(node)}
        aria-label={`Open session: ${headline}`}
      >
        {copy}
      </button>
    )
  }

  if (onItemClick && node.toolCallId && node.sessionId) {
    return (
      <button
        type="button"
        className={rowClass}
        style={{ paddingLeft }}
        onClick={() => onItemClick(node)}
        aria-label={`Open detail: ${headline}`}
      >
        {copy}
      </button>
    )
  }

  return (
    <div className={rowClass} style={{ paddingLeft }}>
      {copy}
    </div>
  )
}
