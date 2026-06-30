import type { BrowserTab } from '@/lib/browserTypes'
import { isUrl } from '@/lib/fileCapabilities'
import { workspaceRawUrl } from '@/lib/filesApi'

/** ponytail: case-fold paths for tab identity; upgrade if workspace needs case-sensitive dedup on case-sensitive FS. */
export function normalizeFilePath(path: string): string {
  return path.trim().replace(/\\/g, '/').replace(/^\/+/, '').toLowerCase()
}

export function fileTabId(relativePath: string): string {
  return `file:${normalizeFilePath(relativePath)}`
}

export function tabMatchesFilePath(tab: BrowserTab, relativePath: string): boolean {
  if (tab.source !== 'file' && tab.source !== 'content') return false
  return normalizeFilePath(tab.location) === normalizeFilePath(relativePath)
}

export function findFileTab(tabs: BrowserTab[], relativePath: string): BrowserTab | undefined {
  const id = fileTabId(relativePath)
  return tabs.find((tab) => tab.id === id || tabMatchesFilePath(tab, relativePath))
}

/** Drop duplicate tabs for the same file path; canonical tab id becomes `keepTabId`. */
export function dedupeFileTabs(tabs: BrowserTab[], relativePath: string, keepTabId: string): BrowserTab[] {
  const existing = findFileTab(tabs, relativePath)
  if (!existing) return tabs
  return tabs
    .filter((tab) => tab.id === existing.id || !tabMatchesFilePath(tab, relativePath))
    .map((tab) => (tab.id === existing.id ? { ...tab, id: keepTabId } : tab))
}

function toAbsoluteUrl(href: string): string {
  try {
    return new URL(href, window.location.origin).href
  } catch {
    return href
  }
}

/** URL to open the active browser tab in the user's default browser. */
export function resolveBrowserExternalHref(tab: BrowserTab | null | undefined): string | undefined {
  if (!tab) return undefined

  if (tab.source === 'url' || tab.mode === 'navigate') {
    const location = tab.location.trim()
    if (!location) return undefined
    if (isUrl(location) || location.startsWith('/')) return toAbsoluteUrl(location)
    return undefined
  }

  const content = tab.content.trim()
  if (content && (isUrl(content) || content.startsWith('data:'))) {
    return content.startsWith('data:') ? content : toAbsoluteUrl(content)
  }

  if (tab.source === 'file') {
    const path = tab.location.trim()
    if (!path || isUrl(path)) return path ? toAbsoluteUrl(path) : undefined
    return toAbsoluteUrl(workspaceRawUrl(path))
  }

  return undefined
}
