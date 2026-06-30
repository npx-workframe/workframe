import type { ReactNode } from 'react'

type SettingsSectionProps = {
  title: string
  hint?: ReactNode
  children: ReactNode
  className?: string
}

export function SettingsSection({ title, hint, children, className }: SettingsSectionProps) {
  return (
    <section className={className ?? 'wf-settings-section wf-wizard-section'}>
      <h3 className="wf-wizard-section__title">{title}</h3>
      {hint ? <p className="wf-wizard-section__hint">{hint}</p> : null}
      {children}
    </section>
  )
}
