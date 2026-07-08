import { useMemo, type ReactNode } from 'react'

import { ThemeSwitcher } from '@/components/shell/ThemeSwitcher'
import { useDocumentTheme } from '@/hooks/useDocumentTheme'
import { BRAND_ICON } from '@/lib/brandAssets'
import type { Theme } from '@/lib/theme'

export type WizardStepItem = {
  id: string
  label: string
  group: string
  /** Short summary of saved config (shown under the label). */
  detail?: string
  /** Step has required/minimum config saved. */
  configured?: boolean
}

type OnboardingWizardShellProps = {
  projectName: string
  /** When set, replaces the default workframe.svg mark in the rail brand. */
  brandLogoUrl?: string | null
  step: string
  steps: WizardStepItem[]
  /** Highest step index the user may jump to (inclusive). */
  maxReachableIndex?: number
  onStepSelect?: (stepId: string) => void
  title: string
  description?: ReactNode
  footer?: ReactNode
  children: ReactNode
}

function defaultWizardRailLogo(theme: Theme): { src: string; mono: boolean } {
  if (theme === 'neo-light' || theme === 'neo-blue') {
    return { src: BRAND_ICON.workframeColor, mono: false }
  }
  return { src: BRAND_ICON.workframe, mono: true }
}

export function OnboardingWizardShell({
  projectName,
  brandLogoUrl,
  step,
  steps,
  maxReachableIndex,
  onStepSelect,
  title,
  description,
  footer,
  children,
}: OnboardingWizardShellProps) {
  const theme = useDocumentTheme()
  const stepIndex = Math.max(0, steps.findIndex((s) => s.id === step))
  const reachable = maxReachableIndex ?? stepIndex
  const progress = steps.length > 1 ? Math.round(((stepIndex + 1) / steps.length) * 100) : 100

  const groups = useMemo(() => {
    const map = new Map<string, WizardStepItem[]>()
    for (const item of steps) {
      const list = map.get(item.group) ?? []
      list.push(item)
      map.set(item.group, list)
    }
    return [...map.entries()]
  }, [steps])

  const defaultLogo = defaultWizardRailLogo(theme)
  const railLogoSrc = brandLogoUrl ?? defaultLogo.src
  const railLogoMono = brandLogoUrl ? false : defaultLogo.mono

  return (
    <div className="wf-onboarding-page">
      <div className="wf-onboarding-page__theme">
        <ThemeSwitcher />
      </div>
      <div className="wf-onboarding-wizard">
        <aside className="wf-onboarding-wizard__rail" aria-label="Setup steps">
          <div className="wf-onboarding-wizard__brand">
            <span className="wf-onboarding-wizard__logo wf-onboarding-wizard__logo--image" aria-hidden="true">
              <img
                src={railLogoSrc}
                alt=""
                className={railLogoMono ? 'wf-brand-img--mono' : undefined}
              />
            </span>
            <div className="wf-onboarding-wizard__brand-copy">
              <strong>{projectName}</strong>
              <span>Setup wizard</span>
            </div>
          </div>

          <nav className="wf-onboarding-wizard__nav wf-scroll wf-scroll--vertical wf-scroll--inset-rail wf-scroll-host">
            {groups.map(([group, items]) => (
              <div key={group} className="wf-onboarding-wizard__group">
                <span className="wf-onboarding-wizard__group-label">{group}</span>
                <ol className="wf-onboarding-wizard__steps">
                  {items.map((item) => {
                    const idx = steps.findIndex((s) => s.id === item.id)
                    const state = idx < stepIndex ? 'done' : idx === stepIndex ? 'current' : 'upcoming'
                    const clickable = Boolean(onStepSelect) && idx >= 0 && idx <= reachable && state !== 'current'
                    const mark =
                      state === 'done' ? '✓' : item.configured && state === 'upcoming' ? '●' : String(idx + 1)
                    const inner = (
                      <>
                        <span className="wf-onboarding-wizard__step-mark" aria-hidden="true">
                          {mark}
                        </span>
                        <span className="wf-onboarding-wizard__step-copy">
                          <span className="wf-onboarding-wizard__step-label">{item.label}</span>
                          {item.detail ? (
                            <span className="wf-onboarding-wizard__step-detail">{item.detail}</span>
                          ) : null}
                        </span>
                      </>
                    )
                    return (
                      <li
                        key={item.id}
                        className={`is-${state}${item.configured ? ' is-configured' : ''}${clickable ? ' is-clickable' : ''}`}
                        aria-current={state === 'current' ? 'step' : undefined}
                      >
                        {clickable ? (
                          <button
                            type="button"
                            className="wf-onboarding-wizard__step-btn"
                            title={item.detail ? `${item.label}: ${item.detail}` : item.label}
                            onClick={() => onStepSelect?.(item.id)}
                          >
                            {inner}
                          </button>
                        ) : (
                          <div className="wf-onboarding-wizard__step-btn is-static">{inner}</div>
                        )}
                      </li>
                    )
                  })}
                </ol>
              </div>
            ))}
          </nav>
        </aside>

        <section className="wf-onboarding-wizard__panel">
          <header className="wf-onboarding-wizard__header">
            <div
              className="wf-onboarding-wizard__progress"
              role="progressbar"
              aria-valuenow={progress}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Setup progress"
            >
              <div className="wf-onboarding-wizard__progress-bar" style={{ width: `${progress}%` }} />
            </div>
            <p className="wf-onboarding-wizard__step-count">
              Step {stepIndex + 1} of {steps.length}
            </p>
            <h1 className="wf-onboarding-wizard__title">{title}</h1>
            {description ? <p className="wf-onboarding-wizard__description">{description}</p> : null}
          </header>

          <div className="wf-onboarding-wizard__body wf-scroll wf-scroll--vertical wf-scroll-host">
            {children}
          </div>

          {footer ? <footer className="wf-onboarding-wizard__footer">{footer}</footer> : null}
        </section>
      </div>
    </div>
  )
}
