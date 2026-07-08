export type Theme = 'strato-dark' | 'neo-light' | 'neo-blue'

export type ChromeMode = 'line' | 'relief'

const CHROME_MODE: Record<Theme, ChromeMode> = {
  'strato-dark': 'line',
  'neo-light': 'relief',
  'neo-blue': 'relief',
}

const STORAGE_KEY = 'wf-theme'

const VALID_THEMES: Theme[] = ['strato-dark', 'neo-light', 'neo-blue']

/** ponytail: one-time localStorage migration from pre-rebrand slugs */
const LEGACY_THEME: Record<string, Theme> = {
  dark: 'strato-dark',
  neo: 'neo-light',
  blueprint: 'neo-blue',
}

function normalizeTheme(value: string | null): Theme | null {
  if (!value) return null
  if (VALID_THEMES.includes(value as Theme)) return value as Theme
  return LEGACY_THEME[value] ?? null
}

function readStoredTheme(): Theme | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const theme = normalizeTheme(raw)
    if (theme && raw !== theme) {
      localStorage.setItem(STORAGE_KEY, theme)
    }
    return theme
  } catch {
    return null
  }
}

export function getInitialTheme(): Theme {
  return readStoredTheme() ?? 'neo-light'
}

export function isStratoDark(theme: Theme): boolean {
  return theme === 'strato-dark'
}

export function isReliefTheme(theme: Theme): boolean {
  return theme === 'neo-light' || theme === 'neo-blue'
}

export function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme
  document.documentElement.dataset.chromeMode = CHROME_MODE[theme]
  document.documentElement.style.colorScheme = isStratoDark(theme) ? 'dark' : 'light'
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', '#0A0A0F')
  installNeoPressFeedback(isReliefTheme(theme))
}

let neoPressCleanup: (() => void) | undefined

function installNeoPressFeedback(enabled: boolean) {
  neoPressCleanup?.()
  neoPressCleanup = undefined
  if (!enabled) return

  const onPointerUp = (event: PointerEvent) => {
    const close = (event.target as Element | null)?.closest?.('.wf-browser-tabs__close')
    if (!(close instanceof HTMLElement) || close.matches(':disabled')) return
    close.classList.add('wf-neo-pressed')
    window.setTimeout(() => close.classList.remove('wf-neo-pressed'), 500)
  }

  document.addEventListener('pointerup', onPointerUp)
  neoPressCleanup = () => document.removeEventListener('pointerup', onPointerUp)
}

export function persistTheme(theme: Theme) {
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    /* ignore quota / private mode */
  }
}
