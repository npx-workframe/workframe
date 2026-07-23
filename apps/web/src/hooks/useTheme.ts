import { useCallback, useEffect, useState } from 'react'

import { applyTheme, getInitialTheme, isDarkTheme, isTheme, persistTheme, type Theme } from '@/lib/theme'

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => getInitialTheme())

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  useEffect(() => {
    const root = document.documentElement
    const observer = new MutationObserver(() => {
      const next = root.dataset.theme
      if (isTheme(next)) setThemeState(next)
    })
    observer.observe(root, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next)
    persistTheme(next)
    applyTheme(next)
  }, [])

  const toggleTheme = useCallback(() => {
    setTheme(isDarkTheme(theme) ? 'neo-light' : 'minimal-dark')
  }, [setTheme, theme])

  return { theme, setTheme, toggleTheme }
}
