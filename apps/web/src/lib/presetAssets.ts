import avatarCatalogData from '@/assets/avatars/catalog.json'
import logoCatalogData from '@/assets/project-logos/catalog.json'

export type PresetKind = 'agent' | 'user' | 'logo'

type CatalogRow = { id: string; file?: string; label?: string }
type AvatarCatalog = { public_base?: string; avatars?: CatalogRow[] }
type LogoCatalog = { public_base?: string; logos?: CatalogRow[] }

const avatarCatalog = avatarCatalogData as AvatarCatalog
const logoCatalog = logoCatalogData as LogoCatalog

const avatarModules = import.meta.glob<string>('../assets/avatars/*.png', {
  eager: true,
  query: '?url',
  import: 'default',
})
const logoModules = import.meta.glob<string>('../assets/project-logos/*.png', {
  eager: true,
  query: '?url',
  import: 'default',
})

const avatarPublicBase = avatarCatalog.public_base || '/assets/avatars'

function urlFromGlob(modules: Record<string, string>, file: string): string {
  const suffix = `/${file}`
  const key = Object.keys(modules).find((entry) => entry.replace(/\\/g, '/').endsWith(suffix))
  return key ? modules[key] : ''
}

export type PresetItem = { id: string; src: string; label: string }

function buildPresets(
  rows: CatalogRow[],
  modules: Record<string, string>,
  publicBase: string,
): PresetItem[] {
  return rows.map((row) => {
    const file = row.file || `${row.id}.png`
    const bundled = urlFromGlob(modules, file)
    const src = bundled || `${publicBase.replace(/\/$/, '')}/${file}`
    return { id: row.id, src, label: row.label || row.id }
  })
}

const avatarPresets = buildPresets(
  avatarCatalog.avatars ?? [],
  avatarModules,
  avatarPublicBase,
)
const logoPresets = buildPresets(
  logoCatalog.logos ?? [],
  logoModules,
  logoCatalog.public_base || '/assets/project-logos',
)

const presetsByKind: Record<PresetKind, PresetItem[]> = {
  agent: avatarPresets,
  user: avatarPresets,
  logo: logoPresets,
}

export function listPresets(kind: PresetKind): PresetItem[] {
  return presetsByKind[kind]
}

export function presetUrl(kind: PresetKind, id: string): string | null {
  const row = presetsByKind[kind].find((item) => item.id === id)
  return row?.src ?? null
}

export function pickRandomPreset(kind: PresetKind): string {
  const list = presetsByKind[kind]
  if (!list.length) return ''
  return list[Math.floor(Math.random() * list.length)].src
}

export const DEFAULT_USER_AVATAR =
  presetUrl('user', 'grace') || avatarPresets[0]?.src || ''
export const DEFAULT_WORKSPACE_LOGO =
  presetUrl('logo', '4') || logoPresets[0]?.src || ''

export function agentPresetUrl(id: string): string | null {
  return presetUrl('agent', id)
}

function urlPath(src: string): string {
  const raw = String(src || '').trim()
  if (!raw) return ''
  try {
    if (raw.startsWith('http://') || raw.startsWith('https://')) {
      return new URL(raw).pathname
    }
  } catch {
    /* ponytail: not a URL — use as path */
  }
  return raw.split('?')[0].split('#')[0]
}

function catalogForKind(kind: PresetKind): AvatarCatalog | LogoCatalog {
  return kind === 'logo' ? logoCatalog : avatarCatalog
}

/** Map picker src, stable /assets/{kind}/*.png, or vite-hashed /assets/*.png → catalog id. */
export function presetIdFromSrc(kind: PresetKind, src: string): string | null {
  const path = urlPath(src)
  if (!path) return null
  const list = presetsByKind[kind]
  const direct = list.find((item) => urlPath(item.src) === path || item.src === src)
  if (direct) return direct.id

  const catalog = catalogForKind(kind)
  const itemsKey = kind === 'logo' ? 'logos' : 'avatars'
  const items = (catalog[itemsKey as keyof typeof catalog] as CatalogRow[] | undefined) ?? []
  const base = String(catalog.public_base || '').replace(/\/$/, '')

  const legacyBases =
    kind === 'logo'
      ? [base, '/assets/logos', '/assets/project-logos'].filter((entry, index, all) => all.indexOf(entry) === index)
      : [base, '/assets/agents', '/assets/users'].filter((entry, index, all) => all.indexOf(entry) === index)

  for (const legacyBase of legacyBases) {
    if (!legacyBase) continue
    const escaped = legacyBase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const stable = path.match(new RegExp(`^${escaped}/([^/]+)\\.png$`, 'i'))
    if (stable) {
      const stem = stable[1]
      const byId = list.find((item) => item.id === stem)
      if (byId) return byId.id
      for (const row of items) {
        const file = String(row.file || `${row.id}.png`).replace(/\.png$/i, '')
        if (file === stem || String(row.id) === stem) return String(row.id)
      }
    }
  }

  const hashed = path.match(/\/assets\/([a-z0-9]+)-[A-Za-z0-9_]+\.png$/i)
  if (hashed) {
    const prefix = hashed[1]
    if (list.some((item) => item.id === prefix)) return prefix
    for (const row of items) {
      const stem = String(row.file || `${row.id}.png`).replace(/\.png$/i, '')
      if (stem === prefix) return String(row.id)
    }
  }
  return null
}

/** Stable API payload: catalog id + nginx-served path (not vite hash). */
export function agentAvatarPersistPayload(
  pick: string,
): { avatar_id?: string; avatar_url: string } {
  const raw = String(pick || '').trim()
  if (!raw) return { avatar_url: '' }
  if (raw.startsWith('data:')) return { avatar_url: raw }
  const id = presetIdFromSrc('agent', raw)
  if (id) {
    const row = (avatarCatalog.avatars ?? []).find((entry) => entry.id === id)
    const file = row?.file || `${id}.png`
    return { avatar_id: id, avatar_url: `${avatarPublicBase}/${file}` }
  }
  return { avatar_url: raw }
}

/** Picker highlight value from saved API/catalog url. */
export function agentAvatarPickerValue(saved: string): string {
  return presetPickerValue('agent', saved)
}

function presetPickerValue(kind: PresetKind, saved: string): string {
  const raw = String(saved || '').trim()
  if (!raw) return ''
  const catalog = catalogForKind(kind)
  const itemsKey = kind === 'logo' ? 'logos' : 'avatars'
  const items = (catalog[itemsKey as keyof typeof catalog] as CatalogRow[] | undefined) ?? []
  const id =
    presetIdFromSrc(kind, raw) ||
    (items.some((row) => row.id === raw) ? raw : null)
  if (id) return presetUrl(kind, id) ?? raw
  return raw
}

function presetPersistUrl(
  kind: 'user' | 'logo',
  pick: string,
): { avatar_url: string } {
  const raw = String(pick || '').trim()
  if (!raw) return { avatar_url: '' }
  if (raw.startsWith('data:')) return { avatar_url: raw }
  const id = presetIdFromSrc(kind, raw)
  const catalog = kind === 'logo' ? logoCatalog : avatarCatalog
  const itemsKey = kind === 'logo' ? 'logos' : 'avatars'
  const base = String(
    catalog.public_base || (kind === 'logo' ? '/assets/project-logos' : '/assets/avatars'),
  ).replace(/\/$/, '')
  if (id) {
    const row = (catalog[itemsKey as keyof typeof catalog] as CatalogRow[] | undefined)?.find(
      (entry) => entry.id === id,
    )
    const file = row?.file || `${id}.png`
    return { avatar_url: `${base}/${file}` }
  }
  return { avatar_url: raw }
}

export function userAvatarPersistPayload(pick: string): { avatar_url: string } {
  return presetPersistUrl('user', pick)
}

export function logoAvatarPersistPayload(pick: string): { avatar_url: string } {
  return presetPersistUrl('logo', pick)
}

export function userAvatarPickerValue(saved: string): string {
  return presetPickerValue('user', saved)
}

export function logoAvatarPickerValue(saved: string): string {
  return presetPickerValue('logo', saved)
}
