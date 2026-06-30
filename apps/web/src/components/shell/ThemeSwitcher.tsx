import { useEffect, useRef, useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useTheme } from '@/hooks/useTheme'
import { THEME_OPTIONS } from '@/lib/themeOptions'

/** Compact header dropdown — prefer ThemeSettingsPanel in user settings. */
export function ThemeSwitcher() {
  const { theme, setTheme } = useTheme()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [open])

  const current = THEME_OPTIONS.find((o) => o.value === theme) ?? THEME_OPTIONS[0]

  return (
    <div className="wf-theme-switcher" ref={ref}>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="wf-theme-switcher__trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Theme: ${current.label}`}
        onClick={() => setOpen((v) => !v)}
      >
        <current.icon aria-hidden="true" />
        <span>{current.label}</span>
        <ChevronDown aria-hidden="true" className={open ? 'wf-theme-switcher__chevron--open' : ''} />
      </Button>

      {open ? (
        <ul className="wf-theme-switcher__menu" role="listbox" aria-label="Theme">
          {THEME_OPTIONS.map(({ value, label, icon: Icon }) => (
            <li key={value} role="option" aria-selected={theme === value}>
              <button
                type="button"
                className="wf-theme-switcher__item"
                onClick={() => {
                  setTheme(value)
                  setOpen(false)
                }}
              >
                <Icon aria-hidden="true" />
                <span>{label}</span>
                {theme === value ? <Check aria-hidden="true" className="wf-theme-switcher__check" /> : null}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
