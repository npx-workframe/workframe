export type Theme = 'dark' | 'neo'

const STORAGE_KEY = 'wf-theme'

const VALID_THEMES: Theme[] = ['dark', 'neo']

function readStoredTheme(): Theme | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    if (VALID_THEMES.includes(value as Theme)) {
      return value as Theme
    }
    return null
  } catch {
    return null
  }
}

export function getInitialTheme(): Theme {
  return readStoredTheme() ?? 'neo'
}

export function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme
  document.documentElement.style.colorScheme = theme === 'neo' ? 'light' : 'dark'
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', '#0A0A0F')
  installNeoPressFeedback(theme === 'neo')
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
