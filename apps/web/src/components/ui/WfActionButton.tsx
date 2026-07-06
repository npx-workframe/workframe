import * as React from 'react'

import { cn } from '@/lib/utils'

export type WfActionTone = 'default' | 'inactive' | 'primary'

export type WfActionButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  tone?: WfActionTone
  wizardSize?: boolean
}

export const WfActionButton = React.forwardRef<HTMLButtonElement, WfActionButtonProps>(
  ({ tone = 'default', wizardSize = false, className, type = 'button', ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      data-tone={tone}
      className={cn('wf-action-btn', wizardSize && 'wf-wizard-btn', className)}
      {...props}
    />
  ),
)
WfActionButton.displayName = 'WfActionButton'
