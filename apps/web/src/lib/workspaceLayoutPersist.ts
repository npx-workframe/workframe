import type { DockviewApi, SerializedDockview } from 'dockview'

import { WORKSPACE_PANEL_ORDER } from '@/lib/workspaceLayoutTokens'

const LAYOUT_VERSION = 1
const PERSIST_DEBOUNCE_MS = 400

const KNOWN_COMPONENTS = new Set([
  'chatWorkspace',
  'filesExplorer',
  'browser',
  'activity',
])

export type PersistedWorkspaceLayout = {
  version: typeof LAYOUT_VERSION
  dockview: SerializedDockview
  railExpanded?: boolean
}

function projectKey(): string {
  return import.meta.env.VITE_WORKFRAME_PROJECT?.trim() || 'Workframe'
}

function storageKey(): string {
  return `workframe.workspaceLayout:${projectKey()}`
}

function readJson<T>(key: string): T | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    return JSON.parse(raw) as T
  } catch {
    return null
  }
}

function writeJson(key: string, value: unknown): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // quota or privacy mode
  }
}

export function isValidPersistedWorkspaceLayout(
  value: unknown,
): value is PersistedWorkspaceLayout {
  if (!value || typeof value !== 'object') return false
  const candidate = value as PersistedWorkspaceLayout
  if (candidate.version !== LAYOUT_VERSION) return false
  if (!candidate.dockview?.grid || !candidate.dockview.panels) return false

  const panelIds = Object.keys(candidate.dockview.panels)
  if (!panelIds.length) return false

  const allowed = new Set<string>(WORKSPACE_PANEL_ORDER)
  if (!panelIds.every((id) => allowed.has(id))) return false

  for (const state of Object.values(candidate.dockview.panels)) {
    const component = state.contentComponent
    if (component && !KNOWN_COMPONENTS.has(component)) return false
  }

  return true
}

export function readPersistedWorkspaceLayout(): PersistedWorkspaceLayout | null {
  const data = readJson<unknown>(storageKey())
  return isValidPersistedWorkspaceLayout(data) ? data : null
}

export function tryRestorePersistedWorkspaceLayout(api: DockviewApi): boolean {
  const saved = readPersistedWorkspaceLayout()
  if (!saved) return false

  try {
    api.fromJSON(saved.dockview)
    return true
  } catch {
    return false
  }
}

export function readPersistedRailExpanded(): boolean | undefined {
  return readPersistedWorkspaceLayout()?.railExpanded
}

let persistTimer: ReturnType<typeof setTimeout> | undefined

export function schedulePersistWorkspaceLayout(
  api: DockviewApi,
  railExpanded: boolean,
): void {
  if (typeof window === 'undefined') return
  if (persistTimer) clearTimeout(persistTimer)
  persistTimer = setTimeout(() => {
    persistTimer = undefined
    try {
      const payload: PersistedWorkspaceLayout = {
        version: LAYOUT_VERSION,
        dockview: api.toJSON(),
        railExpanded,
      }
      writeJson(storageKey(), payload)
    } catch {
      // layout not ready
    }
  }, PERSIST_DEBOUNCE_MS)
}

export function clearPersistedWorkspaceLayout(): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.removeItem(storageKey())
  } catch {
    // ignore
  }
}
