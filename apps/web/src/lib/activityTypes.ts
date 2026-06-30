/**
 * Activity feed types — shaped for deterministic Hermes stores (no agent-logs.db).
 *
 * Gateway mapping (future):
 * - `session`       → profiles/{p}/state.db `sessions`
 * - `message`       → profiles/{p}/state.db `messages` (tool_use blocks)
 * - `kanban_event`  → kanban.db `task_events` ⨝ `tasks`
 * - `kanban_run`    → kanban.db `task_runs` + Agents/kanban/logs/{task_id}.log lines
 * - `gateway_log`   → profiles/{p}/logs/*.log (coarse, optional)
 */

export type ActivitySource =
  | 'session'
  | 'message'
  | 'kanban_event'
  | 'kanban_run'
  | 'gateway_log'

export type ActivityKind =
  | 'session_start'
  | 'session_end'
  | 'message'
  | 'tool_call'
  | 'file_read'
  | 'file_write'
  | 'file_edit'
  | 'kanban_task'
  | 'kanban_status'
  | 'kanban_comment'
  | 'kanban_run'
  | 'plan'
  | 'search'
  | 'delegate'

export type ActivityStatus = 'active' | 'completed' | 'failed' | 'idle'

/** Stable refs for round-tripping to Hermes rows / log lines. */
export type ActivityRefs = {
  profile?: string
  sessionId?: string
  messageId?: string
  taskId?: string
  eventId?: string
  runId?: string
  toolName?: string
  filePath?: string
  model?: string
  platform?: string
}

export type ActivityNode = {
  id: string
  /** ISO 8601 — sort key for chronological trail */
  ts: string
  source: ActivitySource
  kind: ActivityKind
  profile: string
  agentName: string
  agentColor: string
  /** Primary line shown under the agent name */
  label: string
  status: ActivityStatus
  refs: ActivityRefs
  /** Nested run steps (kanban log lines, tool chain) */
  children?: ActivityNode[]
  /** Tool-call roundtrip refs (when source === 'message') */
  toolCallId?: string
  messageId?: string
  sessionId?: string
  tokenCount?: number
}

export function isActivityGroup(node: ActivityNode): node is ActivityNode & { children: ActivityNode[] } {
  return Boolean(node.children?.length)
}

/** Round-tripped BFF payload from `GET /api/activity/detail`. */
export type ActivityDetail = {
  ok: boolean
  error?: string
  profile: string
  toolCallId: string
  sessionId: string
  request: {
    tool_name: string
    arguments: Record<string, unknown>
    messageId: string
    timestamp: string
    model: string
  } | null
  response: {
    content: string
    parsed: unknown
    messageId: string
    timestamp: string
    tokenCount: number
  } | null
  metadata: {
    sessionTitle: string
    model: string
    messageCount: number
    startedAt: string
    endedAt: string | null
    toolCallCount: number
    inputTokens: number
    outputTokens: number
  }
  /** Tool-call wall time in seconds (response.timestamp - request.timestamp). */
  runDurationSeconds: number | null
  /** LLM model identifier from the profile's config.yaml (e.g. `openrouter/owl-alpha`). */
  modelName: string
  /** LLM provider (e.g. `openrouter`). */
  provider: string
}

export function formatSourceEyebrow(source: ActivitySource): string {
  switch (source) {
    case 'session':
      return 'session'
    case 'message':
      return 'message'
    case 'kanban_event':
      return 'kanban'
    case 'kanban_run':
      return 'run'
    case 'gateway_log':
      return 'log'
    default:
      return source
  }
}
