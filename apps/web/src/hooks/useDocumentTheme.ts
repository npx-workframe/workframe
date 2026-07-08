import { useEffect, useState } from 'react'

import type { Theme } from '@/lib/theme'

const VALID: Theme[] = ['strato-dark', 'neo-light', 'neo-blue']

function readDomTheme(): Theme {
  const value = document.documentElement.dataset.theme
  return VALID.includes(value as Theme) ? (value as Theme) : 'neo-light'
}

/** Sync React to data-theme on html (ThemeSwitcher / applyTheme). */
export function useDocumentTheme(): Theme {
  const [theme, setTheme] = useState<Theme>(() => readDomTheme())

  useEffect(() => {
    const root = document.documentElement
    const observer = new MutationObserver(() => setTheme(readDomTheme()))
    observer.observe(root, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])

  return theme
}
