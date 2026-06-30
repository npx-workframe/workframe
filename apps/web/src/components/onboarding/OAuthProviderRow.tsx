import type { ReactNode } from 'react'

type OAuthProviderRowProps = {
  label: string
  description: string
  icon: ReactNode
  enabled: boolean
  disabled?: boolean
  onToggle: (next: boolean) => void
  children?: ReactNode
}

export function OAuthProviderRow({
  label,
  description,
  icon,
  enabled,
  disabled,
  onToggle,
  children,
}: OAuthProviderRowProps) {
  return (
    <li className={`wf-sign-in-app${enabled ? ' is-on' : ''}`}>
      <div className="wf-sign-in-app__head">
        <div className="wf-sign-in-app__icon" aria-hidden="true">
          {icon}
        </div>
        <div className="wf-sign-in-app__copy">
          <div className="wf-sign-in-app__title-row">
            <strong>{label}</strong>
          </div>
          <p className="wf-sign-in-app__desc">{description}</p>
        </div>
        <label className="wf-provider-connect__switch">
          <input
            type="checkbox"
            checked={enabled}
            disabled={disabled}
            aria-label={`Enable ${label}`}
            onChange={(event) => onToggle(event.target.checked)}
          />
          <span className="wf-provider-connect__switch-ui" aria-hidden="true" />
        </label>
      </div>
      {enabled && children ? <div className="wf-sign-in-app__body">{children}</div> : null}
    </li>
  )
}
