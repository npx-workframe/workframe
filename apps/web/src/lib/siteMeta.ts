export type PublicSiteMeta = {
  ok: boolean
  install_complete: boolean
  title: string
  short_name: string
  description: string
  tagline: string
  theme_color: string
  og_image: string
  favicon: string
  canonical_url: string
  manifest_url: string
  source?: {
    title: string
    description: string
    og_image: string
    favicon: string
  }
}

const META_KEYS = [
  'description',
  'og:title',
  'og:description',
  'og:image',
  'og:url',
  'twitter:title',
  'twitter:description',
  'twitter:image',
] as const

function upsertMeta(attr: 'name' | 'property', key: string, content: string) {
  if (!content) return
  let el = document.head.querySelector<HTMLMetaElement>(`meta[${attr}="${key}"]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, key)
    document.head.appendChild(el)
  }
  el.content = content
}

function upsertLink(rel: string, href: string, type?: string) {
  if (!href) return
  let el = document.head.querySelector<HTMLLinkElement>(`link[rel="${rel}"]`)
  if (!el) {
    el = document.createElement('link')
    el.rel = rel
    document.head.appendChild(el)
  }
  el.href = href
  if (type) el.type = type
}

export function applySiteMeta(meta: PublicSiteMeta) {
  document.title = meta.title || 'Workframe'
  upsertMeta('name', 'description', meta.description)
  upsertMeta('name', 'theme-color', meta.theme_color)
  upsertMeta('property', 'og:type', 'website')
  upsertMeta('property', 'og:site_name', meta.title)
  upsertMeta('property', 'og:title', meta.title)
  upsertMeta('property', 'og:description', meta.description)
  upsertMeta('property', 'og:url', meta.canonical_url)
  upsertMeta('property', 'og:image', meta.og_image)
  upsertMeta('name', 'twitter:card', 'summary_large_image')
  upsertMeta('name', 'twitter:title', meta.title)
  upsertMeta('name', 'twitter:description', meta.description)
  upsertMeta('name', 'twitter:image', meta.og_image)
  upsertLink('icon', meta.favicon)
  upsertLink('apple-touch-icon', meta.favicon)
  upsertLink('manifest', meta.manifest_url || '/manifest.webmanifest')
}

export async function fetchPublicSiteMeta(): Promise<PublicSiteMeta | null> {
  try {
    const res = await fetch('/api/public/site-meta', { credentials: 'same-origin' })
    if (!res.ok) return null
    return (await res.json()) as PublicSiteMeta
  } catch {
    return null
  }
}

export function clearDynamicSiteMeta() {
  for (const key of META_KEYS) {
    const attr = key.startsWith('og:') ? 'property' : 'name'
    document.head.querySelector(`meta[${attr}="${key}"]`)?.remove()
  }
}
