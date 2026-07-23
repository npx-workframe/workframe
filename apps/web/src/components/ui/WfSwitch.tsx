import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react'

import { cn } from '@/lib/utils'

type WfSwitchProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & {
  label?: ReactNode
  wrapperClassName?: string
}

/**
 * Workframe behavior wrapper for Architectonic's native switch component.
 * Architectonic owns structure/theme styling; callers own checked state.
 */
export const WfSwitch = forwardRef<HTMLInputElement, WfSwitchProps>(
  ({ className, label, wrapperClassName, ...props }, ref) => (
    <label className={cn('archi-switch wf-switch', wrapperClassName)}>
      <input
        ref={ref}
        type="checkbox"
        className={cn('archi-switch__input wf-switch__input', className)}
        {...props}
      />
      {label ? <span className="archi-switch__label">{label}</span> : null}
    </label>
  ),
)

WfSwitch.displayName = 'WfSwitch'
