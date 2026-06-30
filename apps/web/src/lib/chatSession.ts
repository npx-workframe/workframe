/**
 * Browser-tab identity helpers persisted in localStorage.
 *
 * Identity keys (client_id, schema versions) live here.
 * Lane/room/message hints live in `workspacePersist.ts` — optimistic UI cache
 * only; BFF bind (`ensureProfileBind`) remains authoritative on every open.
 */

const CLIENT_ID_KEY = 'wf-chat-client-id'
const SCHEMA_KEY_PREFIX = 'wf-chat-session-schema:'
const LEGACY_KEYS = [
  'wf-chat-session-id',
  'wf-chat-gateway-sid',
  'wf-chat-state-session-id',
  'wf-chat-session-v2-reset',
  'wf-chat-persistent-session-id',
] as const

/**
 * Native profile uses binding_version=2 so its lane-registry bucket stays
 * isolated from specialists. Specialists omit binding_version (undefined).
 */
export const WORKFRAME_UI_BINDING_VERSION = 2

function schemaKey(profile: string, scope = ''): string {
  const suffix = scope ? `:${scope}` : ''
  return `${SCHEMA_KEY_PREFIX}${profile}${suffix}`
}

export function getOrCreateClientId(): string {
  if (typeof window === 'undefined') return 'server'
  const current = localStorage.getItem(CLIENT_ID_KEY)
  if (current) return current
  const next = `ui-${Math.random().toString(36).slice(2, 10)}-${Date.now().toString(36)}`
  localStorage.setItem(CLIENT_ID_KEY, next)
  return next
}

/**
 * Drop prior dual-session / PTY bootstrap storage from the rolled-back design.
 * Runs once at module load.
 */
if (typeof window !== 'undefined') {
  for (const key of LEGACY_KEYS) {
    sessionStorage.removeItem(key)
    localStorage.removeItem(key)
  }
}

/**
 * Schema marker for the lane-registry binding. If the binding_version changes,
 * the lane-registry bucket is implicitly invalidated and the BFF will create a
 * fresh binding on the next session lookup. Stored in localStorage so a returning
 * tab upgrades without a clean install.
 */
export function markBindingSchema(profile: string, scope = ''): void {
  if (typeof window === 'undefined' || !profile) return
  const key = schemaKey(profile, scope)
  const current = localStorage.getItem(key)
  const next = String(WORKFRAME_UI_BINDING_VERSION)
  if (current !== next) {
    localStorage.setItem(key, next)
  }
}
