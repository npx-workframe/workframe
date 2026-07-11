import type { ReactNode } from 'react'

import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

type SignInAppFieldProps = {
  label: string
  hint?: string
  htmlFor?: string
  children: ReactNode
  fullWidth?: boolean
}

/** Label + field + hint row inside `wf-sign-in-app` provider editors. */
export function SignInAppField({ label, hint, htmlFor, children, fullWidth }: SignInAppFieldProps) {
  return (
    <div className={cn('wf-sign-in-app__field', fullWidth && 'wf-sign-in-app__field--full')}>
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint ? <p className="wf-sign-in-app__hint">{hint}</p> : null}
    </div>
  )
}
