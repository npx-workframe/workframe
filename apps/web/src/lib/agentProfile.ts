const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

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
  const templates = [
    'workframe-agent',
    'architect',
    'visionary',
    'docs',
    'dev',
    'research',
    'designer',
  ]
  for (const template of templates) {
    if (rest === template || rest.endsWith(`-${template}`)) return template
  }
  return profileOrRuntime.trim()
}

/** Hermes profile slug for API calls — never a workspace agent_profiles UUID. */
export function resolveHermesProfileSlug(
  room: AgentProfileRef | null | undefined,
  _fallback = '',
): string {
  if (!isAgentChatRoom(room)) return ''
  const hermes = room?.hermes_profile?.trim()
  if (hermes) return templateProfileSlug(hermes)
  const ref = room?.agent_profile_id?.trim() || ''
  if (!ref) return ''
  if (!UUID_RE.test(ref)) return templateProfileSlug(ref)
  // ponytail: agent DM rooms store agent_profiles.id (UUID). Never guess from stale activeProfile.
  return ''
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
