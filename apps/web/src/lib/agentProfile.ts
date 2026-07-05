import { nativeProfileSlug } from '@/lib/workframeProfile'

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

const TEMPLATE_PROFILES = [
  'workframe-agent',
  nativeProfileSlug(),
  'architect',
  'visionary',
  'docs',
  'dev',
  'research',
  'designer',
]

export type AgentProfileRef = {
  agent_profile_id?: string | null
  hermes_profile?: string | null
  room_type?: string | null
}

/** Map u-{user}-{template} runtime slugs back to template for API bind paths. */
export function templateProfileSlug(profileOrRuntime: string): string {
  const slug = profileOrRuntime.trim().toLowerCase()
  if (!/^u-[a-z0-9]/.test(slug)) return profileOrRuntime.trim()
  const rest = slug.slice(2)
  const templates = [...new Set(TEMPLATE_PROFILES.filter(Boolean))]
  for (const template of templates) {
    if (rest === template || rest.endsWith(`-${template}`)) return template
  }
  return profileOrRuntime.trim()
}

/** Hermes profile slug for API calls — never a workspace agent_profiles UUID. */
export function resolveHermesProfileSlug(
  room: AgentProfileRef | null | undefined,
  fallback = '',
): string {
  if (!isAgentChatRoom(room)) return ''
  const hermes = room?.hermes_profile?.trim()
  if (hermes) return templateProfileSlug(hermes)
  const ref = room?.agent_profile_id?.trim() || ''
  if (ref && !UUID_RE.test(ref)) return templateProfileSlug(ref)
  const fb = fallback.trim()
  if (fb && !UUID_RE.test(fb)) return templateProfileSlug(fb)
  // ponytail: agent DM rooms store agent_profiles.id (UUID). Never guess from stale activeProfile.
  return ''
}

/** Template Hermes slug for agent settings / routes — not per-user runtime u-*. */
export function resolveAgentTemplateProfile(
  room: AgentProfileRef | null | undefined,
  activeProfile: string,
): string {
  return (
    resolveHermesProfileSlug(room, activeProfile) ||
    (activeProfile.trim() && !isAgentProfileUuid(activeProfile)
      ? templateProfileSlug(activeProfile)
      : '') ||
    nativeProfileSlug()
  )
}

/** Hermes profile for model reads/writes in agent DM — bound runtime when available. */
export function resolveAgentModelsProfile(
  room: AgentProfileRef | null | undefined,
  activeProfile: string,
  runtimeProfile = '',
): string {
  if (!isAgentChatRoom(room)) return ''
  const runtime = runtimeProfile.trim()
  if (runtime && /^u-[a-z0-9]/i.test(runtime)) return runtime
  return resolveAgentTemplateProfile(room, activeProfile)
}

/** Agent DM room only — direct + bound agent. Projects use room_memberships for agents. */
export function isAgentChatRoom(room: AgentProfileRef | null | undefined): boolean {
  if (!room) return false
  const roomType = String(room.room_type || '').trim()
  if (roomType && roomType !== 'direct') return false
  return Boolean(room.hermes_profile?.trim() || room.agent_profile_id?.trim())
}

export function isAgentProfileUuid(value: string): boolean {
  return UUID_RE.test(value.trim())
}
