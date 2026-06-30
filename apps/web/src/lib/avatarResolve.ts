import catalogData from '@/assets/avatars/catalog.json'
import { agentAvatarForSlug, DEFAULT_USER_AVATAR } from '@/lib/workframeAssets'
import { agentPresetUrl, presetIdFromSrc, presetUrl } from '@/lib/presetAssets'

type CatalogRow = { id: string; file?: string; label?: string }
type AvatarCatalog = { public_base?: string; avatars?: CatalogRow[] }

const catalog = catalogData as AvatarCatalog
const catalogBase = String(catalog.public_base || '/assets/avatars').replace(/\/$/, '')
const catalogById = new Map(
  (catalog.avatars ?? []).map((row) => [row.id, row]),
)

/** Catalog PNG URL for an assigned avatar id (installer / agents.json). */
export function avatarUrlFromCatalogId(avatarId: string | null | undefined): string | null {
  const id = String(avatarId || '').trim()
  if (!id) return null
  const bundled = agentPresetUrl(id)
  if (bundled) return bundled
  const row = catalogById.get(id)
  const file = row?.file || `${id}.png`
  return `${catalogBase}/${file}`
}

export type AgentAvatarInput = {
  avatar_url?: string | null
  avatar_id?: string | null
  key?: string
  profile?: string
  is_native?: boolean
}

/** Single resolver for agent rail, chat, and activity surfaces. */
export function resolveAgentAvatarUrl(input: AgentAvatarInput): string | null {
  const fromCatalog = avatarUrlFromCatalogId(input.avatar_id)
  if (fromCatalog) return fromCatalog

  const explicit = String(input.avatar_url || '').trim()
  if (explicit) {
    const fromPick = presetIdFromSrc('agent', explicit)
    if (fromPick) {
      const fromId = avatarUrlFromCatalogId(fromPick)
      if (fromId) return fromId
    }
    const catalogId = explicit.match(/\/assets\/(?:avatars|agents|users)\/([^.]+)\.png$/i)?.[1]
    if (catalogId) {
      const fromPath = avatarUrlFromCatalogId(catalogId)
      if (fromPath) return fromPath
    }
    return explicit
  }

  const slug = String(input.key || input.profile || '').trim().toLowerCase()
  if (slug) {
    const fromSlug = agentAvatarForSlug(slug)
    if (fromSlug) return fromSlug
  }

  if (input.is_native) return agentPresetUrl('steve')
  return null
}

/** User avatar: saved profile URL, else default placeholder. */
export function resolveUserAvatarUrl(avatarUrl: string | null | undefined): string {
  const explicit = String(avatarUrl || '').trim()
  if (explicit) {
    const id = presetIdFromSrc('user', explicit)
    if (id) {
      const fromPreset = presetUrl('user', id)
      if (fromPreset) return fromPreset
    }
    if (
      explicit.startsWith('/assets/avatars/') ||
      explicit.startsWith('/assets/users/') ||
      explicit.startsWith('/assets/agents/')
    ) {
      return explicit
    }
    return explicit
  }
  return DEFAULT_USER_AVATAR
}

/** Workspace / space logo from stable catalog path or vite hash. */
export function resolveLogoUrl(logoUrl: string | null | undefined, fallback: string): string {
  const explicit = String(logoUrl || '').trim()
  if (!explicit) return fallback
  const id = presetIdFromSrc('logo', explicit)
  if (id) {
    const fromPreset = presetUrl('logo', id)
    if (fromPreset) return fromPreset
  }
  if (explicit.startsWith('/assets/project-logos/') || explicit.startsWith('/assets/logos/')) return explicit
  return explicit
}
