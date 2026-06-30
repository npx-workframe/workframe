import { Check } from 'lucide-react'

import { useTheme } from '@/hooks/useTheme'
import { THEME_OPTIONS } from '@/lib/themeOptions'
import { cn } from '@/lib/utils'

export function ThemeSettingsPanel() {
  const { theme, setTheme } = useTheme()

  return (
    <div className="wf-wizard-panel wf-onboarding-form" role="tabpanel">
      <ul className="wf-theme-settings" role="listbox" aria-label="Theme">
        {THEME_OPTIONS.map(({ value, label, icon: Icon }) => {
          const selected = theme === value
          return (
            <li key={value} role="option" aria-selected={selected}>
              <button
                type="button"
                className={cn('wf-theme-settings__option', selected && 'is-active')}
                onClick={() => setTheme(value)}
              >
                <Icon aria-hidden="true" className="wf-theme-settings__icon" />
                <span className="wf-theme-settings__label">{label}</span>
                {selected ? <Check aria-hidden="true" className="wf-theme-settings__check" /> : null}
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
