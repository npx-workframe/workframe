import { useEffect, useState } from 'react'

import { getInitialTheme, type Theme } from '@/lib/theme'

const VALID: Theme[] = ['dark', 'neo', 'blueprint']

function readDocumentTheme(): Theme {
  const value = document.documentElement.dataset.theme
  if (VALID.includes(value as Theme)) return value as Theme
  return getInitialTheme()
}

/** Sync React to data-theme on html (ThemeSwitcher / applyTheme). */
export function useDocumentTheme(): Theme {
  const [theme, setTheme] = useState<Theme>(() => readDocumentTheme())

  useEffect(() => {
    const sync = () => setTheme(readDocumentTheme())
    sync()
    const obs = new MutationObserver(sync)
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => obs.disconnect()
  }, [])

  return theme
}
