import { useCallback, useEffect, useState } from 'react'
import type { IDockviewPanelProps } from 'dockview'

import { ActivityTree } from '@/components/activity/ActivityTree'
import { PanelHeader } from '@/components/workspace/PanelHeader'
import { PanelShell } from '@/components/workspace/PanelShell'
import { useBrowserWorkspace } from '@/contexts/BrowserWorkspaceContext'
import { useHermesSession } from '@/contexts/HermesSessionContext'
import { useWorkspacePanels } from '@/contexts/WorkspacePanelsContext'
import { fetchActivityDetail, fetchWorkspaceActivityFeed } from '@/lib/activityFeed'
import { formatActivityDetailMarkdown } from '@/lib/activityDetailMarkdown'
import type { ActivityNode } from '@/lib/activityTypes'
import { isAgentDmRoom, isProjectRoom } from '@/lib/roomChat'
import { PANEL_IDS } from '@/lib/panelControlConfig'
import { watchWorkspaceEvents, workframeAuthApi } from '@/lib/workframeAuthApi'

export function ActivityPanel({ api }: IDockviewPanelProps) {
  const { activeRoom } = useWorkspacePanels()
  const { stateDbSessionId, resumeSession } = useHermesSession()
  const { openContent } = useBrowserWorkspace()
  const [nodes, setNodes] = useState<ActivityNode[]>([])
  const [workspaceId, setWorkspaceId] = useState('')

  const reloadFeed = useCallback(async () => {
    const wid = workspaceId.trim()
    if (!wid) {
      setNodes([])
      return
    }
    try {
      const feed = await fetchWorkspaceActivityFeed(wid)
      setNodes(feed)
    } catch {
      setNodes([])
    }
  }, [workspaceId])

  useEffect(() => {
    let cancelled = false
    void workframeAuthApi.getMe().then((profile) => {
      if (cancelled) return
      const wid =
        profile.current_workspace?.id ??
        profile.default_workspace?.id ??
        profile.workspaces?.[0]?.id ??
        ''
      setWorkspaceId(wid)
    })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!workspaceId) {
      setNodes([])
      return
    }

    let cancelled = false

    async function load() {
      try {
        const feed = await fetchWorkspaceActivityFeed(workspaceId)
        if (!cancelled) setNodes(feed)
      } catch {
        if (!cancelled) setNodes([])
      }
    }

    void load()
    const interval = window.setInterval(() => {
      void load()
    }, 5000)
    const stopEvents = watchWorkspaceEvents(workspaceId, () => {
      void load()
    })

    return () => {
      cancelled = true
      window.clearInterval(interval)
      stopEvents()
    }
  }, [workspaceId, stateDbSessionId])

  const handleSessionActivate = useCallback(
    async (node: ActivityNode) => {
      const sessionId = node.sessionId?.trim()
      const roomId = activeRoom?.id ?? ''
      if (!sessionId) return
      try {
        if (activeRoom && isAgentDmRoom(activeRoom)) {
          await resumeSession(sessionId)
        } else if (activeRoom && isProjectRoom(activeRoom) && roomId) {
          await workframeAuthApi.activateRoomSession(roomId, { session_id: sessionId, profile: node.profile })
        }
        await reloadFeed()
      } catch {
        // ponytail: errors surface via chat/session context
      }
    },
    [activeRoom, reloadFeed, resumeSession],
  )

  const handleItemClick = async (node: ActivityNode) => {
    const toolCallId = node.toolCallId ?? ''
    const sessionId = node.sessionId ?? ''
    const messageId = node.messageId ?? ''
    if (!node.profile || !toolCallId || !sessionId) return
    const tabId = `activity:${node.profile}:${toolCallId}`
    const title = `${node.agentName} — ${node.label}`.trim()
    try {
      const detail = await fetchActivityDetail(node.profile, toolCallId, sessionId, messageId)
      const markdown = formatActivityDetailMarkdown(detail)
      openContent({ id: tabId, title, content: markdown })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Activity detail unavailable'
      openContent({
        id: tabId,
        title,
        content: `# ${title}\n\n\`\`\`text\n${message}\n\`\`\``,
      })
    }
  }

  return (
    <PanelShell className="wf-panel--activity wf-panel--dockable">
      <PanelHeader label="Activity" panelId={PANEL_IDS.activity} api={api} />

      <ActivityTree
        nodes={nodes}
        className="wf-activity-tree--panel"
        activeSessionId={activeRoom && isAgentDmRoom(activeRoom) ? stateDbSessionId : null}
        onItemClick={handleItemClick}
        onSessionActivate={handleSessionActivate}
      />
    </PanelShell>
  )
}
