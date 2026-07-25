import { Check } from 'lucide-react'
import type { CSSProperties } from 'react'

import { THEME_OPTION_GROUPS } from '@/lib/themeOptions'
import { getThemePreviewTokens } from '@/generated/themePreviewTokens'
import type { Theme } from '@/lib/theme'
import { cn } from '@/lib/utils'

type ThemeCardStyle = CSSProperties & {
  '--wf-theme-preview-canvas': string
  '--wf-theme-preview-surface': string
  '--wf-theme-preview-ink': string
  '--wf-theme-preview-ink-muted': string
  '--wf-theme-preview-accent': string
  '--wf-theme-preview-font': string
  '--wf-theme-preview-radius': string
  '--wf-theme-preview-panel-shadow': string
  '--wf-theme-preview-panel-inset-shadow': string
  '--wf-theme-preview-panel-border': string
}

type ThemePickerGridProps = {
  value: Theme
  onChange: (theme: Theme) => void
  className?: string
  compact?: boolean
  disabled?: boolean
  label?: string
}

export function ThemePickerGrid({
  value,
  onChange,
  className,
  compact = false,
  disabled = false,
  label = 'Theme',
}: ThemePickerGridProps) {
  return (
    <div
      className={cn('wf-theme-settings', compact && 'wf-theme-settings--compact', className)}
      role="radiogroup"
      aria-label={label}
    >
      {THEME_OPTION_GROUPS.map((group) => (
        <section className="wf-theme-settings__group" key={group.family} aria-label={group.label}>
          <h3 className="wf-theme-settings__group-label">{group.label}</h3>
          <ul className="wf-theme-settings__group-list">
            {group.options.map(({ value: optionValue, label: optionLabel, preview, style, texture }) => {
              const selected = value === optionValue
              const tokens = getThemePreviewTokens(optionValue, preview)
              const cardStyle: ThemeCardStyle = {
                '--wf-theme-preview-canvas': tokens.canvas,
                '--wf-theme-preview-surface': tokens.surface,
                '--wf-theme-preview-ink': tokens.ink,
                '--wf-theme-preview-ink-muted': tokens.inkMuted,
                '--wf-theme-preview-accent': tokens.accent,
                '--wf-theme-preview-font': tokens.fontFamily,
                '--wf-theme-preview-radius': tokens.radius,
                '--wf-theme-preview-panel-shadow': tokens.panelShadow,
                '--wf-theme-preview-panel-inset-shadow': tokens.panelInsetShadow,
                '--wf-theme-preview-panel-border': tokens.panelBorder,
              }
              return (
                <li key={optionValue}>
                  <button
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    className={cn('archi-theme-swatch wf-theme-settings__option', selected && 'is-active')}
                    aria-current={selected ? 'true' : undefined}
                    data-preview-theme={optionValue}
                    data-preview-style={style}
                    data-preview-texture={texture}
                    onClick={() => onChange(optionValue)}
                    disabled={disabled}
                  >
                    <span className="archi-theme-swatch__fill wf-theme-settings__fill" style={cardStyle}>
                      <span className="wf-theme-settings__mock" aria-hidden="true">
                        <span className="wf-theme-settings__mock-rail" />
                        <span className="wf-theme-settings__mock-surface">
                          <span className="wf-theme-settings__mock-line" />
                          <span className="wf-theme-settings__mock-line is-short" />
                          <span className="wf-theme-settings__mock-action" />
                        </span>
                      </span>
                      <span className="wf-theme-settings__option-copy">
                        <span className="wf-theme-settings__label">{optionLabel}</span>
                        <span className="wf-theme-settings__meta">{style}</span>
                      </span>
                      {selected ? <Check aria-hidden="true" className="wf-theme-settings__check" /> : null}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        </section>
      ))}
    </div>
  )
}
