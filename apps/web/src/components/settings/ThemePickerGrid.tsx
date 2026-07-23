import { Check } from 'lucide-react'
import type { CSSProperties } from 'react'

import { THEME_OPTION_GROUPS } from '@/lib/themeOptions'
import type { Theme } from '@/lib/theme'
import { cn } from '@/lib/utils'

type ThemePreviewStyle = CSSProperties & {
  '--wf-theme-preview-canvas': string
  '--wf-theme-preview-surface': string
  '--wf-theme-preview-ink': string
  '--wf-theme-preview-accent': string
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
              const previewStyle: ThemePreviewStyle = {
                '--wf-theme-preview-canvas': preview.canvas,
                '--wf-theme-preview-surface': preview.surface,
                '--wf-theme-preview-ink': preview.ink,
                '--wf-theme-preview-accent': preview.accent,
              }
              return (
                <li key={optionValue}>
                  <button
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    className={cn('wf-theme-settings__option', selected && 'is-active')}
                    onClick={() => onChange(optionValue)}
                    disabled={disabled}
                  >
                    <span
                      className="wf-theme-settings__preview"
                      data-preview-style={style}
                      data-preview-texture={texture}
                      style={previewStyle}
                      aria-hidden="true"
                    >
                      <span className="wf-theme-settings__preview-rail" />
                      <span className="wf-theme-settings__preview-surface">
                        <span className="wf-theme-settings__preview-line" />
                        <span className="wf-theme-settings__preview-line is-short" />
                        <span className="wf-theme-settings__preview-action" />
                      </span>
                    </span>
                    <span className="wf-theme-settings__option-copy">
                      <span className="wf-theme-settings__label">{optionLabel}</span>
                      <span className="wf-theme-settings__meta">{style}</span>
                    </span>
                    {selected ? <Check aria-hidden="true" className="wf-theme-settings__check" /> : null}
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
