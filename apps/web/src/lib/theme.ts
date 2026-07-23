import {
  ARCHITECTONIC_THEME_REGISTRY,
  type ArchitectonicTheme,
  type ArchitectonicThemeDefinition,
} from '@/generated/architectonicThemes'

export type Theme = ArchitectonicTheme
export type ChromeMode = 'line' | 'relief' | 'glass'

export const THEME_DEFINITIONS = ARCHITECTONIC_THEME_REGISTRY.themes
export const VALID_THEMES = THEME_DEFINITIONS.map((definition) => definition.id) as Theme[]

const STORAGE_KEY = 'wf-theme'
const LEGACY_THEME: Record<string, Theme> = {
  ...ARCHITECTONIC_THEME_REGISTRY.legacyAliases,
  'strato-dark': 'liquid-glass-dark',
  'neo-blue': 'neo-dark',
}

export function isTheme(value: string | null | undefined): value is Theme {
  return Boolean(value && VALID_THEMES.includes(value as Theme))
}

export function getThemeDefinition(theme: Theme): ArchitectonicThemeDefinition {
  return THEME_DEFINITIONS.find((definition) => definition.id === theme) ?? THEME_DEFINITIONS[0]
}

function normalizeTheme(value: string | null): Theme | null {
  if (!value) return null
  if (isTheme(value)) return value
  return LEGACY_THEME[value] ?? null
}

function readStoredTheme(): Theme | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const theme = normalizeTheme(raw)
    if (theme && raw !== theme) localStorage.setItem(STORAGE_KEY, theme)
    return theme
  } catch {
    return null
  }
}

export function getInitialTheme(): Theme {
  return readStoredTheme() ?? ARCHITECTONIC_THEME_REGISTRY.defaultTheme
}

export function isDarkTheme(theme: Theme): boolean {
  return getThemeDefinition(theme).mode === 'dark'
}

export function isReliefTheme(theme: Theme): boolean {
  return getThemeDefinition(theme).style === 'shadows'
}

export function applyTheme(theme: Theme) {
  const root = document.documentElement
  const definition = getThemeDefinition(theme)
  const chromeMode: ChromeMode =
    definition.style === 'shadows' ? 'relief' : definition.style === 'glass' ? 'glass' : 'line'

  root.dataset.theme = theme
  root.dataset.archTheme = theme
  root.dataset.colorMode = definition.mode
  root.dataset.style = definition.style
  root.dataset.texture = definition.texture
  root.dataset.chromeMode = chromeMode
  root.dataset.density = 'technical'
  root.dataset.space = 'default'
  root.dataset.typeScale = 'compact'
  root.style.colorScheme = definition.mode

  const canvas = getComputedStyle(root).getPropertyValue('--bg').trim()
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute('content', canvas || (definition.mode === 'dark' ? '#0b1120' : '#f7f9fb'))
}

export function persistTheme(theme: Theme) {
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    /* ignore quota / private mode */
  }
}
