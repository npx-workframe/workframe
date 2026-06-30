import { resolveAgentAvatarUrl } from '@/lib/avatarResolve'

/**
 * Crew row shape from the Workframe backend crew contract — stable for future gateway wiring.
 * @see Workframe/packages/create-workframe/workframe-api/server.py
 */
export type HermesProfile = {
  /** Profile directory slug (e.g. `architect`, `workframe-agent`). */
  profile: string
  /** Normalized lookup key. */
  key: string
  display_name: string
  /** Two-letter badge when no avatar asset exists. */
  code: string
  role: string
  tagline?: string
  color: string
  is_native?: boolean
  platform?: string
  route_status?: string
  avatar_url?: string
  avatar_id?: string
}

/** UI-enriched agent used across rail, chat, and activity placeholders. */
export type WorkframeAgent = HermesProfile & {
  avatarUrl: string | null
}

const CREW_COLORS = [
  'var(--wf-violet-glow)',
  'var(--wf-cyan)',
  'var(--wf-mint)',
  '#f59e0b',
  '#ec4899',
  '#6366f1',
  '#14b8a6',
] as const

function profileCode(displayName: string): string {
  return displayName
    .split(/\s+/)
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

function enrichProfile(profile: HermesProfile): WorkframeAgent {
  return {
    ...profile,
    avatarUrl: resolveAgentAvatarUrl(profile),
  }
}

/** Map a gateway crew row into the UI agent shape. */
export function workframeAgentFromHermes(row: HermesProfile): WorkframeAgent {
  return enrichProfile(row)
}

export function buildMockCrew(projectName: string): WorkframeAgent[] {
  const nativeSlug = `${projectName.toLowerCase().replace(/\s+/g, '')}-agent`
  const nativeName = `${projectName} Agent`

  const seeds: HermesProfile[] = [
    {
      profile: nativeSlug,
      key: nativeSlug,
      display_name: nativeName,
      code: profileCode(nativeName),
      role: 'Concierge',
      color: CREW_COLORS[0],
      is_native: true,
      platform: 'Workframe',
    },
    {
      profile: 'visionary',
      key: 'visionary',
      display_name: 'Visionary',
      code: 'VI',
      role: 'Strategy',
      color: CREW_COLORS[1],
    },
    {
      profile: 'architect',
      key: 'architect',
      display_name: 'Architect',
      code: 'AR',
      role: 'Systems',
      color: CREW_COLORS[2],
    },
    {
      profile: 'docs',
      key: 'docs',
      display_name: 'Docs',
      code: 'DO',
      role: 'Documentation',
      color: CREW_COLORS[3],
    },
    {
      profile: 'dev',
      key: 'dev',
      display_name: 'Dev',
      code: 'DE',
      role: 'Implementation',
      color: CREW_COLORS[4],
    },
    {
      profile: 'research',
      key: 'research',
      display_name: 'Research',
      code: 'RE',
      role: 'Evidence',
      color: CREW_COLORS[5],
    },
    {
      profile: 'designer',
      key: 'designer',
      display_name: 'Designer',
      code: 'DS',
      role: 'Visual',
      color: CREW_COLORS[6],
    },
  ]

  return seeds.map(enrichProfile)
}

export function findAgentByProfile(
  crew: WorkframeAgent[],
  profileOrKey: string,
): WorkframeAgent | undefined {
  const needle = profileOrKey.toLowerCase()
  let hit = crew.find(
    (member) =>
      member.profile.toLowerCase() === needle ||
      member.key.toLowerCase() === needle ||
      member.display_name.toLowerCase() === needle,
  )
  if (hit) return hit
  // Runtime DM profiles: u-{user}-{template} → match crew by template suffix.
  const runtimeMatch = needle.match(/^u-[a-z0-9][a-z0-9-]{0,62}$/)
  if (!runtimeMatch) return undefined
  const rest = needle.slice(2)
  return crew.find((member) => {
    const slug = member.profile.toLowerCase()
    return rest === slug || rest.endsWith(`-${slug}`)
  })
}

export function crewInitials(name: string) {
  return profileCode(name)
}
