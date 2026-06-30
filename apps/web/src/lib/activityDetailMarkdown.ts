import type { ActivityDetail } from '@/lib/activityTypes'

/**
 * Format an activity detail as a markdown document for display in the browser panel.
 */
export function formatActivityDetailMarkdown(detail: ActivityDetail): string {
  if (!detail.ok) {
    return `# Activity Detail\n\n**Error:** ${detail.error ?? 'Unknown error'}`
  }

  const lines: string[] = []
  const req = detail.request
  const resp = detail.response
  const meta = detail.metadata

  lines.push(`# ${req?.tool_name ?? 'Tool Call'} — ${detail.profile}`)
  lines.push('')

  lines.push('## Metadata')
  lines.push('')
  lines.push('| Field | Value |')
  lines.push('|-------|-------|')
  lines.push(`| Agent | ${detail.profile} |`)
  lines.push(`| Model | ${formatModel(detail.modelName, detail.provider, detail.profile)} |`)
  if (meta.sessionTitle) lines.push(`| Session title | ${meta.sessionTitle} |`)
  lines.push(`| Session ID | \`${detail.sessionId}\` |`)
  if (req?.messageId) lines.push(`| Request message | \`${req.messageId}\` |`)
  if (resp?.messageId) lines.push(`| Response message | \`${resp.messageId}\` |`)
  lines.push(`| Tool call ID | \`${detail.toolCallId || '—'}\` |`)
  lines.push(`| Timestamp | ${formatTimestamp(req?.timestamp || resp?.timestamp || '')} |`)
  lines.push(`| Run duration | ${formatRunDuration(detail.runDurationSeconds)} |`)
  if (meta.messageCount) lines.push(`| Session messages | ${meta.messageCount} |`)
  if (meta.toolCallCount) lines.push(`| Session tool calls | ${meta.toolCallCount} |`)
  if (meta.inputTokens || meta.outputTokens) {
    lines.push(`| Tokens | ${meta.inputTokens || 0} in / ${meta.outputTokens || 0} out |`)
  }
  if (resp?.tokenCount) lines.push(`| Response tokens | ${resp.tokenCount} |`)
  lines.push('')

  if (req) {
    lines.push('## Request')
    lines.push('')
    lines.push(`**Tool:** \`${req.tool_name}\``)
    lines.push('')
    if (req.arguments && Object.keys(req.arguments).length > 0) {
      lines.push('### Arguments')
      lines.push('')
      lines.push('```json')
      lines.push(JSON.stringify(req.arguments, null, 2))
      lines.push('```')
      lines.push('')
    }
  }

  if (resp) {
    lines.push('## Response')
    lines.push('')

    const parsed = resp.parsed
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      const record = parsed as Record<string, unknown>

      if ('success' in record) {
        lines.push(`**Status:** ${record.success ? '✅ Success' : '❌ Failed'}`)
        lines.push('')
      }

      if (typeof record.diff === 'string' && record.diff.trim()) {
        lines.push('### Diff')
        lines.push('')
        lines.push('```diff')
        lines.push(record.diff)
        lines.push('```')
        lines.push('')
      }

      if (typeof record.content === 'string' && record.content.trim()) {
        lines.push('### Content')
        lines.push('')
        lines.push('```')
        lines.push(record.content)
        lines.push('```')
        lines.push('')
      }

      if (record.bytes_written != null) {
        lines.push(`**Bytes written:** ${record.bytes_written}`)
        lines.push('')
      }

      if (record.path != null && String(record.path).trim()) {
        lines.push(`**Path:** \`${record.path}\``)
        lines.push('')
      }

      const shown = new Set([
        'success',
        'diff',
        'content',
        'bytes_written',
        'path',
        'error',
        'lint',
        'resolved_path',
        'files_modified',
      ])
      const remaining: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(record)) {
        if (!shown.has(k) && v !== null && v !== undefined && v !== '') {
          remaining[k] = v
        }
      }
      if (Object.keys(remaining).length > 0) {
        lines.push('### Additional fields')
        lines.push('')
        lines.push('```json')
        lines.push(JSON.stringify(remaining, null, 2))
        lines.push('```')
        lines.push('')
      }
    } else if (resp.content.trim()) {
      lines.push('```text')
      lines.push(resp.content)
      lines.push('```')
      lines.push('')
    } else {
      lines.push('*Empty tool response*')
      lines.push('')
    }

    lines.push('## Raw response')
    lines.push('')
    lines.push('```text')
    lines.push(resp.content || '(empty)')
    lines.push('```')
    lines.push('')
  } else {
    lines.push('## Response')
    lines.push('')
    lines.push('*No response recorded yet*')
    lines.push('')
  }

  if (req?.arguments && Object.keys(req.arguments).length > 0) {
    lines.push('## Raw request')
    lines.push('')
    lines.push('```json')
    lines.push(JSON.stringify(req.arguments, null, 2))
    lines.push('```')
    lines.push('')
  }

  return lines.join('\n')
}

function formatTimestamp(iso: string): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function formatModel(modelName: string, provider: string, profile: string): string {
  const trimmed = modelName.trim()
  if (trimmed) {
    if (trimmed.toLowerCase() === profile.toLowerCase()) return '—'
    return trimmed
  }
  if (provider.trim()) return provider
  return '—'
}

function formatRunDuration(seconds: number | null): string {
  if (seconds == null) return '—'
  if (seconds < 1) return `${Math.round(seconds * 1000)} ms`
  if (seconds < 60) return `${seconds.toFixed(2)}s`
  const mins = Math.floor(seconds / 60)
  const rem = seconds - mins * 60
  return `${mins}m ${rem.toFixed(1)}s`
}
