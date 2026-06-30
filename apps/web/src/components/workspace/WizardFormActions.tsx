import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

type WizardFormActionsProps = {
  children: ReactNode
  className?: string
}

export function WizardFormActions({ children, className }: WizardFormActionsProps) {
  return <div className={cn('wf-wizard-form-actions', className)}>{children}</div>
}
