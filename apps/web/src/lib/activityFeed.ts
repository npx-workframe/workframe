import { apiGet } from '@/lib/apiClient'
import type {
  ActivityDetail,
  ActivityKind,
  ActivityNode,
  ActivitySource,
  ActivityStatus,
} from '@/lib/activityTypes'

/**
 * Pulls the activity feed from the BFF snapshot (Hermes-native stores).
 * No args — the activity is global to the project, not per-source.
 */
export async function fetchActivityFeed(): Promise<ActivityNode[]> {
  const data = await apiGet<{ activity?: Array<Record<string, unknown>> }>('/api/snapshot')
  const rows = data.activity ?? []
  return buildActivityTree(rows.map((row, index) => mapActivityRow(row, index)))
}

/** Room-scoped activity from `room_sessions` + Hermes tool runs for that room. */
export async function fetchRoomActivityFeed(roomId: string): Promise<ActivityNode[]> {
  const rid = roomId.trim()
  if (!rid) return []
  const data = await apiGet<{ activity?: Array<Record<string, unknown>> }>(
    `/api/rooms/${encodeURIComponent(rid)}/activity`,
  )
  const rows = data.activity ?? []
  return buildActivityTree(rows.map((row, index) => mapActivityRow(row, index)))
}

/** Workspace-wide activity (all rooms + kanban on the workspace board). */
export async function fetchWorkspaceActivityFeed(workspaceId: string): Promise<ActivityNode[]> {
  const wid = workspaceId.trim()
  if (!wid) return []
  const data = await apiGet<{ activity?: Array<Record<string, unknown>> }>(
    `/api/workspace/${encodeURIComponent(wid)}/activity`,
  )
  const rows = data.activity ?? []
  return buildActivityTree(rows.map((row, index) => mapActivityRow(row, index)))
}

export function watchActivityFeed(onUpdate: (nodes: ActivityNode[]) => void): () => void {
  const source = new EventSource('/api/events')
  let cancelled = false

  const apply = (payload: { activity?: Array<Record<string, unknown>> }) => {
    if (cancelled) return
    const rows = payload.activity ?? []
    onUpdate(buildActivityTree(rows.map((row, index) => mapActivityRow(row, index))))
  }

  source.onmessage = (event) => {
    try {
      apply(JSON.parse(event.data) as { activity?: Array<Record<string, unknown>> })
    } catch {
      // ignore malformed frames
    }
  }

  source.onerror = () => {
    // EventSource reconnects automatically
  }

  return () => {
    cancelled = true
    source.close()
  }
}

function mapActivityRow(row: Record<string, unknown>, index: number): ActivityNode {
  const source = normalizeSource(String(row.source ?? 'session'))
  const kind = normalizeKind(String(row.kind ?? ''), source)
  const sessionId = String(row.session_id ?? '').trim()
  const toolCallId = String(row.tool_call_id ?? '').trim()
  const profile = String(row.profile ?? 'unknown')
  const toolName = String(row.tool_name ?? '').trim()

  return {
    id: String(row.id ?? `${source}:${profile}:${index}`),
    ts: String(row.created_at ?? new Date().toISOString()),
    source,
    kind,
    profile,
    agentName: String(row.agent_name ?? row.profile ?? 'Agent'),
    agentColor: 'var(--wf-violet-glow)',
    label: String(row.task_description ?? ''),
    status: normalizeStatus(String(row.status ?? 'completed')),
    refs: {
      model: String(row.model_used ?? ''),
      toolName: toolName || undefined,
      sessionId: sessionId || undefined,
    },
    toolCallId: toolCallId || undefined,
    messageId: String(row.message_id ?? '') || undefined,
    sessionId: sessionId || undefined,
    tokenCount: Number(row.token_count ?? 0),
  }
}

export function buildActivityTree(flat: ActivityNode[]): ActivityNode[] {
  const sessions = new Map<string, ActivityNode>()
  const tools = new Map<string, ActivityNode[]>()
  const standalone: ActivityNode[] = []

  for (const node of flat) {
    if (node.source === 'session') {
      const sid = node.sessionId ?? ''
      if (sid) sessions.set(sid, node)
      else standalone.push(node)
      continue
    }
    if (node.source === 'message' && node.sessionId) {
      const list = tools.get(node.sessionId) ?? []
      list.push(node)
      tools.set(node.sessionId, list)
      continue
    }
    standalone.push(node)
  }

  const trees: ActivityNode[] = []
  const usedSessions = new Set<string>()

  for (const [sid, children] of tools) {
    const sortedChildren = [...children].sort((a, b) => Date.parse(b.ts) - Date.parse(a.ts))
    const hasActiveChild = sortedChildren.some((child) => child.status === 'active')
    const session = sessions.get(sid)

    if (session) {
      trees.push({
        ...session,
        status: hasActiveChild ? 'active' : session.status,
        children: sortedChildren,
      })
      usedSessions.add(sid)
      continue
    }

    const head = sortedChildren[0]
    if (!head) continue
    trees.push({
      id: `session-wrap:${sid}`,
      ts: head.ts,
      source: 'session',
      kind: 'session_start',
      profile: head.profile,
      agentName: head.agentName,
      agentColor: head.agentColor,
      label: `${sortedChildren.length} tool run${sortedChildren.length === 1 ? '' : 's'}`,
      status: hasActiveChild ? 'active' : 'idle',
      refs: head.refs,
      sessionId: sid,
      children: sortedChildren,
    })
    usedSessions.add(sid)
  }

  for (const [sid, session] of sessions) {
    if (!usedSessions.has(sid)) trees.push(session)
  }

  trees.push(...standalone)

  return sortActivityNewestFirst(trees)
}

export async function fetchActivityDetail(
  profile: string,
  toolCallId: string,
  sessionId: string,
  messageId: string,
): Promise<ActivityDetail> {
  const params = new URLSearchParams({
    profile,
    tool_call_id: toolCallId,
    session_id: sessionId,
    message_id: messageId,
  })
  const raw = await apiGet<RawActivityDetail>(`/api/activity/detail?${params.toString()}`)
  return normalizeActivityDetail(raw)
}

/** BFF returns snake_case; the UI type and formatter use camelCase. */
type RawActivityDetail = {
  ok: boolean
  error?: string
  profile: string
  tool_call_id: string
  session_id: string
  request: {
    tool_name: string
    arguments: Record<string, unknown>
    message_id: string
    timestamp: string
    model: string
  } | null
  response: {
    content: string
    parsed: unknown
    message_id: string
    timestamp: string
    token_count: number
  } | null
  metadata: {
    session_title: string
    model: string
    message_count: number
    started_at: string
    ended_at: string | null
    tool_call_count: number
    input_tokens: number
    output_tokens: number
  }
  run_duration_seconds: number | null
  model_name: string
  provider: string
}

function normalizeActivityDetail(raw: RawActivityDetail): ActivityDetail {
  return {
    ok: raw.ok,
    error: raw.error,
    profile: raw.profile,
    toolCallId: raw.tool_call_id,
    sessionId: raw.session_id,
    request: raw.request
      ? {
          tool_name: raw.request.tool_name,
          arguments: raw.request.arguments,
          messageId: raw.request.message_id,
          timestamp: raw.request.timestamp,
          model: raw.request.model,
        }
      : null,
    response: raw.response
      ? {
          content: raw.response.content,
          parsed: raw.response.parsed,
          messageId: raw.response.message_id,
          timestamp: raw.response.timestamp,
          tokenCount: raw.response.token_count,
        }
      : null,
    metadata: {
      sessionTitle: raw.metadata.session_title,
      model: raw.metadata.model,
      messageCount: raw.metadata.message_count,
      startedAt: raw.metadata.started_at,
      endedAt: raw.metadata.ended_at,
      toolCallCount: raw.metadata.tool_call_count,
      inputTokens: raw.metadata.input_tokens,
      outputTokens: raw.metadata.output_tokens,
    },
    runDurationSeconds: raw.run_duration_seconds ?? null,
    modelName: raw.model_name ?? '',
    provider: raw.provider ?? '',
  }
}

function normalizeSource(raw: string): ActivitySource {
  const source = raw.toLowerCase()
  if (source === 'session') return 'session'
  if (source === 'message') return 'message'
  if (source === 'kanban') return 'kanban_event'
  if (source === 'kanban_event') return 'kanban_event'
  if (source === 'kanban_run') return 'kanban_run'
  if (source === 'gateway_log') return 'gateway_log'
  return 'session'
}

function normalizeKind(raw: string, source: ActivitySource): ActivityKind {
  const kind = raw.toLowerCase()
  if (kind === 'tool_call') return 'tool_call'
  if (kind === 'session_start') return 'session_start'
  if (source === 'message') return 'tool_call'
  if (source === 'session') return 'session_start'
  if (source === 'kanban_run') return 'kanban_run'
  if (source === 'kanban_event') return 'kanban_task'
  return 'message'
}

function normalizeStatus(raw: string): ActivityStatus {
  const status = raw.toLowerCase()
  if (status.includes('fail') || status === 'blocked') return 'failed'
  if (status === 'active' || status === 'running' || status === 'in_progress') return 'active'
  if (status === 'completed' || status === 'done') return 'completed'
  return 'idle'
}

export function sortActivityNewestFirst(nodes: ActivityNode[]): ActivityNode[] {
  return [...nodes].sort((a, b) => {
    const activeDelta = Number(b.status === 'active') - Number(a.status === 'active')
    if (activeDelta !== 0) return activeDelta
    return Date.parse(b.ts) - Date.parse(a.ts)
  })
}
