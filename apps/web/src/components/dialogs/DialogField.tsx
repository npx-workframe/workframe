import type { ReactNode } from 'react'

import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

type DialogFieldProps = {
  label: string
  htmlFor?: string
  hint?: ReactNode
  className?: string
  children: ReactNode
}

export function DialogField({ label, htmlFor, hint, className, children }: DialogFieldProps) {
  return (
    <div className={cn('wf-dialog-field', className)}>
      {htmlFor ? (
        <Label htmlFor={htmlFor} className="wf-dialog-field__label">
          {label}
        </Label>
      ) : (
        <span className="wf-dialog-field__label">{label}</span>
      )}
      {children}
      {hint ? <p className="wf-dialog-field__hint">{hint}</p> : null}
    </div>
  )
}
