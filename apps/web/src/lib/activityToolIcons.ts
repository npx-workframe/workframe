import type { LucideIcon } from 'lucide-react'
import {
  Brain,
  CheckSquare,
  Code2,
  FileDiff,
  FileInput,
  FilePen,
  FolderOpen,
  FolderSearch,
  GitBranch,
  Globe,
  Image,
  Kanban,
  ListTodo,
  OctagonAlert,
  Search,
  Sparkles,
  Terminal,
  TextSearch,
  Wrench,
} from 'lucide-react'

import type { ActivityNode } from '@/lib/activityTypes'

/** ponytail: curated Hermes tool → icon map; unknown tools fall back to Wrench. */
const TOOL_ICONS: Record<string, LucideIcon> = {
  terminal: Terminal,
  read_file: FileInput,
  write_file: FilePen,
  edit_file: FilePen,
  patch_file: FileDiff,
  apply_patch: FileDiff,
  list_dir: FolderOpen,
  find: FolderSearch,
  glob: FolderSearch,
  grep: TextSearch,
  web_search: Search,
  search: Search,
  brave_search: Search,
  browser_navigate: Globe,
  browser_click: Globe,
  browser_snapshot: Globe,
  browser: Globe,
  delegate_task: GitBranch,
  subagent: GitBranch,
  memory: Brain,
  memory_update: Brain,
  memory_search: Brain,
  skill_view: Sparkles,
  skill_load: Sparkles,
  plan: ListTodo,
  execute_code: Code2,
  run_python: Code2,
  kanban_complete: CheckSquare,
  kanban_block: OctagonAlert,
  kanban_dispatch: Kanban,
  fetch_url: Globe,
  image_generate: Image,
  generate_image: Image,
  todo_write: ListTodo,
  _thinking: Brain,
  think: Brain,
}

export function normalizeToolName(name: string): string {
  const trimmed = name.trim().toLowerCase()
  if (!trimmed) return 'tool'
  return trimmed.replace(/^tool:\s*/i, '').split(/[\s/→]+/)[0] ?? 'tool'
}

export function toolIconFor(name: string): LucideIcon {
  const key = normalizeToolName(name)
  return TOOL_ICONS[key] ?? Wrench
}

export function toolNameFor(node: ActivityNode): string {
  return node.refs.toolName?.trim() || node.label.replace(/^(running )?tool:\s*/i, '').trim() || 'tool'
}

export function toolDisplayText(node: ActivityNode): string {
  const stripped = node.label.replace(/^(running )?tool:\s*/i, '').trim()
  if (stripped) return stripped
  return toolNameFor(node)
}

export function isToolActivityNode(node: ActivityNode): boolean {
  if (node.source === 'message' || node.kind === 'tool_call') return true
  if (node.refs.toolName) return true
  if (/^(running )?tool:/i.test(node.label)) return true
  return ['file_read', 'file_write', 'file_edit', 'search', 'plan', 'delegate'].includes(node.kind)
}

export type ActivityToolLabel = {
  toolName: string
  text: string
}

export function activityToolLabel(node: ActivityNode): ActivityToolLabel | null {
  if (!isToolActivityNode(node)) return null
  const toolName = normalizeToolName(toolNameFor(node))
  return { toolName, text: toolDisplayText(node) }
}
